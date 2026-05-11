#!/usr/bin/env python3
"""Cross-reference every {instance, reg, field} citation in a clock-tree
specification against the actual extracted block models.

Clock-tree topology references registers and fields by name (e.g.
`{reg: CFGR, field: SW}`).  Those names are sourced from the reference
manual, while the register-set itself is extracted from the SVD.  The
two can drift independently — a SVD update may rename a field, or a
hand-authored clock-tree edit can introduce a typo.  This validator
walks every reference, resolves the target block via a chip's
`models:` map (an arbitrary chip that consumes the clock spec — found
by scanning for `clocktree:` / `inherits:` references), and checks
that the register and field exist.

Usage:
    python3 tools/validate_clock_refs.py [--models-root models]
        --docs "models/**/*.yaml"

Files that don't look like clock specs (no `signals:` at the top level
and no `clocks:` section) are skipped silently, so the docs glob can
be the same broad pattern other validators use.
"""

import argparse
import glob
import sys
from pathlib import Path

import yaml


def _safe_load(path):
    try:
        return yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    except yaml.YAMLError:
        return None


def _clock_content(data):
    """Return the clock-tree content dict if `data` is a clock spec, else None.

    Recognises both shapes: legacy clock-tree files (signals: at top level)
    and subfamily-shaped files (clocks: at top level).
    """
    if not isinstance(data, dict):
        return None
    if 'clocks' in data and isinstance(data['clocks'], dict):
        return data['clocks']
    if 'signals' in data:
        return data
    return None


