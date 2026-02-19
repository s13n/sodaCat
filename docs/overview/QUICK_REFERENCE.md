# STM32H7 Model Extraction - Quick Reference Card

## One-Sentence Summary
Automatically extract reusable functional block models for 21 STM32H7 microcontroller variants using quality-scored SVD source selection, configuration-driven transformations, and intelligent array pattern detection.

---

## Core Files You Need

| File | Purpose | Location | Status |
|------|---------|----------|--------|
| **stm32h7-transforms.yaml** | All transformation rules | `extractors/` | ✅ Ready |
| **generate_stm32h7_models.py** | Main extraction script | `extractors/` | 🟡 40% coded |
| **stm32h7-extraction.cmake** | CMake build integration | `cmake/` | ✅ Ready |
| **STM32H757_template.py** | Shows config-driven approach | `extractors/` | ✅ Reference |

---

## Architecture Layers

```
Input:     21 STM32H7 SVD files
           ↓
Layer 1:   SVD Parser (tools/svd.py)
           ↓
Layer 2:   Configuration-Driven Transformations (stm32h7-transforms.yaml)
           ↓
Layer 3:   Quality Selection (BlockSourceSelector)
           ↓
Layer 4:   Array Pattern Detection (ArrayTransformationDetector)
           ↓
Output:    58 Common Models + 42 Subfamily Variants
```

---

## Transformation Types (All Config-Driven)

1. **Header Struct Mapping** - Instance (TIM1) → Block Type (AdvCtrlTimer)
2. **Rename Rules** - Strip prefixes from field names
3. **Array Clustering** - Repetitive registers → array clusters (S[0..7])
4. **Parameter Assignment** - Add capability metadata per instance
5. **Special Handling** - Custom code for complex blocks (RCC)

---

## Three-Tier Model Organization

```
H7/                       ← H7 family folder
├── ADC.yaml                (58 common blocks → all variants use these)
├── DMA.yaml
├── RTC.yaml
├── ...
│
├── H73x/
│   ├── RCC.yaml          ← H73x-specific variants (12 blocks)
│   └── ...
│
├── H74x_H75x/
│   ├── RCC.yaml          ← H74x/H75x-specific variants (8 blocks)
│   └── ...
│
└── H7A3_B/
    ├── RCC.yaml          ← H7A3/B-specific variants (3 blocks)
    └── ...
```

---

## Configuration Example

```yaml
GpTimer:                          # Block name
  instances: [TIM2, TIM3, ...]   # Which MCU instances
  
  headerStructName: GpTimer       # Block type
  
  parameters:
    TIM2:                         # Per-instance parameters
      wide: 1                     # 32-bit counter
      chan_max: 3                 # 4 channels
      rep: 0                      # No repetition counter
    
    TIM3:                         # Different instance
      wide: 0                     # 16-bit counter
      chan_max: 3
      rep: 0
  
  renames:                        # Field normalization
    - target: interrupts
      field: name
      pattern: 'TIM\d+_(.+)'
      replacement: '\1'           # TIM2_UP → UP
```

---

## Quality Scoring (Block Source Selection)

**Score = 50 + descriptions(+1) + enums(+3) + registers(+2) + doc(+5) + variant(+10)**

Example for ADC Block:
```
STM32H743.svd:  50 + 7 + 9 + 14 + 5 + 0 = 85 ⭐ SELECTED
STM32H750.svd:  50 + 5 + 3 + 10 + 0 + 0 = 68
STM32H730.svd:  50 + 4 + 0 + 8  + 0 + 0 = 62
```

---

## Array Patterns Detected

### ✅ Confirmed (In transforms.yaml)
- **MDMA:** `MDMA_C[0..31]` (32 channels)
- **DMA:** `S[0..7]` (8 streams)
- **DFSDM:** `CH[0..7]` (8 channels), `FLT[0..3]` (4 filters)
- **RTC:** `BKP[0..31]` (32 backup registers)
- **ADC:** `JDR[0..3]` (4 injected channels)

### 📋 Recommended (High confidence)
- **SAI:** `CH[0..3]` (4 audio channels)
- **I2C:** Status register variants
- **RCC:** Domain clustering (complex)

---

## To Run Full Extraction

```bash
# 1. Analyze and select best SVD source for each block
python3 extractors/generate_stm32h7_models.py --analyze-sources

# 2. Extract all models
python3 extractors/generate_stm32h7_models.py --extract-all

# 3. Verify output
ls models/ST/H7/ | wc -l    # Should be 58
ls models/ST/H7/H73x/ | wc -l  # Variable
```

---

## Implementation Checklist

- [x] Configuration created (stm32h7-transforms.yaml)
- [x] CMake module created (stm32h7-extraction.cmake)
- [x] Design documented (5 documents)
- [x] Reference implementation provided (STM32H757_template.py)
- [ ] Move extraction script to extractors/
- [ ] Implement TransformationLoader class
- [ ] Implement BlockSourceSelector class
- [ ] Implement ArrayTransformationDetector class
- [ ] Run full extraction test suite
- [ ] Validate against reference (STM32H757.py)

**Estimated Remaining Effort:** 10-14 hours

---

## Common Patterns in Configuration

### Pattern 1: Instance-to-Block Mapping
```yaml
BasicTimer:
  instances: [TIM6, TIM7]
  headerStructName: BasicTimer
```

