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

### EXTI

**STM32F745, STM32F767 (SVD v1.6):**

| Register  | Field     | Bug                          | All three RMs say            |
|-----------|-----------|------------------------------|------------------------------|
| IMR       | MR0-MR22  | Named MRx, stops at line 22  | Named IMx, 24 lines (0-23)  |
| EMR       | MR0-MR22  | Named MRx, stops at line 22  | Named EMx, 24 lines (0-23)  |
| RTSR      | TR0-TR22  | Stops at line 22             | 24 lines (TR0-TR23)         |
| FTSR      | TR0-TR22  | Stops at line 22             | 24 lines (TR0-TR23)         |
| SWIER     | SWIER0-22 | Stops at line 22             | 24 lines (SWIER0-SWIER23)   |
| PR        | PR0-PR22  | Stops at line 22             | 24 lines (PR0-PR23)         |

Note: All EXTI registers are missing line 23. All three RMs document 24 EXTI lines
(0-23). The F745/F767 SVD also uses the older MRx naming for IMR/EMR fields instead
of the RM-standard IMx/EMx naming.

**STM32F722 (SVD v1.4):**

| Register | Field     | Bug                          | RM0431 says                  |
|----------|-----------|------------------------------|------------------------------|
| IMR      | MI9       | Typo (MI9 instead of IM9)    | Field is IM9                 |

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

### FMC

**STM32F745, STM32F767 (SVD v1.6):**

| Register | Field     | Bug                          | All three RMs say            |
|----------|-----------|------------------------------|------------------------------|
| BCR1     | CPSIZE    | Missing                      | Bits 18:16, CRAM page size   |
| BCR1     | WFDIS     | Missing                      | Bit 21, Write FIFO Disable   |
| BCR2-4   | WRAPMOD   | Present at bit 10            | Bit 10 reserved (legacy field removed in F7) |
| BCR2-4   | CPSIZE    | Missing                      | Bits 18:16, CRAM page size   |
| BWTR1-4  | BUSTURN   | Missing                      | Bits 19:16, Bus turnaround phase duration |
| BWTR1-4  | CLKDIV    | Present at bits 23:20        | Bits 27:20 reserved (CLKDIV is in BTRx only) |
| BWTR1-4  | DATLAT    | Present at bits 27:24        | Bits 27:20 reserved (DATLAT is in BTRx only) |
| SDCR2    | RPIPE     | Present at bits 14:13        | Bits 14:13 reserved (RPIPE is in SDCR1 only) |

Note: The F745/F767 SVD BWTRx registers have CLKDIV and DATLAT fields copied from
BTRx (read timing), but these fields only exist in the read timing registers per
all three RMs. The write timing registers should have BUSTURN instead.

**STM32F722 (SVD v1.4):**

| Register | Field     | Bug                          | RM0431 says                  |
|----------|-----------|------------------------------|------------------------------|
| SDSR     | RE        | Missing                      | Bit 0, Refresh error flag (read-only) |

### GPIO

**STM32F745, STM32F767 (SVD v1.6):**

| Register | Field     | Bug                          | All three RMs say            |
|----------|-----------|------------------------------|------------------------------|
| BRR      | (entire)  | Register present at offset 0x28 | No BRR register in GPIO (register map ends at AFRH, offset 0x24) |

### SDMMC

**STM32F745, STM32F767 (SVD v1.6):**

| Register | Field     | Bug                          | All three RMs say            |
|----------|-----------|------------------------------|------------------------------|
| CMD      | ENCMDcompl | Present at bit 12           | Bit 12 reserved (CE-ATA removed in SDMMC IP) |
| CMD      | nIEN       | Present at bit 13           | Bit 13 reserved              |
| CMD      | CE_ATACMD  | Present at bit 14           | Bit 14 reserved              |
| STA      | STBITERR   | Present at bit 9            | Bit 9 reserved               |
| STA      | CEATAEND   | Present at bit 23           | Bit 23 reserved              |
| ICR      | STBITERRC  | Present at bit 9            | Bit 9 reserved               |
| ICR      | CEATAENDC  | Present at bit 23           | Bit 23 reserved              |
| MASK     | STBITERRIE | Present at bit 9            | Bit 9 reserved               |
| MASK     | CEATAENDIE | Present at bit 23           | Bit 23 reserved              |

Note: These CE-ATA fields are vestiges of the older SDIO IP (STM32F1/F2/F4). The F7 SDMMC
peripheral dropped CE-ATA support entirely; all three RMs mark these bits as reserved.

### SYSCFG

**STM32F745, STM32F767 (SVD v1.6):**

