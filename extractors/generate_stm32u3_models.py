#!/usr/bin/env python3
"""
Extract and generate YAML models for all STM32U3 family members.
Creates functional block models and chip-level models automatically.
"""

import sys
import os
import tempfile
from pathlib import Path
from collections import defaultdict

# Add sodaCat tools to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))
import svd
import transform

# Define STM32U3 family information
STM32U3_FAMILIES = {
    'U37x': {
        'chips': ['STM32U375'],
        'cores': {'': None},  # Single core
    },
    'U38x': {
        'chips': ['STM32U385'],
        'cores': {'': None},
    },
}

# Peripheral blocks to extract
FUNCTIONAL_BLOCKS = frozenset({
    'ADC', 'ADC_Common', 'ADF', 'AES', 'CCB', 'COMP', 'CRC', 'CRS', 'DAC',
    'DBGMCU', 'EXTI', 'FDCAN', 'Flash', 'GPDMA', 'GPIO', 'HASH',
    'I2C', 'I3C', 'IWDG', 'LPTIM', 'LPUART', 'OCTOSPI', 'OPAMP',
    'PKA', 'PWR', 'RAMCFG', 'RCC', 'RNG', 'RTC',
    'SAES', 'SAI', 'SDMMC', 'SPI', 'SYSCFG',
    'TAMP', 'AdvCtrlTimer', 'GpTimer', 'BasicTimer',
    'TSC', 'USART', 'USB', 'VREFBUF', 'WWDG',
})

# Map SVD peripheral instance names to canonical block type names.
# Entries where canonical == instance name are omitted (handled by .get() default).
# None means the peripheral is skipped (ARM core internals, security shadows, etc.).
NAME_MAP = {
    'DLYBOS1': None,
    'DLYBSD1': None,
    'GTZC1_MPCBB1': None,
    'GTZC1_MPCBB2': None,
    'GTZC1_TZIC': None,
    'GTZC1_TZSC': None,
    'ICACHE': None,
    'SEC_ADC1': None,
    'SEC_ADC12': None,
    'SEC_ADC2': None,
    'SEC_ADF': None,
    'SEC_AES': None,
    'SEC_CCB': None,
    'SEC_COMP': None,
    'SEC_CRC': None,
    'SEC_CRS': None,
    'SEC_DAC': None,
    'SEC_DLYBOS1': None,
    'SEC_DLYBSD1': None,
    'SEC_ExTI': None,
    'SEC_FDCAN1': None,
    'SEC_FLASH': None,
    'SEC_GPDMA1': None,
    'SEC_GPIOA': None,
    'SEC_GPIOB': None,
    'SEC_GPIOC': None,
    'SEC_GPIOD': None,
    'SEC_GPIOE': None,
    'SEC_GPIOG': None,
    'SEC_GPIOH': None,
    'SEC_GTZC1_MPCBB1': None,
    'SEC_GTZC1_MPCBB2': None,
    'SEC_GTZC1_TZIC': None,
    'SEC_GTZC1_TZSC': None,
    'SEC_HASH': None,
    'SEC_I2C1': None,
    'SEC_I2C2': None,
    'SEC_I2C3': None,
    'SEC_I3C1': None,
    'SEC_I3C2': None,
    'SEC_ICACHE': None,
    'SEC_IWDG': None,
    'SEC_LPTIM1': None,
    'SEC_LPTIM2': None,
    'SEC_LPTIM3': None,
    'SEC_LPTIM4': None,
    'SEC_LPUART': None,
    'SEC_OCTOSPI': None,
    'SEC_OPAMP': None,
    'SEC_PKA': None,
    'SEC_PWR': None,
    'SEC_RAMCFG': None,
    'SEC_RCC': None,
    'SEC_RNG': None,
    'SEC_RTC': None,
    'SEC_SAES': None,
    'SEC_SAI1': None,
    'SEC_SDMMC1': None,
    'SEC_SPI1': None,
    'SEC_SPI2': None,
    'SEC_SPI3': None,
    'SEC_SYSCFG': None,
    'SEC_TAMP': None,
    'SEC_TIM1': None,
    'SEC_TIM15': None,
    'SEC_TIM16': None,
    'SEC_TIM17': None,
    'SEC_TIM2': None,
    'SEC_TIM3': None,
    'SEC_TIM4': None,
    'SEC_TIM6': None,
    'SEC_TIM7': None,
    'SEC_TSC': None,
    'SEC_UART4': None,
    'SEC_UART5': None,
    'SEC_USART1': None,
    'SEC_USART3': None,
    'SEC_USB': None,
    'SEC_USBSRAM': None,
    'SEC_VREFBUF': None,
    'SEC_WWDG': None,
    'USBSRAM': None,
    'ADC1': 'ADC',
    'ADC2': 'ADC',
    'ADC12': 'ADC_Common',
    'TIM1': 'AdvCtrlTimer',
    'TIM6': 'BasicTimer',
    'TIM7': 'BasicTimer',
    'ExTI': 'EXTI',
    'FDCAN1': 'FDCAN',
    'FLASH': 'Flash',
    'GPDMA1': 'GPDMA',
    'GPIOA': 'GPIO',
    'GPIOB': 'GPIO',
    'GPIOC': 'GPIO',
    'GPIOD': 'GPIO',
    'GPIOE': 'GPIO',
    'GPIOG': 'GPIO',
    'GPIOH': 'GPIO',
    'TIM15': 'GpTimer',
    'TIM16': 'GpTimer',
    'TIM17': 'GpTimer',
    'TIM2': 'GpTimer',
    'TIM3': 'GpTimer',
    'TIM4': 'GpTimer',
    'I2C1': 'I2C',
    'I2C2': 'I2C',
    'I2C3': 'I2C',
    'I3C1': 'I3C',
    'I3C2': 'I3C',
    'LPTIM1': 'LPTIM',
    'LPTIM2': 'LPTIM',
    'LPTIM3': 'LPTIM',
    'LPTIM4': 'LPTIM',
    'SDMMC1': 'SDMMC',
    'SPI1': 'SPI',
    'SPI2': 'SPI',
    'SPI3': 'SPI',
    'UART4': 'USART',
    'UART5': 'USART',
    'USART1': 'USART',
    'USART3': 'USART',
}


