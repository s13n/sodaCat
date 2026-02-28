#!/usr/bin/env python3
"""
Unified model generator: extract YAML models from vendor SVD files.

Usage: generate_models.py <vendor> <family_code> <svd_source> <output_dir> [--audit]

Vendor-specific behavior (SVD access, source formatting, config location) is
provided by extension modules in extractors/vendors/.
"""

import argparse
import copy
import importlib
import re
import sys
from pathlib import Path
from collections import defaultdict
from ruamel.yaml import YAML

# Add sodaCat tools to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))
import svd
from transform import renameEntries


# ============================================================================
# Vendor registry
# ============================================================================

VENDORS = {
    'stm32': 'vendors.stm32',
    'lpc': 'vendors.lpc',
}


# ============================================================================
# Config loading & resolution
# ============================================================================

def _parse_block_cfg(block_cfg):
    """Parse a block config dict from YAML into a plain dict."""
    entry = {}
    if block_cfg.get('from'):
        entry['from'] = block_cfg['from']
    if block_cfg.get('uses'):
        entry['uses'] = block_cfg['uses']
    if block_cfg.get('instances') is not None:
        entry['instances'] = list(block_cfg['instances'])
    if block_cfg.get('interrupts') is not None:
        entry['interrupts'] = dict(block_cfg['interrupts'])
    if block_cfg.get('transforms') is not None:
        entry['transforms'] = [dict(t) for t in block_cfg['transforms']]
    if block_cfg.get('params') is not None:
        entry['params'] = [dict(p) for p in block_cfg['params']]
    if block_cfg.get('variants') is not None:
        entry['variants'] = {k: dict(v) for k, v in block_cfg['variants'].items()}
    if block_cfg.get('description'):
        entry['description'] = block_cfg['description']
    return entry


def load_family_config(family_code, config_file):
    """Load the YAML config for a given family code.

    Returns (families, blocks_config, chip_params, chip_interrupts,
             shared_blocks_config, svd_tag).
    """
    if not config_file.exists():
        print(f"Error: Config {config_file} not found")
        sys.exit(1)

    yaml = YAML()
    with open(config_file, 'r') as f:
        full_config = yaml.load(f)

    config = full_config['families'].get(family_code)
    if not config:
        print(f"Error: Family '{family_code}' not found in {config_file}")
        sys.exit(1)

    families = {}
    for name, info in config['subfamilies'].items():
        families[name] = {'chips': list(info['chips'])}

    blocks_config = {}
    for block_type, block_cfg in (config.get('blocks') or {}).items():
        blocks_config[block_type] = _parse_block_cfg(block_cfg)

    shared_blocks_config = {}
    for block_type, block_cfg in (full_config.get('shared_blocks') or {}).items():
        shared_blocks_config[block_type] = _parse_block_cfg(block_cfg)

    chip_params = {}
    for sf_key, sf_val in (config.get('chip_params') or {}).items():
        chip_params[sf_key] = {k: dict(v) for k, v in sf_val.items()}

    chip_interrupts = {}
    for sf_key, sf_val in (config.get('chip_interrupts') or {}).items():
        chip_interrupts[sf_key] = {k: dict(v) for k, v in sf_val.items()}

    svd_tag = full_config.get('svd', {}).get('tag', '')

    return families, blocks_config, chip_params, chip_interrupts, shared_blocks_config, svd_tag


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


def _resolve_chip_interrupts(chip_interrupts, subfamily, chip, instance, block_type):
    """Resolve manual interrupt overrides for an instance.

    Same cascade as _resolve_chip_param. Returns {canonical_name: irq_number}.
    """
    for sf_key in (subfamily, '_all'):
        sf = chip_interrupts.get(sf_key)
        if not sf:
            continue
        chip_keys = [chip, '_all'] if sf_key != '_all' else ['_all']
        for chip_key in chip_keys:
            chip_section = sf.get(chip_key)
            if not chip_section:
                continue
            for target_key in (instance, block_type):
                if target_key and target_key in chip_section:
                    return dict(chip_section[target_key])
    return {}


def _resolve_block_config(block_cfg, subfamily_name):
    """Resolve a block config for a specific subfamily by merging variant overrides."""
    variants = block_cfg.get('variants')
    if not variants or subfamily_name not in variants:
        return block_cfg

    resolved = dict(block_cfg)
    variant = variants[subfamily_name]
    resolved.update(variant)
    del resolved['variants']
    # Enforce from/uses mutual exclusivity based on variant's intent
    if 'from' in variant:
        resolved.pop('uses', None)
    elif 'uses' in variant:
        resolved.pop('from', None)
    return resolved


