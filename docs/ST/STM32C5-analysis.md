# STM32C5 Family Analysis

**Date:** 2026-03-25
**Source:** RM0522 Rev 1 (February 2026), 2572 pages
**SVD status:** Not yet published by ST (not in their SVD index)

## Family Overview

- **Core:** Cortex-M33 with FPU
- **NVIC:** 99 IRQs (0-98), individual EXTI lines (no grouping), 16 priority levels
- **DMA:** LPDMA (low-power), 2 controllers x 8 channels each
- **Datasheets:** DS15125 (C53x), DS15135 (C542), DS14928 (C55x), DS14927 (C562), DS15136 (C59x), DS15137 (C5A3)
- **Erratasheets:** ES0676 (C53x/C542), ES0661 (C55x/C562), ES0677 (C59x/C5A3)

### Subfamilies

| Subfamily | SRAM | Flash (est.) | Key extras |
|-----------|------|-------------|------------|
| C53x/C542 | 32+32 KB | up to 256 KB | Smallest: 1 ADC, 1 OPAMP, 1 FDCAN, no TIM3-5/16-17 |
| C55x/C562 | 64+64 KB | up to 512 KB | Mid: 2 ADCs (dual mode), TIM5, SPI3, TIM16/17, I2C2, USART3 |
| C59x/C5A3 | 128+128 KB | up to 1 MB | Full: 3 ADCs, ETH, XSPI1, SAES, PKA, CCB, TIM3/4, GPIOF/G |

### Peripheral inventory (from memory map, Table 3)

```
AHB4:  XSPI1, DLYB                           (C59x only)
AHB3:  DBGMCU, EXTI, RCC, PWR
APB3:  TAMP, RTC, LPTIM1, LPUART1, SBS
AHB2:  CCB, PKA, SAES                        (C59x only)
       RNG, HASH, AES                        (all)
       ADC1, ADC2, ADC3, ADCC12, ADCC3       (ADC2: C55x+, ADC3: C59x)
       DAC1                                  (all)
       GPIOA-H                               (F/G: C59x only)
AHB1:  ICACHE, ETH                           (ETH: C59x only)
       RAMCFG, CORDIC, CRC, FLASH
       LPDMA1, LPDMA2
APB2:  USB, TIM17, TIM16, TIM15              (TIM16/17: C55x+)
       USART1, TIM8, SPI1, TIM1
APB1:  FDCAN1, FDCAN2                        (FDCAN2: C53x+C59x, not C55x)
       UART7, USART6                         (C59x only)
       CRS, I3C1, I2C1, I2C2                 (I2C2: C55x+)
       UART5, UART4, USART3, USART2          (USART3: C55x+)
       COMP1/2, SPI3, SPI2                   (COMP2: C53x only; SPI3: C55x+)
       OPAMP1                                (C53x only)
       IWDG, WWDG, TIM12
       TIM6, TIM7, TIM5, TIM4, TIM3, TIM2   (TIM5: C55x+; TIM3/4: C59x)
```

## Existing shared blocks compatible with C5

19 blocks can reference existing shared models via `uses:`.

### Exact register-map matches

| Block | Shared As | C5 Instances | Verification |
|-------|-----------|-------------|--------------|
| CRC | CRC | CRC | Offsets 0x000-0x014 identical |
| CORDIC | CORDIC | CORDIC | Offsets 0x000-0x008 identical |
| USB | USB_DRD | USB | All 14 registers identical (CHEP0R-7R, CNTR, ISTR, FNR, DADDR, LPMCSR, BCDR) |

### Matches with parameters

| Block | Shared As | C5 Instances | Notes |
|-------|-----------|-------------|-------|
| Timer | TimerV2 | TIM1-5, TIM8, TIM12, TIM15-17 | DITHEN, ECR, TISEL, DBSS all present. TIM2/TIM5 are 32-bit (`width: 32`). |
| BasicTimer | BasicTimer | TIM6, TIM7 | Standard |
| GPIO | GPIO | GPIOA-H | Core regs match. No HSLVR (param). SECCFGR TBD. |
| I2C | I2C | I2C1, I2C2 | Core regs match. AUTOCR optional. |
| USART | USART | USART1-3,6, UART4-5,7 | Modern USART with FIFO/PRESC. Params for lpbaud, sync, etc. |
| LPUART | USART | LPUART1 | Same USART IP |
| SPI | ModernSPI | SPI1-3 | CR1+CFG1+CFG2 style (not legacy CR1+CR2). Has BPASS/DRDS in CFG1, RDIOP/RDIOM in CFG2. |
| LPTIM | LPTIM | LPTIM1 | Core regs match. Channel count via params. |
| FDCAN | FDCAN | FDCAN1, FDCAN2 | Core FDCAN regs match (0x000-0x07C). Message RAM area in model only. |
| ETH | ETH | ETH (C59x only) | Synopsys DWC EQOS. Core regs match. |
| CRS | CRS | CRS | Standard. trim_width param TBD. |
| IWDG | IWDG | IWDG | C5 adds ICR at 0x018 (interrupt clear). Newer gen — may need `gen` param update. |
| WWDG | WWDG | WWDG | With `cfr_version: 2` |
| HASH | HASH | HASH | Same gen as H5/U3 (structural match) |
| PKA | PKA | PKA (C59x only) | Same gen as H5/U3 (structural match) |
| RTC | RTC_V2 | RTC | New RTC IP (ICSR register, not legacy ISR) |

