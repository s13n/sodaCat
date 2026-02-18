# Using and Extending the Transformation System

## Quick Start

### For Users: Run Extraction with New Framework

```python
from tools.generic_transform import TransformationEngine, discover_family_transformations
from ruamel.yaml import YAML
import tools.svd as svd

# 1. Create transformation engine
engine = TransformationEngine(verbose=True)

# 2. Auto-discover and register family-specific transformations
family_transforms = discover_family_transformations('extractors/stm32h7')
for name, func in family_transforms.items():
    engine.register_transformation(name, func)

# 3. Load configuration
yaml = YAML()
with open('extractors/stm32h7-transforms.yaml') as f:
    config = yaml.load(f)

# 4. Parse SVD and apply transformations
root = svd.parse('svd/STM32H757_CM4.svd')
chip = svd.collateDevice(root)

# 5. For each block instance, apply configured transformations
blocks_config = config.get('blocks', {})
for block_name, block_config in blocks_config.items():
    for instance_name in block_config.get('instances', []):
        block = svd.findNamedEntry(chip['peripherals'], instance_name)
        if block:
            # Single call—engine handles everything
            engine.apply_transformations(block, instance_name, block_config)
```

---

## For Developers: Adding a New Transformation Type

### Scenario 1: Generic Transformation (Works for Any MCU)

**Example:** Add an `addDescriptions` transformation that enhances field descriptions

#### Step 1: Add Function to `tools/generic_transform.py`

```python
# At the end of TransformationRegistry class, add new method:

class TransformationRegistry:
    # ... existing code ...
    
    @staticmethod
    def _transform_add_descriptions(block: dict, config: dict) -> None:
        """Enhance field descriptions with additional context.
        
        Configuration format (in YAML):
          addDescriptions:
            - registerName: CR1
              field: ENABLE
              description_append: "(Set to 1 to enable peripheral)"
        """
        descriptions_config = config.get('addDescriptions', [])
        
        for desc_spec in descriptions_config:
            reg_name = desc_spec['registerName']
            field_name = desc_spec['field']
            suffix = desc_spec['description_append']
            
            for reg in block.get('registers', []):
                if reg['name'] == reg_name:
                    for field in reg.get('fields', []):
                        if field['name'] == field_name:
                            if 'description' not in field:
                                field['description'] = ''
                            field['description'] += ' ' + suffix
```

#### Step 2: Register in TransformationRegistry.__init__

```python
def _register_builtin_transformations(self):
    # ... existing registrations ...
    self.register('addDescriptions', self._transform_add_descriptions)
```

#### Step 3: Use in Configuration

```yaml
# In stm32h7-transforms.yaml or any config file

ADC:
  instances: [ADC1, ADC2, ADC3]
  
  addDescriptions:
    - registerName: CR1
      field: ENABLE
      description_append: "(Set to 1 to enable the ADC)"
```

#### Step 4: That's It!

The engine will automatically discover and call `addDescriptions` when present in config.

---

### Scenario 2: Family-Specific Transformation (STM32H7 Only)

**Example:** Add RCC bus domain enumeration

#### Step 1: Add Function to `extractors/stm32h7_transforms.py`

```python
# In extractors/stm32h7_transforms.py

def transform_rcc_bus_domain_enums(block: dict, config: dict) -> None:
    """
    Add enumeration values for RCC clock source selections per bus domain.
    
    STM32H7 RCC has different clock sources depending on the bus domain
    (AHB, APB1, APB2, APB4). This transformation documents which sources
    are available for which domains.
    
    Configuration example:
        RCC:
          instances: [RCC]
          rccBusDomainEnums: true
    """
    
    print(f"    → Adding RCC bus domain enumerations...")
    
    # Define which clock sources are available per domain
    domain_sources = {
        'D1CCIPR': {  # Domain 1 Clock Configuration
            'HSEL': ['HSI', 'HSE', 'PLL1'],
            'RTCSRC': ['HSI', 'LSE', 'LSI', 'HSE']
        },
        'D2CCIP1R': {  # Domain 2 Clock Config Part 1
            'SAI1SRC': ['PLL1', 'PLL2', 'PLL3', 'I2S_CKIN'],
        }
    }
    
    # Apply enumerations to registers and fields
    for reg_name, field_enums in domain_sources.items():
        reg = svd.findNamedEntry(block.get('registers', []), reg_name)
        if reg:
            for field_name, enum_values in field_enums.items():
                field = next(
                    (f for f in reg.get('fields', []) if f['name'] == field_name),
                    None
                )
                if field:
                    field['enumeratedValues'] = {
                        'name': f'{reg_name}_{field_name}_Sources',
                        'description': f'Clock sources for {field_name}',
                        'enumeratedValue': [
                            {'name': src, 'value': i}
                            for i, src in enumerate(enum_values)
                        ]
                    }
    
    print(f"    → RCC bus domain enumerations complete")
```

