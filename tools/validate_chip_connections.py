#!/usr/bin/env python3
"""Validate chip-level `connections:` entries against their block models.

For every chip model (top-level `instances:` map), for every instance, look up
the referenced block YAML via the chip's `models:` map and check:

  * Output side — each signal name the chip wires (under per-instance
    `connections:`) appears in the block's `outputs:` list.
  * Destination side — each destination string in the value list parses as
    one of the supported shapes:
        <target>.<int>            — integer port (NVIC, DMAMUX, EXTI, …)
        <target>.<port>.<int>     — sub-port + integer slot (TIM2.ITR.0, …)
        <target>.<input_name>     — named input slot, only valid when the
                                    destination block declares an `inputs:`
                                    list containing <input_name>.

This catches:

  * Stale chip YAMLs that still use a SVD-raw signal name after the block's
    canonical name was renamed.
  * Hand-maintained chip YAMLs that invented an output name the block doesn't
    know about — drivers that switch on the block's canonical names would
    never see those entries.
  * Destination typos: malformed strings, non-integer NVIC vectors, named
    inputs that don't appear in the target block's `inputs:` declaration,
    or named inputs aimed at a block that doesn't declare `inputs:` at all.

The block index is built once over the full `--models-root` tree so cross-vendor
chips (e.g. ARM/MPS2 chips referencing models in models/ARM/) resolve correctly
regardless of which globs are passed in `--docs`.

Usage:
    python3 tools/validate_chip_connections.py \
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
    """Map 'Vendor/.../BlockName' (no extension) -> {outputs, inputs} sets.

    A YAML file is treated as a block model if it has a top-level `registers`
    key.  Chip models (which have `instances` instead) are skipped.

    `outputs` is always a set (empty when the block declares no outputs).
    `inputs` is a set when the block declares `inputs:`, or None when the
    block omits the key entirely — the distinction tells the destination
    validator whether named-port destinations (`instance.input_name`) are
    permitted for this block at all.
    """
    index = {}
    root = Path(models_root)
    for f in root.rglob('*.yaml'):
        data = _safe_load(f)
        if not isinstance(data, dict) or 'registers' not in data:
            continue
        rel = f.relative_to(root).with_suffix('').as_posix()
        index[rel] = {
            'outputs': {i['name'] for i in (data.get('outputs') or [])},
            'inputs': ({i['name'] for i in data['inputs']}
                       if 'inputs' in data else None),
        }
    return index


def is_chip(data):
    return isinstance(data, dict) and isinstance(data.get('instances'), dict)


def check_chip(chip_path, data, block_index):
    """Return [(check_id, message)] for signal-name mismatches and malformed
    destinations in one chip."""
    errors = []
    models_map = data.get('models') or {}

    # Build instance → block-index-entry map for this chip, so destination
    # validation can look up the destination block's declared inputs.
    instance_block = {}
    for inst_name, inst in data['instances'].items():
        if not isinstance(inst, dict):
            continue
        model = inst.get('model')
        if not model:
            continue
        block_path = models_map.get(model, model)
        instance_block[inst_name] = (block_path, block_index.get(block_path))

    for inst_name, inst in data['instances'].items():
        if not isinstance(inst, dict):
            continue
        model = inst.get('model')
        if not model:
            continue
        block_path = models_map.get(model, model)
        block_info = block_index.get(block_path)
        canon_outputs = block_info['outputs'] if block_info else None
        connections = inst.get('connections') or {}
        if canon_outputs is not None:
            for name in connections:
                if name not in canon_outputs:
                    errors.append((
                        'out-canon',
                        f"instance '{inst_name}' (model={model}, "
                        f"block={block_path}): connection '{name}' not in "
                        f"block's declared outputs {sorted(canon_outputs)}"
                    ))

        # Destinations follow three shapes:
        #   1. `<target>.<int>`           — integer port at the boundary
        #      (NVIC vectors, DMAMUX request slots, EXTI lines).
        #   2. `<target>.<port>.<int>`    — sub-port + integer slot
        #      (TIM2.ITR.0, ADC1.ext_trg.9 — integer-natural sub-spaces).
        #   3. `<target>.<input_name>`    — named input slot
        #      (HRTIM_Master.bm_ck1) — only valid when the destination
        #      block declares an `inputs:` list containing <input_name>.
        for name, dests in connections.items():
            for dest in (dests or []):
                if not isinstance(dest, str):
                    errors.append((
                        'out-dest',
                        f"instance '{inst_name}': output '{name}' has "
                        f"non-string destination {dest!r}"
                    ))
                    continue
                parts = dest.split('.')
                if not (2 <= len(parts) <= 3) or not all(parts):
                    errors.append((
                        'out-dest',
                        f"instance '{inst_name}': output '{name}' has "
                        f"malformed destination '{dest}' (expected "
                        f"<target>.<port> or <target>.<port>.<int>)"
                    ))
                    continue
                target = parts[0]
                tail = parts[-1]
                try:
                    int(tail)
                    tail_is_int = True
                except ValueError:
                    tail_is_int = False

                # NVIC and similar non-block pseudo-targets are not in
                # the chip's instance map; for them, only integer ports
                # are well-defined.
                target_entry = instance_block.get(target)
                if target == 'NVIC' and not tail_is_int:
                    errors.append((
                        'out-dest',
                        f"instance '{inst_name}': output '{name}' "
                        f"destination '{dest}' has non-integer NVIC vector"
                    ))
                    continue

                if len(parts) == 3:
                    # Sub-port + integer slot form.  Port-name validation
                    # against the destination block is deferred; we only
                    # check the integer slot here.
                    if not tail_is_int:
                        errors.append((
                            'out-dest',
                            f"instance '{inst_name}': output '{name}' "
                            f"destination '{dest}' has non-integer slot "
                            f"after sub-port"
                        ))
                    continue

                # 2-part shape.
                if tail_is_int:
                    # Integer port — always syntactically valid.
                    continue

                # Named-input shape: must match the destination block's
                # declared `inputs:` list.
                if target_entry is None:
                    # Unknown target (not in instances).  Conservatively
                    # accept — could be a pseudo-target like EXTI that's
                    # modelled but not present on this chip yaml's
                    # instance list, or a future Phase-2 target.  The
                    # generator's strict resolution will catch genuine
                    # typos.
                    continue
                _, block_info = target_entry
                if block_info is None:
                    # Block model not in index (rare — likely a path-resolution
                    # miss); skip rather than spuriously fail.
                    continue
                inputs_decl = block_info['inputs']
                if inputs_decl is None:
                    errors.append((
                        'out-dest',
                        f"instance '{inst_name}': output '{name}' "
                        f"destination '{dest}' uses named-input form, "
                        f"but target block declares no inputs: list"
                    ))
                elif tail not in inputs_decl:
                    errors.append((
                        'out-dest',
                        f"instance '{inst_name}': output '{name}' "
                        f"destination '{dest}' references input '{tail}' "
                        f"not in target block's inputs: declaration"
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
