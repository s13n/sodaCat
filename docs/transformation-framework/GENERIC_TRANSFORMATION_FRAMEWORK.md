# Generic Transformation Framework

## Overview

The `generic_transform.py` module provides a **plugin-based, configuration-driven transformation system** that separates concerns and enables easy extension.

**Key Innovation:** Transformations are no longer hardcoded and called for every block. Instead:
1. Configuration specifies what transformations apply to each block
2. Engine only calls the transformations that are actually configured
3. New transformation types can be added by registering a function
4. No code changes needed to support new transformation types

---

## Architecture

### Three-Layer Design

```
Configuration Layer (YAML)
    ↓
    Specifies which transformations apply to each block
    (e.g., block_config has 'arrays' key → apply array transformation)
    
TransformationEngine
    ↓
    Reads configuration
    Dispatches to registered transformation functions
    Only calls transformations that appear in config
    
TransformationRegistry
    ↓
    Maintains mapping: {transformation_name: function}
    Built-in generic transformations (rename, array, etc.)
    Family-specific transformations (registered at startup)
```

### Transformation Types

#### Built-in Generic Transformations (MCU-family agnostic)

1. **`setHeaderStructName`** - Set the block type name
   ```yaml
   headerStructName: AdvCtrlTimer
   # or
   headerStructNameMap:
     TIM1: AdvCtrlTimer
     TIM2: GpTimer
   ```

2. **`renameFields`** - Normalize field names
   ```yaml
   renames:
     - target: fields
       field: name
       pattern: 'FIELD(\d+)_(.+)'
       replacement: '\2'
   ```

3. **`renameRegisters`** - Normalize register names
   ```yaml
   renames:
     - target: registers
       field: name
       pattern: 'S(\d+)(.+)'
       replacement: '\2'
   ```

4. **`renameInterrupts`** - Normalize interrupt names
   ```yaml
   renames:
     - target: interrupts
       field: name
       pattern: 'USART\d+_(.+)'
       replacement: '\1'
   ```

5. **`createArrays`** - Convert repetitive registers to cluster arrays
   ```yaml
   arrays:
     - name: streams
       pattern: 'S(\d+)(.+)'
       clusterName: 'S'
       clusterDesc: 'DMA stream'
       count: 8
   ```

6. **`setParameters`** - Add capability metadata
   ```yaml
   parameters:
     TIM2:
       wide: 1
       chan_max: 3
   ```

7. **`addFields`** - Add missing fields to registers
   ```yaml
   addFields:
     - registerName: RCC_D1CCIPR
       field:
         name: DSISRC
         bitOffset: 8
         bitWidth: 3
   ```

#### Family-Specific Transformations

Complex transformations specific to a MCU family go in separate modules:

```
parsers/stm32h7/
    └── stm32h7_transforms.py
        ├── def transform_rcc_cpu_clustering(block, config):
        └── def transform_quadspi_mapping(block, config):

parsers/nxp/
    └── imx_transforms.py
        ├── def transform_ccm_clock_gating(block, config):
        └── def transform_iomuxc_mux_selection(block, config):
```

These are auto-discovered and registered at startup.

---

## Usage

### Basic Usage

```python
from generic_transform import TransformationEngine

# 1. Create engine
engine = TransformationEngine(verbose=True)

# 2. Load configuration
config = load_yaml('stm32h7-transforms.yaml')

# 3. For each block instance, apply configured transformations
for instance_name in ['TIM2', 'TIM3', 'DMA1', ...]:
    block = chip['peripherals'][instance_name]
    block_config = config['blocks'][block_type]
    
    # Single call—engine figures out what to do
    engine.apply_transformations(block, instance_name, block_config)
```

### With Family-Specific Transformations

```python
from generic_transform import TransformationEngine, discover_family_transformations

# 1. Create engine
engine = TransformationEngine(verbose=True)

# 2. Register family-specific transformations
family_transforms = discover_family_transformations('parsers/stm32h7')
for name, func in family_transforms.items():
    engine.register_transformation(name, func)

# 3. Now both generic and family-specific transformations are available
# Apply as normal—engine handles the dispatch
engine.apply_transformations(block, instance_name, block_config)
```

### Adding a Custom Transformation

#### Step 1: Create Function in Family Folder

```python
# parsers/stm32h7/stm32h7_transforms.py

def transform_rcc_cpu_clustering(block: dict, config: dict) -> None:
    """
    Special handling for RCC: cluster CPU-specific registers.
    
    RCC has different registers visible per CPU (C0_*, C1_*, C2_*).
    This transform groups them into a clustered view.
    """
    from tools import svd, transform
    
    # Add missing fields
    d1ccipr = svd.findNamedEntry(block['registers'], 'D1CCIPR')
    if d1ccipr:
        d1ccipr['fields'].append({
            'name': 'DSISRC',
            'bitOffset': 8,
            'bitWidth': 3,
            'description': 'DSI kernel clock source'
        })
    
    # Clustering logic...
    block['registers'] = transform.createClusterArray(
        block['registers'],
        r"C(\d+)_(.+?)$",
        {'name': 'C', 'description': 'CPU-specific registers'}
    )
```

