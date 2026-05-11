# Subfamily Model & Inheritance

This document describes the family/subfamily/chip layering — how family-common
facts are owned at the right tier and how chips inherit and override them.

## Why this exists

Before the layering, every chip YAML carried its full picture: the full
interrupt vector table, a `clocktree:` pointer to a separate file, every
peripheral instance, every parameter.  For an 8-chip subfamily, the same 117
common IVT entries appeared 8 times, the clock tree lived in a separate
hand-authored file with no schematic link to the rest of the chip data, and
mixed-ownership creep (parts of the chip YAML hand-edited, parts
extractor-managed) crept in unannounced.

The subfamily-model tier addresses both problems.  Family-common facts
(currently: clock-tree topology and the common interrupt vector table; later:
DMA-request fabric, EXTI routing, ...) live in one place per subfamily.  Chip
YAMLs carry only what's chip-specific.

## Tiers and what lives where

| Tier      | File location                                         | Owner       | Contents |
| --------- | ----------------------------------------------------- | ----------- | -------- |
| Family    | `svd/<Vendor>/<Family>.yaml`                          | hand-author | Extraction config: chips, blocks, patches, **clock-tree topology** |
| Subfamily | `models/<Vendor>/<Family>/<Subfamily>/<Subfamily>.yaml` | extractor | Derived artifact: header metadata, **clocks: section**, **interrupts: section** (common IVT) |
| Chip      | `models/<Vendor>/<Family>/<Subfamily>/<Chip>.yaml`     | extractor | Derived artifact: per-instance data, IVT delta, `inherits:` link |

The subfamily YAML is fully derived: deleting it and re-extracting yields a
byte-identical file.  Chip YAMLs reach their subfamily via an `inherits:` key
whose value is the model-root-relative path of the subfamily YAML.

## Two fabric mechanisms

The pattern accommodates both **hand-authored** fabrics (topology that has to
come from a human reading the reference manual — currently just the clock
tree) and **computed** fabrics (data derivable mechanically from per-chip
SVD-extracted content — currently the interrupt vector table).

### Clock tree (hand-authored, family-config source)

The clock topology is authored under `families.<F>.subfamilies.<S>.clocks:` in
the vendor config.  Its shape matches `schemas/subfamily.schema.yaml#/clocks` —
`instance`, `signals`, `generators`, `muxes`, `plls`, `dividers`, `gates`.
References like `{reg: CFGR, field: SW}` cite registers/fields in the
extracted block models (typically the RCC / SYSCON peripheral); the
`tools/validate_clock_refs.py` validator cross-checks every reference.

The extractor copies this content verbatim into the subfamily YAML's `clocks:`
section, stripping ruamel comment metadata so source-file dividers don't leak
into output string values.

### Instances and models map (computed by intersection)

Both the peripheral-instance map (`instances:`) and the block-model
index (`models:`) follow the same intersection pattern as the IVT.
After per-chip processing, the extractor extracts entries that appear
with byte-identical content in every chip in the subfamily, lifts them
to the subfamily YAML, and reduces each chip's own map to the delta.

For a typical multi-chip subfamily (e.g. H745_H757 with 8 chips, 114
instances each), 108 instances and 51 of 53 model paths are common —
so chip YAMLs shrink to ~6 instance entries each.  Single-chip
subfamilies (RP2040, SAM-Gen1 consumers) lift their entire instance
set up; the chip YAML becomes a thin header.

Chip-level entries override ancestor entries by key (instance name /
block name).  The chip-header generator walks the `inherits:` chain to
assemble the merged view.

### Interrupt vector table (computed by intersection)

The IVT is fully derived from the per-chip data the extractor already
produces.  The algorithm runs **after** every existing patch mechanism:

1. SVD raw interrupt names → canonical names via the block's `interrupts:`
   map and the algorithmic prefix-stripping resolver.
2. `chip_interrupts:` overrides applied (injects or corrects per chip).
3. `chip_instances:` exclusions remove un-present instances and their IRQs.
4. Each chip's per-instance interrupts assemble into a chip-level IVT keyed
   by vector number.

Only then, after every chip in the subfamily has gone through 1–4, the
extractor computes the *intersection*: a (vector, "Instance.Signal") pair
survives into the subfamily IVT iff it appears at the same vector in **every**
chip's IVT.  Each chip's `interrupts:` is then reduced to its delta.

This means patches behave as before — they shape the per-chip IVTs that feed
the intersection.  A patch that makes one chip agree with its siblings causes
the corrected entry to lift cleanly into the subfamily section (the patch
becomes invisible in the output, which is the right behaviour: the family
config is the durable record of "here's a fix"; the YAML reflects what the
silicon does).

