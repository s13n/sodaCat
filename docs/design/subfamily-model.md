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

Out of scope, on legacy `clocktree:` form:

  - Microchip SAM_Gen1 (shared across 6 families — Shape A doesn't fit
    "one tree, many families" without a new shared-spec mechanism)
  - Microchip PIC32CZ_Gen2 (same cross-family issue + pre-existing block
    model drift around `MCLK.CLKMSK[N].MASK` vs. individual bit fields)

## Resilience

  - Delete a subfamily YAML, re-extract: identical regeneration.
  - Subfamily declares `inherits:` but target is missing AND no `clocks:`
    source in the family config: extractor exits non-zero with a clear
    diagnostic naming the missing file.
  - Subfamily YAML can be partially extractor-managed (only the `interrupts:`
    section) if the family config has no `clocks:` — useful as a migration
    halfway state, but not a long-term arrangement.

## See also

  - `schemas/subfamily.schema.yaml` — the file-level shape.
  - `tools/validate_clock_refs.py` — cross-references clock-spec citations
    against extracted block models.
  - `extractors/generate_models.py` — the extractor implementation:
    `_ivt_intersection`, `_ivt_delta`, `_emit_subfamily_yaml`,
    `_update_subfamily_yaml`.
  - `generators/cxx/generate_chip_header.py:_collectInterrupts` — the C++
    side merging IVTs along the inheritance chain.
