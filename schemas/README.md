# Clock-tree specs

This folder contains schemas for checking models in YAML files.

## Validate clock trees
```bash
python -m pip install PyYAML jsonschema
python tools/validate_clock_specs.py \
  --schema schemas/clock-tree.schema.json \
  --docs "spec/clock-tree/**/*.y*ml"