## Family-specific blocks (22, need SVD for extraction)

### Always family-specific

| Block | Instances | Notes |
|-------|-----------|-------|
| RCC | RCC | Clock tree is always unique per family |
| Flash | FLASH | Flash controller varies per family |
| PWR | PWR | Power controller varies per family |
| EXTI | EXTI | Event routing is family-specific |
| DBGMCU | DBGMCU | Debug/trace config varies per family |

### New or incompatible IP revisions

| Block | Instances | Issue |
|-------|-----------|-------|
| ADC | ADC1, ADC2, ADC3 | **Newer IP** — split OFCFGR (config at 0x050-0x05C) / OFR (value at 0x060-0x06C) offset registers. H5 combines these into single OFFSETy regs. Separate LTR/HTR watchdog regs. 12-bit, single-ended only, gain+offset compensation, oversampler up to 1024x. |
| ADC_Common | ADCC12, ADCC3 | Two common blocks (dual-mode ADC1/2 + standalone ADC3). Standard CSR/CCR/CDR/CDR2 layout. |
| RNG | RNG | **Newer gen** — expanded health test registers: HTCR0-3 (at 0x010-0x01F), HTSR0-1 (at 0x020-0x024), MSMR (at 0x030). Shared model only has single HTCR. |
| OPAMP | OPAMP1 (C53x only) | **G4-style IP** — CSR + TCMR registers only (PGA_GAIN[4:0], OPAHSM). No OTR/LPOTR/HSOTR. Incompatible with both LPOPAMP and HSOPAMP shared blocks. |

### Blocks in multiple families but not yet shared

| Block | Instances | Current families | Notes |
|-------|-----------|-----------------|-------|
| SAES | SAES (C59x only) | H5, H7RS, N6, U3, U5 | No transforms in any family |
| RAMCFG | RAMCFG | H5, H7RS, N6, U3, U5 | H7RS needs 1 transform |
| I3C | I3C1 | H5, N6, U3 | No transforms |
| ICACHE | ICACHE | H5, H7RS, U5 | No transforms |
| SBS | SBS | H5, H7RS | No transforms |
| LPDMA | LPDMA1, LPDMA2 | U5 | Same linked-list DMA core IP, U5 has 1x4ch, C5 has 2x8ch |
| COMP | COMP | G0, G4, H5, H7, L1, L4, L4P, L5, U0, U3, U5 | Many IP variants across gens |
| DAC | DAC | F3-U5 (15 families) | Multiple generations |
| AES | AES | Family-specific in H5 | TBD whether C5 matches |
| TAMP | TAMP | Family-specific in H5 | TBD whether C5 matches |

### C59x/C5A3-only blocks

| Block | Instances | Notes |
|-------|-----------|-------|
| XSPI | XSPI1 | Also in H7RS, N6. Not shared yet. |
| DLYB | DLYB | Also in H7RS. Not shared yet. |
| CCB | CCB | Also in U3. Coupling and chaining bridge. |

## New shared block candidates

Blocks currently family-specific in 2+ families that could be promoted to `shared_blocks`.
C5 would add one more family to each.

### Tier 1 -- High value (5+ families including C5)

| Block | Families | Transforms needed | Assessment |
|-------|----------|-------------------|------------|
| **SAES** | H5, H7RS, N6, U3, U5 (+C5 = 6) | None | **Prime candidate.** All families source from different chips but none need transforms. Single instance, no params. |
| **RAMCFG** | H5, H7RS, N6, U3, U5 (+C5 = 6) | H7RS: 1 | **Good candidate.** Minor variant in H7RS only. |

### Tier 2 -- Medium value (3-4 families including C5)

| Block | Families | Transforms needed | Assessment |
|-------|----------|-------------------|------------|
| **I3C** | H5, N6, U3 (+C5 = 4) | None | **Strong candidate.** Clean across all families. |
| **ICACHE** | H5, H7RS, U5 (+C5 = 4) | None | **Strong candidate.** Clean across all families. |
| **SBS** | H5, H7RS (+C5 = 3) | None | **Good candidate.** Needs register-map comparison to confirm. |

### Tier 3 -- Lower value (2 families including C5)

