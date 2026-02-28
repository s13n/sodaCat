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

**Python dependencies:** `pip install ruamel.yaml PyYAML` (or `pip install -r requirements-dev.txt`). The primary YAML library is `ruamel.yaml` (roundtrip-safe); `PyYAML` is used in generators for safe loading.

**CMake requirement:** 3.28+, C++20 compiler, Python 3

## Architecture

### Pipeline stages

1. **SVD parsing** (`tools/svd.py`): `svd.parse()` reads XML, `svd.collateDevice()` normalizes into Python dicts with numeric values, collated arrays, and cleaned interrupts.

2. **Transformation** (`tools/transform.py`, `tools/generic_transform.py`): Fixes SVD issues — strips instance-specific prefixes from field names, groups repetitive registers into arrays (`createClusterArray`), maps instance names to block types (`headerStructName`). Can be driven declaratively via YAML config files (e.g., `extractors/stm32h7-transforms.yaml`). Note: the family generator (`generate_models.py`) has its own auto-strip and inline transform system — see "Family generator" below.

3. **Model output** (`svd.dumpModel`, `svd.dumpDevice`): Writes YAML using `ruamel.yaml` with `indent(mapping=2, sequence=4, offset=2)`.

4. **C++ generation** (`generators/cxx/`): `generate_peripheral_header.py` produces per-block headers with `HwReg<T>` smart register wrappers; `generate_chip_header.py` produces chip-level integration headers with base addresses and instance parameters.

### Directory roles

- `extractors/` — Python scripts that convert SVD → YAML. The unified `generate_models.py` handles all families via vendor extensions in `extractors/vendors/`.
- `generators/cxx/` — Python scripts that convert YAML → C++20 headers. Also contains `hwreg.hpp` (the HwReg template).
- `tools/` — Shared libraries: `svd.py` (parser), `transform.py` (register/field transforms), `compare_peripherals.py` (similarity analysis).
- `cmake/` — One `stm32XX-extraction.cmake` module per family, plus `sodaCat.cmake` (the `generate_header()` macro).
- `models/` — Generated YAML organized as `models/<Vendor>/<Family>/`. The `ST/H7/H757/` directory contains manually maintained reference models.
- `svd/` — Vendor SVD files, organized by vendor. `svd/ST/` contains STM32 zip archives, the consolidated `STM32.yaml` config, and `CMakeLists.txt` with family registrations; other vendors' loose `.svd` files are in `svd/` directly.
- `schemas/` — JSON Schema (Draft 7) for peripheral and clock-tree model validation.
- `tasks/` — AI agent task descriptions for writing parsers and generators.

### Model directory organization (four-tier)

```
models/ST/
├── WWDG.yaml              # Cross-family shared blocks (identical across families)
├── <Family>/
│   ├── GPIO.yaml          # Blocks shared by 2+ subfamilies in this family
│   ├── <Subfamily_A>/     # Blocks unique to or variant for this subfamily
│   │   ├── RCC.yaml
│   │   ├── AES.yaml
│   │   └── STM32xxxx.yaml # Chip-level model
│   └── <Subfamily_B>/
│       └── ...
```

Model placement is config-driven: cross-family shared blocks (defined in `shared_blocks`) go to the top level; within a family, blocks used by only one subfamily go in that subfamily's directory, blocks shared by 2+ subfamilies go in the family base directory — see "Family generator" below.

### CMake integration

The unified `cmake/stm32-extraction.cmake` module provides:
- `stm32_add_family()` — registers a family and creates extraction/rebuild/audit targets
- `stm32_print_families()` — prints a summary of all registered families

The `generate_header()` macro in `sodaCat.cmake` wires YAML → C++ generation as CMake custom commands with proper dependency tracking.

### C++ generation

