# Task: MCU Clock-Tree Specification (YAML) for sodaCat, ST specifics

Extract all clock-related elements from the STM32H7 RCC configuration XML file
and generate a YAML document that conforms to the schema defined in
`clock-tree.schema.yaml`.

Include the following elements:
- All clock signals (with nominal, min, max frequencies if available)
- All clock sources (with output signal and control register field)
- All multiplexers (with input signals, output signal, and control register field)
- All gates (with input/output signals and enable control)
- All PLLs (with input/output signals, feedback integer/fraction, post-divider, and VCO limits)
- All dividers (with input/output signals, fixed or register-based factor, and optional offset)

Ensure the YAML structure matches the schema:
- Use the `Signal`, `Source`, `Mux`, `Gate`, `Pll`, and `Divider` definitions from the schema
- Include register field details (register name, field name, instance, value range, scale, offset, etc.)
- Use meaningful names for each block and signal
- If any values are missing, leave them null or empty but preserve the structure

The goal is to enable recursive frequency computation from any signal back to
its source, considering all intermediate blocks.

Input file: RCC-STM32H7_rcc_v1_0_Modes.xml
Schema file: clock-tree.schema.yaml
Output: Valid YAML document


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

The goal is to enable recursive frequency computation from any signal back to
its source, considering all intermediate blocks.
