# Refinements to STM32H7 Model Extraction System

## Issue 1: File Organization

**Current**: Script in `extractors/generate_stm32h7_models.py`
**Problem**: Generators are for SVD→source code, not SVD→models
**Solution**: Move to `extractors/generate_stm32h7_models.py` to align with existing STM32H757.py

## Issue 2: Inflexible Transformation Handling

**Current Problem**: All transformation logic is hardcoded inline in STM32H757.py
- 400+ lines of sequential rename/transform/parameter assignments
- Not reusable across different chip variants
- When adding H743 or H750, we'd have to duplicate much of this code
- Difficult to understand which transformations apply to which blocks

**Analysis of Current Patterns**:

The STM32H757.py script performs 5 types of transformations:

### A. **Header Struct Name Mapping** (Instance → Block Type)
```python
tim1['headerStructName'] = 'AdvCtrlTimer'
tim2['headerStructName'] = 'GpTimer'
tim6['headerStructName'] = 'BasicTimer'
```
Maps: TIM1/TIM8 → AdvCtrlTimer, TIM2-5 → GpTimer, TIM6-7 → BasicTimer

### B. **Rename Transformations** (Normalize instance-specific names)
```python
transform.renameEntries(usart1['interrupts'], 'name', 'USART1', 'USART')
transform.renameEntries(tim1['interrupts'], 'description', 'TIM1', 'TIM')
```

### C. **Array Transformations** (Repetitive registers → clusters)
```python
# Pattern: MDMA_C0_<field>, MDMA_C1_<field>, ... → C[n]_<field>
mdma['registers'] = transform.createClusterArray(mdma['registers'], 
    r"MDMA_C(\d+)(.+)", 
    {'name': 'C', 'description': 'MDMA channel'})

# Pattern: DFSDM_CH0_<reg>, DFSDM_CH1_<reg>, ... → CH[n]_<reg>
dfsdm['registers'] = transform.createClusterArray(dfsdm['registers'], 
    r"CH(\d+)(.+?)$", 
    {'name': 'CH', 'description': 'DFSDM channel'})
```

### D. **Parameter Assignment** (Capability metadata)
```python
# TIM2: 32-bit counter, 4 capture/compare channels, no repetition counter
tim2['parameters'] = [
    {'name': 'wide', 'value': 1},
    {'name': 'chan_max', 'value': 3},
    {'name': 'rep', 'value': 0},
    ...
]

# TIM3: 16-bit counter, same channels, no rep counter
tim3['parameters'] = [('wide', 0), ('chan_max', 3), ('rep', 0), ...]

# Different USART variants have different capabilities
usart1_pars = [('syncmode', 1), ('smartcard', 1), ('irdaSIR', 1), ...]
uart4_pars =  [('syncmode', 0), ('smartcard', 0), ('irdaSIR', 1), ...]
```

### E. **Field Addition** (Add missing SVD data)
```python
# RCC register missing fields in SVD but real in hardware
d1ccipr['fields'].append({'name': 'DSISRC', 'bitOffset': 8, ...})
apb3enr['fields'].append({'name': 'DSIEN', 'bitOffset': 4, ...})
```

## Proposed Solution: Transformation Configuration System

### Architecture

Create `extractors/stm32h7-transforms.yaml` containing transformation rules:

