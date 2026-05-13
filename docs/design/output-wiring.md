# Output wiring: kind belongs to destination, not source

Block models declare named output signals in a top-level `outputs:` list —
flat `{name, description?}` entries with **no kind classification at the
source**.  Chip-level wiring assigns meaning per-instance via
`outputs: {signal: [destination, ...]}`, where each destination is a dotted
`instance.input` string identifying the consumer (NVIC, DMAMUX, EXTI, ...)
and its input port.  The kind of a signal — interrupt vs DMA request vs
wakeup vs trigger — follows from which destination instance receives it.

## Why no source-side kind discriminator

The same source signal can have multiple meanings depending on where the
chip routes it.  On STM32H7 H745 (dual-core M7 + M4), one wakeup output
drives both its own core's wake controller **and** the peer core's NVIC —
same wire, two kinds simultaneously.  A source-side `kind` tag can't
express that without duplicating the signal name on the block side, which
makes the block model lie about its physical interface.

The conceptual core: the SoC is a graph of named blocks with named ports.
Routing fabrics (DMAMUX, EXTI, timer trigger crossbars) are nodes in that
graph, not special cases.  IP-XACT and SystemRDL extensions converge on
the same shape for the same reasons — the design isn't novel, just
explicit.

## Destination encoding

Destinations are strings of the form `<instance>.<input_id>`.  The input ID
is whatever the destination instance names its inputs — for NVIC it's the
absolute exception vector index, for DMAMUX it'll be the request line
number, for HRTIM it's a named external event (`EEV1..EEV10`).  Strings
throughout, not ints: the combined form is a string anyway, and some
fabrics name their inputs by symbol.

An output can have multiple destinations.  The chip YAML lists them all
under that signal's entry:

```yaml
USART1:
  outputs:
    global_irq:
      - NVIC_CM7.37
    wakeup:
      - EXTI.25            # wakeup line (Phase 2)
      - NVIC_CM4.87        # peer-core interrupt (Phase 2)
    tx_dma_req:
      - DMAMUX1.41         # Phase 2
```

(Today only NVIC destinations appear; the rest are Phase 2 examples for
illustration.)

## Phase 1 (current, NVIC-only)

Every destination is `NVIC.<absolute_vector>`.  Absolute = NVIC's own input
numbering, which on Cortex-M is `svd_value + interruptOffset` (typically
+16, since vectors 0–15 are system exceptions).  The chip's
`interruptOffset:` is now purely descriptive metadata; the C++ chip-header
template emits `.ex<NAME> = <vec>u` without the `+ interruptOffset` it
previously applied at emit time.

`validate_chip_interrupts.py` enforces the dotted `instance.port` shape
on every destination and additionally requires the port to be an integer
when the instance is `NVIC` — the only target whose port grammar is
fixed today.  Other targets' port-format rules land alongside their
schema definitions in Phase 2.

## Phase 2 (planned, deferred)

Each new destination kind lands end-to-end:

1. **DMAMUX** as a first-class instance with declared input range;
   peripheral DMA-request outputs wire to its request lines.
2. **EXTI** as a first-class instance with line inputs; peripheral wakeup
   outputs wire through, and the same EXTI line can route to multiple
   NVICs (dual-core).
3. **Trigger crossbars / ADC injected triggers / HRTIM event router** —
   each is a routing-fabric instance with declared input/output ports.
4. **NVIC** itself eventually becomes a first-class instance, with its
   `interruptOffset:` migrating onto its instance entry (or becoming
   derivable from `cpu.name`).

The C++ side gains field-type dispatch by destination kind (today every
output emits as `Exception ex<NAME>`).  The schema already accepts
multi-kind destinations — Phase 1 deliberately defers the dispatch until
there's actual heterogeneity to dispatch on.

A subtlety to address in Phase 2: routing fabrics have **configurable**
edges (DMAMUX's request → channel selector is a register field, not fixed
wiring).  The chip-level `outputs:` map captures *fixed* wiring; the
fabric's *configurable* routing belongs in the fabric block's register
model and is the driver's concern, not the chip's.

## How to apply

When proposing new fabrics, think "intermediate routing block with declared
input/output ports", not "kind of interrupt".  A configurable edge inside
a fabric is the fabric's register-level concern, not a chip-wiring
concern.  Phase 2 work means modelling one fabric end-to-end at a time;
mixing fabrics in one change tends to entangle the schema discussion.

## See also

- CLAUDE.md "Output wiring" — day-to-day reference.
- [docs/design/subfamily-model.md](subfamily-model.md) — how per-instance
  outputs lift through the subfamily inheritance chain.
- `schemas/chip.schema.yaml` — schema for the chip-level wiring shape.
- `tools/validate_chip_interrupts.py` — destination-format check
  (dotted shape, NVIC-port integer rule).
- `generators/cxx/generate_chip_header.py:_collectInterrupts` — derives
  the vector-table view from per-instance outputs on the C++ side.
