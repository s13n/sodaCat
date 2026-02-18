# Block Source Selection System Design

## Overview

When the same functional block appears in multiple SVD files (e.g., ADC in H730.svd, H743.svd, H750.svd), we need an intelligent mechanism to **select the best SVD source** based on quality metrics like field description completeness, enum definitions, and register coverage.

This document details the `BlockSourceSelector` system for automated source selection.

---

## Problem Statement

### Current Situation

Each STM32H7 variant has its own SVD file with potentially overlapping blocks:

```
H730.svd  → ADC block (variant A - 8 fields, 2 enums)
H743.svd  → ADC block (variant B - 12 fields, 5 enums) ← Better
H757.svd  → ADC block (variant C - 8 fields, 2 enums)
```

### Challenges

1. **No Quality Guidance**: Which SVD's ADC should we use as the canonical definition?
2. **Manual Selection**: Currently picking first-found or hardcoding per-block
3. **Lost Context**: Don't know what information differences exist
4. **Scalability**: With 100+ blocks × 21 chips = 2,100+ block instances, manual selection is infeasible

### Solution Approach

Create `BlockSourceSelector` class that:
1. **Scans all SVD files** - Find all instances of each block type
2. **Scores each instance** - Assign quality metrics
3. **Selects the best** - Choose highest-scoring SVD source
4. **Reports decisions** - Show why each block was selected

---

## Quality Scoring Algorithm

### Score Calculation

Score = (base_score) + (field_descriptions) + (field_enums) + (register_coverage) + (documentation) + (variant_bonus)

**Each component defined below:**

#### 1. Base Score: `50` points

Every block starts with 50 points for existing in the SVD.

#### 2. Field Descriptions: `+1 point per field with description`

```python
field_desc_score = sum(1 for field in block['fields'] 
                       if field.get('description', '').strip())
```

**Example:**
```
SVD A: ADC with 8 fields, 4 have descriptions → +4
SVD B: ADC with 8 fields, 7 have descriptions → +7
Winner: SVD B (+3 points advantage)
```

#### 3. Field Enums: `+3 points per field with enumeration values`

```python
enum_score = sum(3 for field in block['fields'] 
                 if 'enumeratedValues' in field)
```

**Example:**
```
SVD A: ADC with 3 fields having enums (e.g., MODE=[0=single, 1=continuous])
       → 3 × 3 = +9 points
SVD B: ADC with 5 fields having enums
       → 5 × 3 = +15 points
Winner: SVD B (+6 points advantage)
```

**Why Worth More:** Enums are expensive to extract; automatically found enums are valuable.

#### 4. Register Coverage: `+2 points per register with detailed fields`

```python
register_score = sum(
    2 for reg in block.get('registers', [])
    if len(reg.get('fields', [])) >= 4  # Non-trivial field count
)
```

**Rationale:** More detailed registers = more useful block definition.

#### 5. Documentation Quality: `+5 bonus for complete block description`

```python
doc_score = 5 if (block.get('description', '').split() >= 10) else 0
```

**Example:**
```
SVD A: "ADC block" → 2 words → +0
SVD B: "12-bit analog-to-digital converter with up to 21 input 
        channels and hardware comparators" → 18 words → +5
Winner: SVD B (+5 points)
```

#### 6. Variant Bonus: `+10 for matching subfamily`

When multiple SVDs score similarly, prefer the one from the **same subfamily**:

```python
variant_bonus = 10 if svd_subfamily == target_subfamily else 0
```

**Example:** When generating H743 models, prefer H743.svd over H730.svd if scores are tied.

---

## Scoring in Action

### Example 1: ADC Block

|  | H730.svd | H743.svd | H750.svd | H7A3.svd |
|---|----------|----------|----------|----------|
| Base | 50 | 50 | 50 | 50 |
| Field Descriptions | +4 | +7 | +5 | +3 |
| Field Enums | +0 | +9 | +3 | +0 |
| Register Coverage | +8 | +14 | +10 | +6 |
| Documentation | +0 | +5 | +0 | +0 |
| **Total** | **62** | **85** ⭐ | **68** | **59** |