def _resolve_uses_config(family_block_cfg, shared_blocks_config):
    """Merge shared block defaults with family block overrides for a uses: block.

    Returns a new config dict with shared defaults overlaid by family overrides.
    The 'uses' key is removed from the result; 'from' is carried from the shared block.
    """
    uses_name = family_block_cfg.get('uses')
    if not uses_name:
        return family_block_cfg
    shared = shared_blocks_config.get(uses_name)
    if not shared:
        print(f"Error: shared block '{uses_name}' not found in shared_blocks")
        sys.exit(1)
    resolved = dict(shared)
    for k, v in family_block_cfg.items():
        if k != 'uses':
            resolved[k] = v
    return resolved


# ============================================================================
# Entry selection
# ============================================================================

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


# ============================================================================
# Transform engine
# ============================================================================

def _describe_transform(t):
    """Return a one-line human-readable summary of a transform."""
    typ = t['type']
    if typ == 'renameRegisters':
        return f"renameRegisters: /{t['pattern']}/ -> '{t['replacement']}'"
    elif typ == 'renameFields':
        return f"renameFields: {t['register']}: /{t['pattern']}/ -> '{t['replacement']}'"
    elif typ == 'patchFields':
        reg = t.get('register') or t.get('register_pattern', '?')
        names = [f['name'] for f in t.get('fields', [])]
        return f"patchFields: {reg}: {', '.join(names)}"
    elif typ == 'patchRegisters':
        names = [r['name'] for r in t.get('registers', [])]
        return f"patchRegisters: {', '.join(names)}"
    elif typ == 'patchAddressBlock':
        props = {k: v for k, v in t.items() if k != 'type'}
        return f"patchAddressBlock: {props}"
    elif typ == 'cloneRegister':
        return f"cloneRegister: {t['source']} -> {t['name']}"
    else:
        return f"{typ}: {t}"


def _audit_patch_properties(existing, props):
    """Audit a patch merge: which non-description properties still differ?

    Returns (fixed_props, needed_props) where:
      fixed_props = list of (key, value) already matching in SVD
      needed_props = list of (key, old_value, new_value) still differing
    Description properties are ignored (SVD descriptions are always accepted).
    """
    fixed = []
    needed = []
    for k, v in props.items():
        if k == 'description':
            continue
        if v is None:
            # Removal: still needed if key exists
            if k in existing:
                needed.append((k, existing[k], None))
            else:
                fixed.append((k, None))
        else:
            old = existing.get(k)
            if old == v:
                fixed.append((k, v))
            else:
                needed.append((k, old, v))
    return fixed, needed


def _audit_rename(entries, key, pattern):
    """Check if a rename pattern matches any entries.

    Returns list of entry values that match the pattern.
    """
    pat = re.compile(pattern)
    return [e[key] for e in entries if key in e and pat.search(e[key])]


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
        props = {k: v for k, v in patch.items() if k not in ('name', 'newName')}
        existing = next((r for r in registers if r.get('name') == name), None)

        if props or 'newName' in patch:
            if existing:
                if 'newName' in patch:
                    existing['name'] = patch['newName']
                    existing['displayName'] = patch['newName']
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


def _apply_transforms(block_data, transforms, audit=False, block_name=''):
    """Apply a list of transforms to extracted block data (in-place).

    When audit=True, returns a list of findings: (block_name, category, description, details).
    Categories: 'noop' (safe to remove), 'partial' (some properties fixed), 'active'.
    """
    findings = []
    for t in transforms:
        typ = t['type']

        # Tier 1: snapshot before transform (skip cloneRegister — always structural)
        snapshot = None
        if audit and typ != 'cloneRegister':
            snapshot = copy.deepcopy(block_data)

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
                if 'removeFields' in t and clone.get('fields'):
                    remove_set = set(t['removeFields'])
                    clone['fields'] = [f for f in clone['fields']
                                       if f.get('name') not in remove_set]
                for rf in t.get('renameFields', []):
                    renameEntries(clone.get('fields', []), 'name',
                                  rf['pattern'], rf['replacement'])
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

        # Audit: compare snapshot to current state
        if audit and snapshot is not None:
            desc = _describe_transform(t)
            if snapshot == block_data:
                # Tier 1: complete no-op
                findings.append((block_name, 'noop', desc, None))
            else:
                # Tier 2: check per-property details for patch transforms
                details = _audit_transform_details(snapshot, block_data, t)
                if details:
                    findings.append((block_name, 'partial', desc, details))

    return findings


