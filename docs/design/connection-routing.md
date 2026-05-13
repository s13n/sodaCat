# Connection routing: from "exception number" to first-class wiring

The C++ chip header used to expose each peripheral instance's interrupt
output as an `Exception` field — a `uint16_t` holding the Cortex-M
exception/vector number on the (single) NVIC.  This was load-bearing
for driver code: a UART driver could read `intgr.exINTR` and pass it
straight to peLua's `insert(vec, isr)` to chain its handler under that
vector.

The model has outgrown this view.  Three new realities make the
exception-number-as-field encoding insufficient:

1. **Multi-destination.**  The same output can land on several
   targets — on dual-core H745/H757, every peripheral interrupt
   reaches *both* the CM7 and the CM4 NVIC.  A single integer can't
   represent two destinations.
2. **Intermediate routing.**  Many destinations are configurable
   routers (DMAMUX request-mux, EXTI line selector, trigger
   crossbar).  The "destination" the chip wires is the router's
   input number, not the final consumer's channel — that's set up
   dynamically by software.
3. **Non-interrupt purposes.**  DMA requests, wakeup signals,
   timer triggers, ADC trigger sources, comparator outputs feeding
   timer break inputs — none of these are interrupt vectors and
   none of them belong on NVIC.  Encoding them as `Exception` was
   already a stretch.

This document describes the scheme that replaces the exception-number
field: a chip-scope **`Connection` identity** plus generated
**per-target routing tables** plus per-target constexpr **resolvers**.
The basic driver-side pattern survives — peLua's `insert(...)` still
takes one argument and the rest is internal — but the argument is now
a Connection rather than a vector number, and the resolution from
Connection to vector happens inside `insert` instead of at the call
site.

## The shape

```cpp
namespace stm32h7 {

// Chip-scope identity for every (instance, output) pair the chip wires.
// `NONE = 0` is reserved as "no connection" — the absence sentinel,
// so resolvers can return 0 unambiguously when no route matches.
enum class Connection : uint16_t {
    NONE = 0,
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

// Intgr struct field carries the Connection identity, not a port number.
constexpr USART_Intgr usart1 = {
    .registers  = HwPtr<...>{0x40011000},
    .connINTR   = Connection::USART1_INTR,
    .connTX_DMA = Connection::USART1_TX_DMA,
    .connRX_DMA = Connection::USART1_RX_DMA,
    // ... params ...
};

// One pair-list table per target instance.  Each table is its own
// constexpr symbol — eligible for linker GC.  Sorted by Connection
// to support constexpr binary-search resolvers.
struct NvicRoute   { Connection conn; uint16_t vec;   };
struct DmamuxRoute { Connection conn; uint16_t input; };
struct TimerRoute  { Connection conn; uint16_t input; };

constexpr NvicRoute nvic_routes[] = {
    {Connection::USART1_INTR, 53},
    {Connection::USART2_INTR, 54},
    // ...
};
constexpr DmamuxRoute dmamux1_routes[] = {
    {Connection::USART1_RX_DMA, 41},
    {Connection::USART1_TX_DMA, 42},
    // ...
};
constexpr TimerRoute tim2_routes[] = {
    {Connection::TIM1_TRGO, 0},   // TIM2.ITR0
    {Connection::TIM8_TRGO, 1},   // TIM2.ITR1
    // ...
};
// ... one table per sink instance (NVIC, DMAMUX1, DMAMUX2, BDMAMUX,
// EXTI, EXTI_S, every TIMx, every ADCx, every DACx, HRTIM, ...).

// One resolver per target instance.  Each references only its own
// table; the linker drops both when the resolver is uncalled.
constexpr uint16_t nvic_vector(Connection c) {
    auto* lo = std::begin(nvic_routes);
    auto* hi = std::end(nvic_routes);
    while (lo < hi) {
        auto* mid = lo + (hi - lo) / 2;
        if (mid->conn < c) lo = mid + 1; else hi = mid;
    }
    return (lo != std::end(nvic_routes) && lo->conn == c) ? lo->vec : 0;
}
constexpr uint16_t dmamux1_input(Connection c) { /* same shape */ }
constexpr uint16_t tim2_input(Connection c)    { /* same shape */ }

}  // namespace stm32h7
```

## Why this shape

**`Connection` is a chip-scope identity, not a destination.**  Each
enumerator names one signal on one block instance.  The same identity
appears in *every* table where that signal lands — once in
`nvic_routes` if it goes to NVIC, once in `dmamux1_routes` if it
generates a DMA request, etc.  The Connection value itself doesn't
carry destination information; that lives in the route tables.

**`uint16_t` is the right size.**  RM0399 chapter 14 + chapter 15
together describe ~1200 distinct routes on H7 H745.  Even with
significant headroom for chip variants, we don't approach 65535
enumerators on any plausible chip.  A wider type would waste space on
every Intgr field for no payoff.

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
target instances no driver in the binary actually queries — the
guarantee is that the `(table, resolver)` pair for any unused target
goes away wholesale.

**Pair-list, not sparse table.**  At small fan-in counts the storage
is identical (one slot per route either way), but the pair list scales
with route count whereas the sparse table scales with
`N_connections × N_targets`.  Once the chip has 30+ targets, the
sparse encoding wastes most of its cells on zeros.  Pair-list also
mirrors the YAML's `chip_connections` shape one-to-one — each YAML
destination is one row in some target's table.