**Decision:** Use **H743.svd** as canonical ADC source (+85 score)

**Impact:** H743's ADC has:
- ✅ All 8 fields documented
- ✅ Mode enum fully mapped
- ✅ Channel selection enum present
- ✅ Detailed register descriptions

---

### Example 2: RCC Block (Complex)

|  | H730.svd | H743.svd | H757.svd | H7A3.svd |
|---|----------|----------|----------|----------|
| Base | 50 | 50 | 50 | 50 |
| Field Descriptions | +12 | +16 | +14 | +8 |
| Field Enums | +12 | +15 | +15 | +9 |
| Register Coverage | +20 | +28 | +26 | +18 |
| Documentation | +5 | +5 | +5 | +0 |
| Variant Bonus (vs H743) | 0 | +10 | 0 | 0 |
| **Total** | **99** | **124** ⭐ | **110** | **85** |

**Decision:** Use **H743.svd** as canonical RCC source

**Why H743 Wins:**
- All MCUs from same family prefer same subfamily
- H743 has most field documentation (16 fields)
- H743 has most detailed registers (28 vs 26, 20, 18)
- When generating H750 models, can still reference H743 RCC (common subfamily)

---

### Example 3: PWR Block (Tight Scores)

|  | H730.svd | H743.svd | H757.svd | H7A3.svd |
|---|----------|----------|----------|----------|
| Base | 50 | 50 | 50 | 50 |
| Field Descriptions | +5 | +6 | +6 | +4 |
| Field Enums | +3 | +3 | +3 | +0 |
| Register Coverage | +8 | +10 | +10 | +6 |
| Documentation | +0 | +0 | +0 | +0 |
| Variant Bonus (vs H743) | 0 | +10 | 0 | 0 |
| **Total** | **66** | **79** ⭐ | **69** | **60** |

**Decision:** Use **H743.svd**

**Note:** H757 and H743 are tied before variant bonus (69 vs 69), but H743's subfamily bonus breaks the tie.

---

## Implementation Design

### Class Interface

```python
class BlockSourceSelector:
    """
    Scores and selects the best SVD source for each functional block.
    """
    
    def __init__(self, transforms_config):
        """
        Load transformation config to identify which blocks to score.
        
        Args:
            transforms_config: Parsed YAML from stm32h7-transforms.yaml
        """
        self.blocks = transforms_config['blocks']
        self.scores = {}
        self.decisions = {}
    
    def scan_svd_files(self, svd_dir):
        """
        Scan all STM32H7 SVD files and extract blocks.
        
        Builds internal map: {block_name: {svd_file: parsed_block}}
        """
        pass
    
    def score_block_instance(self, block_data, svd_name, svd_subfamily):
        """
        Calculate quality score for one block instance.
        
        Args:
            block_data: Parsed block from SVD
            svd_name: Name of SVD file (e.g., "STM32H743.svd")
            svd_subfamily: Subfamily (e.g., "H74x")
        
        Returns:
            {
                'base': 50,
                'field_descriptions': 7,
                'field_enums': 9,
                'register_coverage': 14,
                'documentation': 5,
                'variant_bonus': 0,
                'total': 85,
                'reasoning': ["8 fields documented", "5 enums", ...]
            }
        """
        pass
    
    def select_best_source(self, block_name, target_subfamily=None):
        """
        Select the best SVD source for a block.
        
        Args:
            block_name: Block type (e.g., "ADC", "RCC")
            target_subfamily: Prefer this subfamily if tied (e.g., "H74x")
        
        Returns:
            {
                'selected_svd': "STM32H743.svd",
                'score': 85,
                'alternatives': {
                    "STM32H730.svd": 62,
                    "STM32H750.svd": 68,
                    "STM32H7A3.svd": 59
                }
            }
        """
        pass
    
    def generate_selection_report(self, output_file):
        """
        Write a human-readable report of all block source selections.
        
        Example output:
            ADC
              ✓ Selected: STM32H743.svd (score 85)
                Reasons: 7 fields documented, 5 enums, 14 detailed registers
                Alternatives:
                  - STM32H750.svd (score 68, -17 points)
                  - STM32H730.svd (score 62, -23 points)
        """
        pass

    def export_block_sources_map(self, output_file):
        """
        Export JSON map: {block_name: best_svd_file}
        
        Used by extraction pipeline to know which SVD to parse for each block.
        """
        pass
```

