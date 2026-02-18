# Quick Start: STM32H7 Model Extraction

## TL;DR - In 3 Steps

### 1. Include Module in `CMakeLists.txt`
```cmake
include(cmake/stm32h7-extraction.cmake)
add_stm32h7_extraction_target(extract_stm32h7_models)
```

### 2. Build
```bash
mkdir build && cd build
cmake ..
cmake --build . --target extract_stm32h7_models
```

### 3. Models Are Ready
```
build/models/ST/
├── H7_common/          ← 58 universal blocks
├── H73x/blocks/        ← H73x-specific blocks
├── H74x_H75x/blocks/   ← H74x/H75x-specific blocks
└── H7A3_B/blocks/      ← H7A3/B-specific blocks
```

## Summary of What You Got

### 📊 Compatibility Analysis Results
- **58 blocks** (58%) are identical across all STM32H7 variants
- **42 blocks** (42%) have subfamily-specific variants
- **14 blocks** have structural differences that prevent sharing

### 🏗️ Three CMake Helper Functions

```cmake
# Get chip model path (automatically determines family)
get_stm32h7_chip_path(STM32H757_CM4 H74x_H75x my_path)

# Get block path (smart: routes to H7_common/ OR family-specific/)
get_stm32h7_block_path(GPIO H73x gpio_path)     # → H7_common/GPIO.yaml
get_stm32h7_block_path(ADC H73x adc_path)       # → H73x/blocks/ADC.yaml

# Get all variants in a family
get_stm32h7_family_chips(H74x_H75x all_chips)
```

### 📁 Model Organization

```
H7_common/              # GPIO, I2C, SPI, USART, SAI, EXTI, etc. (58 blocks)
├── ADC.yaml
├── GPIO.yaml
└── ...

H73x/                   # H723, H725, H730, H733, H735, H73x
├── blocks/ADC.yaml     # H73x-specific ADC
├── H723.yaml
└── ...

H74x_H75x/              # H742, H743, H745, H747, H750, H753, H755, H757 (+CM4/CM7)
├── blocks/ADC.yaml     # H74x/H75x-specific ADC (different from H73x)
├── H757_CM4.yaml
└── ...

H7A3_B/                 # H7A3, H7B0, H7B3
├── blocks/ADC.yaml     # H7A3/B-specific ADC
└── ...
```

## Blocks That Require Variants (14 Critical)

| Block | Reason |
|-------|--------|
| **ADC** | Different register structures per subfamily |
| **RCC** | Clock tree architecture differs |
| **Flash** | Flash control registers vary |
| **SYSCFG** | System config differs |
| **PWR** | Power domain layout differs |
| **DBGMCU** | Debug capabilities differ |
| DMA, BDMA, MDMA | Memory access architecture |
| QUADSPI, FMC | Memory interfaces |
| AdvCtrlTimer, GpTimer | Timer variants |
| RTC, LPTIM | Real-time logic |
| Plus 28 more... | See `ANALYSIS_STM32H7_COMPATIBILITY.md` |

## Files Delivered

| File | Purpose |
|------|---------|
| `cmake/stm32h7-extraction.cmake` | **Main module** - Include this in your CMakeLists.txt |
| `extractors/generate_stm32h7_models.py` | Python script that does the extraction |
| `cmake/stm32h7-extraction-example.cmake` | Usage examples |
| `ANALYSIS_STM32H7_COMPATIBILITY.md` | Detailed compatibility breakdown |
| `README_STM32H7_EXTRACTION.md` | Full documentation |
| `IMPLEMENTATION_SUMMARY.md` | Architecture & design rationale |
| **This file** | Quick start guide |

## Common Tasks

### Extract all models
```bash
cmake --build build --target extract_stm32h7_models
```

### Force re-extraction (discard cache)
```bash
rm -f build/models/ST/.extracted
cmake --build build --target extract_stm32h7_models
```

### Get all H74x/H75x variants
```cmake
get_stm32h7_family_chips(H74x_H75x chips)
# chips = H742;H743;H745_CM4;H745_CM7;...;H757_CM7
```

### Reference a chip model in C++
```cmake
get_stm32h7_chip_path(STM32H757_CM4 H74x_H75x chip_model_path)
# Use ${chip_model_path} in your generator scripts
```

