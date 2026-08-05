# Subfamily Model & Inheritance

This document describes the family/subfamily/chip layering — how family-common
facts are owned at the right tier and how chips inherit and override them.

## Why this exists

Before the layering, every chip YAML carried its full picture: every
peripheral instance with its interrupt wiring, a `clocktree:` pointer to
a separate file, every parameter.  For an 8-chip subfamily, the same 114
common peripheral-instance entries (with their NVIC vector assignments)
appeared 8 times, the clock tree lived in a separate hand-authored file
with no schematic link to the rest of the chip data, and mixed-ownership
creep (parts of the chip YAML hand-edited, parts extractor-managed)
crept in unannounced.

The subfamily-model tier addresses both problems.  Family-common facts
(currently: clock-tree topology and the common peripheral-instance set
with its wiring; later: DMA-request fabric as a first-class instance,
EXTI routing fabric, ...) live in one place per subfamily.  Chip YAMLs
carry only what's chip-specific.

## Tiers and what lives where

| Tier      | File location                                         | Owner       | Contents |
| --------- | ----------------------------------------------------- | ----------- | -------- |
| Family    | `svd/<Vendor>/<Family>.yaml`                          | hand-author | Extraction config: chips, blocks, patches, **clock-tree topology** |
| Subfamily | `models/<Vendor>/<Family>/<Subfamily>/<Subfamily>.yaml` | extractor | Derived artifact: header metadata, **clocks: section**, **instances:** (common subset, with wiring) |
| Chip      | `models/<Vendor>/<Family>/<Subfamily>/<Chip>.yaml`     | extractor | Derived artifact: chip-specific instance entries, `inherits:` link |

The subfamily YAML is fully derived: deleting it and re-extracting yields a
byte-identical file.  Chip YAMLs reach their subfamily via an `inherits:` key
whose value is the model-root-relative path of the subfamily YAML.

**Single-chip subfamilies where chip name = subfamily name** (Raspberry RP2040
/ RP2350) would otherwise produce two YAMLs in the same directory with the
same stem (`RP2040/RP2040.yaml`) and two header outputs at the same path
(`rp/RP2040.hpp`).  Convention: the subfamily YAML uses the stem
`_common.yaml` (`RP2040/_common.yaml`); the chip keeps its own name.  Both
emit into the same namespace, but their header filenames differ
(`rp/_common.hpp` carries the clocktree, `rp/RP2040.hpp` carries the chip
integration).  The vendor config's `inherits:` picks the stem.

## Two fabric mechanisms

The pattern accommodates both **hand-authored** fabrics (topology that has to
come from a human reading the reference manual — currently just the clock
tree) and **computed** fabrics (data derivable mechanically from per-chip
SVD-extracted content — currently the peripheral-instance set with its
interrupt wiring, and the block-model index).

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
index (`models:`) follow an intersection pattern.  After per-chip
processing, the extractor extracts entries that appear with
byte-identical content in every chip in the subfamily, lifts them to
the subfamily YAML, and reduces each chip's own map to the delta.

Each instance entry carries its own wiring under `connections:` — a map
from each block-declared output signal to its dotted-string
destination list (e.g. `connections: {INTR: ["NVIC.53"]}`).  Vector-
table merging is therefore implicit in the instance lift: an instance
whose entire entry (baseAddress + model + connections + parameters) is
byte-identical across every chip lifts wholesale; an instance whose
connection map differs across chips (e.g. one chip routes USART1.INTR
to NVIC.37 and another to NVIC.38) stays per-chip on every chip in the
subfamily.

For a typical multi-chip subfamily (e.g. H745_H757 with 8 chips, 114
instances each), most instances and model paths are common — so chip
YAMLs shrink to a handful of instance entries each.  Single-chip
subfamilies (RP2040, SAM-Gen1 consumers) lift their entire instance
set up; the chip YAML becomes a thin header.

