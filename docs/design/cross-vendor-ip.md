# Cross-Vendor Licensed IP Blocks

## Candidates for future cross-vendor unification

These four IP blocks are third-party licensed silicon IP used by multiple
MCU/SoC vendors. Unifying models enables shared driver implementations across
vendors — the primary benefit.

### 1. Synopsys DWC Ethernet (GMAC 3.x / EQOS 4-5.x)

Three generations in sodaCat today:
- **GMAC 3.x** (legacy): STM32 F4/F7 (split into 4 sub-blocks), LPC43 (monolithic)
- **EQOS 4.x**: STM32 H7 (split into 4 sub-blocks)
- **EQOS 5.x**: STM32 H5/H7RS/N6 (monolithic ETH), LPC54, MCXN

Cross-vendor naming divergence is the main obstacle:
- ST uses compressed names: `MACCR`, `MACECR`, `DMACCR`
- LPC54 uses mixed-case verbose: `MAC_CONFIG`, `DMA_CH0_CONTROL`
- MCXN uses full verbose: `MAC_CONFIGURATION`, `DMA_CH0_CONTROL`

Other known licensees (not in sodaCat): Allwinner, Amlogic, Rockchip, NVIDIA Tegra,
Intel/Altera SoCFPGA, Qualcomm, Samsung Exynos, StarFive, Sophgo, Tesla FSD,
NXP i.MX8, Loongson, Toshiba Visconti. Mostly Linux-class SoCs, not MCUs.

### 2. Synopsys DWC2 USB OTG

Already a cross-family shared block within STM32 (`OTG`, 8 families).
"Billions of units shipped" per Synopsys.

Other known licensees (not in sodaCat):
- **MCU-class** (realistic targets): Espressif ESP32-S2/S3/P4, GigaDevice GD32,
  Infineon XMC4500, Artery AT32F4xx
- **SoC-class**: Broadcom BCM2711/2837 (RPi), Rockchip, Samsung Exynos

### 3. Bosch M_CAN (FDCAN in STM32)

Already a cross-family shared block within STM32 (`FDCAN`, 9 families).
Dominant CAN FD controller IP in automotive.

Other known licensees (not in sodaCat):
- **MCU-class** (realistic targets): Microchip SAM C21/E51/E54/E70 (publish ATDF),
  TI Sitara AM243x/AM64x, Infineon AURIX TC2xx/TC3xx/TC4x, Renesas RH850
- **Automotive**: NXP MPC5xxx/S32K3xx

### 4. Synopsys DWC SD/eMMC (SDMMC)

Already a cross-family shared block within STM32 (`SDMMC`, 9 families).
Two generations: older dw_mmc and newer SDHCI-compliant dwcmshc.

Other known licensees (not in sodaCat):
- Samsung Exynos, Rockchip, HiSilicon/Huawei Kirin, Intel/Altera SoCFPGA,
  Sophgo, StarFive, T-Head/Alibaba
- Mostly application processors, limited near-term MCU relevance.

## ARM PrimeCell PL08x (PL080 / PL081)

**Status:** Wired up in sodaCat as `models/ARM/PL08x.yaml`, owned by NXP LPC43
(only PL08x-bearing chip currently in the repo). Mechanism: shared block in
`svd/NXP/LPC.yaml` with `designer: ARM`, which routes the generated model to
`models/<designer>/` instead of `models/NXP/`. LPC43's GPDMA family-block uses
`uses: PL08x`. ARM is a "designer" namespace, not a chip-vendor — a convention
introduced for licensed-IP shared blocks.

**PL080 vs PL081 unification:** The two ARM-published variants (DDI 0196 vs
DDI 0218) share one register layout — PL081 is a strict subset of PL080
(2 channels instead of 8, 1 AHB master instead of 2). One model `PL08x`
covers both, with a 1-bit int param `pl081` (default 0 = PL080) describing
the differences. The previously hand-maintained stub `models/ARM/PL081.yaml`
was deleted. C++-side: the unified struct is sized for the PL080 superset;
PL081 instances get six phantom channels and a few reserved bits (M1, LM,
S, D) — accepted because PL081 is rare in real silicon.

**Other known PL08x instances (not in sodaCat):** NXP LPC17xx, LPC178x/LPC408x,
LPC18xx, LPC24xx; ST SPEAr, ST-Ericsson Nomadik; Samsung S3C6410 (2× PL080);
Faraday FTDMAC020 derivative; ARM RealView/Versatile reference platforms. All
real PL080 silicon is 8-channel; the 32-bit-wide channel-mask register fields
are synthesis-time headroom that nobody uses.

**Deferred work — needed before a second PL08x vendor can be added cleanly:**

The current `models/ARM/PL08x.yaml` carries LPC43-specific enum values on
`SRCPERIPHERAL` and `DESTPERIPHERAL` (5-bit DMA-request-routing fields):
`SOURCE_SPIFI`, `SOURCE_SSP0_9`, `DESTINATION_TIMER_3`, etc. These names are
wrong for any non-LPC43 PL080 — the request-line matrix is vendor-specific
silicon-routing, not part of the IP. Accepted as a known wart for now since
LPC43 is the only PL080 instance.

When a second PL080 vendor lands (LPC17/18/178/408 most likely), do this:
1. Strip the enum values from `SRCPERIPHERAL` / `DESTPERIPHERAL` in the shared
   model — leave them as plain 5-bit integer fields.
2. Add a way for each family's `uses: PL080` block-cfg to layer routing-name
   enums back on via a `patchFields` transform applied *after* the shared
   model is materialised. The current transforms framework patches blocks
   during family-extraction, not during shared-block consumption — so this
   needs a small new code path (e.g. a `post_uses_transforms:` list that
   runs when generating chip models that reference the shared block).
3. Move the per-family enum tables into each family's `blocks.GPDMA` entry.

Until then: any second PL080 vendor would inherit LPC43's routing names,
which would be misleading. Better to factor first, then add.

## NXP Ethernet Models (Not Unifiable)

Three different DWC generations across NXP families — kept as separate
family-specific blocks:
- LPC43 ETHERNET: GMAC 3.x (legacy, ~37 registers, no MTL, single-channel DMA)
- LPC54 ENET: EQOS 4.x (~70+ registers, MTL, multi-channel DMA)
- MCXN ENET: EQOS 5.x (~100+ registers, 2 queues/channels, HW_FEATURE[0-3])
