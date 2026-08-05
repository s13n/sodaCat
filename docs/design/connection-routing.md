# Connection routing: separating system-level wiring from peripheral drivers

The chip header used to expose each peripheral instance's interrupt
output as an `Exception` field on its `Intgr` struct — a `uint16_t`
holding the Cortex-M exception/vector number on the (single) NVIC.
A UART driver could read `intgr.exINTR` and pass it to peLua's
`insert(vec, isr)` to chain its handler under that vector.

The model has outgrown that view in two directions:

**1. Interrupt wiring isn't just "peripheral → NVIC input."**

Three new realities make the exception-number-as-field encoding
insufficient:

- *Multi-destination.*  The same output can land on several targets —
  on dual-core H745/H757, every peripheral interrupt reaches *both*
  the CM7 and the CM4 NVIC.  A single integer can't represent two
  destinations.
- *Intermediate routing.*  Many destinations are configurable routers
  (DMAMUX request-mux, EXTI line selector, trigger crossbar).  The
  "destination" the chip wires is the router's input number, not the
  final consumer's channel — that's set up dynamically by software.
- *Non-interrupt purposes.*  DMA requests, wakeup signals, timer
  triggers, ADC trigger sources, comparator outputs feeding timer
  break inputs — none of these are interrupt vectors and none of them
  belong on NVIC.  Encoding them as `Exception` was already a stretch.

**2. Drivers don't own routing knowledge.**

Even on a simple chip with a single NVIC, knowing *that* a peripheral
output reaches the NVIC, *which* vector it lands on, and *what
intermediate fabric* (mux, gate, crossbar) sits between source and
destination is a system-level concern.  Drivers describe what a
peripheral does; the system level decides how its signals are wired
into the rest of the SoC.  Mixing the two on the driver-facing `Intgr`
struct couples drivers to routing decisions that don't belong to them
— a UART driver should compile against any STM32 family without
acquiring a dependency on that chip's NVIC layout or its DMA fabric.

This document describes the scheme that replaces the
exception-number-as-field encoding: a chip-scope **`Connection`
identity** plus generated **per-target routing tables** plus
**resolvers** that turn a Connection into a port number on a named
target.  The Connection layer is emitted by the chip header and
consumed by the system level — peripheral drivers see only register
pointers and integration parameters.

## The shape

`Connection` is a strong opaque type whose declaration lives in
`hwreg.hpp` — chip-independent — and whose enumerators are populated
by the chip header that gets included.  The forward declaration with
an explicit underlying type is complete enough to be a type the
infrastructure can name (size and alignment are fixed), but the
enumerator names only exist after the chip header reopens
`namespace hwreg` to define the enum.

