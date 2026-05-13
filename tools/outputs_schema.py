"""Shared helpers for the block-level `outputs:` schema.

Both the family-config interpreter (`extractors/generate_models.py`) and
the SVD processor (`tools/svd.py`) need to resolve SVD raw interrupt
names to canonical output names against the configured outputs map.
This module normalises the map into a uniform list of
`(canonical, description, pattern)` triples and resolves SVD raws
against it.

`pattern` semantics inside a triple:
    None: never matches (non-SVD output, or no SVD source).
    str:  regex matched against SVD raw names via `re.fullmatch`.
          Use '.*' to opt into match-everything.

In an outputs map entry, omitting `pattern:` (or writing `pattern: ~`)
yields pattern=None — i.e. the canonical is declared as an available
output but isn't sourced from any SVD interrupt.  This is the safe
default: a non-SVD output (DMA request, wakeup line) reads as just
`<CANONICAL>:` or `<CANONICAL>: {description: ...}` without needing
an explicit opt-out marker.  Match-everything is opt-in via
`pattern: '.*'` when the author has confirmed every SVD raw on the
block legitimately collapses to the one canonical.
"""

import re


def normalize_outputs(output_map):
    """Return a list of (canonical, description, pattern) triples in
    declaration order.

    `output_map` is the YAML `outputs:` map keyed by canonical name;
    values are dicts with optional `description:` and `pattern:`, or
    YAML null for a bare canonical declaration.
    """
    if not output_map:
        return []

    result = []
    for canonical, spec in output_map.items():
        if spec is None:
            description = ''
            pattern = None
        elif isinstance(spec, dict):
            description = spec.get('description', '') or ''
            pattern = spec.get('pattern')  # absent or null → None
        else:
            raise ValueError(
                f"outputs entry '{canonical}' value must be a dict or null, "
                f"got {type(spec).__name__}")
        result.append((canonical, description, pattern))
    return result


def resolve_canonical(decl_list, raw_name):
    """Return (canonical, description) for the first entry in decl_list
    whose pattern matches raw_name via `re.fullmatch`, or (None, '') if
    no entry matches.  Entries with `pattern is None` are skipped.
    """
    for canonical, description, pattern in decl_list:
        if pattern is None:
            continue
        if re.fullmatch(pattern, raw_name):
            return canonical, description
    return None, ''
