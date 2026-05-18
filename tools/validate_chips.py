#!/usr/bin/env python3
"""Validate chip-level YAML models against schema and cross-reference rules.

Phase 1: JSON Schema (Draft 7) against `schemas/chip.schema.yaml`.

Phase 2: Semantic checks not expressible in standard JSON Schema:

  Uniqueness:
    * parameter names unique within each instance

  Cross-references:
    * each instance's `model` is present in the chip's `models` index

Per-instance `connections:` is a YAML mapping, so signal-name uniqueness is
enforced by the parser.  Cross-instance destination validity (e.g. that
'NVIC.53' refers to a known input) belongs to validate_chip_connections.py.

Files that don't look like chip models (no top-level `instances` map) are
skipped silently — this lets the same glob also feed `validate_peripherals.py`.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jsonschema import Draft7Validator
from validate_lib import find_duplicates, run


_DEFAULT_SCHEMA = str(
    Path(__file__).parent.parent / 'schemas' / 'chip.schema.yaml')


def is_chip(data):
    """Discriminator: chip models have `cpu:` at the top level.

    Subfamily YAMLs now also carry an `instances:` map (the
    subfamily-common subset) but they don't have `cpu:` — only chips do.
    Using `cpu:` as the marker keeps subfamily files out of the
    chip-validator (which would then complain that they're not chips).
    """
    return isinstance(data, dict) and 'cpu' in data


def _merged_models(chip_path, chip):
    """Build the chip's effective models map by walking the inherits chain.

    Chip-level entries override ancestor entries by block name.  Returns
    the chip's own map unchanged when no `inherits:` chain is present.
    """
    if not chip_path:
        return chip.get('models') or {}
    import yaml as _yaml
    from pathlib import Path
    merged = {}
    node = chip
    node_path = Path(chip_path)
    seen = set()
    while node is not None and str(node_path) not in seen:
        seen.add(str(node_path))
        parent_ref = node.get('inherits')
        if parent_ref:
            # Find models/ root by walking up.
            d = node_path.parent
            root = None
            while d != d.parent:
                if d.name == 'models':
                    root = d
                    break
                d = d.parent
            if root is None:
                break
            parent_path = root / f'{parent_ref}.yaml'
            if not parent_path.exists():
                break
            with open(parent_path) as f:
                parent = _yaml.safe_load(f) or {}
            # Root contributes first; chip-level wins at the end.
            for name, p in (parent.get('models') or {}).items():
                merged.setdefault(name, p)
            node = parent
            node_path = parent_path
        else:
            break
    for name, p in (chip.get('models') or {}).items():
        merged[name] = p
    return merged


def validate_semantics(data, file_path=None):
    errors = []

    instances = data.get('instances') or {}
    models = _merged_models(file_path, data)

    for inst_name, inst in instances.items():
        if not isinstance(inst, dict):
            continue
        # Parameter-name uniqueness within the instance.
        for n, c in find_duplicates(inst.get('parameters')).items():
            errors.append(('param-dup',
                           f"instance '{inst_name}': parameter '{n}' "
                           f"declared {c} times"))
        # Model reference resolves to an entry in the models index.
        m = inst.get('model')
        if m and m not in models:
            errors.append(('model-ref',
                           f"instance '{inst_name}' references model '{m}' "
                           f"which is not in the models index"))

    return errors


def main():
    run(
        parser_desc='Validate chip-level YAML models',
        default_schema=_DEFAULT_SCHEMA,
        draft_class=Draft7Validator,
        phase2_func=validate_semantics,
        accept_doc=is_chip,
    )


if __name__ == '__main__':
    main()