```cpp
// In hwreg.hpp — chip-independent.  Three pieces:
//   1. The forward-declared Connection type.
//   2. The pair-list entry struct, RouteEntry.
//   3. A single resolve() template that dispatches between the two
//      table shapes via the element type, using constexpr if.
inline namespace hwreg {

enum class Connection : uint16_t;   // complete type, no enumerators yet

// Single point of customisation for the port-value type.  Today
// uint16_t — a future per-target typed-port upgrade lands here
// without touching call sites that write `auto`.  See "Deferred
// decisions" for the trade-off analysis.
using port_t = uint16_t;

struct RouteEntry {
    Connection conn;
    port_t     port;
};

// One resolver, two shapes.  Caller passes the table directly; ADL
// finds this overload via the Connection / RouteEntry types in hwreg::.
constexpr port_t resolve(const auto& table, Connection c) {
    using Elem = std::remove_cvref_t<decltype(table[0])>;
    if constexpr (std::is_same_v<Elem, Connection>) {
        // Direct-array shape — linear scan, returns the array index.
        for (std::size_t i = 0; i < std::size(table); ++i)
            if (table[i] == c) return static_cast<port_t>(i);
        return 0;
    } else {
        // Pair-list shape — binary search (table sorted by Connection).
        auto lo = std::begin(table);
        auto hi = std::end(table);
        while (lo < hi) {
            auto mid = lo + (hi - lo) / 2;
            if (mid->conn < c) lo = mid + 1; else hi = mid;
        }
        return (lo != std::end(table) && lo->conn == c) ? lo->port : 0;
    }
}

}

// In USART.hpp — chip-independent peripheral header.  Intgr carries
// register pointers and integration parameters.  No Connection fields
// — the routing layer is invisible to peripheral code.
struct USART_Intgr {
    HwPtr<USART_Type> registers;
    // ... params (has_fifo, has_wakeup, ...) ...
};

// In the chip header (e.g. stm32h7.hpp) — chip-specific.  Reopens
// hwreg to provide the actual enum definition with the chip's
// inventory of (instance, output) pairs.
namespace hwreg {
    enum class Connection : uint16_t {
        NONE = 0,                  // reserved: "no connection" sentinel
        USART1_INTR    = 1,
        USART1_TX_DMA  = 2,
        USART1_RX_DMA  = 3,
        USART2_INTR    = 4,
        // ... one enumerator per (instance, canonical) on this chip
        TIM1_TRGO      = 287,
        TIM2_TRGO      = 290,
        COMP1_OUT      = 412,
        // ...
    };
}

namespace stm32h7 {

constexpr USART_Intgr i_USART1 = {
    .registers  = HwPtr<...>{0x40011000},
    // ... params ...
};

// Per-target tables.  Plain constexpr arrays — no class wrapping, no
// per-target resolver wrapper functions.  The element type alone
// distinguishes the two shapes:
//
// 1. Pair-list of `RouteEntry` — for OR-able targets (multiple
//    Connections may land on the same target input, dispatch ORs
//    them).  NVIC is the canonical example: shared vectors are normal
//    on ST chips.  Sorted by Connection by the generator so resolve()
//    can binary-search.
constexpr RouteEntry c_NVIC[] = {
    {Connection::USART1_INTR, 53},
    {Connection::USART2_INTR, 54},
    // ...
};

// 2. Direct array of `Connection` — for exclusive targets (each input
//    port is fed by at most one source).  Mux-style: DMAMUX request
//    mux inputs, EXTI line selector, TIM ITR selectors, trigger
//    crossbar inputs.  Indexed by port; entries default to
//    Connection::NONE for unwired slots.
constexpr Connection c_DMAMUX1[116] = {
    Connection::NONE,        // slot 0 unwired
    // ...
    Connection::USART1_RX_DMA,   // slot 41
    Connection::USART1_TX_DMA,   // slot 42
    // ...
};

constexpr Connection c_TIM2[8] = {
    Connection::TIM1_TRGO,   // ITR0
    Connection::TIM8_TRGO,   // ITR1
    Connection::NONE,        // ITR2 unwired
    Connection::TIM3_TRGO,   // ITR3
    // ...
};

}  // namespace stm32h7

// System-level glue — peLua's ISR system owns the call to resolve().
// Drivers never touch Connection or the route tables; system code
// names the (instance, signal) pair via the chip-scope Connection
// enumerator and the system layer does the lookup.
namespace peLua {
    using Chip = stm32h7;
    namespace isr {
        inline void insert(Connection c, isr_t fn) {
            isr_table[resolve(Chip::c_NVIC, c)] = fn;
        }
    }
}
```

## Why this shape

**Peripheral drivers don't see the routing layer.**  The `Intgr`
struct carries register pointers and integration parameters — the
things a driver needs to operate the peripheral.  Connection
identifiers and route tables are emitted alongside but consumed one
layer up, by the system code that wires drivers to interrupts, DMA
channels, EXTI lines, and trigger sources.  Keeping the wiring layer
out of `Intgr` makes each driver chip-portable: the same USART driver
compiles against any STM32 family without acquiring a dependency on
that chip's NVIC layout, its DMA fabric, or any other routing
decision the system layer makes on its behalf.

**Type chip-independent, values chip-specific.**  The `Connection`
*type* is forward-declared in `hwreg.hpp` so system-level code can
name the type without acquiring a dependency on any chip namespace.
The chip header is the sole producer of enumerator constants and the
sole owner of the route tables and resolvers; everything below the
chip layer sees only the opaque type.  The forward-declaration form
(no enumerator body in `hwreg.hpp`) lets the chip header *define* the
enum in a re-opened `namespace hwreg`, which means the values still
belong to the same type the system layer references — there is no
second `Connection` floating around to confuse name lookup.

