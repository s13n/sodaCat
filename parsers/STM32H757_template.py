#!/usr/bin/env python3
"""
Updated STM32H757.py using generic transformation framework.

This demonstrates how to refactor the existing parser to use
external transformation configuration (YAML) with a config-driven,
plugin-based transformation system.

The new approach:
1. Load transformation config from stm32h7-transforms.yaml
2. Use TransformationEngine for config-driven transformation dispatch
3. Only call transformations that are actually configured
4. Easy to add new transformation types (just register a function)
5. Family-specific transformations in separate modules (if needed)
6. Support multiple H7 variant families with same generic code
"""

import sys
import os
from pathlib import Path
from ruamel.yaml import YAML

# Add sodaCat tools to path
p = os.path.abspath("./tools")
sys.path.append(p)
import svd
import transform
from generic_transform import TransformationEngine, discover_family_transformations

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION & PATHS
# ═══════════════════════════════════════════════════════════════════════════

OUTPUT_DIR = Path("./models/ST/H757")
TRANSFORMS_CONFIG = Path("./parsers/stm32h7-transforms.yaml")
SVD_FILE = './svd/STM32H757_CM4.svd'
HEADER = "# Created from STM32H757_CM4.svd (Rev 1.9)\n"

# For H73x, H74x_H75x, H7A3_B, would use their respective configs
# TRANSFORMS_CONFIG = Path("./parsers/stm32h7-transforms.yaml")
# TRANSFORMS_CONFIG_H73x = Path("./parsers/stm32h7-transforms-h73x.yaml")
# (These could be combined or split depending on variant differences)

# Transformation engine (singleton)
TRANSFORM_ENGINE = TransformationEngine(verbose=True)

# ═══════════════════════════════════════════════════════════════════════════
# LOAD TRANSFORMATIONS FROM CONFIG
# ═══════════════════════════════════════════════════════════════════════════

def load_transforms_config(config_path):
    """Load transformation configuration from YAML file."""
    yaml = YAML()
    with open(config_path, 'r') as f:
        return yaml.load(f)


def register_family_specific_transformations(engine: TransformationEngine, family_folder: str = 'parsers/stm32h7'):
    """Register any family-specific transformations.
    
    Family-specific transformations are discovered and loaded from a folder.
    This allows custom logic without modifying the generic framework.
    
    Example: Handle RCC block's CPU-specific register clustering (very H7-specific).
    """
    try:
        family_transforms = discover_family_transformations(family_folder)
        for transform_name, transform_func in family_transforms.items():
            engine.register_transformation(transform_name, transform_func)
            print(f"  Registered family-specific: {transform_name}")
    except Exception as e:
        print(f"  Note: No family-specific transformations found ({e})")


def apply_block_transformations(chip_data, transforms_config, engine: TransformationEngine):
    """
    Apply all configurations transformations to the chip data.
    
    This is the key simplification: instead of calling 5 separate functions
    for every block, we now:
    1. Look at what's configured for this block
    2. Only call those transformations
    3. Let the engine handle the dispatch
    
    Args:
        chip_data: Parsed chip data structure
        transforms_config: Configuration from YAML
        engine: TransformationEngine instance
    """
    blocks = transforms_config.get('blocks', {})
    
    for block_name, block_config in blocks.items():
        for instance_name in block_config.get('instances', []):
            periph = svd.findNamedEntry(chip_data['peripherals'], instance_name)
            if not periph:
                continue
            
            print(f"  Transforming {instance_name} → {block_name}...")
            
            # SINGLE CALL: Engine decides what transformations to apply
            # based on what's in block_config
            engine.apply_transformations(periph, instance_name, block_config)