`generators/cxx/generate_peripheral_header.py` and `generate_chip_header.py` are invoked as:
```
python3 generate_peripheral_header.py <model.yaml> <namespace> <model_name> <suffix>
python3 generate_chip_header.py <chip_model.yaml> <namespace> <model_name> <suffix>
```
They use `string.Template` for code emission and produce `HwReg<T>`-based register wrappers with type-safe bitfield access. The `hwreg.hpp` template provides `.val()` (read as int), `.get()` (read as bitfield struct), and assignment for writes.

### Family generator

A single unified `extractors/generate_models.py` script handles all families (STM32, LPC). Vendor-specific behavior (SVD access, source formatting) is provided by lightweight extension modules in `extractors/vendors/`. All STM32 family configuration lives in a single consolidated file `svd/ST/STM32.yaml` with two top-level keys:

- `shared_blocks`: cross-family shared block definitions — blocks whose register map is identical across multiple families. Each entry has the same keys as a family block (`from`, `interrupts`, `transforms`, `params`) except `instances`, which is inherently per-family and must be specified in each family's block entry. Shared models are written to `models/ST/` (top level), not under a family directory.
- `families`: per-family configuration, keyed by family code (C0, F3, ..., U5)

Each family entry has up to four keys:

- `svd`: SVD archive metadata — `{zip, version, date}`. The `zip` filename must match the `ZIP` arg in `svd/ST/CMakeLists.txt`. The `version` and `date` fields are updated automatically by `tools/st_maintenance.py svd --download` when new SVD archives are downloaded.
- `subfamilies`: subfamily → chip list mapping, with optional `ref_manual: {name, url}` per subfamily
- `blocks`: block_type → `{from, instances, interrupts, transforms, params, variants}` — declares which SVD peripherals map to which block types, preferred source chip, interrupt name mappings, inline transforms to fix SVD bugs, optional parameter declarations, and optional per-subfamily overrides. A block may use `uses: <shared_block_name>` instead of `from:` to reference a cross-family shared model; `from` triggers SVD extraction while `uses` references the shared model. Defaults from `shared_blocks` are inherited and can be overridden.
- `chip_params` (optional): subfamily-keyed parameter value overrides for values declared in block `params`
- `chip_interrupts` (optional): subfamily-keyed interrupt overrides to inject or correct chip-level interrupt assignments. Same cascade structure as `chip_params`: `chip_interrupts[subfamily|_all][chip|_all][instance_name] = {canonical_name: irq_number}`. First match wins (no merging across levels). Used to fix SVD bugs where interrupts are misattributed, missing, or misnumbered.

Parameter declarations are arrays of `{name, type, default?, description?}`. Permissible types: `int`, `bool`, `string`.

The `chip_params` section is always keyed by subfamily (or `_all` for family-wide), then by chip name (or `_all` for subfamily-wide), then by block name or instance name. Resolution order: per-chip instance → per-chip block → subfamily `_all` instance → subfamily `_all` block → family `_all._all` instance → family `_all._all` block → param default.

Blocks with a `variants` key contain per-subfamily overrides (shallow-merged over top-level defaults). The `variants` key also controls model file placement: subfamilies **listed** in `variants` are written to subfamily subdirectories; subfamilies **not listed** share a common model. If only one subfamily uses the base config, the model is placed in that subfamily's directory (not the family base directory); if two or more subfamilies share the base config, it goes in the family base directory. This supports partial variants — e.g., H7 ADC has top-level config shared by H742_H753/H745_H757, with only H73x and H7A3_B as variants. A variant's `transforms` list fully replaces (not merges with) the top-level `transforms`.

Three-pass processing: Pass 1 collects blocks from all chips (resolving per-subfamily config via `variants`); Pass 2 writes models using config-driven placement; Pass 3 generates chip models with interrupts, instances, and parameters.

**Usage:** `python3 extractors/generate_models.py <vendor> <family_code> <svd_source> <output_dir> [--audit]`

