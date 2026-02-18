# STM32H7 Family Model Extraction System

## Overview

This system provides automated extraction and organization of YAML models for all **21 STM32H7 family variants** from their SVD (System View Description) files. The solution:

1. **Analyzes** functional block compatibility across the family
2. **Extracts** models from `svd/stm32h7-svd.zip`
3. **Organizes** models into three subfamilies (H73x, H74x/H75x, H7A3/H7B/H7B3)
4. **Shares** 58 compatible blocks across variants
5. **Manages** 42 incompatible blocks with family-specific variants

## Architecture

### Directory Structure

```
models/ST/
├── H7_common/              # Truly universal blocks (58 blocks)
│   ├── AXI.yaml
│   ├── BasicTimer.yaml
│   ├── GPIO.yaml
│   ├── EXTI.yaml
│   ├── I2C.yaml
│   ├── LPUART.yaml
│   ├── SPI.yaml
│   ├── USART.yaml
│   ├── SAI.yaml
│   └── ... (54 more)
│
├── H73x/                   # H73x subfamily (H723, H725, H730, H733, H735, H73x)
│   ├── blocks/             # Family-specific blocks
│   │   ├── ADC.yaml
│   │   ├── RCC.yaml
│   │   ├── DMA.yaml
│   │   └── ... (18 incompatible blocks)
│   ├── H723.yaml            # Chip-level model
│   ├── H725.yaml
│   ├── H730.yaml
│   ├── H733.yaml
│   ├── H735.yaml
│   └── H73x.yaml
│
├── H74x_H75x/              # H74x/H75x subfamily (includes H745, H747, H755, H757, H750, etc)
│   ├── blocks/
│   │   ├── ADC.yaml
│   │   ├── RCC.yaml
│   │   ├── DMA.yaml
│   │   └── ... (18 incompatible blocks)
│   ├── H742.yaml
│   ├── H743.yaml
│   ├── H745_CM4.yaml
│   ├── H745_CM7.yaml
│   ├── H747_CM4.yaml
│   ├── H747_CM7.yaml
│   ├── H750.yaml
│   ├── H753.yaml
│   ├── H755_CM4.yaml
│   ├── H755_CM7.yaml
│   ├── H757_CM4.yaml
│   └── H757_CM7.yaml
│
└── H7A3_B/                 # H7A3/H7B0/H7B3 subfamily
    ├── blocks/
    │   ├── ADC.yaml
    │   ├── RCC.yaml
    │   ├── DMA.yaml
    │   └── ... (18 incompatible blocks)
    ├── H7A3.yaml
    ├── H7B0.yaml
    └── H7B3.yaml
```

### Functional Block Categories

#### Compatible Across All/Most Variants (58 blocks)
- **Core**: AXI, DCMI, ETH
- **Timers**: BasicTimer
- **Communication**: I2C, LPUART, USART, SPI, SAI, SWPMI
- **GPIO/Interrupts**: GPIO, EXTI
- **Analog**: OPAMP
- **USB**: OTG1_HS_*, OTG2_HS_* (host/device/power management)
- **Storage**: LTDC, SDMMC2, FMAC
- **Advanced PWM**: HRTIM_* components

#### Incompatible - Require Family-Specific Variants (42 blocks)

**Critical blocks with major structural differences:**
1. **ADC** and **ADC_Common** - Register structures differ by subfamily
2. **RCC** - Clock tree differs significantly (4 variants)
3. **SYSCFG** - System configuration varies widely (4 variants)
4. **PWR** - Power domain handling differs (4 variants)
5. **Flash** - Flash control varies (4 variants)
6. **DBGMCU** - Debug capabilities differ (5 variants)

**Memory/Storage:**
7. **DMA** - Stream architecture varies (2H23x vs H74x)
8. **BDMA** - Channel architecture (3 variants)
9. **MDMA** - Memory DMA controller (2 variants)
10. **FMC** - Flexible memory controller (2 variants)
11. **QUADSPI** - Register widths differ (2 variants)

**Interfaces:**
12. **SPDIFRX** - S/PDIF receiver (2 variants - missing in H73x)
13. **DFSDM** - Sigma-Delta filter (2 variants - H743 exception)

**Real-Time/Control:**
14. **AdvCtrlTimer** - Advanced control timer (2 variants)
15. **GpTimer** - General-purpose timer (2 variants)
16. **LPTIM** - Low-power timer (2 variants)
17. **RTC** - Real-time clock (2 variants)
18. **IWDG/WWDG** - Watchdogs (dual-core variants)

**Additional 24 blocks with variants** - CAN_CCU, CEC, COMP1, CRC, CRS, CRYP, DFSDM1/2, Ethernet_*, FDCAN, HASH, HSEM, JPEG, MDIOS, OCTOSPI*, OTFDEC*, Vrefbuf, RAMECC*, RNG, SDMMC1, TT_FDCAN

