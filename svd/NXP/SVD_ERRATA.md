# NXP SVD Errata

Known SVD bugs verified against reference manuals, with the transforms that
work around them. When NXP fixes a bug in a new SVD release, the corresponding
transform becomes a no-op and can be detected with `audit-lpc-models`.

## LPC8xx

### LPC86x (MCUX_2.16.100)

Reference: UM11607 LPC86x Rev. 3 (April 2023)

The LPC865 SVD is significantly buggier than the LPC864 SVD. Where noted,
blocks source from LPC864 to work around LPC865 bugs.

**Worked around by sourcing from LPC864:**

| Peripheral | Issue | LPC865 SVD | LPC864 SVD |
|------------|-------|-----------|-----------|
| SYSCON | LPOSCCTRL missing at 0x024 | absent | correct |
| SYSCON | EXTTRACECMD at 0x0FC undocumented | present | absent |
| I3C | Register at 0x07C misnamed | SMSGMAPADDR | SMSGLAST (correct) |
| I3C | SMAPCTRL0 missing at 0x11C | absent | correct |

**Missing interrupts (both LPC864 and LPC865 SVDs):**

| IRQ | SVD name | RM name | Notes |
|-----|----------|---------|-------|
| 11 | (absent) | ACMP_IRQ | Analog comparator interrupt; ACOMP peripheral exists in SVD. Worked around via `chip_interrupts` (COMPEDGE at IRQ 11). |

**Suspected RM bugs (UM11607 NVIC table):**

| IRQ | RM name | Notes |
|-----|---------|-------|
| 22 | GPIO_HS_IRQ0 | No GINT peripheral or registers exist in the LPC86x SVD or memory map. No LPC8xx chip has ever had GINT. The LPC54xxx (which does have GINT) uses IRQ 2–3. Likely copy-paste artifact from LPC54xxx documentation. |
| 23 | GPIO_HS_IRQ1 | Same as above. These slots should be reserved. |

### LPC84x (MCUX_2.16.100)

Reference: UM11029 LPC84x Rev. 1.7 (April 2021)

Cross-checked against UM11029 NVIC table (Table 4) and memory map (Table 3).
No SVD bugs found — all register and interrupt data matches the reference manual.

**Peripherals with variant block models (genuinely different register maps vs LPC86x):**

| Peripheral | Reason for variant |
|------------|-------------------|
| SYSCON | Different clock/peripheral control registers (91 register differences vs LPC86x) |
| SWM | Different switch matrix pin assignment tables (42 register differences) |
| INPUTMUX | Different DMA trigger and SCT input mux channels (36 register differences) |

**Peripherals present in LPC84x but not LPC86x:**

| Peripheral | Notes |
|------------|-------|
| CAPT | Capacitive touch controller; shares IRQ 11 with ACOMP |
| CTIMER0 | 32-bit counter/timer (CT32B0 in RM) |
| DAC0, DAC1 | 10-bit DAC; DAC1 shares IRQ 29 with PINT5 |
| SCT0 | SCTimer/PWM |
| I2C1, I2C2, I2C3 | Additional I2C bus controllers |
| USART3, USART4 | USART3 shares IRQ 30 with PINT6; USART4 shares IRQ 31 with PINT7 |

### LPC83x (MCUX_2.16.100)

Reference: UM11021 LPC83x Rev. 1.1 (October 2016)

Cross-checked against UM11021 NVIC table (Table 4) and memory map (Fig 2).
No SVD bugs found — all register, interrupt, and base address data matches the
reference manual. All 24 active interrupts and 20 peripheral base addresses verified.

**Peripherals with variant block models (genuinely different register maps vs LPC86x):**

| Peripheral | Reason for variant |
|------------|-------------------|
| SYSCON | Different clock/peripheral control registers (40 vs 53 registers; identical to LPC82x) |
| SWM | Different switch matrix pin assignment tables (24 vs 21 registers) |
| INPUTMUX | Different DMA trigger mux channels (3 vs 5 registers; identical to LPC82x) |

**Peripherals present in LPC83x but not LPC86x:**

| Peripheral | Notes |
|------------|-------|
| DMA0 | SmartDMA controller |
| FLASH_CTRL | Flash memory controller |
| SCT0 | SCTimer/PWM |
| SPI1 | Second SPI bus controller |

### LPC802 (MCUX_2.16.100)

Reference: UM11045 LPC802 Rev. 1.5 (March 2021)

Cross-checked against UM11045 NVIC table (Table 38) and all register chapter
base addresses. All 17 peripheral base addresses match the reference manual.

**Missing interrupts:**

| IRQ | SVD name | RM name | Notes |
|-----|----------|---------|-------|
| 10 | (absent) | MRT_IRQ | MRT0 peripheral exists in SVD with no interrupt. Worked around via `chip_interrupts` (MRT at IRQ 10). |
| 11 | (absent) | CMP_IRQ | Analog comparator interrupt; ACOMP peripheral exists in SVD. Worked around via `chip_interrupts` (COMPEDGE at IRQ 11). |
| 12 | (absent) | WDT_IRQ | WWDT peripheral exists in SVD with no interrupt. Other LPC8 SVDs (LPC804, LPC84x, LPC86x) have this. Worked around via `chip_interrupts` (INTR at IRQ 12). |
| 13 | (absent) | BOD_IRQ | BOD interrupt not assigned to SYSCON in SVD. Worked around via `chip_interrupts` (BOD at IRQ 13). |

**Peripherals with variant block models (genuinely different register maps vs LPC86x):**

