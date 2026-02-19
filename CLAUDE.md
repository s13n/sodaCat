# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

sodaCat is a hardware description database for microcontrollers and SoCs. It extracts register-level hardware descriptions from vendor SVD (System View Description) files into normalized YAML models, then generates C++20 headers from those models. The YAML models are the primary artifact — they are vendor-neutral, human-editable, and language-agnostic.

**Three-stage pipeline:** SVD (XML) → YAML models → C++20 headers

## Build Commands

```bash
# Configure (from project root)
mkdir build && cd build && cmake -GNinja ..

# Extract YAML models for a specific MCU family
cmake --build . --target stm32h7-models
cmake --build . --target stm32f4-models
# Available targets: stm32{c0,f3,f4,f7,g0,g4,h5,h7,l0,l1,l4,l4plus,l5,n6,u0,u3,u5}-models

# Build test executable (compile-only validation of generated C++ headers)
cmake --build . --target soc-data-test

# Force rebuild of models (deletes stamp file and re-extracts)
cmake --build . --target rebuild-stm32h7-models

# Run the test (no output = success; it validates that generated headers compile)
./test/soc-data-test
```

**Python dependencies:** `pip install PyYAML` (or `pip install -r requirements-dev.txt`)

**CMake requirement:** 3.28+, C++20 compiler, Python 3

## Architecture

### Pipeline stages

1. **SVD parsing** (`tools/svd.py`): `svd.parse()` reads XML, `svd.collateDevice()` normalizes into Python dicts with numeric values, collated arrays, and cleaned interrupts.

2. **Transformation** (`tools/transform.py`, `tools/generic_transform.py`): Fixes SVD issues — strips instance-specific prefixes from field names, groups repetitive registers into arrays (`createClusterArray`), maps instance names to block types (`headerStructName`). Can be driven declaratively via YAML config files (e.g., `extractors/stm32h7-transforms.yaml`).

3. **Model output** (`svd.dumpModel`, `svd.dumpDevice`): Writes YAML using `ruamel.yaml` with `indent(mapping=2, sequence=4, offset=2)`.

4. **C++ generation** (`generators/cxx/`): `generate_peripheral_header.py` produces per-block headers with `HwReg<T>` smart register wrappers; `generate_chip_header.py` produces chip-level integration headers with base addresses and instance parameters.

### Directory roles

- `extractors/` — Python scripts that convert SVD → YAML. Per-chip scripts (e.g., `STM32H757.py`) and family-wide generators (e.g., `generate_stm32h7_models.py`).
- `generators/cxx/` — Python scripts that convert YAML → C++20 headers. Also contains `hwreg.hpp` (the HwReg template).
- `tools/` — Shared libraries: `svd.py` (parser), `transform.py` (register/field transforms), `compare_peripherals.py` (similarity analysis).
- `cmake/` — One `stm32XX-extraction.cmake` module per family, plus `sodaCat.cmake` (the `generate_header()` macro).
- `models/` — Generated YAML organized as `models/<Vendor>/<Family>/`. The `ST/H7/H757/` directory contains manually maintained reference models.
- `svd/` — Vendor SVD zip archives and `CMakeLists.txt` that wires up all extraction targets.
- `schemas/` — YAML schemas for peripheral and clock-tree model validation.

### Model directory organization (three-tier)

```
models/ST/<Family>/
├── GPIO.yaml              # Blocks identical across ALL subfamilies
├── <Subfamily_A>/         # Blocks that differ for this subfamily
│   ├── RCC.yaml
│   └── STM32xxxx.yaml    # Chip-level model
└── <Subfamily_B>/
    └── ...
```

Family generators use structural hashing (SHA-256 of register names, offsets, field layouts) to automatically determine which blocks are common vs. subfamily-specific.

### CMake integration

The unified `cmake/stm32-extraction.cmake` module provides:
- `stm32_add_family()` — registers a family and creates extraction/rebuild targets
- `stm32_block_path()` — resolves to common or subfamily dir
- `stm32_chip_path()` — resolves chip model path
- `stm32_subfamily_chips()` — gets the list of chips in a subfamily

The `generate_header()` macro in `sodaCat.cmake` wires YAML → C++ generation as CMake custom commands with proper dependency tracking.

### Family generator

A single `extractors/generate_stm32_models.py` script handles all 17 STM32 families. Per-family configuration (subfamily-to-chip mapping and SVD peripheral name map) lives in YAML files under `extractors/families/<CODE>.yaml`. Two-pass processing: Pass 1 collects and hashes all blocks; Pass 2 compares hashes across subfamilies to separate common from subfamily-specific blocks.

**Usage:** `python3 extractors/generate_stm32_models.py <family_code> <zip_path> <output_dir>`

## Key conventions

- YAML models use `ruamel.yaml` (not PyYAML) for roundtrip-safe output
- Peripheral block files are PascalCase (`ADC.yaml`, `BasicTimer.yaml`, `GpTimer.yaml`)
- The `headerStructName` field in a model determines the C++ struct name; it maps instance names to generic block types
- `svd.dumpModel()` writes block models; `svd.dumpDevice()` writes chip-level models
- Tests are compile-only — if `soc-data-test` builds successfully, the generated headers are valid
- The `test/CMakeLists.txt` references models via paths relative to `SODACAT_LOCAL_DIR` (defaults to `${CMAKE_SOURCE_DIR}/models`)
- CMake extraction targets use stamp files (`<target>.stamp`) to avoid redundant re-extraction
- Cache variables like `STM32XX_GENERATOR` persist in CMakeCache.txt — after moving files, a stale cache may need `cmake .. -DSTM32XX_GENERATOR=<new_path>` or a clean reconfigure
