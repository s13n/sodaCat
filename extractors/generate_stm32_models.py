#!/usr/bin/env python3
"""
Generic extractor: generate YAML models for any STM32 family.

Usage: generate_stm32_models.py <family_code> <zip_path> <output_dir>

The family_code selects a YAML config from families/<family_code>.yaml,
which provides the subfamily-to-chip mapping and the block definitions
(source instances, interrupt mappings) for that family.
"""

import copy
import re
import sys
import os
import tempfile
from pathlib import Path
from collections import defaultdict
from ruamel.yaml import YAML

# Add sodaCat tools to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))
import svd
from transform import renameEntries


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

    blocks_config = {}
    for block_type, block_cfg in (config.get('blocks') or {}).items():
        entry = {
            'from': block_cfg.get('from', ''),
            'instances': list(block_cfg.get('instances', [])),
        }
        if block_cfg.get('interrupts') is not None:
            entry['interrupts'] = dict(block_cfg['interrupts'])
        if block_cfg.get('transforms') is not None:
            entry['transforms'] = [dict(t) for t in block_cfg['transforms']]
        if block_cfg.get('params') is not None:
            entry['params'] = {k: dict(v) for k, v in block_cfg['params'].items()}
        if block_cfg.get('variants') is not None:
            entry['variants'] = {k: dict(v) for k, v in block_cfg['variants'].items()}
        blocks_config[block_type] = entry

    chip_params = {}
    for sf_key, sf_val in (config.get('chip_params') or {}).items():
        chip_params[sf_key] = {k: dict(v) for k, v in sf_val.items()}

    return families, blocks_config, chip_params


def _resolve_chip_param(chip_params, subfamily, chip, instance, block_type, param_name, default=None):
    """Resolve a parameter value using the subfamily-keyed chip_params structure.

    Resolution order:
    1. Per-subfamily, per-chip, instance name
    2. Per-subfamily, per-chip, block name
    3. Per-subfamily, _all, instance name
    4. Per-subfamily, _all, block name
    5. Family _all, _all, instance name
    6. Family _all, _all, block name
    7. Param default from block declaration
    """
    for sf_key in (subfamily, '_all'):
        sf = chip_params.get(sf_key)
        if not sf:
            continue
        chip_keys = [chip, '_all'] if sf_key != '_all' else ['_all']
        for chip_key in chip_keys:
            chip_section = sf.get(chip_key)
            if not chip_section:
                continue
            for target_key in (instance, block_type):
                if target_key and target_key in chip_section:
                    params = chip_section[target_key]
                    if param_name in params:
                        return params[param_name]
    return default


def _resolve_block_config(block_cfg, subfamily_name):
    """Resolve a block config for a specific subfamily by merging variant overrides."""
    variants = block_cfg.get('variants')
    if not variants or subfamily_name not in variants:
        return block_cfg

    resolved = dict(block_cfg)
    resolved.update(variants[subfamily_name])
    del resolved['variants']
    return resolved


def _select_block_entry(block_families, families, families_present, block_cfg):
    """Select the best block entry for a shared block, preferring the 'from' chip."""
    source = block_cfg.get('from', '')
    source_chip = source.split('.')[0] if '.' in source else ''

    # Try to find data from the designated source chip
    if source_chip:
        for fam in families:
            if fam in families_present:
                for entry in block_families[fam]:
                    if entry['chip'] == source_chip:
                        return entry

    # Fallback: first chip in declaration order
    first_family = next(f for f in families if f in families_present)
    return block_families[first_family][0]


def _select_subfamily_entry(entries, block_cfg):
    """Select the best entry within a subfamily, preferring the 'from' chip."""
    source = block_cfg.get('from', '')
    source_chip = source.split('.')[0] if '.' in source else ''

    if source_chip:
        for entry in entries:
            if entry['chip'] == source_chip:
                return entry

    return entries[0]


def _patch_fields(registers, reg_name, field_patches):
    """Patch fields in a named register.

    For each entry in field_patches:
      - name + properties, field exists   -> merge properties into existing field
      - name + properties, field absent   -> append new field
      - name only, field exists           -> remove field
      - name only, field absent           -> warning (no-op)
    """
    reg = next((r for r in registers if r.get('name') == reg_name), None)
    if reg is None:
        print(f"  WARNING: patchFields: register '{reg_name}' not found")
        return

    fields = reg.get('fields')
    if fields is None:
        fields = []
        reg['fields'] = fields

    for patch in field_patches:
        name = patch['name']
        props = {k: v for k, v in patch.items() if k != 'name'}
        existing = next((f for f in fields if f.get('name') == name), None)

        if props:
            if existing:
                existing.update(props)
            else:
                fields.append(dict(patch))
        else:
            if existing:
                fields.remove(existing)
            else:
                print(f"  WARNING: patchFields: field '{name}' not found in '{reg_name}'")


