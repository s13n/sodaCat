# SVD Errata

Known bugs in the Espressif ESP32-P4 SVD file, verified against the Technical
Reference Manual (TRM).


## ESP32-P4

SVD source: [espressif/svd](https://github.com/espressif/svd) release 2024-05-09, version 2.

References:
- TRM v0.2 (chip revision v1.3, dated 2025-10-23)
- ESP-IDF `reg_base.h` for base address cross-checks

### Base address bugs

**RMT — wrong address:**

| Peripheral | SVD address  | TRM address  | ESP-IDF `reg_base.h` |
|------------|-------------|-------------|----------------------|
| RMT        | 0x500D4000  | 0x500A2000  | 0x500A2000           |

The TRM (Table 7.3-2) places RMT at 0x500A2000 (HP PERI0, between ISP and
Bit-scrambler). The SVD address 0x500D4000 falls in the HP PERI1 region which
the TRM marks as reserved at that offset.

**DS / HMAC / ECC — 3-way address rotation:**

| Address    | TRM says | SVD says | Status  |
|------------|----------|----------|---------|
| 0x50093000 | DS       | ECC      | Swapped |
| 0x50094000 | HMAC     | DS       | Swapped |
| 0x50095000 | ECC      | HMAC     | Swapped |

All three cryptographic peripherals have their base addresses cyclically
rotated: DS→ECC→HMAC→DS.

### Missing peripherals

These peripherals appear in TRM Table 7.3-2 but have no SVD definition:

| TRM address  | Peripheral                   | Notes                     |
|-------------|------------------------------|---------------------------|
| 0x50000000  | USB 2.0 OTG High-Speed       | Synopsys DWC2 OTG IP      |
| 0x50040000  | USB 2.0 OTG Full-Speed       | Synopsys DWC2 OTG IP      |
| 0x50098000  | GMAC (Ethernet MAC)          | 16 KB, significant omission |
| 0x5009C000  | USB 2.0 OTG High-Speed PHY   |                           |
| 0x500A5000  | HP Peripheral PMS            | Permission controller     |
| 0x500A5800  | LP2HP Peripheral PMS         | Permission controller     |
| 0x500A6000  | HP DMA PMS                   | Permission controller     |
| 0x50118000  | LP Mailbox                   |                           |
| 0x50123000  | LP SPI                       |                           |
| 0x5012E000  | LP Peripheral PMS            | Permission controller     |
| 0x5012E800  | HP2LP Peripheral PMS         | Permission controller     |
| 0x3FF0E000  | L2MEM Monitor                |                           |
| 0x3FF0F000  | SPM Monitor                  |                           |

The SVD only provides USB_WRAP (PHY wrapper at 0x50080000) and USB_DEVICE
(USB-Serial-JTAG at 0x500D2000) — neither of which is the actual USB OTG
controller.

### Timer Group (TIMG)

**Missing T1 timer (TIMG0, TIMG1):**

Each timer group has two general-purpose timers (T0, T1) per TRM Chapter 16.
The SVD defines only T0 registers (offsets 0x0000–0x0020). The entire T1
register set is missing:

| Offset | Register   | Description                    |
|--------|-----------|--------------------------------|
| 0x0024 | T1CONFIG  | Timer 1 configuration          |
| 0x0028 | T1LO      | Timer 1 current value, low 32  |
| 0x002C | T1HI      | Timer 1 current value, high 22 |
| 0x0030 | T1UPDATE  | Timer 1 update trigger         |
| 0x0034 | T1ALARMLO | Timer 1 alarm value, low 32    |
| 0x0038 | T1ALARMHI | Timer 1 alarm value, high 22   |
| 0x003C | T1LOADLO  | Timer 1 reload value, low 32   |
| 0x0040 | T1LOADHI  | Timer 1 reload value, high 22  |
| 0x0044 | T1LOAD    | Timer 1 reload trigger         |

TIMG1 is `derivedFrom` TIMG0, so it inherits the same incomplete register set.

### IO_MUX

**Missing GPIO54 register:**

The SVD defines IO_MUX_GPIO0 through IO_MUX_GPIO53 (dim=54). The TRM
(Chapter 8, HP IO MUX) documents 55 registers: IO_MUX_GPIO0 through
IO_MUX_GPIO54. The ESP32-P4 has 55 GPIO pins (GPIO0–GPIO54).

### GPIO

**Missing FUNC255_IN_SEL_CFG:**

The SVD defines FUNC1_IN_SEL_CFG through FUNC254_IN_SEL_CFG (dim=254,
starting at index 1). The TRM documents 255 entries: FUNC1 through FUNC255.
FUNC0_IN_SEL_CFG is absent from both SVD and TRM for the main GPIO (it exists
in LP_GPIO only).

### SDHOST

The SDHOST peripheral is based on the Synopsys DesignWare Mobile Storage IP.
The SVD is missing several documented fields and registers.

**Missing fields:**

| Register | Field             | Bit(s) | TRM says                              |
|----------|-------------------|--------|---------------------------------------|
| CTRL     | USE_INTERNAL_DMAC | [25]   | DMA mode select (0=external, 1=internal) |
| UHS      | VOLT_REG          | [1:0]  | Voltage switch per card (0=3.3V, 1=1.8V) |

**Missing register:**

| Offset | DWC name | Notes |
|--------|----------|-------|
| 0x0004 | PWREN    | Power Enable — absent from both SVD and TRM. Likely not implemented on this SoC (power managed externally). |

The SVD correctly includes VERID (0x006C) and HCON (0x0070) capability
registers that the TRM omits, and Espressif-custom registers RAW_INTS (0x0804)
and DLL_CONF (0x080C) that are also absent from the TRM.

### ADC

**Pattern table field width:**

| Register       | SVD width | Expected | Notes                          |
|----------------|-----------|----------|--------------------------------|
| SAR1_PATT_TAB1–4 | 24 bits | 32 bits  | 4 items × 8 bits = 32 bits    |
| SAR2_PATT_TAB1–4 | 24 bits | 32 bits  | Same pattern                   |

The SVD declares SAR_PATT_TABx fields as 24-bit [23:0], but each register
holds 4 pattern items of 8 bits each (channel + attenuation + resolution),
requiring the full 32-bit width.

**Undocumented ECO registers:**

| Offset | SVD register  | TRM | Notes                      |
|--------|--------------|-----|----------------------------|
| 0x006C | RND_ECO_LOW  | —   | Not in TRM                 |
| 0x0070 | RND_ECO_HIGH | —   | Not in TRM                 |
| 0x0074 | RND_ECO_CS   | —   | Not in TRM                 |

These Engineering Change Order registers are present in the SVD but not
documented in the TRM. This pattern (undocumented ECO registers) appears
across multiple ESP32-P4 peripherals.

### PCNT (Pulse Count Controller)

**Undocumented delta-counting registers:**

The SVD includes a delta/step-counting feature not documented in TRM
Chapter 46:

| Offset | SVD register     | SVD field             | TRM |
|--------|------------------|-----------------------|-----|
| 0x0060 | CTRL             | DALTA_CHANGE_EN_U0–U3 (bits [11:8]) | Not documented (bits [8:15] reserved) |
| 0x0064 | U3_CHANGE_CONF   | CNT_STEP_U3, CNT_STEP_LIM_U3 | Not documented |
| 0x0068 | U2_CHANGE_CONF   | CNT_STEP_U2, CNT_STEP_LIM_U2 | Not documented |
| 0x006C | U1_CHANGE_CONF   | CNT_STEP_U1, CNT_STEP_LIM_U1 | Not documented |
| 0x0070 | U0_CHANGE_CONF   | CNT_STEP_U0, CNT_STEP_LIM_U0 | Not documented |

Note: "DALTA" is a typo for "DELTA". The registers are listed in reverse
unit order (U3 at lowest offset). These registers may be real hardware features
that the TRM has not yet documented (TRM v0.2 is still a prerelease).

### Systemic issues

**Vestigial clock-select fields:**

Multiple peripherals contain clock-source selection fields (e.g.,
`TIMG_Tx_CLK_SEL`, `LEDC_TICK_SEL_TIMERx`, `I2C_SCLK_SEL`) that were
meaningful on earlier ESP32 variants where each peripheral selected its own
clock source. On the ESP32-P4, clock routing was centralized to the
HP_SYS_CLKRST peripheral, making these local fields vestigial. The SVD
retains them from the register template.

**ECO registers:**

Several peripherals include undocumented Engineering Change Order registers
(typically named `*_ECO_LOW`, `*_ECO_HIGH`, `*_ECO_CS` or similar) that are
present in the SVD but absent from the TRM. These are silicon patch/workaround
registers.

**Access type limitations:**

The TRM uses richer access semantics than SVD can express:
- R/WTC (write-1-to-clear) → SVD uses `read-write`
- R/W/SC (self-clearing) → SVD uses `read-write`
- WT (write-trigger) → SVD uses `read-write`
- R/SS (software-set) → SVD uses `read-write`

No `modifiedWriteValues` attributes are used in this SVD, so the distinction
between write-to-clear, self-clearing, and normal read-write is lost.

**Placeholder descriptions:**

Many field descriptions contain the placeholder text "need_des", indicating
the SVD was auto-generated with incomplete documentation.


## TRM errata

Bugs found in the TRM itself (Table 7.3-2, peripheral address mapping):

| Issue | Details |
|-------|---------|
| DS/ECC/HMAC ordering | Table has addresses scrambled (see SVD base address section above) |
| 2D-DMA base address | Listed as 0x50086000, overlaps JPEG Codec at the same address |
| PAU absent | PAU peripheral not listed in Table 7.3-2 at all |