Where `<vendor>` is `stm32` or `lpc`, and `<svd_source>` is a zip archive (STM32) or SVD repository directory (LPC).

### Register name prefix stripping

SVD files often prefix register names with the instance name (e.g., `ADC_ISR`, `GPIOA_MODER`, `FLASH_ACR`). The generator auto-strips these in Pass 1 via `_strip_instance_prefix()`, which removes prefixes matching `instance_name_`, `base_name_` (digits stripped), or `block_type_` — always requiring a `_` separator. Cases the auto-strip can't handle (case mismatch, compound block names, numbered instances like `OPAMP1_`/`COMP2_`) are covered by explicit `renameRegisters` transforms in the family config.

### Transformation framework

Per-block `transforms` lists in the family YAML config fix SVD bugs and naming issues during extraction. The generator (`generate_models.py`) applies these in-place after auto-strip, before writing models. Supported transform types:

- `renameRegisters` — regex rename on register `name` and `displayName`: `{type, pattern, replacement}`
- `renameFields` — regex rename on field `name` within a specific register: `{type, register, pattern, replacement}`
- `patchFields` — add/modify/remove fields in a register: `{type, register, fields: [{name, ...props}]}`. Name-only entries remove the field; name+props entries add or merge.
- `patchRegisters` — add/modify/remove register-level properties: `{type, registers: [{name, ...props}]}`. Same add/merge/remove semantics.
- `patchAddressBlock` — override addressBlock properties: `{type, size}` (and optionally other addressBlock fields).

Additionally, `tools/generic_transform.py` provides a standalone `TransformationEngine` with broader transforms (`createArrays`, `setParameters`, `setHeaderStructName`, `addFields`) driven via separate YAML config files (see `extractors/stm32h7-transforms.yaml`). This engine is not currently used by the family generator.

## CI

A GitHub Actions workflow validates clock-tree specs: `tools/validate_clock_specs.py` checks `spec/clock-tree/**/*.yaml` against `schemas/clock-tree.schema.yaml`. Triggered on changes to `schemas/`, `spec/clock-tree/`, or the validator script.

## Key conventions

- YAML models use `ruamel.yaml` (not PyYAML) for roundtrip-safe output. Always set `yaml.width = 4096` (prevents non-deterministic line wrapping) and `yaml.indent(mapping=2, sequence=4, offset=2)`. Use `CommentedMap` from ruamel, not `OrderedDict` (avoids `!!omap` tags)
- Peripheral block files are PascalCase (`ADC.yaml`, `BasicTimer.yaml`, `GpTimer.yaml`)
- The `headerStructName` field in a model determines the C++ struct name; it maps instance names to generic block types
- `svd.dumpModel()` writes block models; `svd.dumpDevice()` writes chip-level models
- Tests are compile-only — if `soc-data-test` builds successfully, the generated headers are valid
- The `test/CMakeLists.txt` references models via paths relative to `SODACAT_LOCAL_DIR` (defaults to `${CMAKE_SOURCE_DIR}/models`)
- CMake extraction targets use stamp files (`<target>.stamp`) to avoid redundant re-extraction
- Cache variables like `STM32_GENERATOR` and `LPC_GENERATOR` persist in CMakeCache.txt — after moving files, a stale cache may need explicit reconfiguration (e.g., `cmake .. -DSTM32_GENERATOR=<new_path>`) or a clean reconfigure
- SVD zip naming: STM32 zips live in `svd/ST/`; most are `stm32<family>-svd.zip`; exceptions use underscores: `stm32g4_svd.zip`, `stm32l1_svd.zip`, `stm32l4_svd.zip`, `stm32l4plus-svd.zip`, `stm32u5_svd.zip`
- Interrupt mapping is data-driven via `interrupts` in family config — SVD interrupt names not listed are dropped (acts as filter)
- Reference manuals are pdf files stored in `docs/<Vendor>/` (e.g., `docs/ST/`, `docs/NXP/`)
