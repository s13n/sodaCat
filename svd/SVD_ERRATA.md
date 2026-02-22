# SVD Errata

Known bugs in vendor SVD files, verified against reference manuals.


## ST STM32F7

References:
- RM0385 Rev.8 — STM32F75xxx / STM32F74xxx
- RM0410 Rev.5 — STM32F76xxx / STM32F77xxx
- RM0431 Rev.4 — STM32F72xxx / STM32F73xxx

### Flash (FLASH)

**STM32F722 (SVD v1.4):**

| Register | Field     | Bug                          | RM0431 says                  |
|----------|-----------|------------------------------|------------------------------|
| ACR      | LATENCY   | 3-bit width                  | 4-bit (LATENCY[3:0])        |
| SR       | RDERR     | Missing                      | Bit 8, PCROP protection error|
| CR       | SNB       | 5-bit width                  | 4-bit (single-bank device)   |
| OPTCR    | nWRP      | 12-bit width                 | 8-bit (nWRP[7:0])           |

**STM32F745 (SVD v1.6):**

| Register | Field     | Bug                          | RM0385 says                  |
|----------|-----------|------------------------------|------------------------------|
| OPTKEYR  | OPTKEY    | Field named "OPTKEY"         | Field is "OPTKEYR"           |
| CR       | MER1      | Present at bit 15            | Bit 15 reserved (single-bank)|
| CR       | SNB       | 5-bit width                  | 4-bit (single-bank device)   |
| OPTCR    | nWRP      | 12-bit width                 | 8-bit (nWRP[7:0])           |
| OPTCR    | nDBOOT    | Present at bit 28            | Bit 28 reserved (not dual-bank capable) |
| OPTCR    | nDBANK    | Present at bit 29            | Bit 29 reserved (not dual-bank capable) |

Note: The F745 SVD appears to have dual-bank fields copied from the F767 SVD,
despite F74x hardware being single-bank only.

**STM32F767 (SVD v1.6):**

| Register | Field     | Bug                          | RM0410 says                  |
|----------|-----------|------------------------------|------------------------------|
| SR       | PGSERR    | Field named "PGSERR"         | Field is "ERSERR" (Erase Sequence Error) |
| OPTKEYR  | OPTKEY    | Field named "OPTKEY"         | Field is "OPTKEYR"           |

### PWR

**STM32F722 (SVD v1.4):**

| Register | Field     | Bug                          | RM0431 says                  |
|----------|-----------|------------------------------|------------------------------|
| CSR1     | VOSRDY    | Access read-write            | Read-only                    |
| CSR1     | ODRDY     | Access read-write            | Read-only                    |
| CSR1     | ODSWRDY   | Access read-write            | Read-only                    |

**STM32F745 (SVD v1.6):**

| Register | Field     | Bug                          | RM0385 says                  |
|----------|-----------|------------------------------|------------------------------|
| CSR1     | EIWUP     | Missing                      | Bit 8, Enable internal wakeup|
| CSR1     | VOSRDY    | Access read-write            | Read-only                    |
| CSR1     | ODRDY     | Access read-write            | Read-only                    |
| CSR1     | ODSWRDY   | Access read-write            | Read-only                    |

### BasicTimer (TIM6/TIM7)

**STM32F745, STM32F767 (SVD v1.6):**

| Register | Field     | Bug                          | All three RMs say            |
|----------|-----------|------------------------------|------------------------------|
| CNT      | UIFCPY    | Missing                      | Bit 31, read-only UIF copy   |

### CRC

**STM32F745, STM32F767 (SVD v1.6):**

| Register | Field     | Bug                          | All three RMs say            |
|----------|-----------|------------------------------|------------------------------|
| CR       | CR        | Single 1-bit field (typo "regidter") | Four fields: RESET, POLYSIZE, REV_IN, REV_OUT |

### I2C

**STM32F745, STM32F767 (SVD v1.6):**

| Register | Field     | Bug                          | All three RMs say            |
|----------|-----------|------------------------------|------------------------------|
| CR1      | WUPEN     | Present at bit 18            | Bit 18 reserved (no wakeup from Stop on F7) |

### IWDG

**STM32F745, STM32F767 (SVD v1.6):**

| Register | Field     | Bug                          | All three RMs say            |
|----------|-----------|------------------------------|------------------------------|
| SR       | WVU       | Missing                      | Bit 2, window value update status |

### GPIO

**STM32F745, STM32F767 (SVD v1.6):**

| Register | Field     | Bug                          | All three RMs say            |
|----------|-----------|------------------------------|------------------------------|
| BRR      | (entire)  | Register present at offset 0x28 | No BRR register in GPIO (register map ends at AFRH, offset 0x24) |