def process_chip(svd_root, chip_name):
    """Process a single chip SVD and extract functional blocks."""
    try:
        chip = svd.collateDevice(svd_root)
        blocks = {}
        chip_peripheral_refs = {}

        for periph in chip['peripherals']:
            periph_name = periph['name']
            block_type = NAME_MAP.get(periph_name, periph_name)

            if block_type is None:
                continue
            if block_type not in FUNCTIONAL_BLOCKS:
                continue

            chip_peripheral_refs[periph_name] = {
                'blockType': block_type,
                'baseAddress': periph.get('baseAddress'),
                'interrupts': [i['value'] for i in (periph.get('interrupts') or [])]
            }

            if block_type not in blocks:
                block_data = periph.copy()
                block_data.pop('baseAddress', None)
                block_data['name'] = block_type
                for intr in block_data.get('interrupts', []):
                    intr.pop('value', None)
                blocks[block_type] = block_data

        return blocks, chip_peripheral_refs, chip
    except Exception as e:
        print(f"Error processing {chip_name}: {e}")
        return {}, {}, {}


def save_yaml_model(model_dict, output_path):
    """Save a model dictionary as YAML."""
    from ruamel.yaml import YAML
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        yaml.dump(model_dict, f)
    print(f"  Generated: {output_path.relative_to(output_path.parent.parent)}")