def _audit_transform_details(before, after, t):
    """Tier 2: for patch transforms, check which properties are fixed vs still needed.

    Returns a list of detail strings, or None if no tier-2 info applies.
    """
    typ = t['type']

    if typ == 'patchRegisters':
        details = []
        has_fixed = False
        before_regs = {r.get('name'): r for r in before.get('registers', [])}
        for patch in t.get('registers', []):
            name = patch['name']
            props = {k: v for k, v in patch.items() if k != 'name'}
            if not props:
                continue  # removal — not a property patch
            existing = before_regs.get(name)
            if existing is None:
                continue  # new register added — always needed
            fixed, needed = _audit_patch_properties(existing, props)
            if fixed and not needed:
                has_fixed = True
                details.append(f"  {name}: all non-description properties already correct [FIXED IN SVD]")
            elif fixed:
                has_fixed = True
                for k, v in fixed:
                    details.append(f"  {name}.{k}: already {v!r} [FIXED IN SVD]")
                for k, old, new in needed:
                    details.append(f"  {name}.{k}: {old!r} -> {new!r} (still needed)")
        return details if has_fixed else None

    if typ == 'patchFields':
        details = []
        has_fixed = False
        for reg in before.get('registers', []):
            if reg.get('name') == t.get('register') or \
               (t.get('register_pattern') and re.match(t['register_pattern'], reg.get('name', ''))):
                before_fields = {f.get('name'): f for f in reg.get('fields', [])}
                rn = reg.get('name', t.get('register', '?'))
                for patch in t.get('fields', []):
                    fname = patch['name']
                    props = {k: v for k, v in patch.items() if k != 'name'}
                    if not props:
                        continue  # removal
                    existing = before_fields.get(fname)
                    if existing is None:
                        continue  # new field added
                    fixed, needed = _audit_patch_properties(existing, props)
                    if fixed and not needed:
                        has_fixed = True
                        details.append(f"  {rn}.{fname}: all non-description properties already correct [FIXED IN SVD]")
                    elif fixed:
                        has_fixed = True
                        for k, v in fixed:
                            details.append(f"  {rn}.{fname}.{k}: already {v!r} [FIXED IN SVD]")
                        for k, old, new in needed:
                            details.append(f"  {rn}.{fname}.{k}: {old!r} -> {new!r} (still needed)")
        return details if has_fixed else None

    if typ == 'patchAddressBlock':
        details = []
        has_fixed = False
        before_ab = next(iter(before.get('addressBlocks', [])), {})
        for k, v in t.items():
            if k == 'type':
                continue
            old = before_ab.get(k)
            if old == v:
                has_fixed = True
                details.append(f"  addressBlock.{k}: already {v!r} [FIXED IN SVD]")
            else:
                details.append(f"  addressBlock.{k}: {old!r} -> {v!r} (still needed)")
        return details if has_fixed else None

    if typ in ('renameRegisters', 'renameFields'):
        return None

    return None


# ============================================================================
# Name normalization
# ============================================================================

