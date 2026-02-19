#!/usr/bin/env python3
"""
Extract and generate YAML models for all STM32F7 family members.
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

# Define STM32F7 family information
STM32F7_FAMILIES = {
    'F72x_F73x': {
        'chips': ['STM32F722', 'STM32F723', 'STM32F730', 'STM32F732', 'STM32F733'],
        'cores': {'': None},  # Single core
    },
    'F74x_F75x': {
        'chips': ['STM32F745', 'STM32F746', 'STM32F750', 'STM32F756', 'STM32F765'],
        'cores': {'': None},
    },
    'F76x_F77x': {
        'chips': ['STM32F767', 'STM32F768', 'STM32F769', 'STM32F777', 'STM32F778', 'STM32F779'],
        'cores': {'': None},
    },
}

# Peripheral blocks to extract
FUNCTIONAL_BLOCKS = frozenset({
    'ADC', 'ADC_Common', 'AES', 'bxCAN', 'CEC', 'CRC', 'CRYP', 'DAC',
    'DBGMCU', 'DCMI', 'DFSDM', 'DMA', 'DMA2D', 'DSI',
    'Ethernet_DMA', 'Ethernet_MAC', 'Ethernet_MMC', 'Ethernet_PTP',
    'EXTI', 'Flash', 'FMC', 'GPIO', 'HASH', 'I2C', 'IWDG', 'JPEG',
    'LPTIM', 'LTDC', 'MDIOS',
    'OTG_FS_DEVICE', 'OTG_FS_GLOBAL', 'OTG_FS_HOST', 'OTG_FS_PWRCLK',
    'OTG_HS_DEVICE', 'OTG_HS_GLOBAL', 'OTG_HS_HOST', 'OTG_HS_PWRCLK',
    'PWR', 'QUADSPI', 'RCC', 'RNG', 'RTC', 'SAI', 'SDMMC',
    'SPDIFRX', 'SPI', 'SYSCFG',
    'AdvCtrlTimer', 'GpTimer', 'BasicTimer',
    'USART', 'USBPHYC', 'VREFINT', 'WWDG',
})

def get_canonical_name(periph_name, periph_obj=None):
    """Map peripheral instance name to functional block type."""
    # Skip core/debug peripherals
    if periph_name in ('NVIC', 'SCB', 'SCB_ACTRL', 'STK', 'MPU', 'FPU', 'AC'):
        return None

    # Normalize ADC Common blocks (SVD uses C_ADC or ADC_Common depending on chip)
    if periph_name in ('C_ADC', 'ADC_Common'):
        return 'ADC_Common'
    if periph_name.startswith('ADC'):
        return 'ADC'

    # Normalize naming inconsistencies across F7 SVD files
    if periph_name == 'FLASH':
        return 'Flash'
    if periph_name == 'DBG':
        return 'DBGMCU'
    if periph_name == 'LTCD':  # Typo in F767/F777 SVDs
        return 'LTDC'
    if periph_name == 'SPDIF_RX':
        return 'SPDIFRX'

    # CAN bus
    if periph_name.startswith('CAN'):
        return 'bxCAN'

    # GPIO
    if periph_name.startswith('GPIO'):
        return 'GPIO'

    # DMA (not DMA2D)
    if periph_name in ('DMA1', 'DMA2'):
        return 'DMA'

    # I2C
    if periph_name.startswith('I2C'):
        return 'I2C'

    # SPI
    if periph_name.startswith('SPI'):
        return 'SPI'

    # USART/UART
    if periph_name.startswith('USART') or periph_name.startswith('UART'):
        return 'USART'

    # SAI
    if periph_name.startswith('SAI'):
        return 'SAI'

    # SDMMC
    if periph_name.startswith('SDMMC'):
        return 'SDMMC'

    # LPTIM
    if periph_name.startswith('LPTIM'):
        return 'LPTIM'

    # Timers
    if periph_name.startswith('TIM'):
        if periph_name in ('TIM1', 'TIM8'):
            return 'AdvCtrlTimer'
        elif periph_name in ('TIM6', 'TIM7'):
            return 'BasicTimer'
        return 'GpTimer'

    # DFSDM (may have channel/filter sub-peripherals)
    if periph_name.startswith('DFSDM'):
        return 'DFSDM'

    # Ethernet and OTG sub-blocks keep their individual names
    return periph_name


def extract_svd_from_zip(zip_path, svd_filename):
    """Extract a single SVD from the zip package."""
    import zipfile
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            svd_path = f'STM32F7_svd/STM32F7_svd_V2.4/{svd_filename}.svd'
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
            block_type = get_canonical_name(periph_name, periph)

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
        print("Usage: generate_stm32f7_models.py <zip_path> <output_dir>")
        sys.exit(1)

    zip_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not zip_path.exists():
        print(f"Error: {zip_path} not found")
        sys.exit(1)

    print(f"Extracting STM32F7 models from {zip_path}")
    print(f"Output directory: {output_dir}\n")

    # ================================================================================
    # PASS 1: Collect blocks from all families
    # ================================================================================
    print(f"{'='*60}")
    print("PASS 1: Collecting blocks from all families")
    print(f"{'='*60}")

    all_blocks = defaultdict(lambda: defaultdict(list))

    for family_name, family_info in STM32F7_FAMILIES.items():
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

    # ================================================================================
    # PASS 2: Analyze compatibility and generate models
    # ================================================================================
    print(f"\n{'='*60}")
    print("PASS 2: Analyzing compatibility and generating models")
    print(f"{'='*60}")

    common_blocks_dir = output_dir / 'F7'
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
            print(f"  + {block_name:20} -> F7 (shared)")
            continue

        # Block differs between subfamilies -> subfamily-specific
        for family_name in STM32F7_FAMILIES:
            if family_name in families_present:
                family_specific_count += 1
                family_dir = output_dir / 'F7' / family_name
                family_dir.mkdir(parents=True, exist_ok=True)

                block_data = block_families[family_name][0]['data']
                block_file = family_dir / f'{block_name}.yaml'
                save_yaml_model(block_data, block_file)

    # ================================================================================
    # Summary
    # ================================================================================
    print(f"\n{'='*60}")
    print(f"Generation Summary:")
    print(f"  Common blocks (F7):     {common_count}")
    print(f"  Family-specific blocks:        {family_specific_count}")
    print(f"  Total block types processed:   {len(all_blocks)}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
