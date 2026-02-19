#!/usr/bin/env python3
"""
Generic extractor: generate YAML models for any STM32 family.

Usage: generate_stm32_models.py <family_code> <zip_path> <output_dir>

The family_code selects a YAML config from families/<family_code>.yaml,
which provides the subfamily-to-chip mapping and the SVD peripheral
name map for that family.
"""

import sys
import os
import tempfile
from pathlib import Path
from collections import defaultdict
from ruamel.yaml import YAML

# Add sodaCat tools to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))
import svd


def load_family_config(family_code):
    """Load the YAML config for a given family code."""
    config_dir = Path(__file__).parent / 'families'
    config_file = config_dir / f'{family_code}.yaml'

    if not config_file.exists():
        print(f"Error: Family config {config_file} not found")
        sys.exit(1)

    yaml = YAML()
    with open(config_file, 'r') as f:
        config = yaml.load(f)

    families = {}
    for name, info in config['families'].items():
        families[name] = {'chips': list(info['chips'])}

    name_map = {}
    for k, v in (config.get('name_map') or {}).items():
        name_map[k] = v  # None values are preserved from YAML null

    return families, name_map


def main():
    if len(sys.argv) < 4:
        print("Usage: generate_stm32_models.py <family_code> <zip_path> <output_dir>")
        sys.exit(1)

    family_code = sys.argv[1]
    zip_path = Path(sys.argv[2])
    output_dir = Path(sys.argv[3])

    if not zip_path.exists():
        print(f"Error: {zip_path} not found")
        sys.exit(1)

    families, name_map = load_family_config(family_code)

    print(f"Extracting STM32{family_code} models from {zip_path}")
    print(f"Output directory: {output_dir}\n")

    # ==========================================================================
    # PASS 1: Collect blocks from all subfamilies
    # ==========================================================================
    print(f"{'='*60}")
    print("PASS 1: Collecting blocks from all families")
    print(f"{'='*60}")

    all_blocks = defaultdict(lambda: defaultdict(list))

    for family_name, family_info in families.items():
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
                        blocks, _, _ = svd.processChip(root, chip_name, name_map)

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

    # ==========================================================================
    # PASS 2: Analyze compatibility and generate models
    # ==========================================================================
    print(f"\n{'='*60}")
    print("PASS 2: Analyzing compatibility and generating models")
    print(f"{'='*60}")

    common_blocks_dir = output_dir / family_code
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
            # Pick first family in declaration order (deterministic)
            first_family = next(f for f in families if f in families_present)
            block_data = block_families[first_family][0]['data']
            block_file = common_blocks_dir / block_name
            svd.dumpModel(block_data, block_file)
            print(f"  + {block_name:20} -> {family_code} (shared)")
            continue

        # Block differs between subfamilies -> subfamily-specific
        for fam_name in families:
            if fam_name in families_present:
                family_specific_count += 1
                family_dir = output_dir / family_code / fam_name
                family_dir.mkdir(parents=True, exist_ok=True)

                block_data = block_families[fam_name][0]['data']
                block_file = family_dir / block_name
                svd.dumpModel(block_data, block_file)

    # ==========================================================================
    # Summary
    # ==========================================================================
    print(f"\n{'='*60}")
    print(f"Generation Summary:")
    print(f"  Common blocks ({family_code}):     {common_count}")
    print(f"  Family-specific blocks:        {family_specific_count}")
    print(f"  Total block types processed:   {len(all_blocks)}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