def _patch_registers(registers, reg_patches):
    """Patch register-level properties.

      - name + properties, register exists  -> merge properties
      - name + properties, register absent  -> add new register
      - name only, register exists          -> remove register
      - name only, register absent          -> warning
    """
    for patch in reg_patches:
        name = patch['name']
        props = {k: v for k, v in patch.items() if k != 'name'}
        existing = next((r for r in registers if r.get('name') == name), None)

        if props:
            if existing:
                for k, v in props.items():
                    if v is None:
                        existing.pop(k, None)
                    else:
                        existing[k] = v
            else:
                registers.append(dict(patch))
        else:
            if existing:
                registers.remove(existing)
            else:
                print(f"  WARNING: patchRegisters: register '{name}' not found")


def _apply_transforms(block_data, transforms):
    """Apply a list of transforms to extracted block data (in-place)."""
    for t in transforms:
        typ = t['type']
        if typ == 'renameRegisters':
            renameEntries(block_data.get('registers', []), 'name', t['pattern'], t['replacement'])
            renameEntries(block_data.get('registers', []), 'displayName', t['pattern'], t['replacement'])
        elif typ == 'renameFields':
            reg = next((r for r in block_data.get('registers', [])
                        if r.get('name') == t['register']), None)
            if reg and reg.get('fields'):
                renameEntries(reg['fields'], 'name', t['pattern'], t['replacement'])
            elif reg is None:
                print(f"  WARNING: renameFields: register '{t['register']}' not found")
        elif typ == 'patchFields':
            if 'register_pattern' in t:
                matched = False
                for r in block_data.get('registers', []):
                    if re.match(t['register_pattern'], r.get('name', '')):
                        _patch_fields(block_data.get('registers', []), r['name'], t['fields'])
                        matched = True
                if not matched:
                    print(f"  WARNING: patchFields: no registers match pattern '{t['register_pattern']}'")
            else:
                _patch_fields(block_data.get('registers', []), t['register'], t['fields'])
        elif typ == 'patchRegisters':
            _patch_registers(block_data.get('registers', []), t['registers'])
        elif typ == 'cloneRegister':
            regs = block_data.get('registers', [])
            src = next((r for r in regs if r.get('name') == t['source']), None)
            if src is None:
                print(f"  WARNING: cloneRegister: source '{t['source']}' not found")
            else:
                clone = copy.deepcopy(src)
                clone['name'] = t['name']
                clone['displayName'] = t['name']
                # Remove specified fields
                if 'removeFields' in t and clone.get('fields'):
                    remove_set = set(t['removeFields'])
                    clone['fields'] = [f for f in clone['fields']
                                       if f.get('name') not in remove_set]
                # Rename fields in the clone
                for rf in t.get('renameFields', []):
                    renameEntries(clone.get('fields', []), 'name',
                                  rf['pattern'], rf['replacement'])
                # Insert clone right after the source register
                idx = regs.index(src)
                regs.insert(idx + 1, clone)
        elif typ == 'patchAddressBlock':
            for ab in block_data.get('addressBlocks', []):
                for k, v in t.items():
                    if k != 'type':
                        ab[k] = v
                break  # patch first (typically only) address block
        else:
            print(f"  WARNING: unknown transform type '{typ}'")


def _strip_instance_prefix(block_data, instance_name, block_type):
    """Auto-strip instance/block-type prefix from register names.

    For each register, if its name starts with the instance name or
    block type (optionally followed by '_'), strip that prefix.
    Prefixes are tried longest-first so 'GPIOA_' is preferred over 'GPIO_'.
    """
    registers = block_data.get('registers', [])
    if not registers:
        return

    # Build candidate prefixes (with '_' separator), longest first
    base = re.sub(r'\d+$', '', instance_name)  # e.g., ADC1 -> ADC
    candidates = set()
    for name in (instance_name, base, block_type):
        candidates.add(name + '_')
    # Sort longest-first so we prefer the most specific match
    candidates = sorted(candidates, key=len, reverse=True)

    for reg in registers:
        rname = reg.get('name', '')
        for prefix in candidates:
            if rname.startswith(prefix):
                reg['name'] = rname[len(prefix):]
                dn = reg.get('displayName', '')
                if dn.startswith(prefix):
                    reg['displayName'] = dn[len(prefix):]
                break  # first matching prefix wins


