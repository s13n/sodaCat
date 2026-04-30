# sodaCat Documentation

Documentation for the sodaCat SoC data extraction and model generation system.
For a complete overview of the project architecture, build commands, and
conventions, see [CLAUDE.md](../CLAUDE.md).

## Design documents

Per-topic design notes and rationale for non-obvious decisions:

- [Cross-vendor licensed IP](design/cross-vendor-ip.md) — DWC GMAC/EQOS,
  DWC2 USB OTG, Bosch M_CAN, DWC SDMMC, ARM PrimeCell PL08x; candidates
  for cross-vendor unification and known licensees outside the database.
- [STM32 shared blocks](design/stm32-shared-blocks.md) — per-block design
  rationale for OPAMP variants, GpTimer source choice, OTG, ETH, FDCAN,
  HRTIM, and other notable shared blocks.
- [Multi-CPU chip model refactor](design/multicpu-chip-refactor.md) —
  planned redesign to model multi-core silicon as `chip-with-cores:`
  rather than one-chip-per-CPU-view.

## Per-vendor analysis (STM32)

- [GpTimer comparison](ST/GpTimer_comparison.md)
- [STM32C5 analysis](ST/STM32C5-analysis.md)
- [USART comparison](ST/USART_comparison.md)

## Vendor reference manuals

PDFs of vendor reference manuals live alongside this directory:
[ARM/](ARM/), [ESP/](ESP/), [Microchip/](Microchip/), [NXP/](NXP/),
[Raspberry/](Raspberry/), [ST/](ST/).

## Key concepts

### Three-tier model organisation

Models are organised into three tiers to maximise code reuse:
1. **Top-level shared blocks** (e.g. `models/ST/WWDG.yaml`) — blocks shared across multiple families
2. **Family base directory** (e.g. `models/ST/H7/`) — blocks shared across all subfamilies of a family
3. **Subfamily directories** (e.g. `models/ST/H7/H745_H757/`) — blocks that differ per subfamily

Placement is config-driven: blocks without `variants` in the family YAML
config go to the family base directory; blocks with `variants` go to
subfamily directories. See [CLAUDE.md](../CLAUDE.md) for the full rules.

### STM32 family extraction

All 17 STM32 families use a single unified extractor
(`extractors/generate_models.py`) with consolidated YAML configuration in
`svd/ST/STM32.yaml`. Subfamilies are aligned with ST reference manual
boundaries so each subfamily corresponds to exactly one RM.

### CMake integration

- Models are in the **source tree** (`models/ST/`) for easy user access
- Build artifacts (stamp files) are in the **build directory** (not committed)
- `cmake --build . --target stm32h7-models` regenerates models for a family
- Regular builds just use pre-built models
