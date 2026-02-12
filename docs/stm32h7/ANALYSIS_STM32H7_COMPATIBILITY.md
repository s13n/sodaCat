# STM32H7 Family Functional Block Compatibility Analysis

## Executive Summary

Analysis of **21 STM32H7 family SVD files** (v2.8) reveals that **58 out of 100 peripheral blocks** (58%) are **fully compatible** across all chips, while **42 (42%)** have variants that require chip-specific customization.

## Findings

### Compatible Peripheral Blocks (Fully Reusable)

These **58 blocks** can use a single shared model across all HTM32H7 variants:

- **Core interfaces**: AXI, DCMI, ETH, OTG1_HS_*, OTG2_HS_*
- **Standard timers**: BasicTimer
- **Communication**: I2C, LPUART, USART, SPI, SWPMI
- **Audio**: SAI
- **Memory/Storage**: LTDC, SDMMC2
- **Exceptions**: EXTI
- **GPIO**: GPIO
- **Analog**: OPAMP
- **USB**: OTG devices and hosts

**Benefit**: These can be safely extracted once and shared via cross-references (e.g., symlinks or YAML includes).

---

## Incompatible Peripheral Blocks (Require Variants)

### Category A: Structural Changes Across Subfamilies

These blocks differ due to fundamental architectural differences between H7 subfamilies:

#### **Data Converters**
- **ADC** (3 variants): H73x vs H74x-H75x vs H7A3/H7B0/H7B3
- **ADC_Common** (3 variants): Same grouping as ADC
- **DAC** (2 variants): Most support standard DAC; H750 has different register layout

#### **Controller/Timer Blocks**
- **AdvCtrlTimer** (2 variants): H73x-H75x vs H7A3/H7B0/H7B3
- **GpTimer** (2 variants): H73x-H75x vs H7A3/H7B0/H7B3
- **LPTIM** (2 variants): H73x-H75x vs H7A3/H7B0/H7B3

#### **Direct Memory Access**
- **DMA** (2 variants): H73x/H7A3/H7B3 vs H74x-H75x/H7B0
- **BDMA** (3 variants): Different register structures
- **MDMA** (2 variants): H73x-H75x/H7B0/H7B3 vs H7A3

#### **Clock & Reset**
- **RCC** (4 variants): Significant differences across all subfamily groups
  - H73x (6 chips)
  - H74x-H75x (8 CM4/CM7 pairs)
  - H7A3/H7B0/H7B3 (3 chips)
  - H750 (standalone)

#### **System Configuration**
- **SYSCFG** (4 variants): Different register definitions per subfamily
- **DBGMCU** (5 variants): Most fragmented block

#### **Power Management**
- **PWR** (4 variants): Distinct per subfamily
- **VREFBUF** (2 variants): H73x-H75x vs H750/H7A3/H7B0/H7B3

#### **Memory**
- **Flash** (4 variants): Different flash controllers per subfamily
- **FMC** (2 variants): Alternate memory interface in newer variants

#### **Cryptography**
- **HASH** (2 variants): H73x vs H75x+
- **CRYP** (3 variants): Very fragmented across variants
- **RNG** (2 variants): H73x-H75x vs H750/H7A3/H7B0/H7B3

#### **Storage Interfaces**
- **QUADSPI** (2 variants): H74x-H75x vs H750 (different register widths)
- **OCTOSPI1/2** (2 variants): H73x vs H7A3/H7B0/H7B3 (different capability levels)

#### **Serial Protocols**
- **SPDIFRX** (2 variants): H73x vs H74x+
- **DFSDM** (2 variants): H73x & most H74x-H75x vs H743

#### **Real-Time & Watchdogs**
- **RTC** (2 variants): H73x-H75x vs H7A3/H7B0/H7B3
- **IWDG** (2 variants): Single vs dual-core aware
- **WWDG** (2 variants): Single vs dual-core aware

#### **Ethernet** (Optional in H750, H742/H743)
- **Ethernet_MAC** (2 variants): Standard vs extended versions
- **CAN_CCU** (3 variants): Very fragmented

