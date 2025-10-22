# Task: MCU Clock-Tree Specification (YAML) for sodaCat

**Goal**  
Produce a machine-checkable, vendor-agnostic YAML description of an MCU’s clock tree
that sodaCat can use to generate headers and frequency resolvers.

**Output format**  
- YAML document conforming to `schemas/clock-tree.schema.json`
- Place new families under `spec/clock-tree/<vendor-or-series>/<family>.yaml`  
  (e.g., `spec/clock-tree/st/stm32h7.yaml`)

---

## Required content

### Top-level object structure

The following fields are defined for the top-level object:
- `family`: Name of chip family
- `signals`: Array of signals.
- `gates`: Array of gates.
- `dividers`: Array of dividers.
- `muxes`: Array of multiplexers.
- `plls`: Array of PLLs.
- `sources`: Array of signal sources.

The array fields are described in more detail in their respective chapters
below. Each entry has a few common fields:

- `name`: The unique identifier of the functional block. Mandatory. 
- `description`: Human-readable comment giving a concise functional description
  from the manual. Optional.

### `signals` array

Model any clock that can be *gated*, *muxed*, or *divided* as its own `signals[]` entry:
- Internal oscillators
- External clock inputs and crystal oscillators
- PLL reference input to the phase detector, VCO output
- CPU and bus clocks
- Representative kernel clocks per peripheral
- External clock outputs
- Intermediate clock signals between functional blocks

Use the signal name as used in the reference manual, if possible. If no name is
available, use the name of the functional block where the signal originates.

### `gates` array

Model any functional block that gates a clock signal, where the gate is
controlled by a register bit, as its entry in the `gates[]` array.

Describe the register bit that controls the gate.

The fields of an entry in the `gates[]` array are:
- `reg`: Register name
- `bit`: Name of bit in register.
- `inverted`: If present and true, register bit turns off when set.

### `dividers` array

Model any functional block that divides a clock signal, as its own entry in the
`dividers[]` array.

If the divider is controlled by a register bitfield, describe the bitfield, and
list the bitfield values along with the resulting divisor.

If the divisor is fixed, with no controlling register, list the divisor.

The fields of an entry in the `dividers[]` array are:
- `reg`: Register name
- `field`: Name of bitfield in register
- `factors`: array of divisor values corresponding to bitfield values. Size must
  be a power of two, corresponding to bitfield.

### `muxes` array

Model any functional block that selects between clock signals, as its own entry
in the `muxes[]` array.

List the different input sources in the same order as the bitfield values to
select them. Describe the register and bitfield that controls the Muxer.

The fields of an entry in the `muxes[]` array are:
- `reg`: Register name
- `field`: Name of bitfield in register
- `inputs`: array of input signal names. The inputs array length must be a power
  of two, determined by the bitfield width. Each index corresponds to a bit
  pattern in numeric order:
  * Valid signal names select that input.
  * Use "" for off states.
  * Use null for reserved bit patterns.
- `output`: The signal name at the output of the multiplexer. Mandatory.

### `plls` array

Model any functional block that multiplies the clock frequency by an integer or
fractional factor as an entry in the `plls[]` array.

Describe the register and bitfields that control the multiplier factor. Describe
the frequency limits of the input and the output signal.

The fields of an entry in the `plls[]` array are:
- `input`: Reference clock signal, input of the phase detector
- `output`: VCO output signal
- `feedback_integer`:  
  - `reg`: Register name  
  - `field`: Bitfield name  
  - `value_range`: Min/max allowed values  
  - `offset`: Applied before scaling  
  - `scale`: Applied after offset (default 1)
- `feedback_fraction`: Same structure as `feedback_integer`, only present when
  PLL supports fractional mode. Omitted for integer-only PLLs.
- `vco_limits`: Min/max allowed VCO frequency
- `vco_formula`: Optional formula for computing VCO frequency

Note: `offset` and `scale` allow flexible encoding of register values.
The structure supports both forward and reverse frequency calculations.

### `sources` array

Model any functional block that generates a clock signal as its own entry in the
`sources[]` array.

This includes on-chip oscillators, crystal oscillators, or external clock inputs.

Model registers and bitfields that control the oscillator (enable/disable)
and/or its frequency.

---

## Modeling details

### Frequency Specification Guidelines

- All frequency values must be expressed in **Hz**.
- If source material provides values in kHz or MHz, convert them:
  - `1 kHz = 1,000 Hz`
  - `1 MHz = 1,000,000 Hz`

---

## Acceptance criteria

- YAML validates against `schemas/clock-tree.schema.json`.
- No missing `reg/field/bit` for muxes/dividers/gates.
- All producing nodes with limits include `frequency`/`frequency_limit`.
- A minimal set of kernel examples (at least one timer/serial/storage/USB or ETH).

---

## Example workflow (for a new family)

1. Duplicate template `spec/clock-tree/templates/clock-tree.template.yaml`.
2. Fill in oscillators, PLLs (ref, VCO, P/Q/R), SYSCLK, prescalers.
3. Add 2–5 representative kernel muxes (USART/I2C/SAI/SDMMC/USB/ETH).
4. Run validation:  
   ```bash
   python tools/validate_clock_specs.py \
     --schema schemas/clock-tree.schema.json \
     --docs "spec/clock-tree/**/*.y*ml"
5. Open PR with a short note: RM ID, sections used, and known device caveats.
