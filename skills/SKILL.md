---
name: sodacat-soc-database
description: >
  Query, browse, extract, and generate code from the sodaCat SoC/MCU hardware
  database (github.com/s13n/sodaCat). Use this skill whenever the user asks
  about microcontroller or SoC peripheral registers, hardware features,
  crypto/timer/ADC/DMA/UART capabilities, register maps, interrupt assignments,
  or pin configurations for supported chips. Also use when the user wants to
  compare peripherals across chip variants, extract new models from SVD files,
  generate C++ headers from YAML models, or look up which chip variants include
  a specific peripheral block. Trigger on mentions of sodaCat, STM32 register
  data, SVD extraction, MCU peripheral comparison, SoC data catalog, or any
  request to inspect hardware description YAML models. Covers STM32 (all
  families), NXP LPC, Raspberry Pi RP2040/RP2350, Microchip SAM, TI, and
  iMX processors.
---

# sodaCat SoC Data Catalog

sodaCat is a hardware description database for microcontrollers and SoCs,
stored as normalized YAML models. The repo lives at
`https://github.com/s13n/sodaCat`.

## Step 1: Ensure the repo is available

```bash
if [ -d "$HOME/sodaCat" ]; then
  cd "$HOME/sodaCat" && git pull
else
  cd "$HOME" && git clone https://github.com/s13n/sodaCat.git
fi
```

If cloning fails due to network restrictions, check whether the repo already
exists at `/home/claude/sodaCat` (it may have been cloned in a prior turn).

## Step 2: Read the architecture reference

Before doing anything else, read `CLAUDE.md` in the repo root:

```bash
cat "$HOME/sodaCat/CLAUDE.md"
```

This file is the definitive reference for the repository layout, directory
roles, build commands, model organization (four-tier), the extraction pipeline
(SVD → YAML → C++), the transformation framework, CMake integration, and all
key conventions. Follow its guidance for any task.

## Step 3: Work with the database

The YAML models in `models/` are the primary artifact. Common tasks:

- **Look up peripherals for a chip**: Read the chip-level YAML in its
  subfamily directory (e.g. `models/ST/H7/H73x/STM32H735.yaml`).
- **Inspect a peripheral's registers**: Read the block YAML at the family
  level (e.g. `models/ST/H7/CRYP.yaml`).
- **Check which variants have a peripheral**: Grep chip-level YAMLs for
  the block's model name.
- **Compare peripherals**: Use `tools/compare_peripherals.py`.
- **Extract new models**: Use `extractors/generate_stm32_models.py` for
  STM32, or per-chip scripts in `extractors/` for other vendors.
- **Generate C++ headers**: Use scripts in `generators/cxx/`.

## Important notes

- Always `cd` into the sodaCat directory before running scripts.
- Python dependencies: `ruamel.yaml` and `PyYAML`
  (`pip install -r requirements-dev.txt --break-system-packages`).
- Cross-family shared blocks (e.g. `WWDG.yaml`) live directly in `models/ST/`.
- Some blocks exist only in specific subfamilies; check subfamily directories
  if not found at the family level.
- The `tasks/` directory contains AI agent task descriptions for writing
  parsers and generators.