#### Step 2: Reference in Config

```yaml
# parsers/stm32h7-transforms.yaml

RCC:
  instances: [RCC]
  headerStructName: RCC
  
  # Reference the custom transformation
  specialHandling: rcc_cpu_clustering
  
  # Or if using old-style direct reference:
  customTransformations:
    - rcc_cpu_clustering
```

#### Step 3: Engine Auto-Discovers & Applies

```python
# At startup
engine = TransformationEngine()
family_transforms = discover_family_transformations('parsers/stm32h7')
for name, func in family_transforms.items():
    engine.register_transformation(name, func)
    # Now 'rcc_cpu_clustering' is available without code changes

# During processing
engine.apply_transformations(block, 'RCC', block_config)
# Engine sees config mentions it, calls the registered function automatically
```

---

## Configuration Format

### Complete Example

```yaml
blocks:
  GpTimer:
    description: General-purpose timer (16-bit or 32-bit)
    instances: [TIM2, TIM3, TIM4, TIM5]
    
    # Generic transformations (built-in)
    headerStructName: GpTimer
    
    parameters:
      TIM2:
        wide: 1        # 32-bit counter
        chan_max: 3    # 4 channels
    
    renames:
      - target: interrupts
        field: name
        pattern: 'TIM\d+_(.+)'
        replacement: '\1'
    
    # Special case: family-specific logic
    specialHandling: timer_channel_mapping
  
  RCC:
    description: Reset and clock control
    instances: [RCC]
    
    # Will be discovered and auto-registered
    specialHandling: rcc_cpu_clustering
  
  DMA:
    description: Direct memory access
    instances: [DMA1, DMA2]
    
    arrays:
      - name: streams
        pattern: 'S(\d+)(.+)'
        clusterName: 'S'
        clusterDesc: 'DMA stream'
        count: 8
```

---

## How the Engine Works

### 1. Configuration-Driven Dispatch

Instead of:
```python
# OLD: Hardcoded function calls for all blocks
for periph in chip['peripherals']:
    _apply_header_struct_name(periph, ...)
    _apply_renames(periph, ...)
    _apply_arrays(periph, ...)
    _apply_parameters(periph, ...)
    _apply_special_handling(periph, ...)
```

Now:
```python
# NEW: Only call transformations in configuration
engine.apply_transformations(block, instance_name, block_config)
# Engine internally:
# 1. Looks at keys in block_config
# 2. For each known transformation type:
#    - Check if it's configured for this block
#    - If yes, call the registered function
#    - If no, skip it
```

### 2. Transformation Discovery

```python
# Pseudo-code of what happens
def apply_transformations(block, instance_name, block_config):
    
    # For each registered transformation type
    for transform_name in registry.list_available():
        
        # Check if it's configured
        if transform_is_configured(transform_name, block_config):
            
            # Get the function
            func = registry.get(transform_name)
            
            # Call it (with instance_name for context-aware transforms)
            func(block, block_config, instance_name)
```

### 3. Logging

```python
engine = TransformationEngine(verbose=True)
engine.apply_transformations(block, 'TIM2', config)

# Output:
#   ✓ Applied: setHeaderStructName
#   ✓ Applied: renameInterrupts
#   ✓ Applied: setParameters
#   ⚠️  Transformation 'unknownType' not registered
#   ✓ Applied: rcc_cpu_clustering

# Or programmatically:
log = engine.get_transformation_log()
# [('setHeaderStructName', 'success'),
#  ('renameInterrupts', 'success'),
#  ('setParameters', 'success'),
#  ('rcc_cpu_clustering', 'success')]
```

---

## Benefits of This Design

### 1. **Extensibility**
Add a new transformation type by:
- Writing a function
- Registering it
- Done—no code changes elsewhere

### 2. **Clarity**
- Configuration shows what happens to each block
- No hidden assumptions
- Easy to audit

### 3. **Reusability**
- Generic transformations work for any MCU family
- Core framework in `tools/`
- Family-specific variants in `parsers/<family>/`

### 4. **Performance**
- Only call transformations that are configured
- Avoid unnecessary processing
- Better than calling all 5 functions for every block

### 5. **Maintainability**
- Transformation logic lives in functions (testable)
- Configuration lives in YAML (auditable)
- Clear separation of concerns

### 6. **Discoverability**
- `engine.list_available_transformations()` shows what's possible
- Auto-discovery of family-specific transformations
- Self-documenting system

---

## Comparison: Before vs. After

### Before (Hardcoded Approach)

**File:** parsers/STM32H757.py (401 lines)

```python
def apply_transformations(chip_data):
    for periph in chip_data['peripherals']:
        # Always call all 5 transformations for every peripheral
        _apply_header_struct_name(periph, ...)
        _apply_renames(periph, ...)                  # ← Calls even if no renames configured
        _apply_arrays(periph, ...)                   # ← Calls even if no arrays configured
        _apply_parameters(periph, ...)
        _apply_special_handling(periph, ...)
        
        # Everything hardcoded
        # To add new transformation type: add new function + call site
```