**Connection identifies a source, not a destination.**  Each
enumerator names one signal on one block instance.  The same
identifier appears in *every* table where that signal lands — once in
`c_NVIC` if it goes to NVIC, once in `c_DMAMUX1` if it generates a DMA
request, etc.  The Connection value itself doesn't carry destination
information; that lives in the route tables.

**`uint16_t` is the right size.**  RM0399 chapter 14 + chapter 15
together describe ~1200 distinct routes on H7 H745.  Even with
significant headroom for chip variants, we don't approach 65535
enumerators on any plausible chip.

**No kind classification on the Connection itself.**  An interrupt is
not different from a wakeup is not different from a DMA request *from
the source's point of view* — the block emits an edge or a level on a
wire.  What the wire **does** is a property of the destination.  This
matches the design rule already in force on the YAML side (see
[output-wiring.md](output-wiring.md)) and carries it through to C++.

**Per-target tables, not one master table.**  The interconnect fabric
on a fully-modelled H7 has ~58 destination peripherals (RM0399 ch. 14
Table 102 alone enumerates them).  Most applications use a small
subset.  Per-target symbols let the linker eliminate the wiring for
target instances no code in the binary actually queries — an unused
target's table is a stand-alone constexpr symbol with no references,
so the linker drops it wholesale.  The single `resolve()` template is
instantiated only for the table types actually used in the binary
(once for `RouteEntry[]`, once for `Connection[]`); both
instantiations are independent of which specific tables exist.

**One resolver, two shapes, tables stay first-class data.**  The
shape choice is encoded structurally in the table's element type
(`RouteEntry` vs `Connection`), and the single `resolve()` template
in `hwreg.hpp` dispatches between binary search and linear scan via
`constexpr if`.  This factoring keeps the tables as plain constexpr
arrays — anything that wants to iterate, dump, filter, reverse-look-up,
or generate documentation from a routing table just uses standard
array facilities, without going through accessors a class wrapper
would have to anticipate.  Wrapping the tables in classes would force
that foresight; leaving them as arrays defers it.

**Two table shapes, picked per target by inference.**  Target inputs
come in two flavours that are real properties of the silicon, not
encoding choices:

- *OR-able* targets accept multiple sources on the same input,
  dispatching them via a chained mechanism — NVIC vectors are the
  canonical example (shared IRQ vectors run an ISR list).  The
  (Connection → port) relation is many-to-one; the encoding must
  preserve every (Connection, port) pair, hence a **pair list**.
- *Exclusive* targets accept at most one source per input.  Mux-style
  destinations (DMAMUX request mux, EXTI line selector, TIM ITR
  selectors, trigger crossbars) all behave this way: a configuration
  register picks one input per port, and the unselected sources are
  electrically disconnected.  The (Connection → port) relation is
  at-most-one-to-one in both directions on the wired subset; the
  encoding can be a **direct array indexed by port**, dropping the
  port field entirely.

The generator picks the shape per target by **inferring from the chip's
`chip_connections` data**: group destinations by their target prefix
(`NVIC`, `DMAMUX1`, `TIM2.ITR`, ...) and check whether any port appears
more than once.  Any collision → pair-list.  None → direct-array sized
to `max(port) + 1`, with unwired slots defaulted to `Connection::NONE`.
No declarative classification is required; the resolver lives in the
same translation unit as its table, so the shape choice is local with
no ABI surface.

The inference is permissive about the (rare, programmer-error) case
where an exclusive target accidentally has two Connections wired to
the same port — the generator silently emits a pair-list rather than
flagging the bug.  If this matters for a specific destination kind,
the future `inputs:` schema introduced for Phase 2 destination-string
validation (see [output-wiring.md](output-wiring.md)) is the natural
home for an opt-in `multiplicity: exclusive` assertion the generator
can check against the data.  For now: pure inference.