### Pattern 2: Per-Instance Parameters
```yaml
GpTimer:
  parameters:
    TIM2:  {wide: 1, chan_max: 3}
    TIM3:  {wide: 0, chan_max: 3}
```

### Pattern 3: Field Name Normalization
```yaml
USART:
  renames:
    - target: interrupts
      field: name
      pattern: 'USART\d+_(.+)'
      replacement: '\1'
```

### Pattern 4: Register Array Clustering
```yaml
DMA:
  arrays:
    - name: streams
      pattern: 'S(\d+)(.+)'
      clusterName: 'S'
      count: 8
```

### Pattern 5: Capability Enumerations
```yaml
ADC:
  parameters:
    ADC1:
      resolution_bits: 12
      channels: 21
      dma: 1
      comparator: 1
```

---

## Key Design Decisions

| Decision | Rationale | Benefit |
|----------|-----------|---------|
| **Config-driven** | Reusable across variants | No code duplication |
| **Quality scoring** | Automatic SVD selection | Traceability + scaling |
| **Three-tier org** | Common + variant blocks | 58% DRY (no duplication) |
| **Array clustering** | Reduce repetitive registers | 60-90% compression |
| **YAML format** | Non-programmers can edit | Lower maintenance burden |

---

## File Locations Quick Lookup

**Where to find what:**

**Configurations:**
```
extractors/stm32h7-transforms.yaml         ← Transformation rules
cmake/stm32h7-extraction.cmake          ← Build integration
```

**Implementation (IN PROGRESS):**
```
extractors/generate_stm32h7_models.py      ← Main script
  ├─ TransformationLoader               ← TODO: 2-3h
  ├─ BlockSourceSelector                ← TODO: 3-4h  
  └─ ArrayTransformationDetector        ← TODO: 2-3h
```

**Reference/Design:**
```
extractors/STM32H757.py                    ← Original (401 lines)
extractors/STM32H757_template.py           ← Config-driven refactor
REFINEMENTS.md                          ← Problem analysis
ARRAY_TRANSFORMATION_ANALYSIS.md        ← Array patterns
BLOCK_SOURCE_SELECTION_DESIGN.md        ← Scoring algorithm
IMPLEMENTATION_GUIDE.md                 ← Step-by-step walkthrough
PROJECT_STATUS.md                       ← Status & effort estimates
ANALYSIS_STM32H7_COMPATIBILITY.md       ← Block compatibility breakdown
```

---

## Common Commands

### Extract Single SVD
```bash
python3 extractors/generate_stm32h7_models.py \
  --svd svd/STM32H757_CM4.svd \
  --transforms extractors/stm32h7-transforms.yaml \
  --output models/ST/H7/H757/
```

### Analyze SVD Sources
```bash
python3 extractors/generate_stm32h7_models.py \
  --analyze-sources \
  --svd-dir svd
```

### Extract All H7 Variants
```bash
python3 extractors/generate_stm32h7_models.py \
  --extract-all \
  --models-dir models/ST/
```

### Validate Output
```bash
python3 tools/compare_peripherals.py models/ST/ reference/
```

### Using CMake
```bash
cd build && cmake .. && make models
```

---

## Troubleshooting Quick Guide

| Problem | Solution |
|---------|----------|
| Import svd module fails | `export PYTHONPATH="$PYTHONPATH:./tools"` |
| YAML parse error | `pip install ruamel.yaml` |
| File not found | Check paths are relative to sodaCat root |
| SVD not recognized | Verify file in `svd/` and named `STM32H7*.svd` |
| Transformation not applied | Check block exists in stm32h7-transforms.yaml |

---

## References

- **Algorithm Details:** [BLOCK_SOURCE_SELECTION_DESIGN.md](BLOCK_SOURCE_SELECTION_DESIGN.md)
- **Array Opportunities:** [ARRAY_TRANSFORMATION_ANALYSIS.md](ARRAY_TRANSFORMATION_ANALYSIS.md)
- **Step-by-Step Guide:** [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
- **Current Status:** [PROJECT_STATUS.md](PROJECT_STATUS.md)
- **Problem Analysis:** [REFINEMENTS.md](REFINEMENTS.md)

---

## Success Metrics

**When done:**
- ✅ 58 shared blocks in `H7/`
- ✅ Family-specific variants organized by subfamily
- ✅ All 21 chip models generated
- ✅ Transformation decisions documented
- ✅ Source selection report shows quality metrics
- ✅ Array patterns identified and applied

**Time to completion:** 10-14 hours (Phase 3) + 2-3 hours (Phase 4)

---

## Quick Stats

| Metric | Value |
|--------|-------|
| Total STM32H7 Variants | 21 |
| Total Functional Blocks | 100+ |
| Blocks That Can Be Shared | 58 (58%) |
| Blocks Requiring Variants | 42 (42%) |
| Configuration Lines (Transforms) | ~300 |
| Reference Implementation | 401 lines |
| Refactored with Config | ~100 lines |
| Code Reduction | 75% |
| Array Patterns Found | 6 confirmed + 3 recommended |
| Register Compression | 60-90% per block |
| Estimated Build Time | ~10 seconds |

---

## Next 10 Steps

1. Move extraction script to `extractors/`
2. Load YAML configuration
3. Apply transformations from config
4. Parse all 21 SVDs
5. Score each block occurrence
6. Select best source per block
7. Detect array patterns
8. Generate models
9. Validate quality
10. Document decisions

