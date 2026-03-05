# Task: MCU Clock-Tree Specification (YAML) for sodaCat, ST specifics

Create a Python script that scans the STM32CubeMX installation directory and
extracts all clock-related configuration data for the STM32H745 device.

Use the following inputs:
- The directory structure is defined by a previously generated `tree.txt` file.
- Relevant XML files include:
  - db/mcu/STM32H745ZGTx.xml
  - db/plugins/clock/STM32H7.xml
  - db/mcu/IP/RCC-STM32H7_rcc_v1_0_Modes.xml

The script should:
1. Parse these XML files and extract all clock-related elements:
   - Clock signals
   - Clock sources
   - Multiplexers
   - Gates
   - PLLs
   - Dividers
2. Map each element to the corresponding structure defined in `clock-tree.schema.yaml`.
3. Build a complete YAML document that includes:
   - `version`, `family`, `devices`, `documents`
   - Arrays for `signals`, `sources`, `muxes`, `plls`, `dividers`, `gates`
4. Save the resulting YAML file locally as `stm32h745-clock-tree.yaml`.

Ensure:
- Register fields are included with `reg`, `field`, and optionally `instance`, `values`, `value_range`, `scale`, `offset`.
- All connections between blocks (e.g., input/output signals) are preserved.
- The YAML is valid and matches the schema.

**Important:** After extraction, all `reg` and `field` names must be reconciled
against the corresponding block model YAML (e.g., `models/ST/H7/H745_H757/RCC.yaml`).
CubeMX uses different names than the SVD-derived block models in several cases:
- Field renames from SVD transforms (e.g., `HSI48ON` → `RC48ON`, `RTCSEL` → `RTCSRC`,
  `CECEN` → `HDMICECEN`, `UART7EN` → `USART7EN`)
- Cluster-qualified register paths for dual-core chips (e.g., `AHB1ENR` → `C[0].AHB1ENR`
  where ENR/LPENR registers are inside a per-CPU cluster array)
- Missing SVD fields that need `patchFields` transforms before they appear in the model

The goal is to enable recursive frequency computation from any signal back to
its source, considering all intermediate blocks.