| Register | Field      | Bug                          | RM says                      |
|----------|------------|------------------------------|------------------------------|
| MEMRMP   | MEM_MODE   | 3-bit field at bits 2:0      | RM0385/RM0410: bit 0 is MEM_BOOT (1-bit, read-only) |
| MEMRMP   | FB_MODE    | Present at bit 8             | RM0385: bit 8 reserved; RM0410: bit 8 is SWP_FB     |
| MEMRMP   | (name)     | Named MEMRM                  | All three RMs: MEMRMP        |
| PMC      | I2C1-4_FMP | Missing (bits 0-3)           | RM0410: present (F76x/F77x); RM0385: reserved (F74x/F75x) |
| PMC      | PB6-9_FMP  | Missing (bits 4-7)           | RM0410: present (F76x/F77x); RM0385: reserved (F74x/F75x) |

Note: The F745/F767 SVD MEMRMP register has the old F4-style MEM_MODE field (3-bit memory
mapping selection) instead of the F7's MEM_BOOT (1-bit boot address indicator). The FB_MODE
field at bit 8 does not exist on F74x/F75x (RM0385 marks bit 8 reserved); on F76x/F77x the
field exists but is named SWP_FB (flash bank swap). The PMC register is missing all I2C Fast
Mode Plus enable bits that RM0410 documents for F76x/F77x.

**STM32F722 (SVD v1.4):**

| Register | Field      | Bug                          | RM0431 says                  |
|----------|------------|------------------------------|------------------------------|
| PMC      | I2C4_FMP   | Missing (bit 3)              | RM0410: present on F76x/F77x (not on F72x/F73x per RM0431) |

Note: The F722 SVD correctly omits I2C4_FMP for the F72x/F73x subfamily (RM0431 shows bit 3
as reserved). However, the unified superset model includes it from RM0410.

### USB OTG

**STM32F745, STM32F767 (SVD v1.6):**

| Block          | Issue                                    | F722 SVD has                        |
|----------------|------------------------------------------|-------------------------------------|
| OTG_HS_DEVICE  | Missing DIEPDMA0 (only has DIEPDMA1-7)   | DIEPDMA0-15 (all 16 IN endpoints)   |
| OTG_HS_DEVICE  | Missing all DOEPDMA registers            | DOEPDMA0-15 (all 16 OUT endpoints)  |
| OTG_HS_DEVICE  | addressBlock size 1024                   | 1280 (covers extended DMA regs)     |
| OTG_FS_HOST    | Missing OTG_FS_WKUP interrupt            | Present                             |
| OTG_HS_HOST    | Missing OTG_FS interrupt                 | Present                             |

Note: The F745/F767 SVD OTG_HS_DEVICE peripheral is incomplete — it only lists 7 of the 16
IN-endpoint DMA address registers (DIEPDMA1-7, missing DIEPDMA0) and omits all 16 OUT-endpoint
DMA address registers (DOEPDMA0-15). The F722 SVD has the complete set. The OTG FS/HS HOST
blocks are also missing their interrupt entries in the F745/F767 SVDs. All F7 subfamilies use
the same DWC2 OTG IP, so the F722 description is the correct superset.

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


## ST STM32F4

References:
- RM0368 Rev.6 — STM32F401
- RM0383 Rev.4 — STM32F411
- RM0090 Rev.21 — STM32F405/407/415/417/427/429/437/439
- RM0402 Rev.7 — STM32F412
- RM0430 Rev.9 — STM32F413/F423
- RM0390 Rev.9 — STM32F446
- RM0386 Rev.6 — STM32F469/F479

### OTG_FS_DEVICE

The DWC2 USB OTG IP on F412, F413, F446, and F469 includes Link Power Management
(LPM) support with two additional fields not present on older parts (F401, F411,
F4x5/F42x/F43x). Multiple SVDs are missing one or both of these fields.

**ERRATIM** (bit 15 of OTG_FS_DCFG, erratic error interrupt mask):

| SVD file   | Has field? | RM says    |
|------------|------------|------------|
| STM32F412  | Missing    | Present (RM0402) |
| STM32F413  | Missing    | Present (RM0430) |
| STM32F446  | Present    | Present (RM0390) |
| STM32F469  | Missing    | Present (RM0386) |

**DEVLNSTS** (bits 23:22 of OTG_FS_DSTS, device line status):

| SVD file   | Has field? | RM says    |
|------------|------------|------------|
| STM32F412  | Missing    | Present (RM0402) |
| STM32F413  | Present    | Present (RM0430) |
| STM32F446  | Missing    | Present (RM0390) |
| STM32F469  | Missing    | Present (RM0386) |

**STM32F413 (SVD):** OTG_FS_DEVICE addressBlock.size = 885 (should be 1024).

SVD versions: STM32F401 v2.2, STM32F411 v2.3, STM32F412 v1.4, STM32F413 v1.1,
STM32F429 v1.6, STM32F446 v1.5, STM32F469 v1.4.