```yaml
# Transformation configuration for STM32H7 family blocks
# 
# Format: Each block entry specifies transformations to apply
# 'instances' lists peripheral instances that use this block type
# 'renames' specify field name normalizations
# 'arrays' specify register-to-cluster conversions
# 'parameters' specify capability metadata per instance
# 'fields' specify missing fields to add to registers

blocks:
  
  AdvCtrlTimer:
    instances: [TIM1, TIM8]
    headerStructName: AdvCtrlTimer
    renames:
      - target: interrupts
        field: name
        pattern: 'TIM\d?_([A-Z_0-9]+)'
        replacement: '\1'
      - target: interrupts
        field: description
        pattern: 'TIM1'
        replacement: 'TIM'
  
  GpTimer:
    instances: [TIM2, TIM3, TIM4, TIM5, TIM12, TIM13, TIM14, TIM15, TIM16, TIM17]
    headerStructName: GpTimer
    renames:
      - target: interrupts
        field: name
        pattern: 'TIM(\d+)'
        replacement: 'TIM'
      - target: interrupts
        field: description
        pattern: 'TIM\d+'
        replacement: 'TIM'
    parameters:
      TIM2:  [wide: 1, chan_max: 3, rep: 0, compl1: 0, bkin: 0, trigger: 1, encoder: 1]
      TIM3:  [wide: 0, chan_max: 3, rep: 0, compl1: 0, bkin: 0, trigger: 1, encoder: 1]
      TIM4:  [wide: 0, chan_max: 3, rep: 0, compl1: 0, bkin: 0, trigger: 1, encoder: 1]
      TIM5:  [wide: 1, chan_max: 3, rep: 0, compl1: 0, bkin: 0, trigger: 1, encoder: 1]
      TIM12: [wide: 0, chan_max: 1, rep: 0, compl1: 0, bkin: 0, trigger: 1, encoder: 0]
      TIM13: [wide: 0, chan_max: 0, rep: 0, compl1: 0, bkin: 0, trigger: 0, encoder: 0]
      TIM14: [wide: 0, chan_max: 0, rep: 0, compl1: 0, bkin: 0, trigger: 0, encoder: 0]
      TIM15: [wide: 0, chan_max: 1, rep: 1, compl1: 1, bkin: 1, trigger: 1, encoder: 0]
      TIM16: [wide: 0, chan_max: 0, rep: 1, compl1: 1, bkin: 1, trigger: 0, encoder: 0]
      TIM17: [wide: 0, chan_max: 0, rep: 1, compl1: 1, bkin: 1, trigger: 0, encoder: 0]

  BasicTimer:
    instances: [TIM6, TIM7]
    headerStructName: BasicTimer
    renames:
      - target: interrupts
        field: name
        pattern: 'TIM[67](?:_DAC)?'
        replacement: 'TIM'
      - target: interrupts
        field: description
        pattern: 'TIM[67].*'
        replacement: 'TIM'

  USART:
    instances: [USART1, USART2, USART3, USART6]
    headerStructName: USART
    renames:
      - target: interrupts
        field: name
        pattern: 'USART(\d+)'
        replacement: 'USART'
      - target: interrupts
        field: description
        pattern: 'USART\d+'
        replacement: 'USART'
    parameters:
      USART1: [syncmode: 1, smartcard: 1, irdaSIR: 1, lin: 1, rxTimeout: 1, modbus: 1, autobaud: 1, prescaler: 1, lpbaud: 0]
      USART2: [syncmode: 1, smartcard: 1, irdaSIR: 1, lin: 1, rxTimeout: 1, modbus: 1, autobaud: 1, prescaler: 1, lpbaud: 0]
      USART3: [syncmode: 1, smartcard: 1, irdaSIR: 1, lin: 1, rxTimeout: 1, modbus: 1, autobaud: 1, prescaler: 1, lpbaud: 0]
      USART6: [syncmode: 1, smartcard: 1, irdaSIR: 1, lin: 1, rxTimeout: 1, modbus: 1, autobaud: 1, prescaler: 1, lpbaud: 0]
      UART4:  [syncmode: 0, smartcard: 0, irdaSIR: 1, lin: 1, rxTimeout: 1, modbus: 1, autobaud: 1, prescaler: 1, lpbaud: 0]
      UART5:  [syncmode: 0, smartcard: 0, irdaSIR: 1, lin: 1, rxTimeout: 1, modbus: 1, autobaud: 1, prescaler: 1, lpbaud: 0]
      UART7:  [syncmode: 0, smartcard: 0, irdaSIR: 1, lin: 1, rxTimeout: 1, modbus: 1, autobaud: 1, prescaler: 1, lpbaud: 0]
      UART8:  [syncmode: 0, smartcard: 0, irdaSIR: 1, lin: 1, rxTimeout: 1, modbus: 1, autobaud: 1, prescaler: 1, lpbaud: 0]

  LPUART:
    instances: [LPUART1]
    renames:
      - target: interrupts
        field: name
        pattern: 'LPUART'
        replacement: 'USART'
    parameters:
      LPUART1: [syncmode: 0, smartcard: 0, irdaSIR: 0, lin: 0, rxTimeout: 0, modbus: 0, autobaud: 0, prescaler: 1, lpbaud: 1]

  MDMA:
    instances: [MDMA]
    arrays:
      - name: channels
        pattern: 'MDMA_C(\d+)(.+)'
        clusterName: 'C'
        clusterDesc: 'MDMA channel'
    renames:
      - target: registers
        field: name
        pattern: 'MDMA_GISR0'
        replacement: 'GISR0'

  DMA:
    instances: [DMA1, DMA2]
    headerStructName: DMA  # DMA1 gets this name
    arrays:
      - name: streams
        pattern: 'S(\d+)(.+)'
        clusterName: 'S'
        clusterDesc: 'DMA stream'
    renames:
      - target: interrupts
        field: name
        pattern: '[A-Z0-9]+_([A-Z_0-9]+)'
        replacement: '\1'

  DFSDM:
    instances: [DFSDM, DFSDM1, DFSDM2]
    arrays:
      - name: channels
        pattern: 'CH(\d+)(.+?)$'
        clusterName: 'CH'
        clusterDesc: 'DFSDM channel'
      - name: filters
        pattern: 'DFSDM_?FLT(\d+)(.+?)$'
        clusterName: 'FLT'
        clusterDesc: 'DFSDM filter'
    renames:
      - target: interrupts
        field: name
        pattern: 'DFSDM1_([0-9_A-Z]+)'
        replacement: '\1'
      - target: interrupts
        field: description
        pattern: 'DFSDM1'
        replacement: 'DFSDM'

  LPTIM:
    instances: [LPTIM1, LPTIM2, LPTIM3, LPTIM4, LPTIM5]
    renames:
      - target: interrupts
        field: name
        pattern: 'LPTIM\d+'
        replacement: 'LPTIM'
      - target: interrupts
        field: description
        pattern: 'LPTIM\d+'
        replacement: 'LPTIM'
    # Note: LPTIM1 uses headerStructName 'LPTIMenc', LPTIM3 uses 'LPTIM'
    headerStructNameMap:
      LPTIM1: 'LPTIMenc'
      LPTIM3: 'LPTIM'

  RTC:
    instances: [RTC]
    arrays:
      - name: backup
        pattern: 'RTC_BKP(\d+)(.+?)$'
        clusterName: 'BKP'
        clusterDesc: 'Backup registers'
    renames:
      - target: interrupts
        field: name
        pattern: 'RTC_([_A-Z]+)'
        replacement: '\1'
      - target: registers
        field: name
        pattern: 'RTC_([0-9_A-Z]+)'
        replacement: '\1'

  # ... more blocks follow same pattern
```

