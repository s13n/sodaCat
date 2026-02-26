#!/usr/bin/env python3
"""Check NXP reference manuals against known latest revisions.

Compares local PDF files in docs/NXP/ against revision data tracked in
svd/NXP/LPC.yaml and reports which manuals are up to date, outdated,
missing, or untracked.

Usage:
    python3 tools/check_nxp_manuals.py [--config CONFIG] [--docs-dir DIR]
"""

import argparse
import re
import sys
from pathlib import Path

from ruamel.yaml import YAML


def parse_rev(rev_str):
    """Parse a revision string into a comparable tuple of ints."""
    try:
        return tuple(int(x) for x in str(rev_str).split('.'))
    except (ValueError, AttributeError):
        return (0,)


def collect_config_manuals(config_path):
    """Extract ref_manual entries from all subfamilies in the config."""
    yaml = YAML()
    with open(config_path, 'r') as f:
        config = yaml.load(f)

    manuals = {}
    for family_code, family_cfg in (config.get('families') or {}).items():
        for sf_name, sf_cfg in (family_cfg.get('subfamilies') or {}).items():
            rm = sf_cfg.get('ref_manual')
            if not rm:
                continue
            name = rm.get('name', '')
            manuals[name] = {
                'subfamily': sf_name,
                'family': family_code,
                'rev': str(rm.get('rev', '')),
                'date': str(rm.get('date', '')),
                'url': rm.get('url', ''),
            }
    return manuals


def scan_local_pdfs(docs_dir):
    """Scan docs directory for PDFs and extract UM number + revision."""
    # Pattern: "UM11029 -- LPC84x (Rev. 1.7).pdf"
    pattern = re.compile(r'^(UM\d+)\s+--\s+(.+?)\s+\(Rev\.\s*([^)]+)\)\.pdf$')
    local = {}
    unmatched = []

    for pdf in sorted(docs_dir.glob('*.pdf')):
        m = pattern.match(pdf.name)
        if m:
            local[m.group(1)] = {
                'filename': pdf.name,
                'family': m.group(2),
                'rev': m.group(3).strip(),
            }
        else:
            unmatched.append(pdf.name)

    return local, unmatched


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--config', type=Path,
                        default=Path(__file__).parent.parent / 'svd' / 'NXP' / 'LPC.yaml',
                        help='Path to NXP LPC config YAML')
    parser.add_argument('--docs-dir', type=Path,
                        default=Path(__file__).parent.parent / 'docs' / 'NXP',
                        help='Path to local reference manual directory')
    args = parser.parse_args()

    if not args.config.exists():
        print(f"Error: Config not found: {args.config}", file=sys.stderr)
        sys.exit(1)
    if not args.docs_dir.is_dir():
        print(f"Error: Docs directory not found: {args.docs_dir}", file=sys.stderr)
        sys.exit(1)

    config_manuals = collect_config_manuals(args.config)
    local_pdfs, unmatched_files = scan_local_pdfs(args.docs_dir)

    up_to_date = []
    updates = []
    missing = []

    for um, info in sorted(config_manuals.items()):
        local = local_pdfs.get(um)
        if not local:
            missing.append((um, info))
        elif parse_rev(info['rev']) > parse_rev(local['rev']):
            updates.append((um, info, local))
        else:
            up_to_date.append((um, info, local))

    # Untracked: local files not in config
    config_names = set(config_manuals.keys())
    untracked = [(um, local_pdfs[um]) for um in sorted(local_pdfs) if um not in config_names]

    # Print results
    if up_to_date:
        print("UP TO DATE:")
        for um, info, local in up_to_date:
            print(f"  {um}  Rev. {local['rev']:>5}  {info['subfamily']}")

    if updates:
        print("\nUPDATE AVAILABLE:")
        for um, info, local in updates:
            print(f"  {um}  Rev. {local['rev']:>5} -> {info['rev']}  {info['subfamily']}")
            print(f"         {info['url']}")

    if missing:
        print("\nMISSING:")
        for um, info in missing:
            print(f"  {um}  Rev. {info['rev']:>5}  {info['subfamily']}")
            print(f"         {info['url']}")

    if untracked or unmatched_files:
        print("\nUNTRACKED:")
        for um, local in untracked:
            print(f"  {um}  Rev. {local['rev']:>5}  {local['filename']}")
        for filename in unmatched_files:
            print(f"  (no UM#)          {filename}")

    # Summary
    total = len(config_manuals)
    print(f"\n{len(up_to_date)}/{total} up to date", end="")
    if updates:
        print(f", {len(updates)} update(s) available", end="")
    if missing:
        print(f", {len(missing)} missing", end="")
    print()

    return 1 if updates or missing else 0


if __name__ == '__main__':
    sys.exit(main())