## Extraction pipeline order

Within Pass 3 of `extractors/generate_models.py`:

```
for subfamily in family:
    for chip in subfamily:
        # 1. Per-chip processing (existing logic):
        #    block presence, instance addresses, interrupt canonicalisation,
        #    chip_interrupts overrides, chip_instances exclusions, ...
        chip_model = assemble(chip)
        accumulate(chip_model)        # NOT written to disk yet

    # 2. Subfamily-level synthesis:
    if subfamily has `inherits:`:
        common_ivt = intersect([cm.interrupts for cm in accumulated])
        if subfamily has `clocks:`:
            emit_subfamily_yaml(
                family_label,         # via vendor extension family_label()
                devices,              # dedupe chip names, strip _CMn suffix
                ref_manual → documents,
                clocks,               # from family config
                interrupts=common_ivt,
            )
        elif subfamily YAML exists:
            update_subfamily_yaml(interrupts=common_ivt)  # preserves clocks:
        else:
            FAIL: inherits target doesn't exist, no clocks: to regenerate from

        for chip in accumulated:
            chip.interrupts = ivt_delta(chip.interrupts, common_ivt)

    write all accumulated chip YAMLs
```

The C++ side (`generators/cxx/generate_chip_header.py`) walks `inherits:` when
computing the merged vector-table view — so consumers see the full IVT
regardless of where each entry lives in the YAML hierarchy.

## Adding a new fabric

When a new family-common fabric type lands (DMA-request matrix, EXTI line
routing, event router, ...), the pattern is:

1. Decide whether the fabric is **hand-authored** (topology requires RM
   knowledge — model it like clocks) or **computed** (mechanically derivable
   from per-chip SVD data — model it like interrupts).
2. Add the section to `schemas/subfamily.schema.yaml`.
3. For hand-authored: read the section from the family config, pass it to
   `_emit_subfamily_yaml(...)`, deep-strip ruamel metadata before write.
4. For computed: write the intersection-and-delta logic over the per-chip
   field, applying *after* every existing per-chip patch.
5. Update the C++ generator that consumes the section to walk `inherits:` and
   merge ancestor entries.
6. Add a cross-reference validator if the fabric cites registers/fields in
   block models.

## Coverage today

Migrated to Shape A (9 subfamily YAMLs are derived artifacts):

  - STM32 H5: H503
  - STM32 H7: H73x, H742_H753, H745_H757, H7A3_B
  - NXP LPC8: LPC86x
  - NXP LPC43: LPC43xx
  - Raspberry RP: RP2040, RP2350

Migrated using the cross-family shared-spec mechanism:

  - Microchip SAM_Gen1   (consumed by SAME70, SAMS70, SAMV70, SAMV71,
                          PIC32CZ-CA70, PIC32CZ-MC70)
  - Microchip PIC32CZ_Gen2 (consumed by PIC32CZ-CA80, PIC32CZ-CA90)
    Note: still flags `MCLK.CLKMSK[N].MSK0..MSK31` field-citation drift
    against the block model's single `MASK` field — orthogonal to the
    migration, to be addressed by splitting the block model.

## Cross-family shared specs

When a clock-tree topology is shared across multiple *families* (not just
subfamilies — e.g. Microchip SAM_Gen1 is shared by 6 families), the vendor
config grows a top-level `shared_subfamilies:` map that mirrors the
existing `shared_blocks:` mechanism for peripherals.  Each entry holds the
topology and a `ref_manual:` pointing at the document that backs it.  The
extractor emits each entry to `models/<Vendor>/<Name>.yaml` at the start
of the run (idempotent — invoking any single consuming family produces
the same shared spec).

Consuming subfamilies use the new `extends:` key to chain to the shared
spec, distinct from `inherits:`:

  - `inherits:` (existing) — the path the *chip's* `inherits:` field points
    at; also where the subfamily YAML emits.  For a non-shared subfamily,
    this is the only link and the subfamily YAML carries `clocks:` inline.
  - `extends:` (new) — what the *subfamily YAML's* own `inherits:` field
    is set to.  When set, the subfamily YAML emits with that link instead
    of inlining `clocks:`; the topology comes from the chained parent.

Concretely for Microchip SAME70:

```yaml
shared_subfamilies:
  SAM_Gen1:
    ref_manual: {name: ..., url: ..., rev: ...}
    clocks:
      instance: PMC
      signals: [...]
      ...

families:
  SAME70:
    subfamilies:
      SAME70:
        chips: [ATSAME70Q21B]
        inherits: Microchip/SAME70/SAME70/SAME70   # chip's target
        extends:  Microchip/SAM_Gen1               # subfamily YAML's parent
```