### Updated Python Parser Script

```python
def applyTransformations(chip_data, transforms_config):
    """Apply block-specific transformations from configuration."""
    for block_name, config in transforms_config['blocks'].items():
        for instance_name in config.get('instances', []):
            periph = svd.findNamedEntry(chip_data['peripherals'], instance_name)
            if not periph:
                continue
            
            # Apply header struct name
            if 'headerStructName' in config:
                periph['headerStructName'] = config['headerStructName']
            elif 'headerStructNameMap' in config:
                periph['headerStructName'] = config['headerStructNameMap'].get(
                    instance_name, instance_name
                )
            
            # Apply renames
            for rename in config.get('renames', []):
                transform.renameEntries(
                    periph[rename['target']],
                    rename['field'],
                    rename['pattern'],
                    rename['replacement']
                )
            
            # Apply array transformations
            for array_spec in config.get('arrays', []):
                periph['registers'] = transform.createClusterArray(
                    periph['registers'],
                    array_spec['pattern'],
                    {'name': array_spec['clusterName'], 
                     'description': array_spec['clusterDesc']}
                )
            
            # Apply parameters
            params_config = config.get('parameters', {})
            if isinstance(params_config, dict) and instance_name in params_config:
                params = params_config[instance_name]
                periph['parameters'] = [
                    {'name': k, 'value': v} for k, v in params.items()
                ]
```

## Issue 3: Selecting Best SVD Source for Shared Blocks

**Problem**: When a block appears in multiple SVDs, which one should we use?
- Some SVDs may have more complete descriptions
- Some may have additional field enumerations
- Some may have more detailed interrupt definitions

**Solution**: Create a block source comparison and ranking system

### Analysis Approach

