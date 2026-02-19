#!/usr/bin/env python3
"""
Extract and generate YAML models for all STM32U0 family members.
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

# Define STM32U0 family information
STM32U0_FAMILIES = {
    'U03x': {
        'chips': ['STM32U031'],
        'cores': {'': None},
    },
    'U07x_U08x': {
        'chips': ['STM32U073', 'STM32U083'],
        'cores': {'': None},
    },
}


# Map SVD peripheral instance names to canonical block type names.
# Entries where canonical == instance name are omitted (handled by .get() default).
# None means the peripheral is skipped (ARM core internals, security shadows, etc.).
NAME_MAP = {
    'TIM1': 'AdvCtrlTimer',
    'TIM6': 'BasicTimer',
    'TIM7': 'BasicTimer',
    'COMP1': 'COMP',
    'DMA1': 'DMA',
    'DMA2': 'DMA',
    'FLASH': 'Flash',
    'GPIOA': 'GPIO',
    'GPIOB': 'GPIO',
    'GPIOC': 'GPIO',
    'GPIOD': 'GPIO',
    'GPIOE': 'GPIO',
    'GPIOF': 'GPIO',
    'TIM15': 'GpTimer',
    'TIM16': 'GpTimer',
    'TIM2': 'GpTimer',
    'TIM3': 'GpTimer',
    'I2C1': 'I2C',
    'I2C2': 'I2C',
    'I2C3': 'I2C',
    'LPTIM1': 'LPTIM',
    'LPTIM2': 'LPTIM',
    'LPTIM3': 'LPTIM',
    'LPUART1': 'LPUART',
    'LPUART2': 'LPUART',
    'LPUART3': 'LPUART',
    'SPI1': 'SPI',
    'SPI2': 'SPI',
    'SPI3': 'SPI',
    'USART1': 'USART',
    'USART2': 'USART',
    'USART3': 'USART',
    'USART4': 'USART',
}



def main():
    if len(sys.argv) < 3:
        print("Usage: generate_stm32u0_models.py <zip_path> <output_dir>")
        sys.exit(1)

    zip_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not zip_path.exists():
        print(f"Error: {zip_path} not found")
        sys.exit(1)

    print(f"Extracting STM32U0 models from {zip_path}")
    print(f"Output directory: {output_dir}\n")

    print(f"{'='*60}")
    print("PASS 1: Collecting blocks from all families")
    print(f"{'='*60}")

    all_blocks = defaultdict(lambda: defaultdict(list))

    for family_name, family_info in STM32U0_FAMILIES.items():
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
                        blocks, _, _ = svd.processChip(root, chip_name, NAME_MAP)

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

    print(f"\n{'='*60}")
    print("PASS 2: Analyzing compatibility and generating models")
    print(f"{'='*60}")

    common_blocks_dir = output_dir / 'U0'
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
            print(f"  + {block_name:20} -> U0 (shared)")
            continue

        # Block differs between subfamilies -> subfamily-specific
        for family_name in STM32U0_FAMILIES:
            if family_name in families_present:
                family_specific_count += 1
                family_dir = output_dir / 'U0' / family_name
                family_dir.mkdir(parents=True, exist_ok=True)

                block_data = block_families[family_name][0]['data']
                block_file = family_dir / block_name
                svd.dumpModel(block_data, block_file)

    print(f"\n{'='*60}")
    print(f"Generation Summary:")
    print(f"  Common blocks (U0):     {common_count}")
    print(f"  Family-specific blocks:        {family_specific_count}")
    print(f"  Total block types processed:   {len(all_blocks)}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