#### Step 2: Update Configuration

```yaml
# In stm32h7-transforms.yaml

RCC:
  instances: [RCC]
  headerStructName: RCC
  
  # Both generic and family-specific transformations
  rccBusDomainEnums: true
  specialHandling: rcc_cpu_clustering
```

#### Step 3: Auto-Discovery Handles Registration

When you call:
```python
family_transforms = discover_family_transformations('extractors/stm32h7')
for name, func in family_transforms.items():
    engine.register_transformation(name, func)
```

It automatically finds `transform_rcc_bus_domain_enums` and registers it as `rcc_bus_domain_enums`.

---

### Scenario 3: Family-Specific with Custom Logic

**Example:** Handle ARM CMSIS-CORE vector table for a specific processor

#### Step 1: Create Specialized Function

```python
# In extractors/nxp/imx_transforms.py (for a different MCU family)

def transform_nvic_cmsis_core_vectors(block: dict, config: dict) -> None:
    """
    NVIC configuration for ARM CMSIS-CORE compatibility.
    
    This transformation ensures NVIC register layout matches
    arm_cm7.h definitions from CMSIS.
    
    This is NVIC-specific for a particular ARM Cortex version.
    Different processor families might need different arrangements.
    """
    
    # Add CMSIS-CORE-compatible field to NVIC
    # (Implementation details specific to the processor)
    pass
```

#### Step 2: Use Only for Specific Variants

```python
# In a variant-specific main() function

import importlib.util

# Load this transformation function
spec = importlib.util.spec_from_file_location(
    'custom_transforms', 
    'extractors/cortex_m7_transforms.py'
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Register only if needed for this MCU
engine.register_transformation(
    'nvic_cmsis_core_vectors',
    module.transform_nvic_cmsis_core_vectors
)
```

---

## For Architects: Creating a New MCU Family

### Directory Structure for New MCU Family (e.g., NXP i.MX)

```
extractors/
├── stm32h7-transforms.yaml
├── stm32h7_transforms.py
│
├── imx-transforms.yaml              ← New family config
└── imx_transforms.py                ← New family transformations
    ├── transform_ccm_clock_gating
    ├── transform_iomuxc_pad_mapping
    └── transform_flexram_configuration
```

### Creating Family Transformations for i.MX

```python
# extractors/imx_transforms.py

def transform_ccm_clock_gating(block: dict, config: dict) -> None:
    """CCM (Clock Control Module) specific logic for i.MX."""
    pass

def transform_iomuxc_pad_mapping(block: dict, config: dict) -> None:
    """IOMUXC (I/O Multiplexer Control) pad configuration."""
    pass

def transform_flexram_configuration(block: dict, config: dict) -> None:
    """FlexRAM flexible memory layout configuration."""
    pass
```

### Configuration for i.MX

```yaml
# extractors/imx-transforms.yaml

blocks:
  CCM:
    description: Clock Control Module
    instances: [CCM]
    headerStructName: CCM
    ccmClockGating: true
  
  IOMUXC:
    description: I/O Multiplexer Control
    instances: [IOMUXC]
    iomuxcPadMapping: true
  
  FlexRAM:
    description: Flexible RAM Configuration
    instances: [FLEXRAM]
    flexramConfiguration: true
```

### Running Extraction for i.MX