def hash_block_structure(block_data):
    """Create a hash of a block's register structure for comparison."""
    import hashlib
    import json

    structure = {
        'registers': []
    }

    for reg in block_data.get('registers', []):
        reg_info = {
            'name': reg.get('name'),
            'offset': reg.get('addressOffset'),
            'size': reg.get('size'),
            'fields': []
        }
        for field in (reg.get('fields') or []):
            reg_info['fields'].append({
                'name': field.get('name'),
                'offset': field.get('bitOffset'),
                'width': field.get('bitWidth')
            })
        structure['registers'].append(reg_info)

    json_str = json.dumps(structure, sort_keys=True, indent=None)
    return hashlib.sha256(json_str.encode()).hexdigest()


def main():
    if len(sys.argv) < 3:
        print("Usage: generate_stm32u3_models.py <zip_path> <output_dir>")
        sys.exit(1)

    zip_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not zip_path.exists():
        print(f"Error: {zip_path} not found")
        sys.exit(1)

    print(f"Extracting STM32U3 models from {zip_path}")
    print(f"Output directory: {output_dir}\n")

    # ================================================================================
    # PASS 1: Collect blocks from all families
    # ================================================================================
    print(f"{'='*60}")
    print("PASS 1: Collecting blocks from all families")
    print(f"{'='*60}")

    all_blocks = defaultdict(lambda: defaultdict(list))

    for family_name, family_info in STM32U3_FAMILIES.items():
        print(f"\nProcessing {family_name} family...")

        for chip_name in family_info['chips']:
            try:
                svd_content = svd.extractFromZip(zip_path, chip_name)
                if svd_content is not None:
                    with tempfile.NamedTemporaryFile(mode='wb', suffix='.svd', delete=False) as tf:
                        tf.write(svd_content)
                        temp_svd = tf.name

                    try:
                        root = svd.parse(temp_svd)
                        blocks, _, _ = process_chip(root, chip_name)

                        for block_name, block_data in blocks.items():
                            block_hash = hash_block_structure(block_data)
                            all_blocks[block_name][family_name].append({
                                'hash': block_hash,
                                'data': block_data,
                                'chip': chip_name
                            })
                    finally:
                        os.unlink(temp_svd)

            except Exception as e:
                print(f"  ERROR processing {chip_name}: {e}")

    # ================================================================================
    # PASS 2: Analyze compatibility and generate models
    # ================================================================================
    print(f"\n{'='*60}")
    print("PASS 2: Analyzing compatibility and generating models")
    print(f"{'='*60}")

    common_blocks_dir = output_dir / 'U3'
    common_blocks_dir.mkdir(parents=True, exist_ok=True)

    common_count = 0
    family_specific_count = 0

    for block_name in sorted(all_blocks.keys()):
        block_families = all_blocks[block_name]

        families_present = set(block_families.keys())

        # Check if block is identical across all subfamilies that have it
        hashes = {block_families[f][0]['hash'] for f in families_present}

        if len(hashes) == 1:
            # Block is identical everywhere it appears -> common dir
            common_count += 1
            first_family = next(iter(families_present))
            block_data = block_families[first_family][0]['data']
            block_file = common_blocks_dir / f'{block_name}.yaml'
            save_yaml_model(block_data, block_file)
            print(f"  + {block_name:20} -> U3 (shared)")
            continue

        # Block differs between subfamilies -> subfamily-specific
        for family_name in STM32U3_FAMILIES:
            if family_name in families_present:
                family_specific_count += 1
                family_dir = output_dir / 'U3' / family_name
                family_dir.mkdir(parents=True, exist_ok=True)

                block_data = block_families[family_name][0]['data']
                block_file = family_dir / f'{block_name}.yaml'
                save_yaml_model(block_data, block_file)

    # ================================================================================
    # Summary
    # ================================================================================
    print(f"\n{'='*60}")
    print(f"Generation Summary:")
    print(f"  Common blocks (U3):     {common_count}")
    print(f"  Family-specific blocks:        {family_specific_count}")
    print(f"  Total block types processed:   {len(all_blocks)}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
