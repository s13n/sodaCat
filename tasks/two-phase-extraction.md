# Task: Split STM32 extraction into shared-block and chip-model phases

**Goal**
Refactor `extractors/generate_models.py` so a clean rebuild of all families
produces complete chip models on the first run, regardless of the order in
which family extraction targets execute.

## Problem

Each family extraction currently does three things in one pass:
1. Generate the shared block models it owns (`from: <chip>` chips in this family).
2. Read sibling shared block models that other families own, to populate
   `model_paths` and `model_interrupt_order` for blocks consumed via `uses:`.
3. Generate the chip-level models for this family, embedding the
   `models:` index and sorting per-instance interrupts by the consumed
   model's declaration order.

Step 3 silently degrades when step 2 finds the file missing on disk:
- The `models:` entry for that block is dropped from chip YAMLs.
- The interrupt sort becomes a no-op, leaving SVD-raw order.

This was observed after a parallel `ninja stm32*-models` rebuild: F7 chips
lost `bxCAN: ST/bxCAN` from their `models:` index (F4 owns bxCAN and was
still writing it when F7 ran), and C5 chips' I3C interrupts came out in
SVD order `[ERR, EV]` instead of model-declared `[EV, ERR]` (U3 owns I3C).

## Why option 1 (CMake `add_dependencies`) does not solve this

The use/own graph contains cycles. H7 owns CEC, MDIOS, SDMMC and uses
DLYB/IWDG/LTDC/OTG/PSSI from H7RS; H7RS owns those and uses CEC/MDIOS/
SDMMC from H7. Other cycles likely exist between H5, U3, U5, N6. The
helper script in the appendix below computes the raw graph and confirms
the cycles; the implementation can reuse it for the per-family phase-2
dependencies (where the graph is acyclic by construction, since phase 2
only depends on phase 1).

## Proposed shape

Two phases, both runnable independently and idempotently:

**Phase 1 -- `extract-shared`.** Reads `svd/ST/STM32.yaml`. Generates
only the shared block models the family owns: `models/ST/<Block>.yaml`
plus any per-subfamily variant files under `models/ST/<Family>/`.
No chip models written.

**Phase 2 -- `extract-chips`.** Reads `svd/ST/STM32.yaml` plus all
referenced shared YAMLs (which are guaranteed on disk by build-graph
ordering). Generates chip models under `models/ST/<Family>/<Subfamily>/`.

CMake wiring:
- New stamps `stm32<id>-shared.stamp` and `stm32<id>-chips.stamp` per family.
- `stm32<id>-shared` has no inter-family dependency.
- `stm32<id>-chips` depends on `stm32<id>-shared` plus
  `stm32<owner>-shared` for each owner family of a block this family uses
  (computed from the same graph `tools/st_extraction_deps.py` produces).
- Top-level `stm32<id>-models` aggregates both phase stamps.
- The cycle-prone edges (H7↔H7RS etc.) become safe because phase 2 only
  depends on phase 1, never on another family's phase 2.

## Implementation notes

- The current single-pass code is structured around `Pass 1: collect`,
  `Pass 2: write blocks`, `Pass 3: write chip models`. The split aligns
  naturally with that boundary -- phase 1 = passes 1-2, phase 2 = pass 3
  reading shared YAMLs from disk plus the per-chip lightweight summary
  it already builds in pass 1.
- Phase 2 needs the chip summaries from pass 1 (`device_meta`, peripheral
  base addresses, raw interrupts). Either redo pass 1 in phase 2, or
  cache the summaries to disk between phases (a JSON sidecar would be
  simplest). Redoing pass 1 is cheap (SVD parsing only) and avoids the
  cache-staleness question.
- A new top-level CLI flag `--phase {shared,chips,both}` (default `both`
  preserves current behaviour for direct invocations).
- The dependency-emitter helper in the appendix below is already written
  and produces the right graph; drop it into `tools/` and have the cmake
  module call it at configure time to wire phase-2 deps.

## Acceptance criteria

1. From an empty `models/ST/`, a single parallel `ninja stm32*-models`
   produces byte-identical output to a sequential rebuild.
2. The F7-bxCAN and C5-I3C regressions described in the Problem section
   do not reappear under any extraction order.
3. Existing direct invocations
   `python3 extractors/generate_models.py stm32 <FAM> ...` still work
   end-to-end (phase=both default).
4. CI extraction targets still pass.

## Out of scope

- NXP / MCXN / LPC / Espressif / Raspberry pipelines. Their dependency
  graphs are sparse-to-empty; revisit only if the same symptom appears.
- Any change to the YAML schema or chip-model file layout.

## Appendix -- dependency-emitter helper

Drop into `tools/st_extraction_deps.py`. Invoke as
`python3 tools/st_extraction_deps.py svd/ST/STM32.yaml`; output is one
`set(_STM32_<CODE>_DEPS "<C1>;<C2>;...")` per family, suitable for
`cmake_language(EVAL CODE ...)` consumption.

```python
"""Emit CMake set() statements for STM32 inter-family extraction dependencies.

A family entry's `uses: <SharedBlock>` references the shared block in
`shared_blocks:`, whose `from: <Chip>.<Inst>` identifies the owner family
(the family that contains <Chip> in one of its subfamilies). A consumer
family must wait for the owner family's extraction to finish, so the
shared YAML model is on disk when the consumer's run reaches the
cross-config-loading pass that reads it for the chip-level `models:`
index and interrupt-order sort.

Output: one `set(_STM32_<CODE>_DEPS "<C1>;<C2>;...")` line per family,
where each <Cn> is the CODE of an owner family. Empty list if none.
"""
import sys
from pathlib import Path
from ruamel.yaml import YAML


def main():
    cfg = YAML().load(Path(sys.argv[1]))
    shared_blocks = cfg.get('shared_blocks') or {}
    families = cfg.get('families') or {}

    chip_to_family = {}
    for fam_code, fam in families.items():
        for sub in (fam.get('subfamilies') or {}).values():
            for chip in sub.get('chips') or []:
                chip_to_family[chip] = fam_code

    owner = {}
    for sb_name, sb_cfg in shared_blocks.items():
        from_spec = sb_cfg.get('from', '')
        chip = from_spec.split('.', 1)[0] if '.' in from_spec else ''
        if chip in chip_to_family:
            owner[sb_name] = chip_to_family[chip]

    for fam_code, fam in families.items():
        used = set()
        for block_cfg in (fam.get('blocks') or {}).values():
            if block_cfg.get('uses'):
                used.add(block_cfg['uses'])
            for variant in (block_cfg.get('variants') or {}).values():
                if variant.get('uses'):
                    used.add(variant['uses'])
        deps = sorted({owner[u] for u in used
                       if u in owner and owner[u] != fam_code})
        print(f'set(_STM32_{fam_code}_DEPS "{";".join(deps)}")')


if __name__ == '__main__':
    main()
```
