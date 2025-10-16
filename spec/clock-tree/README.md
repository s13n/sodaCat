# Clock-tree specs

This folder contains vendor-agnostic MCU clock-tree descriptions in YAML,
validated against `schemas/clock-tree.schema.json`.

## Authoring rules

- Use **distinct signals** for anything that can be muxed, divided, or gated.
- Add **frequency constraints** to the producing node (source, PLL VCO, bus).
- For **muxes/dividers/gates**, always include `reg` + `field/bit` and, for muxes, an `encoding` map.
- Use **description** strings to capture manual wording and any device-level nuances.

## Validate locally
```bash
python -m pip install PyYAML jsonschema
python tools/validate_clock_specs.py \
  --schema schemas/clock-tree.schema.json \
  --docs "spec/clock-tree/**/*.y*ml"

---

## 🧭 How this plugs into sodaCat codegen

*Short term* (quickest win):
- Keep the YAML purely as **data**. Your generator can load a family file (e.g., `stm32h7.yaml`), evaluate the mux selections and dividers from a known register set, and **emit C headers**:
  - `#define`/`enum` for mux fields and encodings,
  - inline functions or macros to compute frequencies from a register snapshot,
  - register bitfields for gates (on/off).

*Near term*:
- Add a small “resolver” that starts at a sink clock (e.g., `pclk1`) and walks `from`/`input` links, applying `encoding` and `factors` to produce a frequency and **lint** it against `frequency_limit`.

*Future*:
- Share the template across vendors by adding `spec/clock-tree/<vendor>/<family>.yaml` files and keep one schema.

If you’d like, I can draft the minimal **resolver interface** (language of your choice) that consumes the YAML and returns a **clock graph IR** sodaCat can traverse for header generation.

---

## ✅ What I can do next for you

- **Open a PR** into `s13n/sodaCat` with the four files above (schema, H7 sample, validator, and CI workflow).  
  If you prefer, I can package them as a single patch for you to commit.
- **Extend H7** to include all PLLs (2/3), APB domain clocks, MCOs, and a handful of kernel muxes (USART/I²C/SAI/FDCAN/USB/ETH).
- Start a **U5 or H5** spec using the same schema.

Would you like me to prepare a PR branch (e.g., `feature/clock-tree-schema`) with these files ready to merge? If yes, I’ll generate the exact content as files here so you can drop them into the repo and push.