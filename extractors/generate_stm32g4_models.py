#!/usr/bin/env python3
"""
Extract and generate YAML models for all STM32G4 family members.
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

# Define STM32G4 family information
STM32G4_FAMILIES = {
    'G43x_G44x': {
        'chips': ['STM32G431', 'STM32G441', 'STM32GBK1CBT6'],
        'cores': {'': None},  # Single core
    },
    'G47x_G48x': {
        'chips': ['STM32G471', 'STM32G473', 'STM32G474', 'STM32G483', 'STM32G484'],
        'cores': {'': None},
    },
    'G49x_G4Ax': {
        'chips': ['STM32G491', 'STM32G4A1'],
        'cores': {'': None},
    },
}


# Map SVD peripheral instance names to canonical block type names.
# Entries where canonical == instance name are omitted (handled by .get() default).
# None means the peripheral is skipped (ARM core internals, security shadows, etc.).
NAME_MAP = {
    'ADC1': 'ADC',
    'ADC2': 'ADC',
    'ADC3': 'ADC',
    'ADC4': 'ADC',
    'ADC5': 'ADC',
    'ADC12_Common': 'ADC_Common',
    'ADC345_Common': 'ADC_Common',
    'TIM1': 'AdvCtrlTimer',
    'TIM20': 'AdvCtrlTimer',
    'TIM8': 'AdvCtrlTimer',
    'TIM6': 'BasicTimer',
    'TIM7': 'BasicTimer',
    'DAC1': 'DAC',
    'DAC2': 'DAC',
    'DAC3': 'DAC',
    'DAC4': 'DAC',
    'DMA1': 'DMA',
    'DMA2': 'DMA',
    'FDCAN1': 'FDCAN',
    'FDCAN2': 'FDCAN',
    'FDCAN3': 'FDCAN',
    'FLASH': 'Flash',
    'GPIOA': 'GPIO',
    'GPIOB': 'GPIO',
    'GPIOC': 'GPIO',
    'GPIOD': 'GPIO',
    'GPIOE': 'GPIO',
    'GPIOF': 'GPIO',
    'GPIOG': 'GPIO',
    'TIM15': 'GpTimer',
    'TIM16': 'GpTimer',
    'TIM17': 'GpTimer',
    'TIM2': 'GpTimer',
    'TIM3': 'GpTimer',
    'TIM4': 'GpTimer',
    'TIM5': 'GpTimer',
    'HRTIM_TIMA': 'HRTIM_Timer',
    'HRTIM_TIMB': 'HRTIM_Timer',
    'HRTIM_TIMC': 'HRTIM_Timer',
    'HRTIM_TIMD': 'HRTIM_Timer',
    'HRTIM_TIME': 'HRTIM_Timer',
    'HRTIM_TIMF': 'HRTIM_Timer',
    'I2C1': 'I2C',
    'I2C2': 'I2C',
    'I2C3': 'I2C',
    'I2C4': 'I2C',
    'LPTIM1': 'LPTIM',
    'LPUART1': 'LPUART',
    'SPI1': 'SPI',
    'SPI2': 'SPI',
    'SPI3': 'SPI',
    'SPI4': 'SPI',
    'UCPD1': 'UCPD',
    'UART4': 'USART',
    'UART5': 'USART',
    'USART1': 'USART',
    'USART2': 'USART',
    'USART3': 'USART',
    'USB_FS_device': 'USB',
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


def main():
    if len(sys.argv) < 3:
        print("Usage: generate_stm32g4_models.py <zip_path> <output_dir>")
        sys.exit(1)

    zip_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not zip_path.exists():
        print(f"Error: {zip_path} not found")
        sys.exit(1)

    print(f"Extracting STM32G4 models from {zip_path}")
    print(f"Output directory: {output_dir}\n")

    # ================================================================================
    # PASS 1: Collect blocks from all families
    # ================================================================================
    print(f"{'='*60}")
    print("PASS 1: Collecting blocks from all families")
    print(f"{'='*60}")

    all_blocks = defaultdict(lambda: defaultdict(list))

    for family_name, family_info in STM32G4_FAMILIES.items():
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
                            block_hash = svd.hashBlockStructure(block_data)
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

    common_blocks_dir = output_dir / 'G4'
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
            block_file = common_blocks_dir / block_name
            svd.dumpModel(block_data, block_file)
            print(f"  + {block_name:20} -> G4 (shared)")
            continue

        # Block differs between subfamilies -> subfamily-specific
        for family_name in STM32G4_FAMILIES:
            if family_name in families_present:
                family_specific_count += 1
                family_dir = output_dir / 'G4' / family_name
                family_dir.mkdir(parents=True, exist_ok=True)

                block_data = block_families[family_name][0]['data']
                block_file = family_dir / block_name
                svd.dumpModel(block_data, block_file)

    # ================================================================================
    # Summary
    # ================================================================================
    print(f"\n{'='*60}")
    print(f"Generation Summary:")
    print(f"  Common blocks (G4):     {common_count}")
    print(f"  Family-specific blocks:        {family_specific_count}")
    print(f"  Total block types processed:   {len(all_blocks)}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