### USART

**STM32F745 (SVD v1.6):**

| Register | Field        | Bug                          | RM0385 says                  |
|----------|--------------|------------------------------|------------------------------|
| CR1      | UESM         | Present at bit 1             | Bit 1 reserved               |
| CR3      | WUS          | Present at bits 20-21        | Bits 20-21 reserved          |
| CR3      | WUFIE        | Present at bit 22            | Bit 22 reserved              |
| ISR      | WUF          | Present at bit 20            | Bit 20 reserved              |
| ISR      | REACK        | Present at bit 22            | Bit 22 reserved              |
| ICR      | WUCF         | Present at bit 20            | Bit 20 reserved              |
| BRR      | DIV_Fraction | Split into Fraction+Mantissa | Single BRR[15:0] field       |

Note: The F745 SVD has stop-mode wakeup fields copied from the F767, despite
F74x not supporting USART wakeup from Stop mode per RM0385.

**STM32F767 (SVD v1.6):**

| Register | Field        | Bug                          | RM0410 says                  |
|----------|--------------|------------------------------|------------------------------|
| CR3      | UCESM        | Missing                      | Bit 23, USART clock enable in Stop mode |
| CR3      | TCBGTIE      | Missing                      | Bit 24, TX complete before guard time IE |
| ISR      | TCBGT        | Missing                      | Bit 25, TX complete before guard time |
| ICR      | TCBGTCF      | Missing                      | Bit 7, TCBGT clear flag      |
| BRR      | DIV_Fraction | Split into Fraction+Mantissa | Single BRR[15:0] field       |

**STM32F722 (SVD v1.4):**

| Register | Field        | Bug                          | RM0431 says                  |
|----------|--------------|------------------------------|------------------------------|
| ISR      | RWU          | Missing                      | Bit 19, receiver wakeup from mute mode |

### AES / CRYP naming

**STM32F722 (SVD v1.4), STM32F723 (SVD v1.4), STM32F732 (SVD v1.4), STM32F733 (SVD v1.4):**

The AES hardware accelerator is incorrectly named "CRYP" in these SVD files.
RM0431 Chapter 17 is titled "AES hardware accelerator (AES)", the memory map
lists 0x50060000 as "AES", and the RCC clock enable bit is "AESEN". Only the
STM32F730 SVD (v1.5) correctly names this peripheral "AES".

The real CRYP crypto processor (a completely different, much larger peripheral)
exists only on F74x and F76x devices.


## ST STM32H7 — ADC (needs re-verification)

> **Caveat:** These bugs were identified by cross-comparing SVD files during H7 ADC
> unification. The H723 SVD was chosen as the source because it appeared most
> accurate, but the individual bugs below have not yet been verified against RMs
> with specific page references. To be revisited.

References:
- RM0433 — STM32H742 / STM32H743 / STM32H750 / STM32H753
- RM0468 — STM32H723 / STM32H725 / STM32H730 / STM32H733 / STM32H735
- RM0455 — STM32H7A3 / STM32H7B3 / STM32H7B0

**STM32H743 (SVD v2.4):**

| Register | Field     | Bug                          | H723 SVD (v2.1) has          |
|----------|-----------|------------------------------|------------------------------|
| HTR1     | (name)    | Named "LHTR1"               | "HTR1"                       |
| various  | (resets)  | Wrong reset values           | Different reset values       |
| CFGR     | BOOST     | 1-bit width                  | 2-bit (BOOST[1:0])          |
| DR       | RDATA     | 16-bit width                 | 32-bit                       |

**STM32H7A3 (SVD v3.4):**

| Register | Field     | Bug                          | H723 SVD (v2.1) has          |
|----------|-----------|------------------------------|------------------------------|
| HTR1     | (name)    | Named "LHTR1"               | "HTR1"                       |
| CFGR     | RES       | Wrong width                  | 3-bit (RES[2:0])            |
| CFGR     | BOOST     | Wrong width                  | 2-bit (BOOST[1:0])          |


## ST STM32L0 — ADC (needs re-verification)

> **Caveat:** Identified during L0 ADC work but not yet verified against the RM
> with specific page references. To be revisited.

Reference:
- RM0376 — STM32L0x2 / STM32L0x3

### ADC_Common (CCR)

The VLCDEN bit (VLCD channel enable) is present in some L0 SVD files that
should not have it. Per the RM, only L0x3 devices have the VLCD pin connected
to an ADC input channel. The bit appears inverted across subfamilies in the
SVD files (present where it shouldn't be, or absent where it should be).
SVD versions: STM32L0x0 v1.3, STM32L0x1 v1.6, STM32L0x2 v1.7, STM32L0x3 v1.7.
