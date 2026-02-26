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
| 11 | (absent) | ACMP_IRQ | Analog comparator interrupt |
| 22 | (absent) | GPIO_HS_IRQ0 | GPIO group interrupt 0 |
| 23 | (absent) | GPIO_HS_IRQ1 | GPIO group interrupt 1 |

## LPC54xxx

(none known yet)