### Integration with Extraction Pipeline

```python
def main():
    # 1. Load transformation config
    transforms = load_transforms_config('extractors/stm32h7-transforms.yaml')
    
    # 2. Initialize source selector
    selector = BlockSourceSelector(transforms)
    
    # 3. Scan all SVD files and score blocks
    selector.scan_svd_files('svd')
    
    # 4. Generate report
    selector.generate_selection_report('output/BLOCK_SOURCE_SELECTION.md')
    
    # 5. Export map for use by extraction
    selector.export_block_sources_map('output/block_sources.json')
    
    # 6. Now extract each block from the selected SVD
    block_sources = selector.get_sources_map()
    
    for block_name, best_svd in block_sources.items():
        # Parse only the best SVD for this block
        block_data = parse_block_from_svd(best_svd, block_name)
        
        # Apply transformations
        apply_transformations(block_data, transforms[block_name])
        
        # Output
        dump_model(block_data, f'models/ST/H7_common/{block_name}.yaml')
```

---

## Sample Output Report

### File: `output/BLOCK_SOURCE_SELECTION.md`

```markdown
# Block Source Selection Report
Generated: 2024-01-15 14:23:45

## Executive Summary
- **Total Blocks Analyzed:** 30
- **SVD Files Scanned:** 21
- **Unanimous Best Source:** 15 blocks (50%)
- **Tied Decisions:** 8 blocks (27%) - Resolved via subfamily bonus
- **Complex Decisions:** 7 blocks (23%) - Multiple high-scoring sources

## Blocks by Subfamily

### H7 Common (Shared across all subfamilies) - 15 blocks

#### ADC ✓
- **Selected Source:** [STM32H743.svd](STM32H743.svd)
- **Score:** 85/100
- **Scoring Details:**
  - Field Descriptions: 7/8 fields
  - Field Enumerations: 5 (MODE, CHANNEL, RESOLUTION, ALIGN, CONTINUOUS)
  - Register Coverage: 14 detailed registers
  - Block Documentation: "12-bit analog-to-digital converter..."
  
- **Why This Source?**
  - ✅ Most field documentation (87%)
  - ✅ Complete enum support for all configuration modes
  - ✅ Registers describe function (CONF_REG, DATA_REG, etc.)
  
- **Alternative Sources:**
  - STM32H750.svd (score 68) - Missing channel enum
  - STM32H730.svd (score 62) - Minimal documentation
  - STM32H7A3.svd (score 59) - Unclear field definitions

---

#### DMA ✓
- **Selected Source:** [STM32H743.svd](STM32H743.svd)
- **Score:** 92/100
- **Decision:** Unanimous (No alternatives with >80)
- **Key Features:**
  - Complete stream definitions (S0..S7)
  - Full field documentation
  - Mode and priority enums included

---

#### MDMA ✓
- **Selected Source:** [STM32H743.svd](STM32H743.svd)
- **Score:** 88/100

---

#### RCC (Complex) ⚠️
- **Selected Source:** [STM32H743.svd](STM32H743.svd)
- **Score:** 124/100 (bonus applied)
- **Scoring Details:**
  - Field Descriptions: 16 diverse clock enables
  - Field Enumerations: 15 source selections
  - Register Coverage: 28 detailed domain registers
  - Variant Bonus: +10 (H74x subfamily preference)

- **Scoring Table:**
  ```
  Source          Base  Desc  Enum  Regs  Docs  Bonus  Total
  ─────────────────────────────────────────────────────────────
  H730.svd         50   +12   +12   +20   +5     0     99
  H743.svd         50   +16   +15   +28   +5   +10    124 ✓
  H757.svd         50   +14   +15   +26   +5     0    110
  H7A3.svd         50    +8    +9   +18   +0     0     85
  H750.svd         50   +13   +14   +24   +5     0    106
  ```

- **Interesting Finding:** H730 scores nearly as high (99 vs 124) but H743 selected due to:
  1. Better field documentation (16 vs 12)
  2. Subfamily preference (H74x family)
  3. More detailed register descriptions

- **Usage Recommendation:** All H7 variants can use H743 RCC as baseline due to strong documentation. Subfamily-specific variants (H73x RCC, H7A3 RCC) should override only if significant structural differences detected.

---

#### SYSCFG
- **Selected Source:** [STM32H743.svd](STM32H743.svd)
- **Score:** 76/100
- **Note:** SYSCFG varies between subfamilies but core functionality shared

---

#### PWR
- **Selected Source:** [STM32H743.svd](STM32H743.svd)
- **Score:** 79/100
- **Tied Sources:** H757.svd (79/100)
- **Tiebreaker:** Subfamily bonus (H74x vs H75x—H74x used as baseline)

---

### H73x Subfamily-Specific - 5 blocks

#### ADC_Common (H73x variant)
- **Selected Source:** [STM32H730.svd](STM32H730.svd)
- **Score:** 71/100
- **Subfamily Bonus:** +10 (H73x preference)
- **Note:** H73x ADC_Common has different interrupt handling than H74x

---

#### RCC (H73x variant)
- **Selected Source:** [STM32H730.svd](STM32H730.svd)
- **Score:** 109/100 (with H73x bonus)
- **Note:** Subfamily-specific clock tree; must use H73x variant

---

### H74x/H75x Subfamily-Specific - 5 blocks

(Uses H743 or H757 sources depending on similarity)

---

### H7A3_B Subfamily-Specific - 5 blocks

(Uses H7A3 sources)

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Blocks | 30 |
| Average Score (All Instances) | 82/100 |
| Highest Scored Block | RCC (H743: 124) |
| Lowest Scored Block | BasicTimer (H7A3: 58) |
| Unanimous Selections | 15 (50%) |
| Subfamily-Tied Selections | 8 (27%) |
| Complex/Expert-Review | 7 (23%) |

---

## Potential Data Quality Issues

### Blocks Needing Manual Review

1. **BasicTimer** - H7A3 missing documentation
   - H7A3.svd score: 58
   - Recommendation: Use H743.svd (6x) or supplement docs

2. **I2C** - Inconsistent field naming across SVDs
   - Some variants use ISR, others use SR1/SR2
   - Recommendation: Define mapping in transforms config

3. **USART** - Field width inconsistencies
   - LPUART has different register widths than USART
   - Recommendation: Validate field widths before merging

---

## Automation Confidence

| Category | Count | Confidence |
|----------|-------|-----------|
| Clear Winners (>85 score) | 18 | 100% |
| Tied but Resolvable | 8 | 95% |
| Recommend Human Review | 4 | 60% |

---

## Recommendations

1. ✅ **Majority of blocks can be selected automatically** (18/30 = 60%)
2. 🔍 **Tied blocks solvable with subfamily bonus** (8/30 = 27%)
3. ⚠️ **4 blocks need human review** (13%) before finalizing sources
4. 📋 **Create subfamily-specific configs for critical blocks** (RCC, PWR, SYSCFG)

```
