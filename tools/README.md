compare_peripherals.py — README

Purpose
- `tools/compare_peripherals.py` is a lightweight analysis tool to find structural
  commonalities between peripheral YAML descriptions (SVD-like). It is folder-agnostic
  and can be pointed at any folder containing peripheral YAMLs (for example
  `models/NXP` or `models/ST`).
- It helps identify registers/fields that can be parameterized and can emit a
  fused peripheral template and per-variant parameter files so a single template
  can cover multiple MCU variants.

What it does
- Scans a target folder (default: `models/NXP`) for `**/*.yaml` and computes
  pairwise similarity scores (weighted Jaccard over register names,
  register@offset signatures, and field signatures).
- Produces corpus reports: `tools/compare_report.json` and `tools/compare_report.csv`.
- Modes:
  - `--top N` : print top N matches.
  - `--pair A B` : produce a detailed side-by-side report for two files.
  - `--fuse A B` : create a fused YAML template and per-variant parameter JSON files
    for the two provided peripheral files.
   - `--root PATH` : specify the root folder to scan (default: current folder).
    - `--fused-name NAME` : optional explicit output filename for fused YAML (e.g. `CRC.yaml`). If omitted the script uses its default naming.

Key outputs
- `tools/compare_report.json` / `tools/compare_report.csv` — full pairwise results.
 - Fused YAML files are written to the configured root. When no `--fused-name` is
   provided the script uses the default naming: if both inputs share the same stem
   the fused file uses that stem (e.g. `CRC.yaml`), otherwise the script writes
   `fused_<A>_<B>.yaml`.
  When input stems differ the script uses `fused_<A>_<B>.yaml`; if they share
  the same stem the fused file will use that name.
- Per-variant parameter files are written alongside fused YAMLs with names like
  `<PERIPH>_<FAMILY>_params.json` to avoid collisions.

Parameter inference notes
- If the script detects a constant address delta between variants it will propose
  an `offset_B` numeric parameter. If the delta is zero, `offset_B` is omitted
  (no param emitted).
- The script may propose boolean flags for blocks detected heuristically (e.g.
  `has_fifo`) and will annotate exclusive registers/fields with `present_when`
  expressions (e.g. `has_fifo == true` or `variant == 'LPC54'`).

Dependencies
- Python 3.x
- PyYAML: `pip install pyyaml`

Examples
- Print top matches (default root):

```bash
python3 tools/compare_peripherals.py --top 50
```

- Detailed comparison of two files (example uses default `models/NXP` root):

```bash
python3 tools/compare_peripherals.py --pair models/NXP/LPC54/SPI.yaml models/NXP/LPC8/SPI.yaml
```

- Create a fused template + per-variant params (scan root may be overridden):

```bash
python3 tools/compare_peripherals.py --fuse models/NXP/LPC54/SPI.yaml models/NXP/LPC8/SPI.yaml
# Or run against a different folder, for example models/ST:
python3 tools/compare_peripherals.py --root models/ST --top 20
# Or specify the fused output filename explicitly:
python3 tools/compare_peripherals.py --fuse models/NXP/LPC54/CRC_ENGINE.yaml models/NXP/LPC8/CRC.yaml --fused-name CRC.yaml
```

Where to look for results
- Corpus reports: `tools/compare_report.json`, `tools/compare_report.csv`.
- Fused templates and per-variant params: `<root>/*.yaml` and `<root>/*_params.json`.

Notes & caveats
- Heuristics are conservative and intended to produce human-reviewable proposals
  rather than perfect automatic merges. Review fused templates before using them
  as canonical sources.
- `present_when` expressions are simple strings intended for downstream evaluation
  by your toolchain; they are not executed by this script.

Contact / next steps
- If you want: (a) a `--verify` mode to validate fused templates against sources,
  or (b) improved heuristics for grouping registers (beyond substring matching),
  I can add that next.