def _strip_instance_prefix(block_data, instance_name, block_type):
    """Auto-strip instance/block-type prefix from register names and descriptions.

    For each register, if its name starts with the instance name or
    block type (optionally followed by '_'), strip that prefix.
    Also strips from description (space separator) and alternateRegister
    (underscore separator). The block-level description is also cleaned.
    Prefixes are tried longest-first so 'GPIOA_' is preferred over 'GPIO_'.
    """
    # Build candidate prefixes (with '_' separator), longest first
    base = re.sub(r'\d+$', '', instance_name)  # e.g., ADC1 -> ADC
    candidates = set()
    for name in (instance_name, base, block_type):
        candidates.add(name + '_')
    # Sort longest-first so we prefer the most specific match
    candidates = sorted(candidates, key=len, reverse=True)

    # Description candidates: same roots but with space separator
    desc_candidates = sorted(
        {name + ' ' for name in (instance_name, base, block_type)},
        key=len, reverse=True)

    # Strip instance prefix from block-level description
    block_desc = block_data.get('description', '')
    if block_desc:
        for prefix in desc_candidates:
            if block_desc.startswith(prefix):
                stripped = block_desc[len(prefix):]
                if stripped:
                    block_data['description'] = stripped[0].upper() + stripped[1:]
                break

    registers = block_data.get('registers', [])
    if not registers:
        return

    for reg in registers:
        rname = reg.get('name', '')
        for prefix in candidates:
            if rname.startswith(prefix):
                reg['name'] = rname[len(prefix):]
                dn = reg.get('displayName', '')
                if dn.startswith(prefix):
                    reg['displayName'] = dn[len(prefix):]
                break  # first matching prefix wins

        # Strip instance prefix from alternateRegister
        alt = reg.get('alternateRegister', '')
        if alt:
            for prefix in candidates:
                if alt.startswith(prefix):
                    reg['alternateRegister'] = alt[len(prefix):]
                    break

        # Strip instance prefix from description (space separator)
        desc = reg.get('description', '')
        if desc:
            for prefix in desc_candidates:
                if desc.startswith(prefix):
                    stripped = desc[len(prefix):]
                    if stripped:
                        reg['description'] = stripped[0].upper() + stripped[1:]
                    break


# ============================================================================
# Model writing helpers
# ============================================================================

def _inject_params(block_data, params):
    """Insert params declaration into block_data before 'registers' key."""
    if not params:
        return block_data
    ordered = {}
    for k, v in block_data.items():
        if k == 'registers' and 'params' not in ordered:
            ordered['params'] = list(params)
        ordered[k] = v
    if 'params' not in ordered:
        ordered['params'] = list(params)
    return ordered


def _inject_source(block_data, source):
    """Insert source attribution string into block_data before params/registers."""
    ordered = {}
    for k, v in block_data.items():
        if k in ('params', 'registers') and 'source' not in ordered:
            ordered['source'] = source
        ordered[k] = v
    if 'source' not in ordered:
        ordered['source'] = source
    return ordered


# ============================================================================
# Interrupt resolution
# ============================================================================

def _build_canonical_interrupts(blocks_config, shared_blocks):
    """Build a dict of block_type -> set of canonical interrupt names.

    Sources names from interrupt mappings in both family and shared block configs.
    For blocks with 'uses:', inherits from the referenced shared block.
    """
    result = defaultdict(set)
    for bt, bc in blocks_config.items():
        interrupt_map = bc.get('interrupts') or {}
        if not interrupt_map and bc.get('uses'):
            shared = shared_blocks.get(bc['uses'], {})
            interrupt_map = shared.get('interrupts') or {}
        # Also check variants for interrupt overrides
        for variant_cfg in (bc.get('variants') or {}).values():
            for raw, mapping in (variant_cfg.get('interrupts') or {}).items():
                canonical = mapping['name'] if isinstance(mapping, dict) else mapping
                result[bt].add(canonical)
        for raw, mapping in interrupt_map.items():
            canonical = mapping['name'] if isinstance(mapping, dict) else mapping
            result[bt].add(canonical)
    for bt, bc in shared_blocks.items():
        for raw, mapping in (bc.get('interrupts') or {}).items():
            canonical = mapping['name'] if isinstance(mapping, dict) else mapping
            result[bt].add(canonical)
    return result


def _build_config_interrupt_mapping(blocks_config, shared_blocks):
    """Build a direct raw_name -> canonical mapping per block type from config.

    Provides a config-driven lookup that is tried before algorithmic resolution.
    Useful when interrupt names don't follow prefix-stripping patterns.

    Returns: dict of (block_type, raw_name) -> canonical_name
    """
    mapping = {}
    for bt, bc in blocks_config.items():
        interrupt_map = bc.get('interrupts') or {}
        if not interrupt_map and bc.get('uses'):
            shared = shared_blocks.get(bc['uses'], {})
            interrupt_map = shared.get('interrupts') or {}
        for raw, canonical_spec in interrupt_map.items():
            canonical = canonical_spec['name'] if isinstance(canonical_spec, dict) else canonical_spec
            mapping[(bt, raw)] = canonical
    for bt, bc in shared_blocks.items():
        for raw, canonical_spec in (bc.get('interrupts') or {}).items():
            canonical = canonical_spec['name'] if isinstance(canonical_spec, dict) else canonical_spec
            mapping[(bt, raw)] = canonical
    return mapping