```python
# extractors/generate_imx_models.py

engine = TransformationEngine()

# Auto-discover i.MX-specific transformations
imx_transforms = discover_family_transformations('parsers')  # Finds imx_transforms.py
for name, func in imx_transforms.items():
    if '_ccm_' in name or '_imx' in name:  # Filter to i.MX only
        engine.register_transformation(name, func)

# Load configuration and apply
config = load_yaml('extractors/imx-transforms.yaml')
# ... rest of extraction ...
```

---

## Testing Your Transformations

### Unit Testing

```python
# tests/test_transformations.py

import unittest
from tools.generic_transform import TransformationEngine

class TestTransformations(unittest.TestCase):
    
    def setUp(self):
        self.engine = TransformationEngine()
    
    def test_rename_registers(self):
        """Test that register renaming works correctly."""
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
                    'pattern': 'S(\d+)',
                    'replacement': 'STREAM_\1'
                }
            ]
        }
        
        self.engine.apply_transformations(block, 'DMA', config)
        
        self.assertEqual(block['registers'][0]['name'], 'STREAM_0CR')
        self.assertEqual(block['registers'][1]['name'], 'STREAM_1CR')
    
    def test_set_parameters_per_instance(self):
        """Test that instance-specific parameters are applied."""
        block = {'name': 'Timer'}
        
        config = {
            'parameters': {
                'TIM2': {'wide': 1, 'channels': 4},
                'TIM3': {'wide': 0, 'channels': 4}
            }
        }
        
        self.engine.apply_transformations(block, 'TIM2', config)
        params = {p['name']: p['value'] for p in block.get('parameters', [])}
        
        self.assertEqual(params.get('wide'), 1)
        self.assertEqual(params.get('channels'), 4)
        
        # Different instance, different parameters
        block2 = {'name': 'Timer'}
        self.engine.apply_transformations(block2, 'TIM3', config)
        params2 = {p['name']: p['value'] for p in block2.get('parameters', [])}
        
        self.assertEqual(params2.get('wide'), 0)

if __name__ == '__main__':
    unittest.main()
```

### Integration Testing

```python
def test_stm32h7_complete_extraction():
    """Test complete STM32H7 extraction pipeline."""
    
    engine = TransformationEngine()
    
    # Register family transformations
    import parsers.stm32h7_transforms as stm32h7
    import inspect
    
    for name, obj in inspect.getmembers(stm32h7):
        if name.startswith('transform_') and callable(obj):
            transform_name = name[len('transform_'):]
            engine.register_transformation(transform_name, obj)
    
    # Load config
    yaml = YAML()
    with open('extractors/stm32h7-transforms.yaml') as f:
        config = yaml.load(f)
    
    # Parse SVD
    import tools.svd as svd
    root = svd.parse('svd/STM32H757_CM4.svd')
    chip = svd.collateDevice(root)
    
    # Apply transformations
    blocks_config = config.get('blocks', {})
    transform_count = 0
    
    for block_name, block_config in blocks_config.items():
        for instance_name in block_config.get('instances', []):
            block = svd.findNamedEntry(chip['peripherals'], instance_name)
            if block:
                engine.apply_transformations(block, instance_name, block_config)
                transform_count += 1
    
    # Verify transformations were applied
    assert transform_count > 0, "No transformations were applied"
    
    # Verify specific transformations
    tim2 = svd.findNamedEntry(chip['peripherals'], 'TIM2')
    assert 'headerStructName' in tim2, "headerStructName not set"
    assert tim2['headerStructName'] == 'GpTimer', "Wrong headerStructName"
    
    # Verify arrays were created
    dma1 = svd.findNamedEntry(chip['peripherals'], 'DMA1')
    has_cluster = any(
        '[%s]' in reg.get('name', '')
        for reg in dma1.get('registers', [])
    )
    assert has_cluster, "DMA clusters not created"
    
    print("✓ Complete extraction test passed")
```

---

## Troubleshooting

### Issue: Transformation Not Applied

**Symptom:** You added a configuration key, but transformation didn't run.

**Checklist:**
1. Is the transformation type registered?
   ```python
   print(engine.list_available_transformations())
   ```
