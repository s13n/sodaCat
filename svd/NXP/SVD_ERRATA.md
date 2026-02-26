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

## LPC54xxx

(none known yet)