def _collect_refs(node, default_instance, out, path=''):
    """Walk the clock content and collect every {reg, field, instance} ref."""
    if isinstance(node, dict):
        if 'reg' in node:
            out.append({
                'instance': node.get('instance', default_instance),
                'reg': node['reg'],
                'field': node.get('field'),
                'path': path,
            })
        for k, v in node.items():
            _collect_refs(v, default_instance, out, f'{path}.{k}' if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _collect_refs(v, default_instance, out, f'{path}[{i}]')


_CHIP_INDEX = None  # populated by build_chip_index; spec-path -> chip-path


def build_chip_index(models_root):
    """Pre-scan all chip YAMLs once, building {clock-spec-target: chip-path}.

    Avoids O(M×N) re-scanning when validating multiple clock specs in one run.
    The index follows `inherits:` chains so a chip that inherits from a
    subfamily that itself inherits from a shared spec ends up under the
    shared spec's target as well — letting `validate_clock_refs` resolve
    vendor-wide shared specs (e.g. Microchip SAM_Gen1) via their consumers.
    """
    # First pass: gather every file's inherits link and whether it's a chip.
    inherits_link = {}        # rel-path -> rel-path-of-parent
    chip_paths = {}           # rel-path -> filesystem path
    for f in models_root.rglob('*.yaml'):
        data = _safe_load(f)
        if not isinstance(data, dict):
            continue
        rel = f.relative_to(models_root).with_suffix('').as_posix()
        parent = data.get('clocktree') or data.get('inherits')
        if parent:
            inherits_link[rel] = parent
        if 'instances' in data:
            chip_paths[rel] = f

    # Second pass: each chip propagates as a consumer of every ancestor
    # reachable via the inherits chain.
    index = {}
    for chip_rel, chip_path in chip_paths.items():
        cursor = inherits_link.get(chip_rel)
        seen = set()
        while cursor and cursor not in seen:
            seen.add(cursor)
            index.setdefault(cursor, chip_path)
            cursor = inherits_link.get(cursor)
    return index


def _find_consumer_chip(spec_path, models_root):
    """Return the path to a chip YAML that references this clock spec, or None."""
    target = spec_path.relative_to(models_root).with_suffix('').as_posix()
    if _CHIP_INDEX is None:
        # Lazy build for ad-hoc invocations.
        return _scan_consumer_chip(target, models_root)
    return _CHIP_INDEX.get(target)


def _scan_consumer_chip(target, models_root):
    for f in models_root.rglob('*.yaml'):
        data = _safe_load(f)
        if not isinstance(data, dict) or 'instances' not in data:
            continue
        if data.get('clocktree') == target or data.get('inherits') == target:
            return f
    return None


def _resolve_block_path(chip_path, chip_data, instance_name, models_root):
    """Map an instance name from a chip's `instances:` map to its block YAML.

    Uses the chip's own `models:` index (instance.model -> models[model] ->
    path-without-extension).  Returns None if the instance isn't present
    on the chip (some clock specs cite instances that exist on only some
    chips in the subfamily — e.g. DSIHOST), in which case the caller can
    fall back to searching for a same-named block file near the chip.
    """
    instances = chip_data.get('instances') or {}
    models_map = chip_data.get('models') or {}
    inst = instances.get(instance_name)
    if inst is not None:
        model_name = inst.get('model')
        if model_name:
            rel = models_map.get(model_name, model_name)
            candidate = models_root / f'{rel}.yaml'
            if candidate.exists():
                return candidate
    # Fallback: look near the chip for a block file named after the instance.
    # Walk up from the chip's directory toward models_root.
    dir = chip_path.parent
    while True:
        candidate = dir / f'{instance_name}.yaml'
        if candidate.exists():
            return candidate
        if dir == models_root:
            return None
        dir = dir.parent


def _strip_array(name):
    """Strip an `[N]` or `[%s]` subscript from a register or cluster name.

    The clock-tree refs cite specific cluster indices (e.g. `C[0].AHB3ENR`)
    while block models use templated names (`C[%s]`); validation is per-
    member, so subscripts are ignored on both sides.
    """
    if not name:
        return name
    import re as _re
    return _re.sub(r'\[[^\]]*\]', '', name)


def _load_block_fields(block_path):
    """Return {qualified_register_name: {field_name, ...}} for a block model.

    Walks into cluster arrays so nested registers like `C[%s].AHB3ENR` are
    indexable under both `AHB3ENR` (the leaf) and `C.AHB3ENR` (cluster-
    qualified, subscript-stripped).  Clock-tree refs of the form
    `C[0].AHB3ENR` look up by either form after the same strip.
    """
    data = _safe_load(block_path)
    out = {}
    if not isinstance(data, dict):
        return out

    def _cluster_names(entry):
        """Return the set of concrete cluster names this entry expands to.

        Templated clusters carry a `%s` placeholder in their name and either
        a `dimIndex` (comma-list or arithmetic range) or a `dim` count for
        numeric subscripts.  Clock specs cite concrete forms like `CLK_REF`
        or `C[0]`, so the index needs to expand here to match.
        """
        raw = entry.get('name') or entry.get('displayName') or ''
        if '%s' not in raw:
            return {_strip_array(raw)}
        dim_index = entry.get('dimIndex')
        dim = entry.get('dim')
        if isinstance(dim_index, str):
            indices = [x.strip() for x in dim_index.split(',')]
        elif isinstance(dim_index, list):
            indices = [str(x) for x in dim_index]
        elif isinstance(dim, int):
            indices = [str(i) for i in range(dim)]
        else:
            # Multi-axis arrays (dim/dimIndex as lists) — skip expansion;
            # the subscript-stripped base name is still in the set.
            indices = []
        names = {_strip_array(raw)}  # always include the subscript-stripped form
        for idx in indices:
            names.add(raw.replace('[%s]', idx).replace('%s', idx))
            names.add(_strip_array(raw.replace('[%s]', f'[{idx}]')))
        return {n for n in names if n}

    def _walk(entries, prefixes=('',)):
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            names = _cluster_names(entry)
            if not names:
                continue
            new_prefixes = set()
            for prefix in prefixes:
                for name in names:
                    new_prefixes.add(f'{prefix}{name}' if prefix else name)
            nested = entry.get('registers')
            if nested is not None:
                # Recurse with each concrete cluster prefix.
                _walk(nested, prefixes=tuple(f'{p}.' for p in new_prefixes))
                continue
            fields = {f.get('name') for f in (entry.get('fields') or [])
                      if isinstance(f, dict)}
            for key in new_prefixes | names:
                if key:
                    out.setdefault(key, set()).update(fields)
    _walk(data.get('registers') or [])
    return out


def validate_clock_spec(spec_path, models_root):
    """Return [(check, message)] for every unresolved reference."""
    data = _safe_load(spec_path)
    content = _clock_content(data)
    if content is None:
        return None  # not a clock spec; skip

    default_inst = content.get('instance', '')
    refs = []
    _collect_refs(content, default_inst, refs)
    if not refs:
        return []

    consumer = _find_consumer_chip(spec_path, models_root)
    if consumer is None:
        return [('no-consumer',
                 f"no chip references this clock spec via clocktree: or "
                 f"inherits:; can't resolve instance names")]
    chip_data = _safe_load(consumer)

    # Cache block-field index per resolved path.
    block_cache = {}

    errors = []
    for ref in refs:
        inst, reg, field = ref['instance'], ref['reg'], ref['field']
        block_path = _resolve_block_path(consumer, chip_data, inst, models_root)
        if block_path is None:
            errors.append((
                'no-block',
                f"{ref['path']}: instance '{inst}' "
                f"(consumer chip {consumer.name}) — no block file found"
            ))
            continue
        if block_path not in block_cache:
            block_cache[block_path] = _load_block_fields(block_path)
        fields_by_reg = block_cache[block_path]
        # Strip array subscripts so `C[0].AHB3ENR` matches `C.AHB3ENR` in the
        # index (which itself was built from a templated `C[%s].AHB3ENR`).
        reg_key = _strip_array(reg)
        if reg_key not in fields_by_reg:
            errors.append((
                'no-register',
                f"{ref['path']}: {inst}.{reg} — register not present in "
                f"{block_path.relative_to(models_root)}"
            ))
            continue
        if field is not None and field not in fields_by_reg[reg_key]:
            errors.append((
                'no-field',
                f"{ref['path']}: {inst}.{reg}.{field} — field not present "
                f"in {block_path.relative_to(models_root)} (register has: "
                f"{sorted(fields_by_reg[reg_key])})"
            ))
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--models-root', default='models',
                    help='Root of the models tree (default: models)')
    ap.add_argument('-d', '--docs', nargs='+', required=True,
                    help='Clock-spec YAML files or glob patterns to check')
    args = ap.parse_args()

    models_root = Path(args.models_root).resolve()

    # Pre-build the chip → clock-spec consumer index so each validation call
    # is O(1) instead of re-scanning the whole tree.
    global _CHIP_INDEX
    _CHIP_INDEX = build_chip_index(models_root)

    files = []
    for pattern in args.docs:
        files.extend(glob.glob(pattern, recursive=True))
    if not files:
        print('No files matched', file=sys.stderr)
        return 2

    n_validated = 0
    n_skipped = 0
    had_errors = False
    for f in sorted(set(files)):
        if not f.endswith(('.yaml', '.yml')):
            continue
        path = Path(f).resolve()
        errs = validate_clock_spec(path, models_root)
        if errs is None:
            n_skipped += 1
            continue
        n_validated += 1
        if errs:
            had_errors = True
            print(f"❌ {path.relative_to(Path.cwd())}:")
            for check, msg in errs:
                print(f"   {check:11s}│ {msg}")
        else:
            print(f"✅ {path.relative_to(Path.cwd())}")

    print(f"\nValidated {n_validated} clock specs; "
          f"skipped {n_skipped} non-clock files",
          file=sys.stderr)
    return 1 if had_errors else 0


if __name__ == '__main__':
    sys.exit(main())