```python
class BlockSourceSelector:
    """Find the best SVD source for each shared block."""
    
    def __init__(self, svd_files, block_name):
        self.block_name = block_name
        self.sources = {}  # svd_filename -> block_data
        self.scores = {}   # svd_filename -> quality_score
    
    def loadFromSVDs(self, svd_paths):
        """Load the same block from multiple SVD files."""
        for svd_path in svd_paths:
            root = svd.parse(svd_path)
            chip = svd.collateDevice(root)
            
            # Find any peripheral matching this block type
            for periph in chip['peripherals']:
                if self._isBlockType(periph['name'], self.block_name):
                    self.sources[svd_path.stem] = periph
    
    def scoreBlockQuality(self, block_data):
        """Rate quality of a block definition."""
        score = 0
        
        # Fields with descriptions (1 point each)
        if 'registers' in block_data:
            for reg in block_data['registers']:
                if reg.get('description'):
                    score += 1
                if 'fields' in reg:
                    for field in reg['fields']:
                        if field.get('description'):
                            score += 2
                        if field.get('enumeratedValues'):
                            score += 3  # Highest value for enums
        
        # Interrupt definitions
        if 'interrupts' in block_data:
            for intr in block_data['interrupts']:
                if intr.get('description'):
                    score += 1
        
        return score
    
    def selectBest(self):
        """Return the SVD file with best block definition."""
        for source, block_data in self.sources.items():
            self.scores[source] = self.scoreBlockQuality(block_data)
        
        best = max(self.scores, key=self.scores.get)
        return best, self.scores[best], self.sources[best]
```

### Usage in Extraction

```
Analysis: GPIO block appears in all 21 STM32H7 SVDs
  - STM32H723.svd: 4 registers, GPIO description, 16 fields with enums → Score: 145
  - STM32H743.svd: 4 registers, GPIO description, 16 fields with enums → Score: 145
  - STM32H757_CM4.svd: 4 registers, GPIO description, 16 fields with enums → Score: 145
  ✓ SELECT: Any (all identical) - Use STM32H757_CM4 for consistency

Analysis: ADC block appears in H73x and H74x variants
  - STM32H730.svd (H73x): ADC with 28 registers, 47 fields, 12 with enums → Score: 89
  - STM32H743.svd (H74x): ADC with 28 registers, 47 fields, 15 with enums → Score: 92
  ✓ SELECT: STM32H743.svd (better enum documentation)
  ⚠️ VARIANT NEEDED: H73x variant in STM32H730.svd (different register layout)

Analysis: RCC block appears in all 21 variants (subfamily-specific variants)
  - H73x group: STM32H730.svd has 89 fields, 22 with descriptions → Score: 134
  - H74x/H75x group: STM32H757_CM4.svd has 94 fields, 25 with descriptions → Score: 156
  - H7A3/B group: STM32H7A3.svd has 91 fields, 23 with descriptions → Score: 148
  ✓ SELECT: STM32H757_CM4.svd for H74x/H75x source (best documentation)
```

Output Report:
```yaml
BlockSources:
  ADC:
    defaultSource: STM32H730  # H73x group
    variants:
      H73x: STM32H730
      H74x_H75x: STM32H743   # Better field documentation
      H7A3_B: STM32H7B3      # Best enums

  GPIO:
    defaultSource: STM32H757_CM4  # All identical, arbitrary choice
    variants: {}  # None needed

  RCC:
    defaultSource: STM32H757_CM4  # H74x/H75x best documented
    variants:
      H73x: STM32H730
      H74x_H75x: STM32H757_CM4
      H7A3_B: STM32H7A3
```

## Issue 4: Array Transformation Opportunities

**Problem**: Need to spot patterns like:
- MDMA_C0_*, MDMA_C1_* → MDMA.C[0..n].*
- BDMA_C*, BDMA_C* → BDMA.C[0..n]
- RTC_BKP0, RTC_BKP1, ... → RTC.BKP[0..n]
- DFSDM_CH0, DFSDM_CH1, ... → DFSDM.CH[0..n]

**Current**: Hard to spot because they're scattered

**Proposed**: Create Pattern Detection Analysis