**Pair-list, not sparse table** *(for the OR-able shape).*  At small
fan-in counts the storage is identical (one slot per route either
way), but the pair list scales with route count whereas the sparse
form scales with `N_connections × N_targets`.  Once the chip has 30+
targets, the sparse encoding wastes most of its cells on zeros.
Pair-list also mirrors the YAML's `chip_connections` shape one-to-one
— each YAML destination is one row in some target's table.

**Direct array, not pair-list** *(for the exclusive shape).*  The
array trades the per-row port field (saving 2 B/row) for one slot per
port in the target's address space — including unwired slots,
defaulted to `Connection::NONE`.  Net win when wired density exceeds
~50%, which is the common case for these mux-style targets where the
silicon defines a small fixed port count and most are wired.  Bonus:
the array natively supports the reverse query "what's at port N?"
via direct indexing, useful for debug and introspection without
implying any change to the primary `Connection → port` API.

**Sorted + binary search** *(for the pair-list shape).*  When
`resolve()` is called with a constexpr `Connection` (the universal
case when system code names the enumerator at the call site), the
compiler folds the search to a constant and the resolver evaporates.
The table only lands in `.rodata` if some code path passes a runtime
Connection through — which most system-level glue never does.  Sorted
ordering is the generator's responsibility, not the author's.

**Linear scan** *(for the direct-array shape).*  Same constexpr-fold
property: with a constexpr Connection argument the compiler unrolls
the comparison and emits the matching index as a constant.  Linear is
fine because typical port counts are small (TIM ITR slots: 8; DMAMUX
inputs: 64–128; EXTI lines: 16–88) and the scan never reaches
`.rodata` on the constexpr path.

**No per-target wrapper functions.**  System glue calls
`resolve(Chip::c_NVIC, c)` directly rather than going through a
per-target `nvic_vector(c)` helper.  ADL on the
`RouteEntry`/`Connection` argument types finds `hwreg::resolve`
without qualification.  This drops one emission per target from the
chip header and keeps the resolver in exactly one place; the cost is
that the call site names the table explicitly, which is fine — the
table is the entity system-level code references for any purpose
(lookup, iteration, diagnostics).

## How the layers consume it

The Connection layer has two audiences: peripheral drivers (which see
*nothing*) and system-level glue (which owns the wiring).

**Peripheral drivers.**  A driver constructed against an instance
receives the chip's `Intgr` for that instance — register base address
plus integration parameters.  It operates the peripheral: sets up
registers, handles its protocol, exposes its behaviour.  It never
names a Connection enumerator and never indexes a route table.
Wiring its output to anything in the SoC is somebody else's problem.

```cpp
// Driver constructor — chip-portable, no routing knowledge.
UartDriver::UartDriver(USART_Intgr const& i)
    : hw_{i.registers}, fifo_depth_{i.has_fifo ? 16 : 1}
{}
```

**System-level glue.**  The system layer (peLua's ISR table, a DMA
manager, an EXTI configurator, ...) knows which Connection it cares
about for a given instance because the (instance, signal) pair is
common knowledge between block model and integration code.  The pair
is spelled out at the call site as a compile-time `Connection::INST_SIG`
constant:

```cpp
// In system code that hooks USART1's interrupt:
peLua::isr::insert(Connection::USART1_INTR, &my_isr);

// In system code that configures USART1's DMA channels:
dma_request_setup(resolve(Chip::c_DMAMUX1, Connection::USART1_RX_DMA), ...);

// In system code that configures an EXTI wakeup:
exti_line_setup(resolve(Chip::c_EXTI, Connection::OTG_FS_WKUP), ...);
```

`peLua::isr::insert(Connection, isr_t)` is inline, calls
`resolve(Chip::c_NVIC, c)` to look up the vector, then runs the
existing per-vector ISR list insertion.  When the call site's
`Connection` is constexpr (always true for enumerator-named
arguments), the whole resolution path folds at compile time.

The same pattern extends to other targets — TIM2 setup configuring
its trigger source consults `resolve(Chip::c_TIM2, source)`; DMA
setup subscribing to a peripheral's request consults
`resolve(Chip::c_DMAMUX1, source)`.  Each call site names the table
its local target uses; the same `resolve()` template handles both
shapes via the table's element type.

