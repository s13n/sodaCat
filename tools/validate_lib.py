"""Shared utilities for sodaCat model validators.

Mirrors the two-phase pattern from `validate_clocks.py`:

  Phase 1 — JSON Schema (structural).
  Phase 2 — Python code (semantic, e.g. uniqueness, cross-references).

Standard JSON Schema cannot express "every `name` key in this array is
unique" cleanly, so per-scope uniqueness lives in Phase 2.

This module exposes the bits that are reused across `validate_peripherals.py`
and `validate_chips.py`: schema loading, schema-error extraction, the
generic uniqueness helper, and a CLI driver.  Domain-specific Phase-2
checks live in the validator scripts themselves.
"""

import argparse
import glob
import pathlib
import sys
from collections import defaultdict

import yaml


def load_schema(path, draft_class):
    """Load a YAML/JSON schema file and return a configured validator."""
    schema = yaml.safe_load(pathlib.Path(path).read_text(encoding='utf-8'))
    draft_class.check_schema(schema)
    return draft_class(schema)


_MSG_LIMIT = 200


def _trim(msg):
    """Shorten jsonschema messages that quote whole sub-documents."""
    msg = ' '.join(msg.split())
    if len(msg) > _MSG_LIMIT:
        msg = msg[:_MSG_LIMIT] + ' ...'
    return msg


def schema_errors(data, validator):
    """Return [(json-pointer, trimmed message)] for every schema violation."""
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return [
        ('/'.join(str(p) for p in e.path) or '(root)', _trim(e.message))
        for e in errors
    ]


def find_duplicates(items, key='name'):
    """Return {value: count} for `items[*][key]` values that occur more than once.

    Items lacking the key, or with non-hashable values, are skipped — the
    schema is responsible for catching missing required keys.
    """
    counts = defaultdict(int)
    for it in items or []:
        if not isinstance(it, dict):
            continue
        v = it.get(key)
        if isinstance(v, (str, int)):
            counts[v] += 1
    return {v: c for v, c in counts.items() if c > 1}


def run(parser_desc, default_schema, draft_class, phase2_func,
        accept_doc=lambda data: True):
    """Generic validator CLI.

    `phase2_func(data)` returns [(check_id, message)] for semantic violations.
    `accept_doc(data)` decides whether a parsed YAML doc is the kind this
    validator handles — files that don't match are skipped silently.  This
    lets a single CI command invocation walk `models/**/*.yaml` while each
    validator only inspects the model type it understands.
    """
    ap = argparse.ArgumentParser(description=parser_desc)
    ap.add_argument('-s', '--schema', default=default_schema,
                    help='Path to JSON/YAML schema')
    ap.add_argument('-d', '--docs', nargs='+', required=True,
                    help='YAML files or glob patterns')
    args = ap.parse_args()

    validator = load_schema(args.schema, draft_class)

    files = []
    for pattern in args.docs:
        files.extend(glob.glob(pattern, recursive=True))
    if not files:
        print('No files matched', file=sys.stderr)
        sys.exit(2)

    n_validated = 0
    n_skipped = 0
    had_errors = False
    for f in sorted(set(files)):
        if not (f.endswith('.yaml') or f.endswith('.yml')):
            continue
        data = yaml.safe_load(pathlib.Path(f).read_text(encoding='utf-8'))
        if not accept_doc(data):
            n_skipped += 1
            continue
        n_validated += 1
        s_errs = schema_errors(data, validator)
        # Skip Phase 2 if Phase 1 failed — malformed input can confuse it.
        p_errs = phase2_func(data) if not s_errs else []
        if s_errs or p_errs:
            had_errors = True
            print(f"❌ {f}:")
            for loc, msg in s_errs:
                print(f"   schema  │ at {loc}: {msg}")
            for check, msg in p_errs:
                print(f"   {check:9s}│ {msg}")
        else:
            print(f"✅ {f}")

    print(f"\nValidated {n_validated} files; skipped {n_skipped} non-matching",
          file=sys.stderr)
    sys.exit(1 if had_errors else 0)