### Check if block is common or family-specific
```cmake
# Common blocks are always in H7_common/:
get_stm32h7_block_path(GPIO H73x gpio_path)
# → ${CMAKE_BINARY_DIR}/models/ST/H7_common/GPIO.yaml

# Incompatible blocks route to family subdir:
get_stm32h7_block_path(ADC H73x adc_path)
# → ${CMAKE_BINARY_DIR}/models/ST/H73x/blocks/ADC.yaml
```

## Expected Output

After running extraction, you should see:

```
models/ST/
├── .extracted                          ← Marker (prevents re-extraction)
│
├── H7_common/                          ← Shared across all variants
│   ├── AXI.yaml
│   ├── BasicTimer.yaml
│   ├── DCMI.yaml
│   ├── EXTI.yaml
│   ├── GPIO.yaml
│   ├── I2C.yaml
│   ├── LPUART.yaml
│   ├── LTDC.yaml
│   ├── OPAMP.yaml
│   ├── OTG1_HS_DEVICE.yaml
│   ├── OTG1_HS_HOST.yaml
│   ├── OTG1_HS_PWRCLK.yaml
│   ├── OTG2_HS_DEVICE.yaml
│   ├── OTG2_HS_HOST.yaml
│   ├── OTG2_HS_PWRCLK.yaml
│   ├── SDMMC2.yaml
│   ├── SPI.yaml
│   ├── SWPMI.yaml
│   ├── USART.yaml
│   └── ... (38 more blocks)
│
├── H73x/
│   ├── blocks/                         ← H73x-specific variants
│   │   ├── ADC.yaml
│   │   ├── BDMA.yaml
│   │   ├── DMA.yaml
│   │   ├── DFSDM.yaml
│   │   ├── FMC.yaml
│   │   ├── Flash.yaml
│   │   ├── LPTIM.yaml
│   │   ├── MDMA.yaml
│   │   ├── PWR.yaml
│   │   ├── QUADSPI.yaml
│   │   ├── RCC.yaml
│   │   ├── RTC.yaml
│   │   ├── SPDIFRX.yaml
│   │   ├── SYSCFG.yaml
│   │   ├── AdvCtrlTimer.yaml
│   │   ├── GpTimer.yaml
│   │   ├── DBGMCU.yaml
│   │   └── ... (more)
│   ├── H723.yaml                       ← Chip models
│   ├── H725.yaml
│   ├── H730.yaml
│   ├── H733.yaml
│   ├── H735.yaml
│   └── H73x.yaml
│
├── H74x_H75x/
│   ├── blocks/                         ← Different from H73x!
│   │   ├── ADC.yaml                    ← H74x/H75x-specific
│   │   ├── RCC.yaml                    ← H74x/H75x-specific
│   │   └── ... (16 more)
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
└── H7A3_B/
    ├── blocks/                         ← Different again!
    │   ├── ADC.yaml                    ← H7A3/B-specific
    │   ├── RCC.yaml                    ← H7A3/B-specific
    │   └── ... (16 more)
    ├── H7A3.yaml
    ├── H7B0.yaml
    └── H7B3.yaml
```

## Troubleshooting

### "Module not found" error
```
include(cmake/stm32h7-extraction.cmake)
```
Make sure the path is correct relative to your build/source directories.

### "SVD zip not found"
Ensure `svd/stm32h7-svd.zip` exists. If missing, copy from source distribution.

### Models didn't generate
```bash
rm models/ST/.extracted  # Clear cache
cmake --build . --target extract_stm32h7_models  # Try again
```

### Python script errors
Ensure `tools/svd.py` and `tools/transform.py` exist from sodaCat.

## Next Steps

1. **Test extraction** - Run the target and verify models appear
2. **Update generators** - Point to new model paths
3. **Run test suite** - Ensure generated headers work
4. **Migrate other chips** - Generate H750, H7A3, etc.
5. **Document custom changes** - Any block modifications

## More Information

- **Full analysis**: See `ANALYSIS_STM32H7_COMPATIBILITY.md` (shows all 100+ blocks)
- **Architecture docs**: See `README_STM32H7_EXTRACTION.md` (detailed design)
- **Implementation details**: See `IMPLEMENTATION_SUMMARY.md` (how it works)
- **CMake examples**: See `cmake/stm32h7-extraction-example.cmake` (usage patterns)
