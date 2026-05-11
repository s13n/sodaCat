#!/usr/bin/env python3
"""Validate that chip-level interrupt names match their block model's canonical list.

For every chip model (top-level `instances:` map), for every instance, look up
the referenced block YAML via the chip's `models:` map and verify that each
interrupt name the chip declares appears in the block's `interrupts:` list.

This catches:

  * Stale chip YAMLs that still use a SVD-raw interrupt name after the block's
    canonical name was renamed.
  * Hand-maintained chip YAMLs that invented an interrupt name the block
    doesn't know about — drivers that switch on the block's canonical names
    would never see those entries.

The block index is built once over the full `--models-root` tree so cross-vendor
chips (e.g. ARM/MPS2 chips referencing models in models/ARM/) resolve correctly
regardless of which globs are passed in `--docs`.

Usage:
    python3 tools/validate_chip_interrupts.py \
        --models-root models/ --docs "models/**/*.yaml"
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


def build_block_index(models_root):
    """Map 'Vendor/.../BlockName' (no extension) -> set of canonical IRQ names.

    A YAML file is treated as a block model if it has a top-level `registers`
    key.  Chip models (which have `instances` instead) are skipped.
    """
    index = {}
    root = Path(models_root)
    for f in root.rglob('*.yaml'):
        data = _safe_load(f)
        if not isinstance(data, dict) or 'registers' not in data:
            continue
        rel = f.relative_to(root).with_suffix('').as_posix()
        index[rel] = {i['name'] for i in (data.get('interrupts') or [])}
    return index


def is_chip(data):
    return isinstance(data, dict) and isinstance(data.get('instances'), dict)


def check_chip(chip_path, data, block_index):
    """Return [(check_id, message)] for IRQ name mismatches in one chip."""
    errors = []
    models_map = data.get('models') or {}
    for inst_name, inst in data['instances'].items():
        if not isinstance(inst, dict):
            continue
        model = inst.get('model')
        if not model:
            continue
        block_path = models_map.get(model, model)
        canon = block_index.get(block_path)
        if canon is None:
            # No matching block file — could be an external IP not in the repo.
            # The chip schema validator catches missing models-map entries; we
            # only flag interrupt mismatches here.
            continue
        for irq in inst.get('interrupts') or []:
            name = irq.get('name')
            if name and name not in canon:
                errors.append((
                    'intr-canon',
                    f"instance '{inst_name}' (model={model}, "
                    f"block={block_path}): interrupt '{name}' not in "
                    f"block's canonical list {sorted(canon)}"
                ))
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--models-root', default='models',
                    help="Root of models tree (default: models)")
    ap.add_argument('-d', '--docs', nargs='+', required=True,
                    help='Chip YAML files or glob patterns to check')
    args = ap.parse_args()

    block_index = build_block_index(args.models_root)

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
        data = _safe_load(f)
        if not is_chip(data):
            n_skipped += 1
            continue
        n_validated += 1
        errs = check_chip(f, data, block_index)
        if errs:
            had_errors = True
            print(f"❌ {f}:")
            for check, msg in errs:
                print(f"   {check:11s}│ {msg}")
        else:
            print(f"✅ {f}")

    print(f"\nValidated {n_validated} chip files; "
          f"skipped {n_skipped} non-chip files; "
          f"block index covers {len(block_index)} models",
          file=sys.stderr)
    return 1 if had_errors else 0


if __name__ == '__main__':
    sys.exit(main())
