#!/usr/bin/env python3
"""Broaden new-schema `outputs:` patterns in every vendor config to cover
the SVD raw names that the legacy step-5 fallback in
`_resolve_interrupt_name` was catching.

Input: a TSV file (typically /tmp/step5_audit.tsv) where each line is

    <block_type>\t<canonical>\t<raw_name>

The file is produced by running every vendor's generator with
`SODACAT_STEP5_AUDIT=<path>` set in the environment — the step-5 path
appends one line per hit.

For each (block, canonical), find the matching `outputs:` entry in every
vendor YAML that declares the block (in shared_blocks or per-family
blocks).  If the existing `pattern:` is a literal alternation (or single
literal), extend it with the audited raws; if it's a complex regex, skip
and report it for manual review.

Usage:
    python3 tools/broaden_step5_patterns.py /tmp/step5_audit.tsv
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import SingleQuotedScalarString


# A literal-alternation pattern is `^X$` or `^(X|Y|Z)$` where each
# alternative is plain identifier characters.  Anything else (e.g.
# `^I2C\d+_EV$`) is a complex regex we don't touch — the author wrote it
# deliberately.
_SINGLE = re.compile(r'^\^([A-Za-z0-9_]+)\$$')
_ALT = re.compile(r'^\^\(([A-Za-z0-9_|]+)\)\$$')


def extract_literals(pattern):
    """Return list of literal alternatives, or None if pattern is complex."""
    if pattern is None:
        return None
    m = _ALT.match(pattern)
    if m:
        return m.group(1).split('|')
    m = _SINGLE.match(pattern)
    if m:
        return [m.group(1)]
    return None


def build_pattern(literals):
    if len(literals) == 1:
        return f'^{literals[0]}$'
    return '^(' + '|'.join(literals) + ')$'


def broaden_entry(outputs_node, canonical, raws_to_add):
    """Mutate outputs_node[canonical]'s pattern to include raws_to_add.
    Returns (updated, reason).  reason is one of:
        'extended', 'no-op' (already covers), 'no-pattern',
        'complex-skip', 'missing-canonical'.
    """
    if canonical not in outputs_node:
        return False, 'missing-canonical'
    spec = outputs_node[canonical]
    if not isinstance(spec, dict):
        return False, 'missing-canonical'
    pattern = spec.get('pattern')
    if pattern is None:
        return False, 'no-pattern'
    lits = extract_literals(pattern)
    if lits is None:
        return False, 'complex-skip'
    new_lits = list(lits)
    for r in raws_to_add:
        if r not in new_lits:
            new_lits.append(r)
    if new_lits == lits:
        return False, 'no-op'
    spec['pattern'] = SingleQuotedScalarString(build_pattern(new_lits))
    return True, 'extended'


def walk_and_broaden(doc, to_broaden, path_prefix, summary):
    """Walk a YAML doc (loaded by ruamel) and broaden patterns where the
    block name matches an entry in to_broaden.

    to_broaden: dict (block_name) -> {canonical: [raws_to_add]}
    summary: list of (path, canonical, reason, raws-if-updated).

    For family blocks that use `uses:` and don't carry their own outputs
    override, we also broaden the shared block's pattern (since that's
    where the resolution actually happens).
    """
    shared_blocks = doc.get('shared_blocks') or {}

    def visit_blocks(blocks_node, where):
        if not isinstance(blocks_node, dict):
            return
        for block_name, block_cfg in blocks_node.items():
            if not isinstance(block_cfg, dict):
                continue
            block_path = f"{where}.{block_name}"
            if block_name in to_broaden:
                outputs = block_cfg.get('outputs')
                uses_name = block_cfg.get('uses')
                if outputs:
                    # Block has its own outputs — broaden them.
                    for canonical, raws in to_broaden[block_name].items():
                        updated, reason = broaden_entry(outputs, canonical, raws)
                        summary.append((block_path, canonical, reason, raws if updated else None))
                elif uses_name and uses_name in shared_blocks:
                    # Block uses shared — broaden the shared block's outputs.
                    shared_outputs = shared_blocks[uses_name].get('outputs')
                    if shared_outputs:
                        for canonical, raws in to_broaden[block_name].items():
                            updated, reason = broaden_entry(shared_outputs, canonical, raws)
                            # Tag the path as the shared destination
                            shared_path = f"{path_prefix}.shared_blocks.{uses_name} (via {block_path})"
                            summary.append((shared_path, canonical, reason, raws if updated else None))
            # Recurse into variants
            if 'variants' in block_cfg:
                visit_blocks(block_cfg['variants'], f"{block_path}.variants")

    if shared_blocks:
        visit_blocks(shared_blocks, f"{path_prefix}.shared_blocks")
    if 'families' in doc:
        for fam_code, fam_cfg in doc['families'].items():
            if isinstance(fam_cfg, dict) and 'blocks' in fam_cfg:
                visit_blocks(fam_cfg['blocks'], f"{path_prefix}.families.{fam_code}.blocks")


def load_audit(audit_path):
    by_block = defaultdict(lambda: defaultdict(list))
    seen = set()
    for line in audit_path.read_text().splitlines():
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) != 3:
            continue
        block, canonical, raw = parts
        key = (block, canonical, raw)
        if key in seen:
            continue
        seen.add(key)
        by_block[block][canonical].append(raw)
    return by_block


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('audit_tsv', type=Path)
    ap.add_argument('configs', type=Path, nargs='*',
                    default=[Path('svd/ST/STM32.yaml'),
                             Path('svd/NXP/LPC.yaml'),
                             Path('svd/NXP/MCX.yaml'),
                             Path('svd/Microchip/Microchip.yaml'),
                             Path('svd/Raspberry/Raspberry.yaml'),
                             Path('svd/ESP/ESP32.yaml')])
    args = ap.parse_args()

    to_broaden = load_audit(args.audit_tsv)
    print(f"Audit entries: {sum(len(rs) for rs in to_broaden.values())} (block,canonical) pairs")

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)

    for cfg in args.configs:
        if not cfg.exists():
            print(f"  skip {cfg} (not found)")
            continue
        with open(cfg) as f:
            doc = yaml.load(f)
        summary = []
        walk_and_broaden(doc, to_broaden, cfg.stem, summary)
        extended = [s for s in summary if s[2] == 'extended']
        complex_skip = [s for s in summary if s[2] == 'complex-skip']
        if extended:
            with open(cfg, 'w') as f:
                yaml.dump(doc, f)
            print(f"\n{cfg}: {len(extended)} pattern(s) extended")
            for path, canonical, _, raws in extended:
                print(f"  {path}.{canonical} += {raws}")
        else:
            print(f"\n{cfg}: no changes")
        if complex_skip:
            print(f"  complex patterns skipped (manual review):")
            for path, canonical, _, _ in complex_skip:
                print(f"    {path}.{canonical}")


if __name__ == '__main__':
    main()