### ADC_Common

**addressBlock.size bugs:**

| SVD file   | Reports | Correct | Notes |
|------------|---------|---------|-------|
| STM32F405  | 13      | 12      | Multi-ADC: CSR@0 + CCR@4 + CDR@8 = 12 bytes |
| STM32F413  | 9       | 8       | Single-ADC: CSR@0 + CCR@4 = 8 bytes (no CDR) |
| STM32F469  | 1024    | 12      | Multi-ADC |

**STM32F413 (SVD v1.1):** ADC_Common has a spurious FPU interrupt mapped to it.
The FPU interrupt is a separate Cortex-M4 feature and has nothing to do with ADC.
No F4 ADC_Common peripheral has its own interrupt — ADC interrupts are routed
through the individual ADC blocks.

### I2C

The I2C FLTR register (digital/analog noise filter, offset 0x24) is missing from
several SVD files despite being documented in their reference manuals.

| SVD file   | Has FLTR? | RM says |
|------------|-----------|---------|
| STM32F401  | Missing   | Present (RM0368) |
| STM32F410  | Missing   | Present (RM0401) |
| STM32F411  | Missing   | Present (RM0383) |
| STM32F412  | Missing   | Present (RM0402) |

Per RM0090, the FLTR register is available on STM32F42xxx/F43xxx only — not on
STM32F405/F407/F415/F417. All other subfamilies (F401, F410, F411, F412, F413,
F446, F469) have FLTR per their respective RMs.

**STM32F413 (SVD v1.1):** I2C addressBlock.size = 41 (should be 40: registers
span CR1@0x00 through FLTR@0x24, i.e. 0x24 + 4 = 40 bytes).

### RTC

**TSTR register (offset 0x30) — wrong fields in F429/F446/F469 SVDs:**
These SVDs populate RTC_TSTR with tamper-related fields (TAMP1E, TAMP1TRG,
TAMPIE, TAMP1INSEL, TSINSEL, ALARMOUTTYPE) instead of the correct BCD timestamp
time fields (SU, ST, MNU, MNT, HU, HT, PM). The tamper fields are a subset of
TAFCR (offset 0x40). All RMs (RM0090, RM0390, RM0386) confirm TSTR contains
BCD time fields.

**CR register — missing BYPSHAD and COSEL in F429/F446/F469 SVDs:**
RTC_CR bit 5 (BYPSHAD, bypass shadow registers) and bit 19 (COSEL, calibration
output selection) are documented in all F4 reference manuals but missing from
the STM32F429, STM32F446, and STM32F469 SVDs. The F401/F410/F411/F412/F413
SVDs have them correctly.

**addressBlock.size bugs:**

| SVD file   | Reports | Correct | Notes |
|------------|---------|---------|-------|
| STM32F401  | 1024    | 160     | BKP19R@0x9C + 4 = 160 bytes |
| STM32F410  | 1024    | 160     | |
| STM32F411  | 1024    | 160     | |
| STM32F412  | 1024    | 160     | |
| STM32F413  | 161     | 160     | Off by one |
| STM32F429  | 1024    | 160     | |
| STM32F446  | 1024    | 160     | |
| STM32F469  | 1024    | 160     | |

### SAI

**STM32F469 (SVD v1.4):** SAI has a spurious GCR (Global Configuration Register)
at offset 0x00 with a SYNCOUT field. RM0386 Rev 6 explicitly removed SAI_GCR
(noted in revision history for Rev 4). The F469 has only one SAI instance, so
inter-SAI synchronization is not applicable. Only the F446 (RM0390) genuinely
has SAI_GCR with SYNCIN[1:0] and SYNCOUT[1:0].

**MCJDIV field name typo:** The SAI_xCR1.MCKDIV field (Master ClocK DIVider) is
misspelled as "MCJDIV" in STM32F429, STM32F413, and STM32F446 SVDs. STM32F469
has the correct name. All RMs consistently use MCKDIV.

**addressBlock.size:** All F4 SAI SVDs report 1024; correct is 68
(BDR@0x40 + 4 = 68 bytes).

### FMPI2C

**STM32F413 (SVD v1.1):** Poor field names throughout (ADDRE instead of ADDRIE,
TCDMAEN instead of TXDMAEN, SADD1_7 instead of SADD7_1, etc.) and descriptions
that just repeat the field name. STM32F446 SVD has proper names and descriptions.

