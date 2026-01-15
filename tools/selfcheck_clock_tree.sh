#!/usr/bin/env bash
set -euo pipefail

echo "== Checking required files =="
missing=0
for p in \
  schemas/clock-tree.schema.yaml \
  tools/validate_clock_specs.py \
  .github/workflows/clock-spec.yml \
  tasks/clock-tree-task.md \
  models
do
  [[ -e "$p" ]] && echo "  ✓ $p" || { echo "  ✗ MISSING: $p"; missing=1; }
done
[[ $missing -eq 0 ]] || { echo "Missing files above"; exit 1; }

echo "== Preparing virtualenv =="
PYTHON=${PYTHON:-python3}
VENV_DIR=${VENV_DIR:-.venv}
if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON" -m venv "$VENV_DIR"
fi

echo "== Installing Python deps in $VENV_DIR =="
"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV_DIR/bin/pip" install -q PyYAML jsonschema

echo "== Validating specs =="
"$VENV_DIR/bin/python" tools/validate_clock_specs.py \
  --schema schemas/clock-tree.schema.yaml \
  --docs "models/**/*clocks.y*ml"

echo "All good ✅"