This yields a three-tier chain at C++ generation time:

  chip.hpp → subfamily.hpp (passthrough) → shared-spec.hpp (carries clocks)

The dispatcher emits trivial placeholder `.hpp`/`.cppm` files for the
subfamily passthrough tier so the CMake custom-command output contract
is satisfied; no real C++ content lives at that tier.

## Resilience

  - Delete a subfamily YAML, re-extract: identical regeneration.
  - Subfamily declares `inherits:` but target is missing AND no `clocks:`
    source in the family config: extractor exits non-zero with a clear
    diagnostic naming the missing file.
  - Subfamily YAML can be partially extractor-managed (only the `interrupts:`
    section) if the family config has no `clocks:` — useful as a migration
    halfway state, but not a long-term arrangement.

## Clock-tree audit

`tools/audit_clock_block.py` is a complement to `validate_clock_refs.py`.
The latter answers "does every cited register/field exist?"; the audit
answers harder questions the SVD can't always reliably support:

  **Tier A — width/count mismatches (errors, exit non-zero).**  High-
  confidence checks: a mux's `inputs:` list must fit within the
  selector field's `bitWidth`; if the field's `enumeratedValues` cover
  every encoding (`count == 2^bitWidth`), the input count must agree;
  same idea for divider `values:` lists.  Many vendors list only the
  "active half" of an encoding space (STM32 HPRE: 16 logical positions,
  8 enumeratedValues, with the low half implicitly "divide by 1"), so
  the check only fires when the enum is complete — avoids the obvious
  false-positive class.

  **Tier B — coverage audit (informational).**  Walks the controller
  block and lists fields whose name matches a clock-tree pattern but
  that aren't cited anywhere in the spec:

  | Pattern         | Likely role       |
  | --------------- | ----------------- |
  | `*EN`           | gate enable       |
  | `*SEL`/`*SRC`/`*MUX` | selector mux |
  | `*DIV`/`*PRE`/`*PSC` | divider      |

  Output is necessarily noisy — these regexes catch any field with a
  matching suffix, including LP-mode gates, autonomous-mode bits,
  memory-block enables, and peripheral-internal fields that share the
  naming convention.  Real findings are surfaced *among* the noise;
  reading the list requires human judgement.  The STM32 H7 MCO1PRE /
  MCO2PRE prescalers were found this way — the spec modelled the MCO
  selectors but stopped before the output-pin prescaler.

  **Tier C — fuzzy enum-name hints (warnings).**  When a selector
  field has enumeratedValues with non-trivial names, compare those
  names against the mux's `inputs:` list.  Token-based match (split
  at letter/digit boundaries: `gclkgen0` → `{gclk, gen, 0}` overlaps
  `GCLK0` → `{gclk, 0}`).  A hint fires only when:

    - the enum is complete (sparse-enum guard);
    - the enum names are non-trivial (filters `PSEL_0`/`PSEL_1` style);
    - at least one input in the same mux *does* match the enums
      (i.e. the author broadly aligns with SVD names — an isolated
      divergence stands out; if every input diverges, the author
      chose a different convention and per-input nags are pure noise).

  Useful for catching one-off naming inconsistencies; the SAM_Gen1
  `slck` vs `SLOW_CLK` divergence was the first finding.

**When to run.**  During clock-tree authoring (Tier B coverage helps
ensure nothing is forgotten); as a periodic spot-check on the whole
repo.  Not a CI gate today — Tier B's false-positive rate would block
most PRs.  Tier A is reliable enough to be one if desired, but it's
quiet on the current trees so the value is limited.

**Limitations.**

  - Sparse SVD enums limit Tier A's reach.  H7's RCC has almost no
    enumeratedValues at all, so most of the spec is unchecked.
  - The Tier B regex catches non-clock fields whose names happen to
    match the pattern (e.g. `WPSR.WPVSRC` = write-protection
    violation source).  Triage by hand.
  - Fully automatic extraction of mux input names or divider value
    lists from SVD content is not attempted — the data is too noisy.
    See the audit-tool commit message for the analysis behind this
    choice.

## See also

  - `schemas/subfamily.schema.yaml` — the file-level shape.
  - `tools/validate_clock_refs.py` — cross-references clock-spec citations
    against extracted block models.
  - `tools/audit_clock_block.py` — three-tier audit (Tier A errors,
    Tier B coverage, Tier C name-divergence hints).
  - `extractors/generate_models.py` — the extractor implementation:
    `_ivt_intersection`, `_ivt_delta`, `_emit_subfamily_yaml`,
    `_update_subfamily_yaml`.
  - `generators/cxx/generate_chip_header.py:_collectInterrupts` — the C++
    side merging IVTs along the inheritance chain.