2. Does the configuration key match the transformation name?
   - Config: `renames:` → Transformation: `renameFields`, `renameRegisters`, or `renameInterrupts`?
   - Config: `arrays:` → Transformation: `createArrays`?
3. Is the configuration in the right block?
   ```yaml
   blocks:
     MyBlock:
       renames:  # ← Must be here, not at top level
   ```

### Issue: Custom Transform Function Not Found

**Symptom:** `"Transformation 'my_custom_transform' not registered"`

**Solution:**
1. Verify function exists in `extractors/stm32h7_transforms.py`
2. Function must be named `transform_<name>` (correct format for auto-discovery)
3. Explicitly register if not using auto-discovery:
   ```python
   from parsers.stm32h7_transforms import transform_my_custom_transform
   engine.register_transformation('my_custom_transform', transform_my_custom_transform)
   ```

### Issue: Instance Parameter Not Applied

**Symptom:** Parameters not set for a specific instance.

**Diagnosis:**
```python
# Check the configuration format
config = {
    'parameters': {
        'TIM2': {'wide': 1},    # ← Correct: instance-specific dict
        'TIM3': {'wide': 0}
    }
}

# vs

config = {
    'parameters': {             # ← Wrong: flat dict applies to all
        'wide': 1,
        'channels': 4
    }
}
```

---

## Best Practices

### 1. Keep Transformations Focused
Each transformation should do one thing well:
```python
# ✓ Good: Single responsibility
def transform_rename_fields(block, config):
    """Rename field names only."""

# ✗ Bad: Mixing concerns
def transform_fix_block(block, config):
    """Rename, add arrays, set parameters..."""
```

### 2. Add Documentation
Every transformation should have clear docs:
```python
def transform_my_feature(block: dict, config: dict) -> None:
    """
    Short description.
    
    Longer explanation of what this does and why.
    
    Configuration example (in YAML):
        MyBlock:
          myFeature: true
          myFeatureConfig:
            param1: value1
    
    Side effects:
        - Modifies block in-place
        - Adds parameters to block if not present
    """
```

### 3. Fail Gracefully
Don't crash if configuration is missing or incomplete:
```python
def transform_something(block: dict, config: dict) -> None:
    # Check for required configuration
    my_config = config.get('myFeatureConfig')
    if not my_config:
        print("  (Skipping: no myFeatureConfig)")
        return
    
    # Handle missing required fields
    param1 = my_config.get('param1')
    if not param1:
        print("  ⚠️  myFeatureConfig missing 'param1'")
        return
```

### 4. Log Progress
Users want to know what's happening:
```python
def transform_something(block: dict, config: dict) -> None:
    block_name = block.get('name', 'Unknown')
    print(f"    → Setting up {block_name}...")
    
    # ... do work ...
    
    print(f"    → {block_name} configuration complete")
```

### 5. Validate After Transformation
Check that your transformation actually did something:
```python
def transform_something(block: dict, config: dict) -> None:
    # ... apply transformation ...
    
    # Verify it worked
    if 'myField' not in block:
        print(f"    ⚠️  Transformation may have failed")
```

---

## Summary

| Task | Where | How |
|------|-------|-----|
| Create generic transformation | `tools/generic_transform.py` | Add method to `TransformationRegistry` |
| Create family-specific transformation | `extractors/<family>_transforms.py` | Add `def transform_<name>(block, config)` function |
| Use transformation | `<family>-transforms.yaml` | Add configuration key matching transformation name |
| Register transformation | Code | Automatic via `discover_family_transformations()` or manual `register_transformation()` |
| Test transformation | `tests/` | Unit tests + integration tests |

---

## Examples

- **[GENERIC_TRANSFORMATION_FRAMEWORK.md](GENERIC_TRANSFORMATION_FRAMEWORK.md)** - Complete framework documentation
- **[extractors/STM32H757_template.py](extractors/STM32H757_template.py)** - Using the engine
- **[extractors/stm32h7_transforms.py](extractors/stm32h7_transforms.py)** - Family-specific transformations
- **[extractors/stm32h7-transforms.yaml](extractors/stm32h7-transforms.yaml)** - Configuration examples

