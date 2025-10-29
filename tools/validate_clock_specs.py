#!/usr/bin/env python3
import sys, json, pathlib, argparse
import yaml  # PyYAML
from jsonschema import validate, Draft202012Validator

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-s", "--schema", required=True, help="Path to JSON Schema")
    ap.add_argument("-d", "--docs", nargs="+", required=True, help="YAML spec files or globs")
    args = ap.parse_args()
        
    schema = yaml.safe_load(pathlib.Path(args.schema).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    import glob
    files = []
    for pattern in args.docs:
        files.extend(glob.glob(pattern, recursive=True))
    if not files:
        print("No files matched", file=sys.stderr)
        sys.exit(2)

    had_errors = False
    for f in sorted(set(files)):
        if not (f.endswith(".yaml") or f.endswith(".yml")):
            continue
        data = yaml.safe_load(pathlib.Path(f).read_text(encoding="utf-8"))
        errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
        if errors:
            had_errors = True
            print(f"❌ {f} failed validation:")
            for e in errors:
                loc = "/".join([str(p) for p in e.path]) or "(root)"
                print(f"   - at {loc}: {e.message}")
        else:
            print(f"✅ {f} is valid")
    sys.exit(1 if had_errors else 0)

if __name__ == "__main__":
    main()