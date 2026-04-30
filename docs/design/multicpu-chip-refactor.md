# Multi-CPU chip model refactor (planned)

## Summary

Replace the current "chip = single-CPU view" model with **chip-as-silicon**,
with one or more cores nested under a `cores:` list. Shared
peripherals/baseAddresses live at chip level; per-core NVIC config, interrupt
table, and any access/memory-map overrides live under each core entry.

## Why

Today's model fails to represent multi-core silicon honestly:
- On chips where the vendor ships per-core SVDs (NXP MCXN5xx/9xx dual-core M33),
  the database carries one chip model per core, which both duplicates data and
  is awkward to expose in sodaCat-explorer.
- On chips with one SVD covering multiple cores (STM32H745/H757, LPC43,
  LPC54114, ESP-P4, RP2040/RP2350), only one CPU's view is captured at all.

## Status

The user has signalled this is worth tackling but it has not been painful
enough to schedule yet. Don't start the refactor unprompted.

## When picked up

**First step:** inventory actual cross-core differences for each multi-core
chip in the DB — NVIC only? distinct memory map? partial peripheral
visibility (e.g. LPC43 M0SUB, ESP-P4 LP core)? The `cores:` schema should be
shaped by data, not guesswork.

**Touch points to plan for:**
- `schemas/chip.schema.yaml`
- `extractors/generate_models.py` (Pass 3)
- `tools/validate_chips.py`
- `generators/cxx/generate_chip_header.py`
- The sodaCat-explorer static site builder

**Multi-core chips currently in the database:**
- MCXN546/547/946/947 (per-core SVDs, dual M33)
- STM32H745/H757 (single SVD covering M7 + M4)
- LPC43xx (M4 + 2× M0)
- LPC54114 (M4 + M0+)
- ESP32-P4 (dual HP RISC-V + LP RISC-V)
- RP2040 (dual M0+)
- RP2350 (dual M33 / dual Hazard3 RISC-V)

## Related cosmetic fix already shipped (2026-04-26)

Chip model `name:` now uses the family-config chip name instead of the SVD
`<name>` element, so MCXN dual-core models would lose their `_cm33_core0`
suffix on next regeneration. That patch sidesteps the wildcard-name problem
but does not address the underlying multi-core modelling question.