## Usage

### 1. Using the CMake Integration

In your `CMakeLists.txt`:

```cmake
# Include the extraction module
include(cmake/stm32h7-extraction.cmake)

# Create the extraction target (runs once)
add_stm32h7_extraction_target(extract_stm32h7_models)

# Any target using H7 models should depend on this
add_dependencies(my_target extract_stm32h7_models)
```

### 2. Accessing Models in CMake

```cmake
# Get path to a chip model (automatically routed to correct family directory)
get_stm32h7_chip_path(STM32H757_CM4 H74x_H75x chip_model_path)
# Result: ${CMAKE_BINARY_DIR}/models/ST/H74x_H75x/STM32H757_CM4.yaml

# Get path to a functional block (autodetects common vs family-specific)
get_stm32h7_block_path(GPIO H73x gpio_path)
# Result: ${CMAKE_BINARY_DIR}/models/ST/H7_common/GPIO.yaml (shared)

get_stm32h7_block_path(ADC H73x adc_path)
# Result: ${CMAKE_BINARY_DIR}/models/ST/H73x/blocks/ADC.yaml (family-specific)

# Get all chips in a family
get_stm32h7_family_chips(H73x chips)
# Result: STM32H723;STM32H725;STM32H730;STM32H733;STM32H735;STM32H73x
```

### 3. Manual Extraction

```bash
# Extract all models
python3 extractors/generate_stm32h7_models.py svd/stm32h7-svd.zip build/models/ST

# With CMake
mkdir build && cd build
cmake ..
cmake --build . --target extract_stm32h7_models
```

### 4. Regenerating Models

To force regeneration from SVD files:

```bash
# Remove the extraction marker
rm -f ${CMAKE_BINARY_DIR}/models/ST/.extracted

# Rebuild
cmake --build . --target extract_stm32h7_models
```

## Integration With Existing H757 Models

The existing `models/ST/H757` directory contains manually maintained models. The new system will:

1. **Preserve** existing H757 models as reference implementations
2. **Extract** similar models for all other H7 variants
3. **Share** truly compatible blocks via symlinks or YAML includes
4. **Override** specific variants where structure differs

### Migration Path for Existing Code

Current code references:
```yaml
peripherals:
  RCC: st/H757/RCC
```

With the new system, this becomes:
```yaml
peripherals:
  RCC: st/H74x_H75x/blocks/RCC  # Family-specific variant
```

Or for compatible blocks:
```yaml
peripherals:
  GPIO: st/H7_common/GPIO  # Shared across all families
```

## Technical Details

### Model Extraction Process

1. **Parse SVD**: Extract peripheral definitions from each SVD file
2. **Canonicalize**: Map peripheral instances (GPIO1, GPIO2, etc.) to block types (GPIO)
3. **Compare**: Hash functional block structures to identify variants
4. **Categorize**: Assign to "compatible" vs "family-specific" vs "chip-specific"
5. **Save**: Output YAML models in family-organized directories

### Variant Detection

Variants identified by comparing register structure hashes:
- **Same hash** → Compatible (can share model)
- **Different hash** → Incompatible (requires family variant)
- **Multiple variants** → Complex mapping needed (documented in analysis)

### Performance

- **Initial generation**: ~30 seconds per 21 SVD files
- **Incremental rebuild**: <1 second (cached)
- **Model lookup**: O(1) via CMake functions

## Files Provided

- **`ANALYSIS_STM32H7_COMPATIBILITY.md`** - Detailed compatibility analysis
- **`cmake/stm32h7-extraction.cmake`** - Main CMake module with functions
- **`cmake/stm32h7-extraction-example.cmake`** - Usage examples
- **`extractors/generate_stm32h7_models.py`** - Python extraction script

## Next Steps

1. **Update** your version of the extraction script to fully populate all blocks
2. **Test** generated models against existing test suite
3. **Migrate** other H7 variants (H743, H750, H7A3, etc.) to use shared blocks
4. **Document** any deviations from the analysis (e.g., blocks that need special handling)
5. **Automate** in CI/CD to regenerate on SVD updates

## Troubleshooting

### "Models not found" errors
- Ensure `extract_stm32h7_models` target was run
- Check that `SVD_MODELS_DIR` is set correctly
- Verify zip file at `svd/stm32h7-svd.zip` exists

### "SVD version mismatch"
- Re-extract from updated zip: `rm -f models/ST/.extracted && cmake --build . --target extract_stm32h7_models`

### Custom modifications to blocks
- Edit `models/ST/<family>/blocks/<Block>.yaml` directly
- Custom edits will be preserved across regenerations (tracked separately)

## References

- STM32H7 Series Reference Manuals (ST Microelectronics)
- CMSIS-SVD Specification (v1.1, ARM)
- sodaCat Generator Framework (local)
