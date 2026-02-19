#!/usr/bin/env python3
"""
Extract and generate YAML models for all STM32L4+ family members.
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

# Define STM32L4+ family information
STM32L4P_FAMILIES = {
    'L4Px_L4Qx': {
        'chips': ['STM32L4P5', 'STM32L4Q5'],
        'cores': {'': None},
    },
    'L4Rx_L4Sx': {
        'chips': ['STM32L4R5', 'STM32L4R7', 'STM32L4R9', 'STM32L4S5', 'STM32L4S7', 'STM32L4S9'],
        'cores': {'': None},
    },
}

# Peripheral blocks to extract
FUNCTIONAL_BLOCKS = frozenset({
    'ADC', 'ADC_Common', 'AES', 'bxCAN', 'COMP', 'CRC', 'CRS', 'DAC',
    'DBGMCU', 'DCMI', 'DFSDM', 'DMA', 'DMA2D', 'DMAMUX', 'DSI',
    'EXTI', 'Flash', 'FMC', 'GFXMMU', 'GPIO', 'HASH', 'I2C', 'IWDG',
    'LPTIM', 'LPUART', 'LTDC', 'OCTOSPI', 'OPAMP',
    'OTG_FS_DEVICE', 'OTG_FS_GLOBAL', 'OTG_FS_HOST', 'OTG_FS_PWRCLK',
    'PWR', 'RCC', 'RNG', 'RTC', 'SAI', 'SDMMC', 'SPI',
    'SWPMI', 'SYSCFG', 'AdvCtrlTimer', 'GpTimer', 'BasicTimer',
    'TSC', 'USART', 'VREFBUF', 'WWDG',
})

# Map SVD peripheral instance names to canonical block type names.
# Entries where canonical == instance name are omitted (handled by .get() default).
# None means the peripheral is skipped (ARM core internals, security shadows, etc.).
NAME_MAP = {
    'FIREWALL': None,
    'OCTOSPIM': None,
    'TIM1': 'AdvCtrlTimer',
    'TIM8': 'AdvCtrlTimer',
    'TIM6': 'BasicTimer',
    'TIM7': 'BasicTimer',
    'DFSDM1': 'DFSDM',
    'DMA1': 'DMA',
    'DMA2': 'DMA',
    'DMAMUX1': 'DMAMUX',
    'FLASH': 'Flash',
    'GPIOA': 'GPIO',
    'GPIOB': 'GPIO',
    'GPIOC': 'GPIO',
    'GPIOD': 'GPIO',
    'GPIOE': 'GPIO',
    'GPIOF': 'GPIO',
    'GPIOG': 'GPIO',
    'GPIOH': 'GPIO',
    'GPIOI': 'GPIO',
    'TIM15': 'GpTimer',
    'TIM16': 'GpTimer',
    'TIM17': 'GpTimer',
    'TIM2': 'GpTimer',
    'TIM3': 'GpTimer',
    'TIM4': 'GpTimer',
    'TIM5': 'GpTimer',
    'I2C1': 'I2C',
    'I2C2': 'I2C',
    'I2C3': 'I2C',
    'I2C4': 'I2C',
    'LPTIM1': 'LPTIM',
    'LPTIM2': 'LPTIM',
    'LPUART1': 'LPUART',
    'LTCD': 'LTDC',
    'OCTOSPI1': 'OCTOSPI',
    'OCTOSPI2': 'OCTOSPI',
    'SAI1': 'SAI',
    'SAI2': 'SAI',
    'SDMMC1': 'SDMMC',
    'SDMMC2': 'SDMMC',
    'SPI1': 'SPI',
    'SPI2': 'SPI',
    'SPI3': 'SPI',
    'SWPMI1': 'SWPMI',
    'UART4': 'USART',
    'UART5': 'USART',
    'USART1': 'USART',
    'USART2': 'USART',
    'USART3': 'USART',
    'CAN1': 'bxCAN',
}


def extract_svd_from_zip(zip_path, svd_filename):
    """Extract a single SVD from the zip package."""
    import zipfile
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            svd_path = f'STM32L4+_svd_V1.6/{svd_filename}.svd'
            return zf.read(svd_path)
    except Exception as e:
        print(f"Error extracting {svd_filename}: {e}")
        return None


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
        print("Usage: generate_stm32l4plus_models.py <zip_path> <output_dir>")
        sys.exit(1)

    zip_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not zip_path.exists():
        print(f"Error: {zip_path} not found")
        sys.exit(1)

    print(f"Extracting STM32L4+ models from {zip_path}")
    print(f"Output directory: {output_dir}\n")

    print(f"{'='*60}")
    print("PASS 1: Collecting blocks from all families")
    print(f"{'='*60}")

    all_blocks = defaultdict(lambda: defaultdict(list))

    for family_name, family_info in STM32L4P_FAMILIES.items():
        print(f"\nProcessing {family_name} family...")

        for chip_name in family_info['chips']:
            try:
                svd_content = extract_svd_from_zip(zip_path, chip_name)
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

    print(f"\n{'='*60}")
    print("PASS 2: Analyzing compatibility and generating models")
    print(f"{'='*60}")

    common_blocks_dir = output_dir / 'L4P'
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
            print(f"  + {block_name:20} -> L4P (shared)")
            continue

        # Block differs between subfamilies -> subfamily-specific
        for family_name in STM32L4P_FAMILIES:
            if family_name in families_present:
                family_specific_count += 1
                family_dir = output_dir / 'L4P' / family_name
                family_dir.mkdir(parents=True, exist_ok=True)

                block_data = block_families[family_name][0]['data']
                block_file = family_dir / f'{block_name}.yaml'
                save_yaml_model(block_data, block_file)

    print(f"\n{'='*60}")
    print(f"Generation Summary:")
    print(f"  Common blocks (L4P):    {common_count}")
    print(f"  Family-specific blocks:        {family_specific_count}")
    print(f"  Total block types processed:   {len(all_blocks)}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