| Peripheral | Reason for variant |
|------------|-------------------|
| SYSCON | Different clock/peripheral control registers (32 vs 53 registers; 9 unique to LPC802 including individual CLKSELs and FRG registers) |

**Block model discrepancies (not yet addressed):**

| Peripheral | Issue | Notes |
|------------|-------|-------|
| PMU | LPC802 has WUENAREG/WUSRCREG; base (LPC865) has DPDCTRL | Same issue affects LPC804. Different wake-up register architecture. |
| MRT0 | LPC802 has MODCFG register; base (LPC865) does not | Same issue affects LPC804 and LPC82x. May be genuine silicon difference or SVD omission. |

### LPC804 (MCUX_2.16.100)

Reference: UM11065 LPC804 Rev. 1.3 (July 2018)

Cross-checked against UM11065 NVIC table (Table 38) and all register chapter
base addresses. All 17 peripheral base addresses match the reference manual.

**Missing interrupts:**

| IRQ | SVD name | RM name | Notes |
|-----|----------|---------|-------|
| 10 | (absent) | MRT_IRQ | MRT0 peripheral exists in SVD with no interrupt. Worked around via `chip_interrupts` (MRT at IRQ 10). |
| 11 | (absent) | CMP_IRQ | Analog comparator interrupt; ACOMP peripheral exists in SVD. Shares IRQ 11 with CAPT (which has CMP_CAPT=11 in SVD). Worked around via `chip_interrupts` (COMPEDGE at IRQ 11). |
| 13 | (absent) | BOD_IRQ | BOD interrupt not assigned to SYSCON in SVD. Worked around via `chip_interrupts` (BOD at IRQ 13). |

**SVD naming issue:**

| Peripheral | Issue | Notes |
|------------|-------|-------|
| ADC | Instance named "ADC" instead of "ADC0" | All other LPC8 chips use "ADC0". Worked around by adding "ADC" to ADC block instances list. |

**Peripherals with variant block models (genuinely different register maps vs LPC86x):**

| Peripheral | Reason for variant |
|------------|-------------------|
| SYSCON | Different clock/peripheral control registers (35 vs 53 registers) |
| SWM | Different switch matrix pin assignment tables (22 vs 21 registers) |

**Peripherals present in LPC804 but not LPC86x:**

| Peripheral | Notes |
|------------|-------|
| CAPT | Capacitive touch controller; shares IRQ 11 with ACOMP |
| CTIMER0 | 32-bit counter/timer (CT32B0 in RM) |
| DAC0 | 10-bit DAC |
| PLU | Programmable Logic Unit; unique to LPC804 among LPC8xx |

**Suspected RM bugs (UM11065):**

| Location | Issue | Notes |
|----------|-------|-------|
| ISER0 bit 14 | Labeled ISE_FLASH | Table 38 shows IRQ 14 as Reserved. No flash controller peripheral exists in SVD or RM memory map. Likely copy-paste from LPC84x ISER0 description. |

### LPC82x (MCUX_2.16.100)

Reference: UM10800 LPC82x Rev. 1.3 (July 2018)

Cross-checked against UM10800 NVIC table (Table 5) and memory map (Fig 2).
No SVD bugs found — all register, interrupt, and base address data matches the
reference manual.

**Peripherals with variant block models (genuinely different register maps vs LPC86x):**

| Peripheral | Reason for variant |
|------------|-------------------|
| SYSCON | Different clock/peripheral control registers (40 vs 53 registers) |
| SWM | Different switch matrix pin assignment tables (25 vs 21 registers) |
| INPUTMUX | Different DMA trigger mux channels (3 vs 5 registers) |

### LPC81x (MCUX_2.16.100)

Reference: UM10601 LPC81x Rev. 1.7 (March 2021)

Cross-checked against UM10601 NVIC table (Table 3) and memory map (Fig 2).
All 19 peripheral base addresses match the reference manual. Per-chip peripheral
availability correct: SPI1 and USART2 are LPC812-only (absent from LPC810/LPC811 SVDs).

**Missing interrupts:**

| IRQ | SVD name | RM name | Notes |
|-----|----------|---------|-------|
| 10 | (absent) | MRT_IRQ | MRT0 peripheral exists in SVD with no interrupt. Worked around via `chip_interrupts` (MRT at IRQ 10). |
| 11 | (absent) | CMP_IRQ | Analog comparator interrupt; ACOMP peripheral exists in SVD. Worked around via `chip_interrupts` (COMPEDGE at IRQ 11). |
| 13 | (absent) | BOD_IRQ | BOD interrupt not assigned to SYSCON in SVD. Worked around via `chip_interrupts` (BOD at IRQ 13). |
| 14 | (absent) | FLASH_IRQ | FLASH_CTRL peripheral exists in SVD with no interrupt. Worked around via `chip_interrupts` (FLASH at IRQ 14). |

**Peripherals with variant block models (genuinely different register maps vs LPC86x):**

| Peripheral | Reason for variant |
|------------|-------------------|
| SYSCON | Different clock/peripheral control registers (39 vs 53 registers; similar to LPC82x minus IRCCTRL) |
| SWM | Different switch matrix pin assignment tables (19 vs 21 registers; 9 PINASSIGN, no FTM) |

**Peripherals present in LPC81x but not LPC86x:**

| Peripheral | Notes |
|------------|-------|
| FLASH_CTRL | Flash memory controller |
| SCT0 | SCTimer/PWM |
| SPI1 | Second SPI bus controller (LPC812 only) |

## LPC54xxx

(none known yet)