# ═══════════════════════════════════════════════════════════════════════════
# MAIN PARSING FLOW
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("STM32H757_CM4 Model Generation")
    print(f"Input SVD: {SVD_FILE}")
    print(f"Transforms: {TRANSFORMS_CONFIG}")
    print()
    
    # 1. Initialize transformation engine
    print("Initializing transformation engine...")
    register_family_specific_transformations(TRANSFORM_ENGINE)
    print(f"  Available transformations: {', '.join(TRANSFORM_ENGINE.list_available_transformations())}")
    print()
    
    # 2. Load transformations config
    print("Loading transformation configuration...")
    transforms = load_transforms_config(TRANSFORMS_CONFIG)
    print(f"  Loaded config for {len(transforms['blocks'])} blocks")
    print()
    
    # 3. Parse SVD
    print("Parsing SVD file...")
    root = svd.parse(SVD_FILE)
    chip = svd.collateDevice(root)
    print(f"  Found {len(chip['peripherals'])} peripherals")
    print()
    
    # 4. Apply transformations
    print("Applying transformations (config-driven, only registered types)...")
    apply_block_transformations(chip, transforms, TRANSFORM_ENGINE)
    print()
    
    # 5. Post-transformation cleanup (unchanged from original)
    print("Post-transformation processing...")
    
    # Collect instances and models
    interrupts = svd.collectInterrupts(chip['peripherals'], chip['interruptOffset'])
    models, instances = svd.collectModelsAndInstances(chip['peripherals'])
    
    # Add NVIC
    nvic = {
        'name': 'NVIC',
        'model': 'NVIC',
        'description': 'Nested Vectored Interrupt Controller',
        'baseAddress': 3758153984,
        'parameters': [
            {'name': 'interrupts', 'value': len(interrupts)},
            {'name': 'priobits', 'value': 4}
        ]
    }
    chip['peripherals'].append(nvic)
    
    # Restructure
    del chip['peripherals']
    chip['instances'] = instances
    chip['interrupts'] = interrupts
    
    # Filter out unwanted instances
    instSet = frozenset({
        'MDMA', 'DMA1', 'DMA2', 'BDMA', 'DMAMUX1', 'DMAMUX2', 'RCC', 'ART', 'DBGMCU', 'Flash',
        'ADC1', 'ADC2', 'ADC3', 'ADC3_Common', 'ADC12_Common', 'DAC', 'EXTI', 'SYSCFG', 'NVIC',
        'I2C1', 'I2C2', 'I2C3', 'I2C4', 'SAI1', 'SAI2', 'SAI3', 'SAI4', 'SPDIFRX',
        'TIM1', 'TIM2', 'TIM3', 'TIM4', 'TIM5', 'TIM6', 'TIM7', 'TIM8', 'TIM12', 'TIM13', 'TIM14', 'TIM15', 'TIM16', 'TIM17',
        'LPTIM1', 'LPTIM2', 'LPTIM3', 'LPTIM4', 'LPTIM5',
        'GPIOA', 'GPIOB', 'GPIOC', 'GPIOD', 'GPIOE', 'GPIOF', 'GPIOG', 'GPIOH', 'GPIOI', 'GPIOJ', 'GPIOK',
        'USART1', 'USART2', 'USART3', 'UART4', 'UART5', 'USART6', 'UART7', 'UART8', 'LPUART1',
        'QUADSPI', 'OPAMP', 'DFSDM', 'SPI1', 'SPI2', 'SPI3', 'SPI4', 'SPI5', 'SPI6', 'RTC', 'FMC', 'PWR'
    })
    chip['instances'] = {k: v for k, v in instances.items() if k in instSet}
    
    # 6. Output
    print("Generating output...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    modelSet = set(transforms['blocks'].keys())
    for name, model in models.items():
        if name in modelSet:
            svd.dumpModel(model, OUTPUT_DIR / name, HEADER)
    
    svd.dumpDevice(chip, OUTPUT_DIR / 'H757', HEADER)
    print(f"  Generated {len([n for n in models if n in modelSet])} block models")
    print(f"  Generated 1 chip model (H757)")
    print()
    
    print("✓ Complete!")

if __name__ == '__main__':
    main()
