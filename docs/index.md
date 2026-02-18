# sodaCat Documentation

Complete documentation for the sodaCat SOC data extraction and model generation system.

## Quick Start

**New to sodaCat?** Start here:
- [Project Status](overview/PROJECT_STATUS.md) - What sodaCat is and current progress
- [Quick Reference](overview/QUICK_REFERENCE.md) - Common tasks and commands
- [STM32H7 Quick Start](stm32h7/QUICKSTART_STM32H7.md) - Get started with STM32H7 models

## For Users (Using Pre-Built Models)

The easiest path if you just need the hardware models:

### STM32H7 Family
- [STM32H7 Quick Start](stm32h7/QUICKSTART_STM32H7.md) - Using pre-built STM32H7 models
- [STM32H7 Extraction Guide](stm32h7/README_STM32H7_EXTRACTION.md) - Understanding the three-tier model organization
- [Compatibility Analysis](stm32h7/ANALYSIS_STM32H7_COMPATIBILITY.md) - Which blocks are shared vs subfamily-specific

## For Developers (Maintaining sodaCat)

### Building and Regenerating Models

#### STM32H7 Extraction
- [Implementation Summary](design/IMPLEMENTATION_SUMMARY.md) - Complete architecture overview
- [Implementation Guide](stm32h7/IMPLEMENTATION_GUIDE.md) - Step-by-step setup and usage
- [Extraction CMake Module](../cmake/stm32h7-extraction.cmake) - The build system

### Transformation Framework
- [Framework Overview](transformation-framework/GENERIC_TRANSFORMATION_FRAMEWORK.md) - How the transformation system works
- [Extension Guide](transformation-framework/TRANSFORMATION_EXTENSION_GUIDE.md) - Adding new transformation types
- [Implementation Details](transformation-framework/GENERIC_TRANSFORMATION_DELIVERY.md) - What was delivered and how it works
- [Checklist](transformation-framework/TRANSFORMATION_IMPLEMENTATION_CHECKLIST.md) - Quick reference for using the framework

### Design Documents

Deep-dive technical documentation:

- [Block Source Selection Design](design/BLOCK_SOURCE_SELECTION_DESIGN.md) - Issue #2: Designing block-level model generation
- [Array Transformation Analysis](design/ARRAY_TRANSFORMATION_ANALYSIS.md) - Issue #3: Automatic register array detection
- [Refinements](design/REFINEMENTS.md) - Issue #4 and other improvements
- [Implementation Summary](design/IMPLEMENTATION_SUMMARY.md) - Full architecture and design decisions

## Project Structure

```
sodaCat/
├── docs/                          ← You are here
│   ├── index.md                   (This file)
│   ├── overview/                  (High-level status and references)
│   ├── stm32h7/                   (STM32H7 specific documentation)
│   ├── transformation-framework/  (Transformation system documentation)
│   └── design/                    (Design documents and analysis)
├── cmake/                         (CMake modules for model generation)
├── generators/                    (Model extraction scripts)
├── models/ST/                     (Generated STM32H7 models)
│   ├── H7_common/                 (Blocks shared across all variants)
│   ├── H73x/blocks/               (H73x subfamily-specific blocks)
│   ├── H74x_H75x/blocks/          (H74x/H75x subfamily-specific blocks)
│   └── H7A3_B/blocks/             (H7A3/B subfamily-specific blocks)
├── extractors/                       (MCU-specific extraction code)
├── tools/                         (Generic utilities and frameworks)
└── svd/                           (SVD source files)
```

## Common Tasks

### I want to use pre-built STM32H7 models
→ [STM32H7 Quick Start](stm32h7/QUICKSTART_STM32H7.md)

### I want to regenerate STM32H7 models from SVD
→ [Implementation Guide](stm32h7/IMPLEMENTATION_GUIDE.md)

### I want to add a new transformation type
→ [Extension Guide](transformation-framework/TRANSFORMATION_EXTENSION_GUIDE.md)

### I want to understand why blocks are organized the way they are
→ [Compatibility Analysis](stm32h7/ANALYSIS_STM32H7_COMPATIBILITY.md)

### I want to add support for a new MCU family (NXP, Raspberry, etc.)
→ [Implementation Summary](design/IMPLEMENTATION_SUMMARY.md) (Section: Integration Steps)

## Key Concepts

### Three-Tier Model Organization
Models are organized into three tiers to maximize code reuse:
1. **H7_common/** - Blocks shared identically across ALL subfamilies
2. **Family-specific/** (H73x, H74x_H75x, H7A3_B) - Blocks that differ within subfamilies
3. **Chip-specific/** (referenced in family models) - Chip-level configurations

This prevents duplication while keeping incompatible blocks isolated.

### Generic Transformation Framework
A plugin-based system where:
- **Generic transformations** in `tools/` work across all MCU families
- **Family-specific transformations** in `extractors/` handle MCU-specific logic
- **Configuration files** (YAML) control which transformations apply
- Only configured transformations are executed (no hardcoded logic)

### CMake Integration
- Models are in the **source tree** (`models/ST/`) for easy user access
- Build artifacts (stamp files) are in the **build directory** (not committed)
- `cmake --build . --target stm32h7-models` regenerates models (development task)
- Regular builds just use pre-built models (user task)

## Getting Help

- Check [Quick Reference](overview/QUICK_REFERENCE.md) for command-line examples
- See [Project Status](overview/PROJECT_STATUS.md) for known limitations
- Review the relevant design document for deep technical details
- Consult the docstrings in the source code for implementation specifics

## Project Phases

| Phase | Status | Documentation |
|-------|--------|-----------------|
| **Phase 1** | ✅ Complete | [Compatibility Analysis](stm32h7/ANALYSIS_STM32H7_COMPATIBILITY.md) |
| **Phase 2** | ✅ Complete | [Implementation Summary](design/IMPLEMENTATION_SUMMARY.md) |
| **Phase 3** | 🔄 In Progress | [Transformation Framework](transformation-framework/) |

---

**Last Updated:** February 12, 2026
