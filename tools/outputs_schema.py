"""Shared helpers for the block-level `outputs:` schema.

Both the family-config interpreter (`extractors/generate_models.py`) and
the SVD processor (`tools/svd.py`) need to resolve SVD raw interrupt
names to canonical output names against the same configured outputs
map.  The map can use either of two schemas — old SVD-raw-keyed or new
canonical-keyed (see `is_new_outputs_schema` for detection details).
These helpers hide the schema difference behind a uniform list of
`(canonical, description, pattern)` triples.

`pattern` semantics inside a triple:
    None: never matches (non-SVD output, or no SVD source).
    str:  regex matched against SVD raw names via `re.fullmatch`.
          Use '.*' to opt into match-everything.

In new-schema entries, omitting `pattern:` (or writing `pattern: ~`)
yields pattern=None — i.e. the canonical is declared as an available
output but isn't sourced from any SVD interrupt.  This is the safe
default: a non-SVD output (DMA request, wakeup line) reads as just
`<CANONICAL>:` or `<CANONICAL>: {description: ...}` without needing
an explicit opt-out marker.  Match-everything is opt-in via
`pattern: '.*'` when the author has confirmed every SVD raw on the
block legitimately collapses to the one canonical.
"""

import re


def is_new_outputs_schema(output_map):
    """True iff output_map uses the new canonical-keyed schema.

    Detection by value shape: any value that is a string or a dict
    containing `name:` → old; anything else (null / empty dict / dict
    without `name:`) → new.  Empty map → new (no consumer cares).
    """
    if not output_map:
        return True
    for value in output_map.values():
        if isinstance(value, str):
            return False
        if isinstance(value, dict) and 'name' in value:
            return False
    return True


def normalize_outputs(output_map):
    """Return a list of (canonical, description, pattern) triples in
    declaration order, regardless of which schema output_map uses.

    Old schema entries get grouped by canonical: multiple raws mapping
    to the same canonical become one entry with an anchored alternation
    pattern.  A self-mapping single entry (raw == canonical) becomes a
    never-match entry — that's the canonical-name-only convention old
    schema used for non-SVD outputs.
    """
    if not output_map:
        return []

    if is_new_outputs_schema(output_map):
        result = []
        for canonical, spec in output_map.items():
            if spec is None:
                description = ''
                pattern = None  # default: no SVD source
            elif isinstance(spec, dict):
                description = spec.get('description', '') or ''
                pattern = spec.get('pattern')  # absent or null → None
            else:
                raise ValueError(
                    f"new-schema output '{canonical}' value must be a dict "
                    f"or null, got {type(spec).__name__}")
            result.append((canonical, description, pattern))
        return result

    # Old schema → group entries by canonical, preserving first appearance.
    # NB: a self-mapping entry (raw == canonical) in old schema doesn't
    # imply "non-SVD output" — H7 EXTI uses `WKUP: WKUP` for an SVD-
    # sourced interrupt whose raw name happens to match its canonical.
    # The "non-SVD output" semantics is only available in new schema via
    # explicit `pattern: ~`.  Old-schema self-mappings here become
    # literal-anchored patterns, which match the SVD raw when present
    # and harmlessly fail to match when not (the canonical is still
    # declared as an available output via the separate `_inject_outputs`
    # pass).
    groups = {}  # canonical -> [(raw, description), ...]
    canonical_order = []
    for raw_name, mapping in output_map.items():
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

    result = []
    for canonical in canonical_order:
        entries = groups[canonical]
        raws = [r for r, _ in entries]
        description = next((d for _, d in entries if d), '')
        if len(raws) == 1:
            pattern = '^' + re.escape(raws[0]) + '$'
        else:
            pattern = '^(' + '|'.join(re.escape(r) for r in raws) + ')$'
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
