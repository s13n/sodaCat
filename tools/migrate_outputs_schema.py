#!/usr/bin/env python3
"""Convert a vendor family config from the old SVD-raw-keyed `outputs:`
schema to the new canonical-keyed schema.

Migration is behavior-preserving: every old-schema entry produces an
explicit `pattern:` in the new schema, so SVD-raw resolution stays
bit-identical.  Match-everything (default `pattern: '.*'`) is left as
an opt-in optimisation for authors to apply block-by-block after
migration, once they've verified no SVD raws would be inadvertently
absorbed.

Walks every `outputs:` map under:
  - top-level shared_blocks
  - families.<F>.blocks.<B>
  - families.<F>.blocks.<B>.variants.<S>

Old-schema entries (string-valued or dict with `name:`) get grouped by
canonical; the new entry's pattern is the anchored alternation of the
SVD raws that mapped to that canonical.  A self-mapping single entry
(raw == canonical, the legacy non-SVD convention) becomes a no-pattern
entry in the new schema — pattern absence is the new opt-out marker.

Usage:
    python3 tools/migrate_outputs_schema.py <yaml-path>
    python3 tools/migrate_outputs_schema.py --dry-run <yaml-path>
"""

import argparse
import re
import sys
from pathlib import Path

# Make `tools/` importable when invoked from project root.
sys.path.insert(0, str(Path(__file__).parent))

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import SingleQuotedScalarString

import outputs_schema


def _convert_output_map(old_map):
    """Return a CommentedMap in new schema, behavior-preserving.

    Returns None if old_map is already in new schema (nothing to do).
    """
    if outputs_schema.is_new_outputs_schema(old_map):
        return None

    # Group entries by canonical, preserving first-appearance order.
    groups = {}  # canonical -> [(raw, description), ...]
    canonical_order = []
    for raw_name, mapping in old_map.items():
        if isinstance(mapping, dict):
            canonical = mapping['name']
            desc = mapping.get('description', '') or ''
        else:
            canonical = mapping
            desc = ''
        if canonical not in groups:
            canonical_order.append(canonical)
            groups[canonical] = []
        groups[canonical].append((raw_name, desc))

    out = CommentedMap()
    for canonical in canonical_order:
        entries = groups[canonical]
        raws = [r for r, _ in entries]
        description = next((d for _, d in entries if d), '')

        entry = CommentedMap()
        if description:
            entry['description'] = description
        # Always produce an explicit pattern.  A self-mapping entry
        # (raw == canonical) in the old schema doesn't imply "non-SVD" —
        # H7 EXTI's `WKUP: WKUP` carries an SVD-sourced interrupt whose
        # raw happens to match the canonical.  Dropping the pattern
        # would silently turn it into a non-SVD declaration and lose the
        # SVD-provided description.  Authors can post-migrate manually
        # drop the pattern on entries they've verified are non-SVD.
        if len(raws) == 1:
            pattern_str = '^' + re.escape(raws[0]) + '$'
        else:
            pattern_str = '^(' + '|'.join(re.escape(r) for r in raws) + ')$'
        # Single-quote so YAML doesn't interpret regex meta as YAML.
        entry['pattern'] = SingleQuotedScalarString(pattern_str)
        out[canonical] = entry
    return out


def _walk_blocks(blocks_node, path_prefix, changes):
    """Walk a map of block_name → block_cfg.  For each block_cfg with an
    `outputs:` key in old schema, convert it.  Recurses into `variants:`.
    """
    if not isinstance(blocks_node, dict):
        return
    for block_name, block_cfg in blocks_node.items():
        if not isinstance(block_cfg, dict):
            continue
        path = f"{path_prefix}.{block_name}"
        if 'outputs' in block_cfg:
            new_outputs = _convert_output_map(block_cfg['outputs'])
            if new_outputs is not None:
                block_cfg['outputs'] = new_outputs
                changes.append(path)
        if 'variants' in block_cfg:
            _walk_blocks(block_cfg['variants'], f"{path}.variants", changes)


def migrate_file(path, dry_run=False):
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)

    with open(path) as f:
        doc = yaml.load(f)

    changes = []

    if 'shared_blocks' in doc:
        _walk_blocks(doc['shared_blocks'], 'shared_blocks', changes)

    if 'families' in doc:
        for fam_code, fam_cfg in doc['families'].items():
            if not isinstance(fam_cfg, dict):
                continue
            if 'blocks' in fam_cfg:
                _walk_blocks(fam_cfg['blocks'], f'families.{fam_code}.blocks', changes)

    print(f"Converted {len(changes)} outputs map(s) in {path}")
    for c in changes:
        print(f"  {c}")

    if not dry_run and changes:
        with open(path, 'w') as f:
            yaml.dump(doc, f)
        print(f"Wrote {path}")


def main():
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('yaml_path', type=Path)
    p.add_argument('--dry-run', action='store_true',
                   help='Show what would change without writing.')
    args = p.parse_args()
    migrate_file(args.yaml_path, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