**Sorted + binary-search resolver.**  Both halves are constexpr in
C++20.  When called with a constexpr `Connection` (the universal case
from an Intgr struct field), the compiler folds the search to a
constant and the resolver evaporates.  The table only lands in
`.rodata` if some code path passes a runtime Connection through —
which most drivers never do.  Sorted ordering is the generator's
responsibility, not the author's.

## How drivers consume it

The driver-facing API mirrors what existed before, just with
`Connection` replacing the raw exception number:

```cpp
// Before:
peLua::isr::insert(intgr.exINTR, &my_isr);

// After:
peLua::isr::insert(intgr.connINTR, &my_isr);
```

`peLua::isr::insert(Connection, isr_t)` is inline, calls
`nvic_vector()` to resolve, then runs the existing per-vector ISR list
insertion.  When the call site's `Connection` is constexpr (always
true for Intgr-field reads), the whole resolution path folds at
compile time and the driver pays exactly what it paid before.

The same pattern extends to other targets — a TIM2 driver
configuring its trigger source consults `tim2_input(source)`; a DMA
driver subscribing to a peripheral's request consults
`dmamux1_input(source)`.  Each driver knows which resolver fits its
local target without needing to inspect the Connection value.

## Sharing and multi-destination

**Interrupt sharing** (multiple Connections land on the same NVIC
vector) is the normal case — peripherals frequently share vectors on
ST chips.  In the pair list, this is just multiple rows with the same
`vec`.  Both `nvic_vector(c1)` and `nvic_vector(c2)` return 53, both
calls into `peLua::isr::insert` route into `isr_table[53]`, and the
existing dispatcher walks the list.  Nothing in the routing layer
needs to model "which Connections share this vector" — the dispatch
already handles it at the vector level.

**Multi-destination** (one Connection routed to two targets, e.g.
NVIC + EXTI for a wakeup) falls out naturally: the same Connection
identifier appears in **both** target tables.  `nvic_vector(c)` and
`exti_line(c)` each return the relevant port.  Driver code calls
whichever resolver matches its intent.

**Dual-NVIC** on H745/H757 is a special case of multi-destination
that's handled per-binary.  Each CPU's binary is built against its
own chip header, which carries the wiring for *that* CPU's NVIC.  The
cm7 binary's `nvic_routes` and the cm4 binary's `nvic_routes` are
separate symbols, populated from the same YAML chip_connections data
but filtered per-CPU at generation time.

**One Connection landing on two vectors of the same target** (rare:
a signal split-fed to two NVIC inputs on the same NVIC) is *not*
supported by the single-result resolver shape.  Two rows with the
same `Connection` would resolve to whichever the binary search hits
first.  Accept the limitation; if it materialises in real silicon,
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

- **Constexpr-only resolution** (the typical driver path): zero
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
  that drivers may need to know for correct edge/level configuration
  on the destination side.  We defer including it because the
  vocabulary doesn't obviously generalise: ST's A/S/I/B taxonomy may
  not map cleanly onto NXP or Microchip silicon.  A field worth
  adding once we've looked at more diverse examples; until then,
  drivers that need this info hard-code it from the RM.
- **Multi-result resolvers** (one Connection → multiple destinations
  on the same target).  Single-result API covers every case we've
  seen.  When a real instance forces the issue, add a `_for(c)`
  family of resolvers returning a span next to the existing
  single-result entry points.  Table shape doesn't need to change.
- **Header sharding.**  One monolithic chip header is fine until the
  table count makes compile times painful for the configuration TUs
  that include it.  C++20 modules will sidestep the issue entirely
  once peLua's chip-header import is moduralised; until then,
  monolithic.
- **Cross-binary lookups** (CM7 code reasoning about CM4's NVIC
  wiring).  Out of scope for the per-binary table model.  If it ever
  matters, both binaries' tables can be exposed under distinct
  namespace prefixes (`stm32h7::cm7::nvic_routes` vs `cm4::`) and
  the resolver functions disambiguated.

## Generator implications

The chip-header generator gains responsibility for emitting:

1. The chip-scope `Connection` enum (one enumerator per (instance,
   canonical) appearing in the chip's wiring graph, with stable
   ordering — instance-major is the easiest-to-read default).
2. Per-target route tables, sorted by Connection.  Target instances
   are discovered by walking the chip's connections and collecting
   the distinct destination prefixes.
3. The per-target constexpr resolver functions.

The Intgr struct emit changes too:

- The per-peripheral `Intgr` template (from `generate_peripheral_header.py`)
  emits `Connection conn$name` fields (was `Exception ex$name`).
- The chip-level integration init (from `generate_chip_header.py`)
  references the chip-scope Connection enumerators instead of raw
  integers.  The `NVIC.<n>`-only filter at the chip-header level goes
  away — every destination, regardless of target, becomes a Connection
  reference resolved through the appropriate target table.

The YAML `chip_connections` schema doesn't need to change.  The
destination strings (`NVIC.53`, `DMAMUX1.42`, `TIM2.ITR0`) already
carry exactly what the generator needs.  The generator's job is to
invert them — keyed-by-source today, indexed-by-(target, source) in
the per-target tables.
