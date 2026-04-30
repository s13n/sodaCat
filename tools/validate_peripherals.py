#!/usr/bin/env python3
"""Validate peripheral block YAML models against schema and semantic rules.

Phase 1: JSON Schema (Draft 7) against `schemas/peripheral.schema.yaml`.

Phase 2: Semantic checks not expressible in standard JSON Schema:

  Uniqueness (one source of cross-vendor bugs the schema can't catch):
    * register names unique within the top-level `registers` list
    * register names unique within each cluster's `registers` list
    * field names unique within each register
    * enum value names unique within each field
    * parameter names unique within the block

  Array shape (registers/clusters with `dim`):
    * Without `dimIndex` — name has one `[%s]` per dim dimension, no bare `%s`.
    * With `dimIndex` — `dim` scalar, name has exactly one bare `%s`,
      `dimIndex` is a comma-list of `dim` tokens, every substitution
      yields a valid C identifier.

Files that don't look like peripheral models (no top-level `registers`
list) are skipped silently — this lets the same glob also feed
`validate_chips.py`.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jsonschema import Draft7Validator
from validate_lib import find_duplicates, run


_DEFAULT_SCHEMA = str(
    Path(__file__).parent.parent / 'schemas' / 'peripheral.schema.yaml')

_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def is_peripheral(data):
    """Discriminator: peripheral models have a top-level `registers` list."""
    return isinstance(data, dict) and isinstance(data.get('registers'), list)


def _walk(registers, path='registers'):
    """Yield (json-pointer, register-or-cluster) for every entry, recursively."""
    for i, r in enumerate(registers or []):
        if not isinstance(r, dict):
            continue
        rpath = f"{path}[{i}]"
        yield rpath, r
        if 'registers' in r:
            yield from _walk(r['registers'], f"{rpath}/registers")


def _dim_arity(dim):
    if isinstance(dim, int):
        return 1
    if isinstance(dim, list):
        return len(dim)
    return 0


def _check_array_shape(entry, path):
    """Return [(check, message)] for one register/cluster's array shape."""
    errors = []
    name = entry.get('name', '')
    dim = entry.get('dim')
    dim_index = entry.get('dimIndex')

    if dim is None:
        if dim_index is not None:
            errors.append(('shape',
                f"{path}: 'dimIndex' present on non-array register '{name}'"))
        return errors

    arity = _dim_arity(dim)
    if arity == 0:
        errors.append(('shape',
            f"{path}: 'dim' on '{name}' must be integer or non-empty list"))
        return errors

    bracketed = name.count('[%s]')
    total_placeholders = name.count('%s')
    bare = total_placeholders - bracketed

    if dim_index is None:
        if bare:
            errors.append(('shape',
                f"{path}: register '{name}': bare '%s' not allowed without "
                f"dimIndex (use '[%s]' or provide a comma-list 'dimIndex')"))
        elif bracketed != arity:
            errors.append(('shape',
                f"{path}: register '{name}': expected {arity} '[%s]' in "
                f"name, found {bracketed}"))
    else:
        if arity != 1 or not isinstance(dim, int):
            errors.append(('shape',
                f"{path}: register '{name}': multidim 'dim' with 'dimIndex' "
                f"is not supported"))
            return errors
        tokens = dim_index.split(',')
        if len(tokens) != dim:
            errors.append(('shape',
                f"{path}: register '{name}': dimIndex has {len(tokens)} "
                f"entries but dim={dim}"))
        if bracketed:
            errors.append(('shape',
                f"{path}: register '{name}': '[%s]' not allowed when "
                f"dimIndex is given (use bare '%s')"))
        if total_placeholders != 1:
            errors.append(('shape',
                f"{path}: register '{name}': expected exactly one '%s' in "
                f"name, found {total_placeholders}"))
        for tok in tokens:
            substituted = name.replace('%s', tok)
            if not _IDENT_RE.match(substituted):
                errors.append(('shape',
                    f"{path}: register '{name}' with dimIndex token '{tok}' "
                    f"substitutes to invalid identifier '{substituted}'"))
    return errors


def validate_semantics(data):
    errors = []

    # Catch the stale `parameters:` spelling at the block level.  The chip
    # schema uses `parameters:` for instance values, but a block declares
    # its parameter shape under `params:`; a top-level `parameters:` here
    # is a key mismatch that the C++ generator would silently ignore.
    if 'parameters' in data:
        errors.append(('params-key',
                       "top-level 'parameters:' is the chip-side spelling; "
                       "block models use 'params:'"))

    # Block-level parameter uniqueness.
    for name, count in find_duplicates(data.get('params')).items():
        errors.append(('params-dup',
                       f"param '{name}' declared {count} times"))

    # Register-name uniqueness, both top-level and within each cluster.
    for n, c in find_duplicates(data.get('registers')).items():
        errors.append(('reg-dup',
                       f"registers: register '{n}' declared {c} times"))
    for rpath, r in _walk(data.get('registers') or []):
        if 'registers' in r:
            for n, c in find_duplicates(r['registers']).items():
                errors.append(('reg-dup',
                               f"{rpath}/registers: register '{n}' declared "
                               f"{c} times"))

    # Field-name uniqueness within each register.
    for rpath, r in _walk(data.get('registers') or []):
        if 'fields' in r:
            for n, c in find_duplicates(r.get('fields')).items():
                errors.append(('field-dup',
                               f"{rpath} ({r.get('name', '?')}): field '{n}' "
                               f"declared {c} times"))

    # Enum-value-name uniqueness within each field.
    for rpath, r in _walk(data.get('registers') or []):
        for j, f in enumerate(r.get('fields') or []):
            for n, c in find_duplicates(f.get('enumeratedValues')).items():
                errors.append(('enum-dup',
                               f"{rpath}/fields[{j}] "
                               f"({r.get('name', '?')}.{f.get('name', '?')}): "
                               f"enum value '{n}' declared {c} times"))

    # Array-shape rules from the schema's prose.
    for rpath, r in _walk(data.get('registers') or []):
        errors.extend(_check_array_shape(r, rpath))

    return errors


def main():
    run(
        parser_desc='Validate peripheral block YAML models',
        default_schema=_DEFAULT_SCHEMA,
        draft_class=Draft7Validator,
        phase2_func=validate_semantics,
        accept_doc=is_peripheral,
    )


if __name__ == '__main__':
    main()
