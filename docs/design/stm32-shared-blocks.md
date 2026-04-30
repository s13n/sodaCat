# STM32 shared blocks: design rationale

For the architectural mechanism (the `shared_blocks` section in
`svd/ST/STM32.yaml`, the `uses:` key, and how shared models are placed on
disk), see [CLAUDE.md §Family generator](../../CLAUDE.md#family-generator).
This document captures the **per-block design decisions** that aren't
self-evident from the config.

## OPAMP shared blocks

Two shared blocks cover the two RM-confirmed OPAMP IP variants:

- **LPOPAMP** (LPOTR-type): L4, L4+, L5, U0, U5. Source: STM32U535.
  Registers: `CSR/OTR/LPOTR + CSR2/OTR2/LPOTR2`. Includes a CRS→CSR typo
  fix.
- **HSOPAMP** (HSOTR-type): H7, H5. Source: STM32H723.
  Registers: `CSR/OTR/HSOTR/OR + CSR2/OTR2/HSOTR2`. Three SVD bug fixes
  (TRIMLP→TRIMHS fields, missing VP_SEL in CSR2, missing OR register).

Both use a `single` bool param (true for U0, H5). Block type in family
configs remains `OPAMP`; `uses: LPOPAMP` or `uses: HSOPAMP` selects the
variant. The generator uses `owned_shared_mapping` to handle
`block_type ≠ shared_name`. The model `name` field is set to the shared
block name (LPOPAMP/HSOPAMP) so C++ struct names match the `model:` field
in chip models.

**Family-specific OPAMP blocks (intentionally not shared):**
- U3: LPOTR-type but `VM_SEL` is 1-bit at [9] vs 2-bit at [8:2] — incompatible
- G4: distinct IP (6 packed CSRs + TCMRs, embedded trim, no OTR)
- L1: legacy IP (3 OPAMPs packed in shared registers)

## GpTimer source choice

All families source the `GpTimer` model from **TIM2** (4-channel, 32-bit
superset). TIM2 is cleaner than TIM3 in SVDs (fewer `derivedFrom` bugs)
and is a proper superset (same registers + full 32-bit counter/compare +
OR register on some families).

**Params:**
- `width` (int, default 16): counter bits. 32 for TIM2, TIM5, TIM23, TIM24.
- N6/U3/U5 upgraded TIM3/TIM4 to 32-bit (SVD-confirmed; RM0486 Table 500
  erroneously lists N6 TIM3 as 16-bit). G4/H5 remain 16-bit.
- `channels` (int, default 4): capture/compare channels (1-2 for smaller
  timers).
- F7 also has `has_uifremap` and `has_extended_ocm` (F72x only, newer
  timer IP).

**Known SVD issues:** G0/L1 TIM3 `derivedFrom` broken; L4 L412 lacks
TIM3 entirely.

## Other notable shared blocks

The `shared_blocks` section of `svd/ST/STM32.yaml` holds 45 entries
(check the file for the live list). A few that warrant rationale beyond
the config:

- **OTG** (Synopsys DWC2 USB OTG, source STM32H7S.OTG_HS):
  F4/F7/H7/H7RS/L4/L4P/N6/U5. 7 params (`gccfg`, `in/out_endpoints`,
  `channels`, `tx_fifos`, `has_dma`, `has_lpm`). Three GCCFG variants via
  `cloneRegister` (CDP/BCD/VBUS). Split-SVD families use `OTG_xx_GLOBAL`
  as the instance name (cosmetic wart — base address is correct).
- **TimerV1** (F4/F7/H7/L1) and **TimerV2** (14 other families) — Gen1 vs
  Gen2 timer IP.
- **USB_DEV** (STM32L552.USB) — USB device-only, L4/L5/U5.
- **USB_DRD** (STM32H503.USB) — USB dual-role device, C0/G0/G4/H5/U0/U3.
- **SDMMC** (STM32H743.SDMMC1) — F7/H5/H7/H7RS/L4P/L5/N6/U3/U5.
- **ETH** (STM32H563.ETH) — Synopsys DWC EQOS, H5/H7/H7RS. No params.
  MAC address regs (MACA0-3) split to byte fields + cluster array.
  N6 has a newer EQOS revision (multi-queue, TSN) — separate block needed.
- **FDCAN** (STM32H523.FDCAN) — Bosch M_CAN, F3/G4/H5/H7/H7RS/L5/N6/U3/U5.
- **HRTIM** (hand-maintained, G4 superset) — unified Master + Timer
  cluster + Common, F3/G4/H7. No `from:` (model hand-crafted from 3 SVD
  peripherals). 1 param (`timers`: 5 or 6). All interrupts injected via
  `chip_interrupts` (SVDs scatter them across sub-peripherals).