**Problems:**
- ❌ 5 functions called for every block, even if not needed
- ❌ Hardcoded logic spread across multiple functions
- ❌ Hard to add new transformation types
- ❌ Not reusable across MCU families
- ❌ 400+ lines per MCU variant

### After (Configuration-Driven Approach)

**File:** tools/generic_transform.py (500+ lines of flexible framework)

```python
engine = TransformationEngine()
engine.apply_transformations(block, instance_name, block_config)
# Engine internally:
# 1. Looks at block_config keys
# 2. Only calls transformations that are configured
# 3. Handles dispatch automatically
# 4. Supports custom transformations via registration
```

**Benefits:**
- ✅ Only call transformations in configuration
- ✅ Configuration-driven (YAML)
- ✅ Easy to add new transformation types (just register a function)
- ✅ Reusable framework across all MCU families
- ✅ Family-specific transforms in separate modules
- ✅ ~100 lines per MCU variant (vs 400+)

---

## Family-Specific Transformations

### File Organization

```
tools/
    └── generic_transform.py        ← Framework (MCU-agnostic)
        └── TransformationEngine
        └── TransformationRegistry
        └── Built-in transformations (rename, array, etc.)

parsers/
    ├── stm32h7-transforms.yaml     ← Configuration
    │
    ├── stm32h7_transforms.py       ← Family-specific (auto-discovered)
    │   ├── def transform_rcc_cpu_clustering(block, config)
    │   └── def transform_quadspi_special_mapping(block, config)
    │
    ├── stm32h7/                    ← Family variant folder (optional)
    │   └── stm32h7_transforms.py
    │
    ├── nxp_imx/                    ← Another family
    │   └── imx_transforms.py
    │       ├── def transform_ccm_clock_gating(block, config)
    │       └── def transform_iomuxc_mux_selection(block, config)
```

### Auto-Discovery

```python
# Finds all .py files in a folder
# Imports them and discovers transform_* functions
family_transforms = discover_family_transformations('parsers/stm32h7')
# Returns: {'rcc_cpu_clustering': <function>, 'quadspi_special_mapping': <function>}

# Register with engine
for name, func in family_transforms.items():
    engine.register_transformation(name, func)
```

---

## Testing

### Unit Testing a Transformation

```python
def test_rename_registers():
    block = {
        'name': 'DMA',
        'registers': [
            {'name': 'S0CR', 'addressOffset': 0x00},
            {'name': 'S1CR', 'addressOffset': 0x18},
        ]
    }
    
    config = {
        'renames': [
            {
                'target': 'registers',
                'field': 'name',
                'pattern': 'S(\d+)CR',
                'replacement': 'STREAM_\1_CR'
            }
        ]
    }
    
    engine = TransformationEngine()
    engine.apply_transformations(block, 'DMA', config)
    
    assert block['registers'][0]['name'] == 'STREAM_0_CR'
    assert block['registers'][1]['name'] == 'STREAM_1_CR'
```

### Integration Testing

```python
def test_stm32h7_extraction():
    engine = TransformationEngine()
    family_transforms = discover_family_transformations('parsers/stm32h7')
    for name, func in family_transforms.items():
        engine.register_transformation(name, func)
    
    config = load_yaml('parsers/stm32h7-transforms.yaml')
    
    # Test on actual SVD
    root = svd.parse('svd/STM32H757_CM4.svd')
    chip = svd.collateDevice(root)
    
    for block_name, block_config in config['blocks'].items():
        for instance_name in block_config.get('instances', []):
            block = svd.findNamedEntry(chip['peripherals'], instance_name)
            engine.apply_transformations(block, instance_name, block_config)
    
    # Verify expected transformations applied
    assert 'headerStructName' in chip['peripherals']['TIM2']
    assert len(chip['peripherals']['DMA1']['registers']) < 100  # Arrays applied
```

---

## Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Framework** | Monolithic per-variant | Generic + family-specific |
| **File Location** | parsers/STM32H757.py | tools/generic_transform.py + parsers/* |
| **Lines of Code** | 400+ per variant | ~100 per variant + reusable framework |
| **Adding Transform** | Modify parser code | Register a function |
| **Calling Pattern** | All-5-always | Only-what-configured |
| **Reusability** | Limited to one MCU | Across all MCU families |
| **Testing** | Integrated | Unit-testable functions |
| **Discoverability** | Try to read 400-line file | `engine.list_available_transformations()` |

---

## Next Steps

1. ✅ Create `tools/generic_transform.py`
2. ✅ Update `parsers/STM32H757_template.py` to use it
3. ⏳ Move family-specific transforms to `parsers/stm32h7_transforms.py`
4. ⏳ Update `parsers/generate_stm32h7_models.py` to use the engine
5. ⏳ Create unit tests for transformations
6. ⏳ Document available transformations in reference

