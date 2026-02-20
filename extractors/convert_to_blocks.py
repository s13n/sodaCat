#!/usr/bin/env python3
"""
One-time migration tool: convert old name_map-based family configs to the
new block-centric format with 'from', 'instances', and 'interrupts' fields.

Usage: python3 convert_to_blocks.py [family_code ...]
       python3 convert_to_blocks.py           # converts all families
       python3 convert_to_blocks.py C0 H7     # converts specific families

Reads: extractors/families/<CODE>.yaml (old format) + svd/<zip> (for interrupt data)
Writes: extractors/families/<CODE>.yaml (new format, overwrites)
"""

import sys
import os
import re
import tempfile
from pathlib import Path
from collections import defaultdict
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))
import svd

# Map from family code to SVD zip filename
ZIP_NAMES = {
    'C0': 'stm32c0-svd.zip',
    'F3': 'stm32f3-svd.zip',
    'F4': 'stm32f4-svd.zip',
    'F7': 'stm32f7-svd.zip',
    'G0': 'stm32g0-svd.zip',
    'G4': 'stm32g4_svd.zip',
    'H5': 'stm32h5-svd.zip',
    'H7': 'stm32h7-svd.zip',
    'L0': 'stm32l0-svd.zip',
    'L1': 'stm32l1_svd.zip',
    'L4': 'stm32l4_svd.zip',
    'L4P': 'stm32l4plus-svd.zip',
    'L5': 'stm32l5-svd.zip',
    'N6': 'stm32n6-svd.zip',
    'U0': 'stm32u0-svd.zip',
    'U3': 'stm32u3-svd.zip',
    'U5': 'stm32u5_svd.zip',
}


def load_old_config(config_file):
    """Load old-format family config."""
    yaml = YAML()
    with open(config_file, 'r') as f:
        config = yaml.load(f)

    families = {}  # preserve insertion order (Python 3.7+)
    for name, info in config['families'].items():
        families[name] = list(info['chips'])

    name_map = {}
    for k, v in (config.get('name_map') or {}).items():
        name_map[k] = v  # None = skip
    return families, name_map


def parse_chip(zip_path, chip_name):
    """Parse an SVD file from a zip and return the collated device."""
    svd_content = svd.extractFromZip(zip_path, chip_name)
    if svd_content is None:
        return None

    with tempfile.NamedTemporaryFile(mode='wb', suffix='.svd', delete=False) as tf:
        tf.write(svd_content)
        temp_svd = tf.name

    try:
        root = svd.parse(temp_svd)
        return svd.collateDevice(root)
    finally:
        os.unlink(temp_svd)


def discover_all_peripherals(families, zip_path, name_map):
    """Scan all chips to discover every peripheral instance and its interrupts.

    Returns:
      all_periphs: set of peripheral names seen across all chips
      all_interrupts: dict of instance_name -> interrupt list (from first chip that has them)
      chip_periphs: dict of chip_name -> set of peripheral names
      first_chip_for: dict of periph_name -> first chip that has it
    """
    all_periphs = set()
    all_interrupts = {}
    chip_periphs = {}
    first_chip_for = {}
    skipped = {k for k, v in name_map.items() if v is None}

    for subfamily_chips in families.values():
        for chip_name in subfamily_chips:
            chip = parse_chip(zip_path, chip_name)
            if chip is None:
                continue

            chip_names = set()
            for periph in chip['peripherals']:
                pname = periph['name']
                if pname in skipped:
                    continue
                chip_names.add(pname)
                if pname not in all_periphs:
                    all_periphs.add(pname)
                    first_chip_for[pname] = chip_name
                intrs = periph.get('interrupts', [])
                if intrs and pname not in all_interrupts:
                    all_interrupts[pname] = intrs
            chip_periphs[chip_name] = chip_names

    return all_periphs, all_interrupts, chip_periphs, first_chip_for


