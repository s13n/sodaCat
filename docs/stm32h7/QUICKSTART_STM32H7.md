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
└── H7/                     ← Family folder
    ├── GPIO.yaml             (58 common blocks)
    ├── ...
    ├── H73x/        ← H73x-specific blocks
    ├── H74x_H75x/   ← H74x/H75x-specific blocks
    └── H7A3_B/      ← H7A3/B-specific blocks
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

# Get block path (smart: routes to H7/ OR family-specific/)
get_stm32h7_block_path(GPIO H73x gpio_path)     # → H7/GPIO.yaml
get_stm32h7_block_path(ADC H73x adc_path)       # → H73x/ADC.yaml

# Get all variants in a family
get_stm32h7_family_chips(H74x_H75x all_chips)
```

### 📁 Model Organization

```
H7/                         # Family folder
├── GPIO.yaml                 (58 common blocks: GPIO, I2C, SPI, USART, SAI, EXTI, etc.)
├── ADC.yaml
├── ...
│
├── H73x/                   # H723, H725, H730, H733, H735, H73x
│   ├── ADC.yaml     # H73x-specific ADC
│   ├── H723.yaml
│   └── ...
│
├── H74x_H75x/              # H742, H743, H745, H747, H750, H753, H755, H757 (+CM4/CM7)
│   ├── ADC.yaml     # H74x/H75x-specific ADC (different from H73x)
│   ├── H757_CM4.yaml
│   └── ...
│
└── H7A3_B/                 # H7A3, H7B0, H7B3
    ├── ADC.yaml     # H7A3/B-specific ADC
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
# Common blocks are always in H7/:
get_stm32h7_block_path(GPIO H73x gpio_path)
# → ${CMAKE_BINARY_DIR}/models/ST/H7/GPIO.yaml

# Incompatible blocks route to family subdir:
get_stm32h7_block_path(ADC H73x adc_path)
# → ${CMAKE_BINARY_DIR}/models/ST/H7/H73x/ADC.yaml
```

## Expected Output

After running extraction, you should see:

```
models/ST/
└── H7/                                 ← H7 family folder
    ├── AXI.yaml                          (58 common blocks)
    ├── BasicTimer.yaml
    ├── GPIO.yaml
    ├── I2C.yaml
    ├── SPI.yaml
    ├── USART.yaml
    ├── ... (52 more)
    │
    ├── H73x/
    │   ├── ADC.yaml
    │   ├── RCC.yaml
    │   ├── DMA.yaml
    │   ├── ... (more)
    │   ├── H723.yaml               ← Chip models
    │   ├── H725.yaml
    │   └── ...
    │
    ├── H74x_H75x/
    │   ├── ADC.yaml
    │   ├── RCC.yaml
    │   ├── ... (16 more)
    │   ├── H742.yaml
    │   ├── H757_CM4.yaml
    │   └── ...
    │
    └── H7A3_B/
        ├── ADC.yaml
        ├── RCC.yaml
        ├── ... (16 more)
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