Chip-level entries override ancestor entries by key (instance name /
block name).  The chip-header generator walks the `inherits:` chain to
assemble the merged view.

The patching pipeline still applies per-chip *before* the
intersection: SVD raw interrupt names → canonical via the block's
`outputs:` map; `chip_connections:` overrides; `chip_instances:`
exclusions.  The intersection sees the post-patch state — so a patch
that makes one chip agree with its siblings causes the corrected entry
to lift cleanly into the subfamily (the patch becomes invisible in
the output, which is the right behaviour: the family config is the
durable record of "here's a fix"; the YAML reflects what the silicon
does).

## Extraction pipeline order

Within Pass 3 of `extractors/generate_models.py`:

```
for subfamily in family:
    for chip in subfamily:
        # 1. Per-chip processing (existing logic):
        #    block presence, instance addresses, interrupt canonicalisation,
        #    chip_connections overrides, chip_instances exclusions,
        #    per-instance connections map assembly ...
        chip_model = assemble(chip)
        accumulate(chip_model)        # NOT written to disk yet

    # 2. Subfamily-level synthesis:
    if subfamily has `inherits:`:
        common_instances = dict_intersect([cm.instances for cm in accumulated])
        common_models    = dict_intersect([cm.models    for cm in accumulated])
        if subfamily has `clocks:`:
            emit_subfamily_yaml(
                family_label,         # via vendor extension family_label()
                devices,              # dedupe chip names, strip _CMn suffix
                ref_manual → documents,
                clocks,               # from family config
                instances=common_instances,
                models=common_models,
            )
        elif subfamily YAML exists:
            update_subfamily_yaml(instances=common_instances, models=common_models)
        else:
            FAIL: inherits target doesn't exist, no clocks: to regenerate from

        for chip in accumulated:
            chip.instances = dict_delta(chip.instances, common_instances)
            chip.models    = dict_delta(chip.models,    common_models)

    write all accumulated chip YAMLs
```

The C++ side (`generators/cxx/generate_header.py`, `ChipFormatter`) walks `inherits:`
when computing the merged instance view; the vector-table view is derived on
the fly from each instance's `outputs:` map by parsing `NVIC.<n>` destinations,
so consumers see the full IVT regardless of where each instance lives in the
YAML hierarchy.

## Adding a new fabric

When a new family-common fabric type lands (DMA-request matrix, EXTI line
routing, event router, ...), the pattern is:

1. Decide whether the fabric is **hand-authored** (topology requires RM
   knowledge — model it like clocks) or **computed** (mechanically derivable
   from per-chip SVD data — model it like the instance set).
2. Add the section to `schemas/subfamily.schema.yaml`.
3. For hand-authored: read the section from the family config, pass it to
   `_emit_subfamily_yaml(...)`, deep-strip ruamel metadata before write.
4. For computed: if the fabric is *part of* the instance entry (additional
   destination kinds on `outputs:`, new instance fields), it lifts
   automatically with `_dict_intersection`.  If it's a sibling top-level
   section, add an intersection-and-delta helper over the per-chip field,
   applied *after* every existing per-chip patch.
5. Update the C++ generator that consumes the section to walk `inherits:` and
   merge ancestor entries.
6. Add a cross-reference validator if the fabric cites registers/fields in
   block models, or destination instances that must exist in the chip.

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
  - Subfamily YAML can be partially extractor-managed (only the `instances:`
    and `models:` sections) if the family config has no `clocks:` yet —
    useful as a migration halfway state, but not a long-term arrangement.

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
    `_dict_intersection`, `_dict_delta`, `_emit_subfamily_yaml`,
    `_update_subfamily_yaml`.
  - `generators/cxx/generate_header.py` — `merge_inherited()` assembles the
    merged instance view across the inheritance chain, and
    `ChipFormatter.interruptCount` derives the NVIC vector-table extent on
    the fly by walking each instance's `connections:` map.