def build_block_map(name_map, all_periphs):
    """Build block_type -> [instances] from name_map + unmapped SVD peripherals.

    Peripherals not in name_map use their own name as the block type.
    Peripherals mapped to None are excluded.
    """
    block_instances = defaultdict(list)
    mapped_periphs = set(name_map.keys())

    # Explicit name_map entries
    for inst, block_type in name_map.items():
        if block_type is not None:
            block_instances[block_type].append(inst)

    # Unmapped peripherals: use SVD name as block type
    for pname in sorted(all_periphs):
        if pname not in mapped_periphs:
            block_instances[pname].append(pname)

    # Sort instances within each block
    for bt in block_instances:
        block_instances[bt].sort()

    return dict(block_instances)


def compute_canonical_name(raw_name, instance_name, block_type):
    """Compute a canonical interrupt name from a raw SVD name."""
    inst_upper = instance_name.upper()
    block_upper = block_type.upper()
    base_upper = re.sub(r'\d+$', '', inst_upper)
    nu = raw_name.upper()

    # Try prefixes in order: full instance, base, block type,
    # plus shorter variants dropping the last _component (for multi-part names
    # like OTG1_HS_DEVICE -> also try OTG1_HS, OTG_HS)
    prefixes = []
    for p in [inst_upper, base_upper, block_upper]:
        if p and p not in prefixes:
            prefixes.append(p)
        # Add shorter variant
        last_us = p.rfind('_') if p else -1
        if last_us > 0:
            shorter = p[:last_us]
            if shorter not in prefixes:
                prefixes.append(shorter)

    for prefix in prefixes:
        if nu == prefix:
            return ''
        if nu.startswith(prefix + '_'):
            return raw_name[len(prefix) + 1:]
        # Handle prefix + digits + underscore (e.g. DMA1_Stream0 with base DMA)
        # Only strip digits+underscore when followed by non-digit (instance number pattern).
        # EXTI0_1 should become 0_1, not 1 (the 0 is content, not instance number).
        if (nu.startswith(prefix) and len(raw_name) > len(prefix)
                and raw_name[len(prefix)].isdigit()):
            rest = raw_name[len(prefix):]
            i = 0
            while i < len(rest) and rest[i].isdigit():
                i += 1
            if (i < len(rest) and rest[i] == '_'
                    and i + 1 < len(rest) and not rest[i + 1].isdigit()):
                # Digits followed by _non-digit: instance number pattern
                return rest[i + 1:]
            # Digits at end or followed by _digit: keep digits as content
            return rest

    return raw_name


def _find_owning_block(raw_name, instance_to_block):
    """Find which block the interrupt name starts with (longest instance match).

    Returns the block type if the interrupt name starts with a known peripheral
    instance name (followed by '_', digit, or end of string), or None.
    """
    raw_upper = raw_name.upper()
    best_block = None
    best_len = 0

    for inst, block in instance_to_block.items():
        inst_upper = inst.upper()
        if raw_upper.startswith(inst_upper) and len(inst_upper) > best_len:
            if len(raw_name) == len(inst) or raw_name[len(inst)] in '_0123456789':
                best_block = block
                best_len = len(inst_upper)

    return best_block


def _name_mentions_instance(raw_name, instances):
    """Check if the interrupt name mentions any of the given instance names.

    Matches must be at word boundaries (start of string or after '_',
    followed by '_', digit, or end of string).
    """
    raw_upper = raw_name.upper()
    for inst in instances:
        inst_upper = inst.upper()
        pos = 0
        while True:
            idx = raw_upper.find(inst_upper, pos)
            if idx < 0:
                break
            if idx == 0 or raw_name[idx - 1] == '_':
                end = idx + len(inst)
                if end == len(raw_name) or raw_name[end] in '_0123456789':
                    return True
            pos = idx + 1
    return False


def filter_cross_peripheral(interrupts_list, block_type, block_instances,
                            instance_to_block):
    """Filter out interrupts that clearly belong to a different block.

    An interrupt is dropped when its name starts with an instance from a
    different block AND does not also mention an instance from this block
    (shared vectors that reference both blocks are kept).
    """
    if not interrupts_list:
        return interrupts_list

    filtered = []
    for intr in interrupts_list:
        raw = intr['name']
        owning = _find_owning_block(raw, instance_to_block)
        if owning is not None and owning != block_type:
            if not _name_mentions_instance(raw, block_instances):
                continue
        filtered.append(intr)
    return filtered