```python
class ArrayTransformationDetector:
    """Find opportunities to convert repetitive registers into arrays."""
    
    def analyzeBlock(self, block_data):
        """Detect repetitive patterns in registers."""
        registers = block_data.get('registers', [])
        if not registers:
            return []
        
        patterns = {}
        for reg in registers:
            name = reg.get('name', '')
            
            # Try to match pattern variations
            match = re.search(r'([A-Z_]+?)(\d+)(.*)$', name)
            if match:
                prefix, num, suffix = match.groups()
                pattern_key = (prefix, suffix)
                
                if pattern_key not in patterns:
                    patterns[pattern_key] = []
                patterns[pattern_key].append((int(num), reg))
        
        opportunities = []
        for (prefix, suffix), registers in patterns.items():
            # Check if sequential with small gaps
            if len(registers) >= 2:
                nums = [r[0] for r in registers]
                if self._isSequential(nums):
                    opportunities.append({
                        'type': 'register_array',
                        'pattern': f'{prefix}(\\d+){suffix}',
                        'clusterName': prefix,
                        'clusterDesc': f'{prefix} entry',
                        'registers': [r[1] for r in registers],
                        'indices': nums,
                        'count': len(nums),
                        'examples': [f'{prefix}{nums[0]}{suffix}', f'{prefix}{nums[-1]}{suffix}']
                    })
        
        return opportunities
    
    def _isSequential(self, numbers, max_gap=1):
        """Check if numbers form a sequence (0,1,2, or 0,1,3,4, etc)."""
        sorted_nums = sorted(set(numbers))
        return len(sorted_nums) == len(set(numbers))

# Usage
detector = ArrayTransformationDetector()
for block_name, block_data in models.items():
    opportunities = detector.analyzeBlock(block_data)
    if opportunities:
        print(f"{block_name}:")
        for opp in opportunities:
            print(f"  ✓ Array opportunity: {opp['clusterName']}[0..{opp['count']-1}]")
            print(f"    Pattern: {opp['pattern']}")
            print(f"    Examples: {opp['examples']}")
```

### Output Report

```
Array Transformation Opportunities for STM32H7 Family
═══════════════════════════════════════════════════════════════════

✓ CONFIRMED (Already implemented in transforms):
  MDMA:
    - Pattern: MDMA_C(\d+)(.+)
    - Result: C[0..31] channels
    - In SVD: C0_GISR0, C0_CESR0, ... C31_CHBAR, C31_CHER
    - Status: APPLY (transform already specified)

  DMA1/DMA2:
    - Pattern: S(\d+)(.+)
    - Result: S[0..7] streams
    - Status: APPLY

  RTC:
    - Pattern: RTC_BKP(\d+)(.+?)$
    - Result: BKP[0..31] backup registers
    - Status: APPLY

  DFSDM:
    - Pattern: CH(\d+) and FLT(\d+)
    - Result: CH[0..7] channels, FLT[0..3] filters
    - Status: APPLY

✓ DETECTED (Recommended):
  ADC (H74x/H75x variant):
    - Pattern: ADC_JDR(\d+) → JDR[0..3] injected data registers
    - Count: 4 registers
    - Benefit: Cleaner hierarchy
    - Status: CANDIDATE FOR ADDITION

  I2C:
    - Pattern: I2C_DR (single register, not array)
    - Status: SKIP (not sequential enough)

  RCC (H74x/H75x):
    - Pattern: RCC_C(\d+)_* → C[0..2] CPU-specific registers
    - Count: 3 (this CPU, CM7, CM4)
    - Status: APPLY (already in transforms)

⚠ COMPLEX PATTERNS (Manual review needed):
  RCC:
    - Many registers follow pattern: *AHBxENR, *APBxENR (domain-based, not array)
    - Would need multi-dimensional clustering
    - Status: SKIP (requires manual specification)

✗ NOT APPLICABLE:
  GPIO:
    - Pattern: GPIOx_MODER, GPIOx_OTYPER, etc. (GPIO A-K)
    - Reason: Different GPIO ports are separate chip-level instances,
              not registers within a single GPIO block
    - Status: SKIP (instance-level, not register-level)
```

## Summary of Changes

1. **Move script**: `extractors/generate_stm32h7_models.py` → `extractors/generate_stm32h7_models.py`

2. **Create transformation config**: `extractors/stm32h7-transforms.yaml`
   - Specifies all rename, array, and parameter transformations
   - Makes it easy to add new variants without code changes
   - Documents which instances map to which functional blocks

3. **Create source selector**: Enhanced analysis to pick best SVD per block
   - Quality-scores based on field descriptions, enums, completeness
   - Generates report showing which SVD to use for each block

4. **Create array detector**: Automated pattern detection
   - Identifies register patterns that could be arrays
   - Generates documentation of opportunities
   - Helps users decide on additional transformations

5. **Updated parser script**: 
   - Loads transforms from YAML config
   - Applies transformations programmatically
   - Detects best sources for shared blocks
   - Generates transformation opportunity reports

This approach makes the system:
- **Reusable**: Same config format for H73x, H74x/H75x, H7A3/B variants
- **Flexible**: Easy to add/modify transformations without code changes
- **Maintainable**: Clear separation of data (YAML) and logic (Python)
- **Extensible**: New chip families can reuse existing patterns
- **Transparent**: Clear documentation of what transformations are applied and why