**ADL works for `resolve`, table names are explicit.**  Because both
`Connection` and `RouteEntry` are declared in `hwreg::`, ADL on a
`resolve(table, c)` call finds `hwreg::resolve` regardless of which
chip namespace the table lives in.  The table itself must be named
explicitly (`Chip::c_NVIC`, where `using Chip = stm32h7;` is set up
once per binary by the system layer), but that's appropriate —
system code references tables for other purposes too (iteration,
diagnostics), so the table-as-named-data shape is load-bearing.

## Sharing and multi-destination

**Interrupt sharing** (multiple Connections land on the same NVIC
vector) is the normal case — peripherals frequently share vectors on
ST chips.  In the pair list, this is just multiple rows with the same
`port`.  Both `resolve(c_NVIC, c1)` and `resolve(c_NVIC, c2)` return
53, both calls into `peLua::isr::insert` route into `isr_table[53]`,
and the existing dispatcher walks the list.  Nothing in the routing
layer needs to model "which Connections share this vector" — the
dispatch already handles it at the vector level.

**Multi-destination** (one Connection routed to two targets, e.g.
NVIC + EXTI for a wakeup) falls out naturally: the same Connection
identifier appears in **both** target tables.  System code calls
whichever resolver matches its intent.

**Dual-NVIC** on H745/H757 is a special case of multi-destination
that's handled per-binary.  Each CPU's binary is built against its
own chip header, which carries the wiring for *that* CPU's NVIC.  The
cm7 binary's `c_NVIC` and the cm4 binary's `c_NVIC` are separate
symbols, populated from the same YAML chip_connections data but
filtered per-CPU at generation time.

**One Connection landing on two vectors of the same target** (rare:
a signal split-fed to two NVIC inputs on the same NVIC) is *not*
supported by the single-result resolver shape.  Two rows with the
same `Connection` would resolve to whichever the binary search hits
first; in the direct-array shape the equivalent would be two cells
holding the same Connection — and the linear scan reports the first
match.  Accept the limitation; if it materialises in real silicon,
add a multi-result resolver next to the single-result one without
changing the table shape.

## Sizing

Route counts from RM0399 H7 chapter 14 (block interconnect) + chapter
15 (NVIC vector table):

| Source | Routes |
|---|---|
| Table 102 (peripheral interconnect matrix details) | 703 |
| Table 103 (EXTI wakeup inputs) | 88 |
| Table 104 (EXTI pending-request clear inputs) | 21 |
| Table 105 (MDMA trigger sources) | 32 |
| Table 106 (DMAMUX1 / DMA1 / DMA2 connections) | 147 |
| Table 107 (DMAMUX2 / BDMA connections) | 71 |
| Chapter 15 (NVIC vector table) | ~150 |
| **Total wiring fabric** | **~1200 routes** |

At ~4 bytes per route (2-byte Connection + 2-byte port), the full
wiring fabric is **~4.8 KB**.  Distributed across ~60 target
instances, the largest individual table (NVIC) is ~600 B; most are
much smaller (10-50 B).

In a real binary:

- **Constexpr-only resolution** (the typical system path): zero
  bytes — every resolver call folds and the tables never reach
  `.rodata`.
- **Linker GC with an application using ~10 drivers**: ~10 target
  tables ship, total a few hundred bytes.