def _inject_params(block_data, params):
    """Insert params declaration into block_data before 'registers' key."""
    if not params:
        return block_data
    ordered = {}
    for k, v in block_data.items():
        if k == 'registers' and 'params' not in ordered:
            ordered['params'] = dict(params)
        ordered[k] = v
    if 'params' not in ordered:
        ordered['params'] = dict(params)
    return ordered


def _inject_source(block_data, entry):
    """Insert source attribution into block_data before params/registers."""
    chip = entry.get('chip', '')
    version = entry.get('svd_version', '')
    source = f"{chip} SVD v{version}" if version else f"{chip} SVD"
    ordered = {}
    for k, v in block_data.items():
        if k in ('params', 'registers') and 'source' not in ordered:
            ordered['source'] = source
        ordered[k] = v
    if 'source' not in ordered:
        ordered['source'] = source
    return ordered


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

    families, blocks_config, chip_params = load_family_config(family_code)

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

        # Resolve block configs for this subfamily (applies variant overrides)
        effective_blocks = {
            bt: _resolve_block_config(bc, family_name)
            for bt, bc in blocks_config.items()
        }

        for chip_name in family_info['chips']:
            try:
                svd_content = svd.extractFromZip(zip_path, chip_name)
                if svd_content is not None:
                    with tempfile.NamedTemporaryFile(mode='wb', suffix='.svd', delete=False) as tf:
                        tf.write(svd_content)
                        temp_svd = tf.name

                    try:
                        root = svd.parse(temp_svd)
                        blocks, _, chip_device = svd.processChip(root, chip_name, effective_blocks)
                        svd_version = chip_device.get('version', '') if chip_device else ''

                        # Auto-strip instance prefixes from register names
                        for bn, bd in blocks.items():
                            from_spec = effective_blocks.get(bn, {}).get('from', '')
                            if '.' in from_spec:
                                inst = from_spec.split('.', 1)[1]
                                _strip_instance_prefix(bd, inst, bn)

                        for block_name, block_data in blocks.items():
                            all_blocks[block_name][family_name].append({
                                'data': block_data,
                                'chip': chip_name,
                                'svd_version': svd_version
                            })
                    finally:
                        os.unlink(temp_svd)

            except Exception as e:
                print(f"  ERROR processing {chip_name}: {e}")

    # ==========================================================================
    # PASS 2: Generate models (placement driven by config)
    # ==========================================================================
    print(f"\n{'='*60}")
    print("PASS 2: Generating models")
    print(f"{'='*60}")

    common_blocks_dir = output_dir / family_code
    common_blocks_dir.mkdir(parents=True, exist_ok=True)

    common_count = 0
    family_specific_count = 0

    for block_name in sorted(all_blocks.keys()):
        block_families = all_blocks[block_name]
        block_cfg = blocks_config.get(block_name, {})
        families_present = set(block_families.keys())
        variants = block_cfg.get('variants') or {}

        # Variant subfamilies -> subfamily-specific placement
        for fam_name in families:
            if fam_name in families_present and fam_name in variants:
                family_specific_count += 1
                family_dir = output_dir / family_code / fam_name
                family_dir.mkdir(parents=True, exist_ok=True)

                resolved = _resolve_block_config(block_cfg, fam_name)
                entry = _select_subfamily_entry(
                    block_families[fam_name], resolved)
                block_data = entry['data']
                transforms = resolved.get('transforms')
                if transforms:
                    block_data = copy.deepcopy(block_data)
                    _apply_transforms(block_data, transforms)
                block_data = _inject_params(block_data, block_cfg.get('params'))
                block_data = _inject_source(block_data, entry)
                svd.dumpModel(block_data, family_dir / block_name)

        # Non-variant subfamilies -> shared placement in base dir
        default_present = {f for f in families_present if f not in variants}
        if default_present:
            common_count += 1
            entry = _select_block_entry(
                block_families, families, default_present, block_cfg)
            block_data = entry['data']
            transforms = block_cfg.get('transforms')
            if transforms:
                block_data = copy.deepcopy(block_data)
                _apply_transforms(block_data, transforms)
            block_data = _inject_params(block_data, block_cfg.get('params'))
            block_data = _inject_source(block_data, entry)
            svd.dumpModel(block_data, common_blocks_dir / block_name)
            print(f"  + {block_name:20} -> {family_code} (shared)")

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
