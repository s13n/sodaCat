#!/usr/bin/env python3
"""
Extract and generate YAML models for all STM32H7 family members.
Creates functional block models and chip-level models automatically.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path
from urllib.request import urlretrieve
from collections import defaultdict

# Add sodaCat tools to path
# Script is in generators/, tools are in tools/ (sibling directory)
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))
import svd
import transform

# Define STM32H7 family information
STM32H7_FAMILIES = {
    'H73x': {
        'chips': ['STM32H723', 'STM32H725', 'STM32H730', 'STM32H733', 'STM32H735', 'STM32H73x'],
        'cores': {'': None},  # Single core
    },
    'H74x_H75x': {
        'chips': [
            'STM32H742', 'STM32H743', 'STM32H750', 'STM32H753',
            'STM32H745_CM4', 'STM32H745_CM7', 
            'STM32H747_CM4', 'STM32H747_CM7',
            'STM32H755_CM4', 'STM32H755_CM7', 
            'STM32H757_CM4', 'STM32H757_CM7',
        ],
    },
    'H7A3_B': {
        'chips': ['STM32H7A3', 'STM32H7B0', 'STM32H7B3'],
        'cores': {'': None},  # Single core
    }
}

# Peripheral blocks to extract (from existing H757 implementation)
FUNCTIONAL_BLOCKS = frozenset({
    'ADC', 'ADC_Common', 'ART', 'BDMA', 'RCC', 'DAC', 'DMA', 'DMAMUX1', 'DMAMUX2',
    'EXTI', 'GPIO', 'I2C', 'MDMA', 'SAI', 'SPDIFRX', 'SYSCFG', 'BasicTimer', 'GpTimer',
    'AdvCtrlTimer', 'LPTIM', 'LPTIMenc', 'USART', 'LPUART', 'QUADSPI', 'OPAMP', 'DFSDM',
    'SPI', 'RTC', 'FMC', 'PWR', 'DBGMCU', 'Flash', 'NVIC'
})

INCOMPATIBLE_BLOCKS = frozenset({
    'ADC', 'ADC_Common', 'AdvCtrlTimer', 'BDMA', 'DMA', 'DBGMCU', 'DFSDM',
    'FMC', 'Flash', 'GpTimer', 'LPTIM', 'MDMA', 'PWR', 'QUADSPI', 'RCC',
    'RTC', 'SPDIFRX', 'SYSCFG', 'OPAMP',
})

def get_canonical_name(periph_name, periph_obj=None):
    """Map peripheral instance name to functional block type."""
    if periph_name.startswith('ADC'):
        return 'ADC_Common' if 'Common' in periph_name else 'ADC'
    if periph_name.startswith('SAI'):
        return 'SAI'
    if periph_name.startswith('I2C'):
        return 'I2C'
    if periph_name.startswith('SPI'):
        return 'SPI'
    if periph_name.startswith('USART') or periph_name.startswith('UART'):
        return 'USART'
    if periph_name.startswith('LPUART'):
        return 'LPUART'
    if periph_name.startswith('TIM'):
        if periph_name in ['TIM1', 'TIM8']:
            return 'AdvCtrlTimer'
        elif periph_name in ['TIM2', 'TIM3', 'TIM4', 'TIM5']:
            return 'GpTimer'
        elif periph_name in ['TIM6', 'TIM7']:
            return 'BasicTimer'
        return 'GpTimer'
    if periph_name.startswith('LPTIM'):
        return 'LPTIMenc' if 'enc' in periph_name else 'LPTIM'
    if periph_name.startswith('GPIO'):
        return 'GPIO'
    if periph_name.startswith('DMA') and 'COMMON' not in periph_name:
        return 'DMA'
    if periph_name.startswith('DMAMUX'):
        return periph_name
    if periph_name.startswith('BDMA'):
        return 'BDMA'
    if periph_name.startswith('MDMA'):
        return 'MDMA'
    return periph_name

def extract_svd_from_zip(zip_path, svd_filename):
    """Extract a single SVD from the zip package."""
    import zipfile
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # SVD files are in STM32H7_svd_V2.8 subdirectory
            svd_path = f'STM32H7_svd_V2.8/{svd_filename}.svd'
            return zf.read(svd_path)
    except Exception as e:
        print(f"Error extracting {svd_filename}: {e}")
        return None

def process_chip(svd_root, chip_name):
    """Process a single STM32H7 chip SVD and extract functional blocks."""
    try:
        chip = svd.collateDevice(svd_root)
        blocks = {}
        chip_peripheral_refs = {}
        
        for periph in chip['peripherals']:
            periph_name = periph['name']
            block_type = get_canonical_name(periph_name, periph)
            
            # Only keep relevant blocks
            if block_type not in FUNCTIONAL_BLOCKS and block_type not in INCOMPATIBLE_BLOCKS:
                continue
                
            # Store peripheral reference for chip model
            chip_peripheral_refs[periph_name] = {
                'blockType': block_type,
                'baseAddress': periph.get('baseAddress'),
                'interrupts': [i['value'] for i in periph.get('interrupts', [])]
            }
            
            # Extract block data (skip if already have one)
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
    
    # Extract register structure (names, offsets, fields) - ignore peripheral instance-specific data
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
        for field in reg.get('fields', []):
            reg_info['fields'].append({
                'name': field.get('name'),
                'offset': field.get('bitOffset'),
                'width': field.get('bitWidth')
            })
        structure['registers'].append(reg_info)
    
    # Hash the structure (normalized JSON)
    json_str = json.dumps(structure, sort_keys=True, indent=None)
    return hashlib.sha256(json_str.encode()).hexdigest()

def main():
    if len(sys.argv) < 3:
        print("Usage: generate_stm32h7_models.py <zip_path> <output_dir>")
        sys.exit(1)
    
    zip_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    
    if not zip_path.exists():
        print(f"Error: {zip_path} not found")
        sys.exit(1)
    
    print(f"Extracting STM32H7 models from {zip_path}")
    print(f"Output directory: {output_dir}\n")
    
    # ================================================================================
    # PASS 1: Collect blocks from all families
    # ================================================================================
    print(f"{'='*60}")
    print("PASS 1: Collecting blocks from all families")
    print(f"{'='*60}")
    
    # Structure: all_blocks[block_name][family_name] = { hash, data, chip }
    all_blocks = defaultdict(lambda: defaultdict(list))
    
    for family_name, family_info in STM32H7_FAMILIES.items():
        print(f"\nProcessing {family_name} family...")
        
        for chip_name in family_info['chips']:
            try:
                # Extract and parse SVD
                svd_content = extract_svd_from_zip(zip_path, chip_name)
                if svd_content is not None:
                    # Write to temp file for parsing
                    with tempfile.NamedTemporaryFile(mode='wb', suffix='.svd', delete=False) as tf:
                        tf.write(svd_content)
                        temp_svd = tf.name
                    
                    try:
                        root = svd.parse(temp_svd)
                        blocks, _, _ = process_chip(root, chip_name)
                        
                        # Store blocks by type and family
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
    
    common_blocks_dir = output_dir / 'H7'
    common_blocks_dir.mkdir(parents=True, exist_ok=True)
    
    common_count = 0
    family_specific_count = 0
    
    for block_name in sorted(all_blocks.keys()):
        block_families = all_blocks[block_name]
        
        # Check if block exists in all families
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
            print(f"  + {block_name:20} -> H7 (shared)")
            continue

        # Block differs between subfamilies -> subfamily-specific
        for family_name in STM32H7_FAMILIES:
            if family_name in families_present:
                family_specific_count += 1
                family_dir = output_dir / 'H7' / family_name
                family_dir.mkdir(parents=True, exist_ok=True)

                block_data = block_families[family_name][0]['data']
                block_file = family_dir / f'{block_name}.yaml'
                save_yaml_model(block_data, block_file)
    
    # ================================================================================
    # Summary
    # ================================================================================
    print(f"\n{'='*60}")
    print(f"Generation Summary:")
    print(f"  Common blocks (H7):     {common_count}")
    print(f"  Family-specific blocks:        {family_specific_count // len(STM32H7_FAMILIES)}")
    print(f"  Total block types processed:   {len(all_blocks)}")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