| Block | Families | Notes |
|-------|----------|-------|
| XSPI | H7RS, N6 (+C5 = 3) | C59x only. No transforms. |
| LPDMA | U5 (+C5 = 2) | Same core IP, different channel counts. Parameterizable. |
| DLYB | H7RS (+C5 = 2) | C59x only. Marginal. |
| CCB | U3 (+C5 = 2) | C59x only. Marginal. |

### Too fragmented to share

- **ADC** (18 families, 4+ IP generations): Channel counts, features, and register layouts differ significantly.
- **DAC** (15 families): Multiple generations with different register sets.
- **COMP** (11 families): At least 3 distinct IP variants.
- **EXTI** (18 families): Varies significantly across generations (grouped vs individual lines, different register layouts).

## NVIC Vector Table (99 IRQs)

Single table for all C5 devices (no subfamily differentiation -- peripheral availability per datasheet).

| IRQ | Name | Description |
|-----|------|-------------|
| 0 | WWDG | Window watchdog |
| 1 | PVD | Power voltage monitor |
| 2 | RTC | RTC global |
| 3 | TAMP | Tamper global |
| 4 | RAMCFG | RAM configuration |
| 5 | FLASH | Flash global |
| 6 | RCC | RCC global |
| 7-22 | EXTI0-EXTI15 | Individual EXTI lines |
| 23-30 | LPDMA1_CH0-CH7 | LPDMA1 channels |
| 31 | IWDG | Independent watchdog |
| 32 | ADC1 | ADC1 global |
| 33 | ADC2 | ADC2 global |
| 34-35 | FDCAN1_IT0/IT1 | FDCAN1 interrupts |
| 36 | TIM1_BRK/TERR/IERR | TIM1 break / transition error / index error |
| 37 | TIM1_UP | TIM1 update |
| 38 | TIM1_TRG_COM/DIR/IDX | TIM1 trigger+commutation / direction / index |
| 39 | TIM1_CC | TIM1 capture compare |
| 40 | TIM2 | TIM2 global |
| 41 | TIM5 | TIM5 global |
| 42 | TIM6 | TIM6 global |
| 43 | TIM7 | TIM7 global |
| 44-45 | I2C1_EV/ER | I2C1 event/error |
| 46-47 | I3C1_EV/ER | I3C1 event/error |
| 48-50 | SPI1-SPI3 | SPI globals |
| 51-55 | USART1-3, UART4-5 | USART/UART globals |
| 56 | LPUART1 | LPUART1 global |
| 57 | LPTIM1 | LPTIM1 global |
| 58 | TIM12 | TIM12 global |
| 59-61 | TIM15-TIM17 | Timer globals |
| 62 | USB_FS | USB FS global |
| 63 | CRS | Clock recovery |
| 64 | RNG | RNG global |
| 65 | FPU | Floating point |
| 66 | ICACHE | Instruction cache |
| 67 | CORDIC | CORDIC |
| 68 | AES | AES global |
| 69 | HASH | HASH |
| 70-71 | I2C2_EV/ER | I2C2 event/error |
| 72 | TIM8_BRK/TERR/IERR | TIM8 break / transition error / index error |
| 73 | TIM8_UP | TIM8 update |
| 74 | TIM8_TRG_COM/DIR/IDX | TIM8 trigger+commutation / direction / index |
| 75 | TIM8_CC | TIM8 capture compare |
| 76 | COMP1 | Comparator 1 |
| 77 | DAC1 | DAC1 global |
| 78-85 | LPDMA2_CH0-CH7 | LPDMA2 channels |
| 86-87 | FDCAN2_IT0/IT1 | FDCAN2 interrupts |
| 88 | COMP2 | Comparator 2 |
| 89 | TIM3 | TIM3 global |
| 90 | TIM4 | TIM4 global |
| 91 | XSPI1 | XSPI1 global |
| 92 | SAES | SAES global |
| 93 | PKA | PKA global |
| 94 | ETH1 | Ethernet |
| 95 | ETH1_WKUP | Ethernet wakeup |
| 96 | USART6 | USART6 global |
| 97 | UART7 | UART7 global |
| 98 | ADC3 | ADC3 global |

## Config scaffold status

Added to `svd/ST/STM32.yaml` and `svd/ST/CMakeLists.txt`.

- **41 blocks** declared (19 shared, 22 family-specific)
- **3 subfamilies** (C53x_C542, C55x_C562, C59x_C5A3)
- **Chip names:** empty (pending SVD/datasheets)
- **`from:` fields:** empty for family-specific blocks (pending SVD)
- **CMake target:** `stm32c5-models` registered

When ST publishes the SVD:
1. `python3 tools/st_maintenance.py svd --download` will fetch it
2. Fill in chip names from SVD contents
3. Fill in `from:` fields (pick best source chip per block)
4. `cmake --build . --target stm32c5-models` to generate
