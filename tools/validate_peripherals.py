#!/usr/bin/env python3
"""Validate peripheral YAML models against schema and structural rules.

Phase 1: JSON Schema validation (Draft 7).

Phase 2: Semantic checks on register/cluster array shape:

A register or cluster with `dim` is an array. Its `name`, `dim` and
optional `dimIndex` must follow one of two shapes:

  * No `dimIndex` (canonical zero-based array):
      - `name` contains one `[%s]` per dim dimension (one for scalar `dim`,
        len(dim) for list-valued `dim`);
      - `%s` never appears bare (outside brackets).

  * `dimIndex` present (sparse or symbolic indices):
      - `dim` must be a scalar integer;
      - `dimIndex` is a comma-list; its length must equal `dim`;
      - `name` contains exactly one `%s`, not bracketed;
      - every `name.replace('%s', token)` must be a valid C identifier.

Range-form `dimIndex` (`0-N`) is rejected at the schema level and should
be normalized away by the extractor.
"""
import sys, pathlib, argparse, glob, re

import yaml  # PyYAML
from jsonschema import Draft7Validator


_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


_MSG_LIMIT = 200


def _trim(msg):
    """Shorten jsonschema messages that dump entire sub-documents."""
    msg = " ".join(msg.split())
    if len(msg) > _MSG_LIMIT:
        msg = msg[:_MSG_LIMIT] + " ..."
    return msg


def validate_schema(data, validator):
    """Return list of (location, message) tuples for schema errors."""
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return [
        ("/".join(str(p) for p in e.path) or "(root)", _trim(e.message))
        for e in errors
    ]


def _dim_arity(dim):
    """Return the number of dimensions for a `dim` value.

    Scalar int -> 1; list -> len(list); anything else -> 0.
    """
    if isinstance(dim, int):
        return 1
    if isinstance(dim, list):
        return len(dim)
    return 0


def _check_array_shape(entry, path):
    """Return list of (location, message) tuples for one register/cluster."""
    errors = []
    name = entry.get('name', '')
    dim = entry.get('dim')
    dim_index = entry.get('dimIndex')

    if dim is None:
        # Not an array; %s has no business appearing in a scalar name, but
        # don't reject it here — transforms occasionally produce templates
        # that are expanded later.  The generator-facing constraints only
        # bite when `dim` is set.
        if dim_index is not None:
            errors.append((path, f"'dimIndex' present on non-array register '{name}'"))
        return errors

    arity = _dim_arity(dim)
    if arity == 0:
        errors.append((path, f"'dim' on '{name}' must be integer or non-empty list"))
        return errors

    bracketed = name.count('[%s]')
    total_placeholders = name.count('%s')
    bare = total_placeholders - bracketed

    if dim_index is None:
        # Canonical zero-based form: name must have one [%s] per dimension,
        # and no bare %s.  Report the most specific problem only.
        if bare:
            errors.append((path,
                f"register '{name}': bare '%s' not allowed without dimIndex "
                f"(use '[%s]' or provide a comma-list 'dimIndex')"))
        elif bracketed != arity:
            errors.append((path,
                f"register '{name}': expected {arity} '[%s]' in name, "
                f"found {bracketed}"))
    else:
        # dimIndex present: sparse/symbolic form, scalar dim only, bare %s.
        if arity != 1 or not isinstance(dim, int):
            errors.append((path,
                f"register '{name}': multidim 'dim' with 'dimIndex' is not supported"))
            return errors
        tokens = dim_index.split(',')
        if len(tokens) != dim:
            errors.append((path,
                f"register '{name}': dimIndex has {len(tokens)} entries "
                f"but dim={dim}"))
        if bracketed:
            errors.append((path,
                f"register '{name}': '[%s]' not allowed when dimIndex is given "
                f"(use bare '%s')"))
        if total_placeholders != 1:
            errors.append((path,
                f"register '{name}': expected exactly one '%s' in name, "
                f"found {total_placeholders}"))
        # Every substitution must yield a valid C identifier.
        for tok in tokens:
            substituted = name.replace('%s', tok)
            if not _IDENT_RE.match(substituted):
                errors.append((path,
                    f"register '{name}' with dimIndex token '{tok}' "
                    f"substitutes to invalid identifier '{substituted}'"))
    return errors


def _walk(entries, path, errors):
    """Recursively walk a list of register-or-cluster entries."""
    for i, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            continue
        loc = f"{path}[{i}]"
        errors.extend(_check_array_shape(entry, loc))
        # Cluster: recurse into nested registers.
        if 'registers' in entry:
            _walk(entry['registers'], f"{loc}/registers", errors)


def validate_structure(data):
    """Run structural checks on a peripheral model."""
    errors = []
    _walk(data.get('registers'), 'registers', errors)
    return errors


def is_peripheral(data):
    """Heuristic: peripheral models have a top-level `registers` list."""
    return isinstance(data, dict) and isinstance(data.get('registers'), list)


def main():
    ap = argparse.ArgumentParser(
        description="Validate peripheral YAML models (schema + structural checks)")
    ap.add_argument("-s", "--schema", required=True, help="Path to JSON/YAML schema")
    ap.add_argument("-d", "--docs", nargs="+", required=True,
                    help="YAML model files or globs")
    args = ap.parse_args()

    schema = yaml.safe_load(pathlib.Path(args.schema).read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    validator = Draft7Validator(schema)

    files = []
    for pattern in args.docs:
        files.extend(glob.glob(pattern, recursive=True))
    if not files:
        print("No files matched", file=sys.stderr)
        sys.exit(2)

    had_errors = False
    skipped = 0
    for f in sorted(set(files)):
        if not (f.endswith(".yaml") or f.endswith(".yml")):
            continue
        data = yaml.safe_load(pathlib.Path(f).read_text(encoding="utf-8"))
        if not is_peripheral(data):
            skipped += 1
            continue

        schema_errors = validate_schema(data, validator)
        struct_errors = validate_structure(data) if not schema_errors else []

        if schema_errors or struct_errors:
            had_errors = True
            print(f"FAIL {f}:")
            for loc, msg in schema_errors:
                print(f"   schema    | at {loc}: {msg}")
            for loc, msg in struct_errors:
                print(f"   structure | at {loc}: {msg}")

    if skipped:
        print(f"(skipped {skipped} non-peripheral files)", file=sys.stderr)
    sys.exit(1 if had_errors else 0)


if __name__ == "__main__":
    main()
