# sodaCat Documentation

Documentation for the sodaCat SOC data extraction and model generation system.
For a complete overview of the project architecture, build commands, and
conventions, see [CLAUDE.md](../CLAUDE.md).

## Transformation Framework

The generic transformation framework in `tools/generic_transform.py` provides a
plugin-based, configuration-driven system for applying SVD post-processing
transformations (renames, array clustering, parameter assignment, etc.).

- [Framework Overview](transformation-framework/GENERIC_TRANSFORMATION_FRAMEWORK.md) - How the transformation system works
- [Extension Guide](transformation-framework/TRANSFORMATION_EXTENSION_GUIDE.md) - Adding new transformation types
- [Implementation Details](transformation-framework/GENERIC_TRANSFORMATION_DELIVERY.md) - What was delivered and how it works
- [Checklist](transformation-framework/TRANSFORMATION_IMPLEMENTATION_CHECKLIST.md) - Quick reference for using the framework

## Key Concepts

### Three-Tier Model Organization

Models are organized into three tiers to maximize code reuse:
1. **Family base directory** (e.g. `H7/`) - Blocks shared across ALL subfamilies
2. **Subfamily directories** (e.g. `H7/H73x/`) - Blocks that differ per subfamily
3. **Chip models** (e.g. `H7/H73x/STM32H723.yaml`) - Chip-level configurations

Placement is config-driven: blocks without `variants` in the family YAML config
go to the base directory; blocks with `variants` go to subfamily directories.

### STM32 Family Extraction

All 17 STM32 families use a single unified extractor
(`extractors/generate_stm32_models.py`) with consolidated YAML configuration in
`extractors/STM32.yaml`. Subfamilies are aligned with ST reference manual
boundaries so each subfamily corresponds to exactly one RM.

### CMake Integration

- Models are in the **source tree** (`models/ST/`) for easy user access
- Build artifacts (stamp files) are in the **build directory** (not committed)
- `cmake --build . --target stm32h7-models` regenerates models for a family
- Regular builds just use pre-built models