**STM32F446 (SVD v1.5):** TXDR register marked `access: read-only` — should be
write-only (it's a transmit data register). ISR register marked read-only at
register level, but TXE and TXIS bits are actually read-write per RM0390.

**addressBlock.size:** STM32F446 reports 1024, STM32F413 reports 45; correct is 44
(TXDR@0x28 + 4 = 44 bytes).

### DMA2D

**STM32F427 (SVD v1.3):** DMA2D_FGPFCCR has spurious CSS (bits 18:2), AI (bit 20),
and RBS (bit 21) fields. DMA2D_BGPFCCR and DMA2D_OPFCCR also have spurious AI and
RBS fields. These fields do not exist on the F4 DMA2D IP — they were added in later
revisions (H7). Both RM0090 and RM0386 confirm bits 18–23 are reserved in FGPFCCR
and BGPFCCR, and bits 3–31 are reserved in OPFCCR.

**STM32F427 (SVD v1.3):** Missing FGCLUT (offset 0x400, 256×32-bit entries) and
BGCLUT (offset 0x800, 256×32-bit entries) color lookup table registers. Both are
documented in RM0090 Section 11.5.24–25.

**STM32F427 (SVD v1.3):** DMA2D_AMTCR description says "AXI master timer" — should
be "AHB master timer" per RM0090 Section 11.3.9.

**STM32F469 (SVD v1.4):** APLHA field name typo (should be ALPHA) in DMA2D_OCOLR,
DMA2D_FGCLUT, and DMA2D_BGCLUT registers.

### OTG_FS_GLOBAL

The OTG_FS GCCFG register has three distinct layouts across the F4 family,
corresponding to different generations of the DWC2 USB OTG IP:

1. **Old VBUS** (F401, F411, F4x5/F42x/F43x): PWRDWN, NOVBUSSENS, VBUSASEN, VBUSBSEN, SOFOUTEN
2. **BCD** (F412, F413): PWRDWN + VBDEN + battery charging detection fields (DCDET, PDET, SDET, PS2DET, BCDEN, DCDEN, PDEN, SDEN)
3. **Minimal** (F446, F469): PWRDWN + VBDEN only (BCD subset without detection hardware)

**F446/F469 SVDs report wrong GCCFG layout:**

| SVD file   | GCCFG fields reported    | RM says                    |
|------------|--------------------------|----------------------------|
| STM32F446  | Old VBUS (PWRDWN, VBUSASEN, VBUSBSEN, SOFOUTEN) | Minimal: PWRDWN + VBDEN only (RM0390) |
| STM32F469  | Old VBUS (PWRDWN, VBUSASEN, VBUSBSEN, SOFOUTEN) | Minimal: PWRDWN + VBDEN only (RM0386) |

These SVDs have the old-VBUS GCCFG fields copied from the F4x5/F42x generation,
despite their hardware using the newer DWC2 IP with VBUS detection enable (VBDEN)
instead of separate VBUSASEN/VBUSBSEN controls.

**Missing NOVBUSSENS (bit 21) in old-VBUS SVDs:**

| SVD file   | Has NOVBUSSENS? | RM says |
|------------|-----------------|---------|
| STM32F401  | Missing         | Present (RM0368) |
| STM32F411  | Missing         | Present (RM0383) |
| STM32F429  | Missing         | Present (RM0090) |

All three RMs document NOVBUSSENS at bit 21 of GCCFG (No VBUS sensing enable).

**Missing GLPMCFG register (offset 0x054, Global LPM Configuration):**

| SVD file   | Has GLPMCFG? | RM says |
|------------|--------------|---------|
| STM32F412  | Missing      | Present (RM0402) |
| STM32F413  | Missing      | Present (RM0430) |
| STM32F446  | Missing      | Present (RM0390) |
| STM32F469  | Missing      | Present (RM0386) |

The LPM configuration register exists on all F4 chips with BCD or minimal GCCFG
layouts. Older chips (F401, F411, F4x5/F42x) do not have this register.

**Missing DIEPTXF registers in F412 SVD:**

| SVD file   | DIEPTXF count | RM says |
|------------|---------------|---------|
| STM32F412  | 3 (DIEPTXF1-3) | 5 (DIEPTXF1-5, RM0402) |

The F412 SVD only defines 3 device IN endpoint FIFO registers despite RM0402
documenting 5. The F413 and F469 SVDs correctly have all 5.

**addressBlock.size bugs:**

| SVD file   | Reports | Correct | Notes |
|------------|---------|---------|-------|
| STM32F401  | 1024    | 272     | DIEPTXF3@0x10C + 4 = 0x110 = 272 |
| STM32F411  | 1024    | 272     | Same as F401 |
| STM32F429  | 1024    | 272     | Same as F401 |
| STM32F412  | 273     | 280     | DIEPTXF5@0x114 + 4 = 0x118 = 280 |
| STM32F413  | 273     | 280     | Same as F412 |
| STM32F446  | 1024    | 280     | Same as F412 (5 DIEPTXF per RM0390) |
| STM32F469  | 1024    | 280     | Same as F412 (5 DIEPTXF per RM0386) |