#### **Hardware Semaphores**
- **HSEM** (4 variants): Different capabilities across subfamilies

#### **Misc. Security/Management**
- **CRC, CRS, RAMECC*, JPEG, OTG1_HS_GLOBAL, OTFDEC*, TT_FDCAN**

---

## Chip Groupings for Variant Management

### Group H73x (6 basic chips)
- STM32H723, H725, H730, H733, H735, H73x

### Group H74x-H75x (12 chips: 8 dual-core + single core variants)
- H742, H743, H745 (CM4/CM7), H747 (CM4/CM7), H750, H753, H755 (CM4/CM7), H757 (CM4/CM7)

### Group H7A3/H7B0/H7B3 (3 advanced chips)
- H7A3, H7B0, H7B3

---

## Recommendations

### Approach: Tiered Model Organization

```
models/ST/
├── H7_common/              # 58 truly universal blocks
│   ├── AXI.yaml
│   ├── BasicTimer.yaml
│   ├── GPIO.yaml
│   ├── I2C.yaml
│   ├── ... (all compatible blocks)
│   └── Makefile (symlinks to actual files)
│
├── H73x/                   # H73x group (6 variants)
│   ├── ADC.yaml            # H73x-specific
│   ├── RCC.yaml            # H73x-specific
│   ├── H723.yaml
│   ├── H725.yaml
│   ├── ... (other 4 chips)
│
├── H74x_H75x/              # H74x/H75x group (10 chips) 
│   ├── ADC.yaml            # H74x-H75x specific
│   ├── RCC.yaml            # H74x-H75x specific
│   ├── H742.yaml
│   ├── H743.yaml
│   ├── H745_CM4.yaml
│   ├── H745_CM7.yaml
│   ├── ... (and so on)
│
└── H7A3_B/                 # H7A3/H7B0/H7B3 (3 variants)
    ├── ADC.yaml            # High-end specific
    ├── RCC.yaml            # High-end specific
    ├── H7A3.yaml
    ├── H7B0.yaml
    └── H7B3.yaml
```

### Key Parameters for Compatible Blocks

Many "compatible" blocks are truly identical across variants. For borderline cases, parametrization can extend reusability:

- **Register address offsets**: Include as optional parameters in model
- **Interrupt counts**: Use array dimensions
- **Optional features**: Use conditionals in generation

---

## Blocks Prohibiting Shared Models

The following **14 blocks** have **fundamental structural differences** that make a single shared model impractical:

1. **ADC** - Register structure differs
2. **ADC_Common** - Related to ADC variants
3. **BDMA** - Channel architecture differs
4. **DMA** - Stream/request multiplexing differs
5. **Flash** - Control register layout differs per family
6. **MDMA** - Memory DMA differs between groups
7. **RCC** - Clock tree structure differs significantly
8. **SYSCFG** - System configuration registers differ
9. **PWR** - Power domain registers differ
10. **DBGMCU** - Debug capabilities differ
11. **DFSDM** - Filter configuration differs
12. **QUADSPI** - Register widths and structure differ
13. **FMC** - Memory controller interface differs
14. **H750** - Has unique CRYP/HASH/SDMMC/Ethernet configs

---

## Data Summary

| Metric | Count |
|--------|-------|
| Total SVD files analyzed | 21 |
| Total unique peripheral blocks | 100+ |
| Compatible across all/most variants | 58 (58%) |
| Incompatible (variants exist) | 42 (42%) |
| Truly incompatible (structural) | 14 (14%) |
| Chip variants to support | 18 (21 if counting CM4/CM7 as separate) |

---

## Next Steps

1. **Extract** all 21 SVD files using the generators
2. **Categorize** blocks into common / group-specific / incompatible
3. **Create** symbolic links / YAML references for truly common blocks
4. **Parametrize** borderline blocks where feasible
5. **Version** incompatible blocks per chip group
6. **Implement** CMake target to automate extraction and linking