def build_interrupt_mapping(interrupts_list, instance_name, block_type):
    """Build interrupt name mapping: raw_svd_name -> canonical_name."""
    if not interrupts_list:
        return None

    mapping = CommentedMap()
    for intr in interrupts_list:
        raw = intr['name']
        canonical = compute_canonical_name(raw, instance_name, block_type)
        mapping[raw] = canonical

    # Apply final naming rules
    if len(mapping) == 1:
        key = next(iter(mapping))
        mapping[key] = 'INTR'
    else:
        for key in list(mapping.keys()):
            val = mapping[key]
            if not val or val[0].isdigit():
                mapping[key] = 'INTR' + val

    return mapping


def convert_family(family_code, base_dir):
    """Convert one family config from old to new format."""
    config_file = base_dir / 'extractors' / 'families' / f'{family_code}.yaml'
    zip_file = base_dir / 'svd' / ZIP_NAMES[family_code]

    if not zip_file.exists():
        print(f"  SKIP {family_code}: {zip_file} not found")
        return

    families, name_map = load_old_config(config_file)

    print(f"\n{'='*60}")
    print(f"Converting {family_code}")
    print(f"{'='*60}")

    # Discover all peripherals across all chips
    print(f"  Scanning all chips for peripherals and interrupts...")
    all_periphs, all_interrupts, chip_periphs, first_chip_for = \
        discover_all_peripherals(families, zip_file, name_map)

    block_instances = build_block_map(name_map, all_periphs)
    print(f"  Found {len(block_instances)} block types, {len(all_periphs)} peripheral instances")

    # Build instance -> block_type mapping for cross-peripheral detection
    instance_to_block = {}
    for bt, insts in block_instances.items():
        for inst in insts:
            instance_to_block[inst] = bt

    # Build blocks config
    blocks = CommentedMap()
    for block_type in sorted(block_instances.keys()):
        instances = block_instances[block_type]

        # Find source: prefer first instance that has interrupts, else first instance
        source_inst = instances[0]
        for inst in instances:
            if inst in all_interrupts:
                source_inst = inst
                break

        source_chip = first_chip_for.get(source_inst, '')

        block_cfg = CommentedMap()
        block_cfg['from'] = f'{source_chip}.{source_inst}'
        inst_seq = CommentedSeq(instances)
        inst_seq.fa.set_flow_style()
        block_cfg['instances'] = inst_seq

        # Build interrupt mapping (filter cross-peripheral misattributions first)
        intrs = all_interrupts.get(source_inst)
        if intrs:
            intrs = filter_cross_peripheral(
                intrs, block_type, instances, instance_to_block)
            mapping = build_interrupt_mapping(intrs, source_inst, block_type)
            if mapping:
                block_cfg['interrupts'] = mapping

        blocks[block_type] = block_cfg
        intr_count = len(block_cfg.get('interrupts', {}))
        print(f"  {block_type:25} from {source_chip}.{source_inst:20} "
              f"instances={len(instances):2d}  interrupts={intr_count}")

    # Write new config
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.width = 4096

    output = CommentedMap()
    fam_section = CommentedMap()
    for name, chips in families.items():
        fam_entry = CommentedMap()
        fam_entry['chips'] = chips
        fam_section[name] = fam_entry
    output['families'] = fam_section
    output['blocks'] = blocks

    with open(config_file, 'w') as f:
        yaml.dump(output, f)

    print(f"\n  Written: {config_file}")


def main():
    base_dir = Path(__file__).parent.parent

    if len(sys.argv) > 1:
        codes = sys.argv[1:]
    else:
        codes = list(ZIP_NAMES.keys())

    for code in codes:
        if code not in ZIP_NAMES:
            print(f"Unknown family code: {code}")
            continue
        convert_family(code, base_dir)


if __name__ == '__main__':
    main()