def _resolve_interrupt_name(raw_name, instance_name, canonical_names):
    """Map a raw SVD interrupt name to a canonical block-level name.

    Algorithm:
    1. Direct match against canonical names
    2. Strip instance-name prefix (INSTANCE_ or BASEn_), then exact match
    3. After stripping, progressively remove trailing _SUFFIX segments
       (handles shared vectors like TIM8_BRK_TIM12 -> BRK)
    Returns the canonical name, or None if no match.
    """
    if not canonical_names:
        return None

    # 1. Direct match
    if raw_name in canonical_names:
        return raw_name

    # 2. Strip instance prefix (same logic as register prefix stripping)
    base = re.sub(r'\d+$', '', instance_name)  # e.g., I2C1 -> I2C
    prefixes = sorted(
        {instance_name + '_', base + '_'},
        key=len, reverse=True)

    for prefix in prefixes:
        if raw_name.startswith(prefix):
            stripped = raw_name[len(prefix):]

            # 3. Exact match after stripping
            if stripped in canonical_names:
                return stripped

            # 4. Progressive suffix removal (rightmost _WORD segments)
            parts = stripped.split('_')
            for i in range(len(parts) - 1, 0, -1):
                candidate = '_'.join(parts[:i])
                if candidate in canonical_names:
                    return candidate
            break  # Only try the best-matching prefix

    # 5. Instance-name-as-interrupt: raw name matches instance or base name,
    #    and the block has exactly one canonical interrupt (common for
    #    single-interrupt peripherals like TIM3 -> INTR, USART1 -> INTR)
    if len(canonical_names) == 1:
        raw_base = re.sub(r'\d+$', '', raw_name)
        if raw_name == instance_name or raw_name == base \
                or raw_base == base or raw_base == instance_name:
            return next(iter(canonical_names))

    return None


# ============================================================================
# Instance/param mapping
# ============================================================================

def _build_instance_to_block(blocks_config, subfamily_name):
    """Build instance_name -> block_type mapping for a subfamily.

    Applies variant overrides to get the correct instance list.
    """
    mapping = {}
    for bt, bc in blocks_config.items():
        resolved = _resolve_block_config(bc, subfamily_name)
        for inst in resolved.get('instances', []):
            mapping[inst] = bt
    return mapping


def _get_param_decls(block_type, blocks_config, shared_blocks, subfamily_name):
    """Get parameter declarations for a block type, handling uses: and variants."""
    bc = blocks_config.get(block_type, {})
    resolved = _resolve_block_config(bc, subfamily_name)
    params = resolved.get('params')
    if params:
        return params
    # Check shared block
    uses = resolved.get('uses') or bc.get('uses')
    if uses:
        shared = shared_blocks.get(uses, {})
        return shared.get('params') or []
    return []