- **Worst case** (some path takes every resolver's address):
  ~4.8 KB.

All three regimes are comfortable on any chip we target.

## Deferred decisions

- **The "Type" classification** in RM0399 Table 102 (A=async, S=sync,
  I=immediate, B=break/fault).  This is a real property of each route
  that system code may need to know for correct edge/level
  configuration on the destination side.  We defer including it
  because the vocabulary doesn't obviously generalise: ST's A/S/I/B
  taxonomy may not map cleanly onto NXP or Microchip silicon.  A field
  worth adding once we've looked at more diverse examples; until then,
  system code that needs this info hard-codes it from the RM.
- **Multi-result resolvers** (one Connection → multiple destinations
  on the same target).  Single-result API covers every case we've
  seen.  When a real instance forces the issue, add a `resolve_all()`
  template alongside `resolve()` that returns a span; the table shape
  itself doesn't need to change.
- **Typed per-target ports.**  The port value (NVIC vector number,
  DMAMUX input number, TIM ITR slot, ...) is `port_t = uint16_t`
  today.  A per-target opaque enum-class (`NvicVector`, `Dmamux1Input`,
  `Tim2Itr`, ...) declared in the chip header alongside its table
  would type-check cross-target port mixing at compile time, at the
  cost of ~60 type declarations per chip and either a per-table
  wrapping struct or a parallel `using <target>_port_t = ...;` alias
  that `resolve()` learns to deduce from.  The bug class it catches is
  narrow (system author confused about which target they're writing
  to) and the constexpr-fold path erases the runtime difference, so
  the complexity isn't currently paying for itself.  The `port_t`
  alias in `hwreg.hpp` is the upgrade hook — when we want typed ports,
  `resolve()`'s return type becomes deduced from the table and call
  sites that wrote `auto` keep working.
- **Header sharding.**  One monolithic chip header is fine until the
  table count makes compile times painful for the configuration TUs
  that include it.  C++20 modules will sidestep the issue entirely
  once the system layer's chip-header import is moduralised; until
  then, monolithic.
- **Cross-binary lookups** (CM7 code reasoning about CM4's NVIC
  wiring).  Out of scope for the per-binary table model.  If it ever
  matters, both binaries' tables can be exposed under distinct
  namespace prefixes (`stm32h7::cm7::c_NVIC` vs `cm4::`) and the
  caller picks the right table explicitly when calling `resolve()`.

## Generator implications

The chip-header generator emits:

1. The chip-scope `Connection` enum definition (one enumerator per
   (instance, canonical) appearing in the chip's wiring graph, with
   stable ordering — instance-major is the easiest-to-read default).
   The definition reopens `namespace hwreg` so the enumerators belong
   to the type the system layer already references.
2. Per-target route tables as plain constexpr arrays, in the shape
   inferred from the data: `RouteEntry[]` sorted by Connection when
   any port has more than one source, `Connection[]` indexed by port
   otherwise.  Target instances are discovered by walking the chip's
   connections and collecting the distinct destination prefixes; the
   shape choice falls out of the collision check on each group.

No per-target resolver function is emitted — the single
`hwreg::resolve()` template handles both shapes via the table's
element type, dispatched with `constexpr if`.  System code calls
`resolve(Chip::c_NVIC, c)` directly.

The peripheral header is unaffected by the wiring layer:

- The per-peripheral `Intgr` struct (from
  `generate_header.py`'s `PerFormatter`) carries register pointers and
  integration parameters.  It does **not** carry per-output Connection
  fields.  An earlier revision of this design did — `Intgr` held one
  `Connection conn<NAME>` field per declared output, on the theory
  that drivers would read `intgr.connINTR` to look up their NVIC
  vector.  That coupled drivers to chip-level routing decisions and
  collapsed under the same pressure that retired `Exception ex<NAME>`:
  interrupt wiring is too varied for a per-output field to be the
  right abstraction, and drivers shouldn't know about routing in the
  first place.  The `Intgr` struct is now strictly about driving the
  peripheral; the chip-side instance initialiser correspondingly
  emits only register-pointer and parameter initialisers.
- The chip-level enum definition and route tables are emitted at
  chip-namespace scope, available to the system layer that imports
  the chip module.  Drivers that import only their peripheral module
  never see them.

The YAML `chip_connections` schema doesn't need to change for any of
this.  The destination strings (`NVIC.53`, `DMAMUX1.42`, `TIM2.ITR0`)
already carry exactly what the generator needs.  The generator's job
is to invert them — keyed-by-source on the YAML side,
indexed-by-(target, source) in the per-target tables, with the shape
of each per-target table inferred from the data as described above.

Port-grammar validation (NVIC ports are absolute exception indices,
DMAMUX ports are mux input numbers, TIM ports may need an `ITR.<n>` /
`BRK.<n>` / ... structure) is a separate concern handled by
`validate_chip_connections.py` from
[output-wiring.md](output-wiring.md).  Table-shape inference and
port-grammar validation are orthogonal — inference uses only the
collision structure of `(prefix, port)` tuples, not the meaning of
the port values.
