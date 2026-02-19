#!/usr/bin/env python3
"""
Extract and generate YAML models for all STM32U5 family members.
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

# Define STM32U5 family information
STM32U5_FAMILIES = {
    'U53x_U54x': {
        'chips': ['STM32U535', 'STM32U545'],
        'cores': {'': None},  # Single core
    },
    'U57x_U58x': {
        'chips': ['STM32U575', 'STM32U585'],
        'cores': {'': None},
    },
    'U59x_U5Ax': {
        'chips': ['STM32U595', 'STM32U599', 'STM32U5A5', 'STM32U5A9'],
        'cores': {'': None},
    },
    'U5Fx_U5Gx': {
        'chips': ['STM32U5Fx', 'STM32U5Gx'],
        'cores': {'': None},
    },
}

# Peripheral blocks to extract
FUNCTIONAL_BLOCKS = frozenset({
    'ADC', 'ADC_Common', 'ADF', 'AES', 'COMP', 'CORDIC', 'CRC', 'CRS', 'DAC',
    'DBGMCU', 'DMA2D', 'DSI', 'DTS', 'EXTI', 'FDCAN', 'Flash', 'FMAC', 'FMC',
    'GFXMMU', 'GFXTIM', 'GPDMA', 'GPIO', 'HASH', 'HSPI',
    'I2C', 'I3C', 'IWDG', 'JPEG', 'LPTIM', 'LPUART', 'LTDC',
    'MDF', 'OCTOSPI', 'OPAMP', 'OTG_FS', 'OTG_HS', 'OTFDEC',
    'PKA', 'PSSI', 'PWR', 'RAMCFG', 'RCC', 'RNG', 'RTC',
    'SAES', 'SAI', 'SBS', 'SDMMC', 'SPI', 'SYSCFG',
    'TAMP', 'AdvCtrlTimer', 'GpTimer', 'BasicTimer',
    'TSC', 'UCPD', 'USART', 'USB', 'VREFBUF', 'WWDG',
})

def get_canonical_name(periph_name, periph_obj=None):
    """Map peripheral instance name to functional block type."""
    # Skip security shadow peripherals
    if periph_name.startswith('SEC_'):
        return None
    # Skip security zone controllers
    if periph_name.startswith('GTZC'):
        return None
    # Skip delay blocks
    if periph_name.startswith('DLYB'):
        return None
    # Skip cache controllers
    if periph_name in ('ICACHE', 'DCACHE', 'DCACHE1', 'DCACHE2'):
        return None
    # Skip USB SRAM
    if periph_name == 'USBSRAM':
        return None

    # ADC instances and common block
    if periph_name.startswith('ADC'):
        if 'Common' in periph_name or '_COMMON' in periph_name:
            return 'ADC_Common'
        if periph_name == 'ADC12':
            return 'ADC_Common'
        return 'ADC'

    # Normalize ExTI/EXTI
    if periph_name in ('ExTI', 'EXTI'):
        return 'EXTI'

    # Normalize FLASH
    if periph_name == 'FLASH':
        return 'Flash'

    # GPDMA
    if periph_name.startswith('GPDMA'):
        return 'GPDMA'

    # GPIO
    if periph_name.startswith('GPIO'):
        return 'GPIO'

    # I3C (check before I2C)
    if periph_name.startswith('I3C'):
        return 'I3C'

    # I2C
    if periph_name.startswith('I2C'):
        return 'I2C'

    # SPI
    if periph_name.startswith('SPI'):
        return 'SPI'

    # USART/UART
    if periph_name.startswith('USART') or periph_name.startswith('UART'):
        return 'USART'
    if periph_name.startswith('LPUART'):
        return 'LPUART'

    # SAI
    if periph_name.startswith('SAI'):
        return 'SAI'

    # FDCAN
    if periph_name.startswith('FDCAN'):
        return 'FDCAN'

    # SDMMC
    if periph_name.startswith('SDMMC'):
        return 'SDMMC'

    # LPTIM
    if periph_name.startswith('LPTIM'):
        return 'LPTIM'

    # COMP
    if periph_name.startswith('COMP'):
        return 'COMP'

    # OPAMP
    if periph_name.startswith('OPAMP'):
        return 'OPAMP'

    # UCPD
    if periph_name.startswith('UCPD'):
        return 'UCPD'

    # OTFDEC
    if periph_name.startswith('OTFDEC'):
        return 'OTFDEC'

    # OCTOSPI
    if periph_name.startswith('OCTOSPI'):
        return 'OCTOSPI'

    # HSPI
    if periph_name.startswith('HSPI'):
        return 'HSPI'

    # OTG USB
    if periph_name == 'OTG_FS':
        return 'OTG_FS'
    if periph_name == 'OTG_HS':
        return 'OTG_HS'

    # MDF
    if periph_name.startswith('MDF'):
        return 'MDF'

    # ADF
    if periph_name.startswith('ADF'):
        return 'ADF'

    # DAC
    if periph_name.startswith('DAC'):
        return 'DAC'

    # Timers
    if periph_name.startswith('TIM'):
        if periph_name in ('TIM1', 'TIM8'):
            return 'AdvCtrlTimer'
        elif periph_name in ('TIM6', 'TIM7'):
            return 'BasicTimer'
        return 'GpTimer'

    return periph_name


def extract_svd_from_zip(zip_path, svd_filename):
    """Extract a single SVD from the zip package."""
    import zipfile
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            svd_path = f'STM32U5_svd/STM32U5_svd_V1.3/{svd_filename}.svd'
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
                blocks[block_type] = periph.copy()

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
        print("Usage: generate_stm32u5_models.py <zip_path> <output_dir>")
        sys.exit(1)

    zip_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not zip_path.exists():
        print(f"Error: {zip_path} not found")
        sys.exit(1)

    print(f"Extracting STM32U5 models from {zip_path}")
    print(f"Output directory: {output_dir}\n")

    # ================================================================================
    # PASS 1: Collect blocks from all families
    # ================================================================================
    print(f"{'='*60}")
    print("PASS 1: Collecting blocks from all families")
    print(f"{'='*60}")

    all_blocks = defaultdict(lambda: defaultdict(list))

    for family_name, family_info in STM32U5_FAMILIES.items():
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

    common_blocks_dir = output_dir / 'U5_common'
    common_blocks_dir.mkdir(parents=True, exist_ok=True)

    common_count = 0
    family_specific_count = 0

    for block_name in sorted(all_blocks.keys()):
        block_families = all_blocks[block_name]

        families_present = set(block_families.keys())
        all_families = set(STM32U5_FAMILIES.keys())

        if families_present == all_families:
            first_family = list(families_present)[0]
            reference_hash = block_families[first_family][0]['hash']

            all_hashes_same = all(
                block_families[f][0]['hash'] == reference_hash
                for f in families_present
            )

            if all_hashes_same:
                common_count += 1
                block_data = block_families[first_family][0]['data']
                block_file = common_blocks_dir / f'{block_name}.yaml'
                save_yaml_model(block_data, block_file)
                print(f"  + {block_name:20} -> U5_common (shared across all families)")
                continue

        # Block differs across families or missing in some
        for family_name in STM32U5_FAMILIES:
            if family_name in families_present:
                family_specific_count += 1
                family_dir = output_dir / family_name
                block_dir = family_dir / 'blocks'
                block_dir.mkdir(parents=True, exist_ok=True)

                block_data = block_families[family_name][0]['data']
                block_file = block_dir / f'{block_name}.yaml'
                save_yaml_model(block_data, block_file)

    # ================================================================================
    # Summary
    # ================================================================================
    print(f"\n{'='*60}")
    print(f"Generation Summary:")
    print(f"  Common blocks (U5_common):     {common_count}")
    print(f"  Family-specific blocks:        {family_specific_count}")
    print(f"  Total block types processed:   {len(all_blocks)}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
