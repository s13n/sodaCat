#!/usr/bin/env python3
"""
Extract and generate YAML models for all STM32F4 family members.
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

# Define STM32F4 family information
STM32F4_FAMILIES = {
    'F401_F410_F411': {
        'chips': ['STM32F401', 'STM32F410', 'STM32F411'],
        'cores': {'': None},
    },
    'F405_F407': {
        'chips': ['STM32F405', 'STM32F407', 'STM32F415', 'STM32F417'],
        'cores': {'': None},
    },
    'F412_F413_F423': {
        'chips': ['STM32F412', 'STM32F413', 'STM32F423'],
        'cores': {'': None},
    },
    'F42x_F43x': {
        'chips': ['STM32F427', 'STM32F429', 'STM32F437', 'STM32F439'],
        'cores': {'': None},
    },
    'F446_F469_F479': {
        'chips': ['STM32F446', 'STM32F469', 'STM32F479'],
        'cores': {'': None},
    },
}

# Peripheral blocks to extract
FUNCTIONAL_BLOCKS = frozenset({
    'ADC', 'ADC_Common', 'AES', 'bxCAN', 'CEC', 'CRC', 'CRYP', 'DAC',
    'DBGMCU', 'DCMI', 'DFSDM', 'DMA', 'DMA2D', 'DSI',
    'Ethernet_DMA', 'Ethernet_MAC', 'Ethernet_MMC', 'Ethernet_PTP',
    'EXTI', 'Flash', 'FMC', 'FMPI2C', 'FSMC', 'GPIO', 'HASH',
    'I2C', 'IWDG', 'LPTIM', 'LTDC',
    'OTG_FS_DEVICE', 'OTG_FS_GLOBAL', 'OTG_FS_HOST', 'OTG_FS_PWRCLK',
    'OTG_HS_DEVICE', 'OTG_HS_GLOBAL', 'OTG_HS_HOST', 'OTG_HS_PWRCLK',
    'PWR', 'QUADSPI', 'RCC', 'RNG', 'RTC', 'SAI', 'SDIO', 'SPDIFRX',
    'SPI', 'SYSCFG',
    'AdvCtrlTimer', 'GpTimer', 'BasicTimer',
    'USART', 'WWDG',
})

# Map SVD peripheral instance names to canonical block type names.
# Entries where canonical == instance name are omitted (handled by .get() default).
# None means the peripheral is skipped (ARM core internals, security shadows, etc.).
NAME_MAP = {
    'I2S2ext': None,
    'I2S3ext': None,
    'ADC1': 'ADC',
    'ADC2': 'ADC',
    'ADC3': 'ADC',
    'C_ADC': 'ADC_Common',
    'TIM1': 'AdvCtrlTimer',
    'TIM8': 'AdvCtrlTimer',
    'TIM6': 'BasicTimer',
    'TIM7': 'BasicTimer',
    'HDMI_CEC': 'CEC',
    'DBG': 'DBGMCU',
    'DFSDM1': 'DFSDM',
    'DFSDM2': 'DFSDM',
    'DMA1': 'DMA',
    'DMA2': 'DMA',
    'DSIHOST': 'DSI',
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
    'GPIOJ': 'GPIO',
    'GPIOK': 'GPIO',
    'TIM10': 'GpTimer',
    'TIM11': 'GpTimer',
    'TIM12': 'GpTimer',
    'TIM13': 'GpTimer',
    'TIM14': 'GpTimer',
    'TIM2': 'GpTimer',
    'TIM3': 'GpTimer',
    'TIM4': 'GpTimer',
    'TIM5': 'GpTimer',
    'TIM9': 'GpTimer',
    'I2C1': 'I2C',
    'I2C2': 'I2C',
    'I2C3': 'I2C',
    'I2C4': 'I2C',
    'LPTIM1': 'LPTIM',
    'SAI1': 'SAI',
    'SAI2': 'SAI',
    'SPDIF_RX': 'SPDIFRX',
    'SPI1': 'SPI',
    'SPI2': 'SPI',
    'SPI3': 'SPI',
    'SPI4': 'SPI',
    'SPI5': 'SPI',
    'SPI6': 'SPI',
    'UART10': 'USART',
    'UART4': 'USART',
    'UART5': 'USART',
    'UART7': 'USART',
    'UART8': 'USART',
    'UART9': 'USART',
    'USART1': 'USART',
    'USART2': 'USART',
    'USART3': 'USART',
    'USART6': 'USART',
    'CAN1': 'bxCAN',
    'CAN2': 'bxCAN',
    'CAN3': 'bxCAN',
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
        print("Usage: generate_stm32f4_models.py <zip_path> <output_dir>")
        sys.exit(1)

    zip_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not zip_path.exists():
        print(f"Error: {zip_path} not found")
        sys.exit(1)

    print(f"Extracting STM32F4 models from {zip_path}")
    print(f"Output directory: {output_dir}\n")

    print(f"{'='*60}")
    print("PASS 1: Collecting blocks from all families")
    print(f"{'='*60}")

    all_blocks = defaultdict(lambda: defaultdict(list))

    for family_name, family_info in STM32F4_FAMILIES.items():
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

    print(f"\n{'='*60}")
    print("PASS 2: Analyzing compatibility and generating models")
    print(f"{'='*60}")

    common_blocks_dir = output_dir / 'F4'
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
            print(f"  + {block_name:20} -> F4 (shared)")
            continue

        # Block differs between subfamilies -> subfamily-specific
        for family_name in STM32F4_FAMILIES:
            if family_name in families_present:
                family_specific_count += 1
                family_dir = output_dir / 'F4' / family_name
                family_dir.mkdir(parents=True, exist_ok=True)

                block_data = block_families[family_name][0]['data']
                block_file = family_dir / f'{block_name}.yaml'
                save_yaml_model(block_data, block_file)

    print(f"\n{'='*60}")
    print(f"Generation Summary:")
    print(f"  Common blocks (F4):     {common_count}")
    print(f"  Family-specific blocks:        {family_specific_count}")
    print(f"  Total block types processed:   {len(all_blocks)}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