# ============================================================================
# Main pipeline
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Generate YAML models from vendor SVD files.')
    subs = parser.add_subparsers(dest='vendor', required=True,
                                 help='Vendor name (stm32, lpc)')

    vendor_modules = {}
    for name, mod_path in VENDORS.items():
        mod = importlib.import_module(mod_path)
        sub = subs.add_parser(name)
        sub.add_argument('family_code', help='Family code')
        mod.add_cli_args(sub)
        sub.add_argument('output_dir', type=Path, help='Output directory for models')
        sub.add_argument('--audit', action='store_true',
                         help='Report transforms that had no effect (SVD may be fixed)')
        vendor_modules[name] = mod

    args = parser.parse_args()
    ext = vendor_modules[args.vendor]

    family_code = args.family_code
    output_dir = args.output_dir

    ext.validate_args(args)

    config_file = ext.config_path(args)
    families, blocks_config, chip_params, chip_interrupts, shared_blocks, svd_tag = \
        load_family_config(family_code, config_file)

    # Determine which shared blocks this family is responsible for generating
    family_chips = set()
    for fi in families.values():
        family_chips.update(fi['chips'])
    my_shared_blocks = {}
    for bn, bc in shared_blocks.items():
        from_spec = bc.get('from', '')
        from_chip = from_spec.split('.')[0] if '.' in from_spec else ''
        if from_chip in family_chips:
            my_shared_blocks[bn] = bc

    # Map family block types to owned shared block names
    # (block type key in blocks_config may differ from shared block name)
    owned_shared_mapping = {}  # block_type -> shared_block_name
    for bt, bc in blocks_config.items():
        uses_name = bc.get('uses')
        if uses_name and uses_name in my_shared_blocks:
            owned_shared_mapping[bt] = uses_name

    print(f"Extracting {family_code} models from {args.svd_source}")
    print(f"Output directory: {output_dir}")
    if my_shared_blocks:
        print(f"Shared blocks to generate: {', '.join(sorted(my_shared_blocks))}")
    print()

    # ==========================================================================
    # PASS 1: Collect blocks from all subfamilies
    # ==========================================================================
    print(f"{'='*60}")
    print("PASS 1: Collecting blocks from all subfamilies")
    print(f"{'='*60}")

    all_blocks = defaultdict(lambda: defaultdict(list))
    chip_summaries = defaultdict(dict)

    for family_name, family_info in families.items():
        print(f"\nProcessing {family_name} subfamily...")

        # Resolve block configs for this subfamily (applies variant overrides)
        # Exclude blocks with 'uses:' (they reference shared models, no extraction)
        # Exception: owned shared blocks — resolve uses to get from + instances
        effective_blocks = {}
        for bt, bc in blocks_config.items():
            resolved = _resolve_block_config(bc, family_name)
            if 'uses' not in resolved:
                effective_blocks[bt] = resolved
            elif resolved.get('uses') in my_shared_blocks:
                effective_blocks[bt] = _resolve_uses_config(resolved, shared_blocks)

        for chip_name in family_info['chips']:
            try:
                result = ext.open_svd(args, chip_name)
                if result is None:
                    print(f"  {chip_name}: SVD not found, skipping")
                    continue

                root, extra_meta = result
                blocks, _, chip_device = svd.processChip(root, chip_name, effective_blocks)
                svd_version = chip_device.get('version', '') if chip_device else ''

                # Auto-strip instance prefixes from register names
                for bn, bd in blocks.items():
                    from_spec = effective_blocks.get(bn, {}).get('from', '')
                    if '.' in from_spec:
                        inst = from_spec.split('.', 1)[1]
                        _strip_instance_prefix(bd, inst, bn)

                for block_name, block_data in blocks.items():
                    entry = {
                        'data': block_data,
                        'chip': chip_name,
                        'svd_version': svd_version,
                    }
                    entry.update(extra_meta)
                    all_blocks[block_name][family_name].append(entry)

                # Save lightweight chip summary for Pass 3 (chip model generation)
                if chip_device:
                    periph_summary = {}
                    for periph in chip_device.get('peripherals', []):
                        periph_summary[periph['name']] = {
                            'baseAddress': periph.get('baseAddress'),
                            'interrupts': [
                                {'name': i['name'], 'value': i['value']}
                                for i in periph.get('interrupts', [])
                            ]
                        }
                    summary = {
                        'device_meta': {
                            'name': chip_device.get('name'),
                            'version': chip_device.get('version'),
                            'cpu': chip_device.get('cpu'),
                        },
                        'peripherals': periph_summary
                    }
                    summary.update(extra_meta)
                    chip_summaries[family_name][chip_name] = summary

            except Exception as e:
                print(f"  ERROR processing {chip_name}: {e}")

    # ==========================================================================
    # PASS 2: Generate block models (placement driven by config)
    # ==========================================================================
    print(f"\n{'='*60}")
    print("PASS 2: Generating block models")
    print(f"{'='*60}")

    common_blocks_dir = output_dir / family_code
    common_blocks_dir.mkdir(parents=True, exist_ok=True)

    shared_count = 0
    common_count = 0
    family_specific_count = 0
    all_findings = []

    def _format_block_source(entry):
        name = entry.get('svd_path', entry.get('chip', ''))
        return ext.format_source(name, entry.get('svd_version', ''), svd_tag)

    for block_name in sorted(all_blocks.keys()):
        block_families = all_blocks[block_name]

        # Cross-family shared blocks -> top-level placement
        # Block type may differ from shared block name (e.g. OPAMP -> HSOPAMP)
        shared_name = owned_shared_mapping.get(block_name) or (
            block_name if block_name in my_shared_blocks else None)
        if shared_name:
            shared_count += 1
            shared_cfg = my_shared_blocks[shared_name]
            families_present = set(block_families.keys())
            entry = _select_block_entry(
                block_families, families, families_present, shared_cfg)
            block_data = entry['data']
            transforms = shared_cfg.get('transforms')
            if transforms:
                block_data = copy.deepcopy(block_data)
                all_findings.extend(_apply_transforms(
                    block_data, transforms, audit=args.audit,
                    block_name=f"{shared_name} (shared)"))
            block_data = _inject_params(block_data, shared_cfg.get('params'))
            block_data = _inject_source(block_data, _format_block_source(entry))
            block_data['name'] = shared_name
            if shared_cfg.get('description'):
                block_data['description'] = shared_cfg['description']

            svd.dumpModel(block_data, output_dir / shared_name)
            print(f"  * {shared_name:20} -> top-level (cross-family shared)")
            continue

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
                    all_findings.extend(_apply_transforms(
                        block_data, transforms, audit=args.audit,
                        block_name=f"{block_name} ({fam_name})"))
                block_data = _inject_params(block_data, block_cfg.get('params'))
                block_data = _inject_source(block_data, _format_block_source(entry))
                if resolved.get('description'):
                    block_data['description'] = resolved['description']

                svd.dumpModel(block_data, family_dir / block_name)

        # Non-variant subfamilies -> shared or subfamily-specific placement
        default_present = {f for f in families_present if f not in variants}
        if default_present:
            entry = _select_block_entry(
                block_families, families, default_present, block_cfg)
            block_data = entry['data']
            transforms = block_cfg.get('transforms')
            if transforms:
                block_data = copy.deepcopy(block_data)
                all_findings.extend(_apply_transforms(
                    block_data, transforms, audit=args.audit,
                    block_name=block_name))
            block_data = _inject_params(block_data, block_cfg.get('params'))
            block_data = _inject_source(block_data, _format_block_source(entry))
            if block_cfg.get('description'):
                block_data['description'] = block_cfg['description']

            if len(default_present) == 1:
                # Only one subfamily uses base -> place in subfamily dir
                fam_name = next(iter(default_present))
                family_specific_count += 1
                family_dir = output_dir / family_code / fam_name
                family_dir.mkdir(parents=True, exist_ok=True)
                svd.dumpModel(block_data, family_dir / block_name)
            else:
                common_count += 1
                svd.dumpModel(block_data, common_blocks_dir / block_name)
                print(f"  + {block_name:20} -> {family_code} (shared)")

    # ==========================================================================
    # PASS 3: Generate chip models
    # ==========================================================================
    print(f"\n{'='*60}")
    print("PASS 3: Generating chip models")
    print(f"{'='*60}")

    canonical_interrupts = _build_canonical_interrupts(blocks_config, shared_blocks)
    # Config-driven interrupt lookup: used by LPC (interrupt names don't follow
    # prefix-stripping patterns). STM32 uses algorithmic resolution only.
    if hasattr(ext, 'use_config_interrupt_map') and ext.use_config_interrupt_map:
        config_interrupt_map = _build_config_interrupt_mapping(blocks_config, shared_blocks)
    else:
        config_interrupt_map = {}
    chip_model_count = 0
    unmatched_interrupts = defaultdict(set)  # block_type -> set of unmatched raw names

    for subfamily_name, subfamily_info in families.items():
        instance_to_block = _build_instance_to_block(blocks_config, subfamily_name)

        # Determine model file names per block type for this subfamily
        # (shared block name for uses: blocks, block type name otherwise)
        block_model_names = {}
        for bt, bc in blocks_config.items():
            resolved = _resolve_block_config(bc, subfamily_name)
            uses = resolved.get('uses')
            block_model_names[bt] = uses if uses else bt

        for chip_name in subfamily_info['chips']:
            summary = chip_summaries.get(subfamily_name, {}).get(chip_name)
            if not summary:
                continue

            device_meta = summary['device_meta']

            # Build instances and interrupt table
            instances = {}
            interrupt_table = defaultdict(list)
            interrupt_offset = 16  # Cortex-M: 16 system exceptions before IRQs

            for inst_name, periph in summary['peripherals'].items():
                block_type = instance_to_block.get(inst_name)
                if not block_type:
                    continue  # Unmodeled peripheral

                canonical_names = canonical_interrupts.get(block_type, set())

                # Map interrupts: config-driven lookup first, then algorithmic
                mapped_intrs = []
                for raw_intr in periph.get('interrupts', []):
                    raw_name = raw_intr['name']
                    canonical = config_interrupt_map.get((block_type, raw_name))
                    if not canonical:
                        canonical = _resolve_interrupt_name(
                            raw_name, inst_name, canonical_names)
                    if canonical:
                        mapped_intrs.append({
                            'name': canonical, 'value': raw_intr['value']
                        })
                    else:
                        unmatched_interrupts[block_type].add(raw_name)

                # Apply chip_interrupts overrides/injections
                intr_overrides = _resolve_chip_interrupts(
                    chip_interrupts, subfamily_name, chip_name,
                    inst_name, block_type)
                if intr_overrides:
                    existing = {i['name']: i for i in mapped_intrs}
                    for canonical_name, irq_value in intr_overrides.items():
                        existing[canonical_name] = {
                            'name': canonical_name, 'value': irq_value}
                    mapped_intrs = sorted(
                        existing.values(), key=lambda i: i['value'])

                # Build interrupt table from final mapped interrupts
                for intr in mapped_intrs:
                    vec = intr['value'] + interrupt_offset
                    entry = f"{inst_name}.{intr['name']}"
                    if entry not in interrupt_table[vec]:
                        interrupt_table[vec].append(entry)

                # Resolve parameters
                params_list = []
                param_decls = _get_param_decls(
                    block_type, blocks_config, shared_blocks, subfamily_name)
                for param in param_decls:
                    value = _resolve_chip_param(
                        chip_params, subfamily_name, chip_name,
                        inst_name, block_type, param['name'],
                        default=param.get('default'))
                    if value is not None:
                        params_list.append({'name': param['name'], 'value': value})

                instances[inst_name] = {
                    'baseAddress': periph['baseAddress'],
                    'model': block_model_names.get(block_type, block_type),
                    'interrupts': mapped_intrs,
                    'parameters': params_list,
                }

            # Assemble chip model
            source_name = summary.get('svd_path', chip_name)
            source = ext.format_source(
                source_name, device_meta.get('version', ''), svd_tag)
            chip_model = {
                'name': device_meta.get('name', chip_name),
                'source': source,
                'cpu': device_meta.get('cpu', {}),
                'interruptOffset': interrupt_offset,
                'interrupts': dict(sorted(interrupt_table.items())),
                'instances': dict(sorted(instances.items())),
            }

            # Write chip model
            subfamily_dir = output_dir / family_code / subfamily_name
            subfamily_dir.mkdir(parents=True, exist_ok=True)
            svd.dumpDevice(chip_model, subfamily_dir / chip_name)
            chip_model_count += 1

    print(f"\n  Chip models generated: {chip_model_count}")
    if unmatched_interrupts:
        print(f"\n  Unmatched interrupts (raw SVD names not resolved to canonical):")
        for bt in sorted(unmatched_interrupts):
            names = sorted(unmatched_interrupts[bt])
            print(f"    {bt}: {', '.join(names)}")

    # ==========================================================================
    # Summary
    # ==========================================================================
    print(f"\n{'='*60}")
    print(f"Generation Summary:")
    if shared_count:
        print(f"  Cross-family shared blocks:    {shared_count}")
    print(f"  Common blocks ({family_code}):     {common_count}")
    print(f"  Family-specific blocks:        {family_specific_count}")
    print(f"  Total block types processed:   {len(all_blocks)}")
    print(f"  Chip models generated:         {chip_model_count}")
    print(f"{'='*60}")

    # Audit summary
    if args.audit:
        noops = [(b, d, det) for b, cat, d, det in all_findings if cat == 'noop']
        partials = [(b, d, det) for b, cat, d, det in all_findings if cat == 'partial']
        if noops or partials:
            print(f"\nAUDIT: Transform health report")
            print(f"{'='*60}")
            if noops:
                print("NO-OP (safe to remove):")
                for block_name, desc, _ in noops:
                    print(f"  {block_name}: {desc}")
            if partials:
                if noops:
                    print()
                print("PARTIALLY OBSOLETE (review needed):")
                for block_name, desc, details in partials:
                    print(f"  {block_name}: {desc}")
                    if details:
                        for line in details:
                            print(f"    {line}")
            print(f"\nTotal: {len(noops)} no-op, {len(partials)} partially obsolete")
            print(f"Review these in {config_file} and {ext.errata_path()}")
        else:
            print(f"\nAUDIT: All transforms are active (no no-ops detected)")


if __name__ == '__main__':
    main()
