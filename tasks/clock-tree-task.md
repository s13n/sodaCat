# Task: MCU Clock-Tree Specification (YAML) for sodaCat

**Goal**  
Produce a machine-checkable, vendor-agnostic YAML description of an MCU’s clock
tree that sodaCat can use to generate headers and frequency resolvers.

**Output format**  
- YAML document conforming to `schemas/clock-tree.schema.yaml`
- Place new families under `models/<vendor>/<family>/<chip>_clocks.yaml`  
  (e.g., `models/NXP/LPC8/LPC865_clocks.yaml`)

---

## Modeling guide for clock trees

Refer to the `clock-tree.schema.yaml` file for information about required and
optional fields, and how to structure the model.

### Top-level fields

Those list the information sources used, the devices covered and general
metadata about the device tree model. Those may be obtained from the reference
manual or user manual of the device family.

### `signals` array

Model any clock that can be *gated*, *muxed*, or *divided* as its own
`signals[]` entry:
- Internal oscillators
- External clock inputs and crystal oscillators
- PLL reference input to the phase detector, VCO output
- CPU and bus clocks
- Representative kernel clocks per peripheral
- External clock outputs
- Intermediate clock signals between functional blocks

Use the signal name as used in the reference manual, if possible. It may be
available from the clock tree diagram or from a register description. If no name
is available, use the name of the functional block where the signal originates.
Sometimes the name given in a block diagram contains a placeholder (e.g. `x`)
that is to be substituted for a number or letter denoting the particular
instance. For example a block diagram may describe the structure of a PLL that
exists three times on the chip. In the diagram the VCO output signal might be
given as `vcox_ck`, but the actual signal name would be be `vco1_ck` for the
first PLL, and `vco2_ck` for the second, etc.

The maximum signal frequency may be obtained from the data sheet rather than the
reference manual. If there is no minimum frequency, omit the entry. If no
nominal frequency is known, omit the entry.

There is no need for specifying the unit, as frequencies are always given in Hz.

### `gates` array

Model any functional block that gates a clock signal, where the gate is
controlled by a register bit, as its entry in the `gates[]` array.

Describe the register bit that controls the gate.

### `dividers` array

Model any functional block that divides a clock signal, as its own entry in the
`dividers[]` array.

If the divider is controlled by a register bitfield, describe the bitfield, and
list the bitfield values along with the resulting divisor.

If the divisor is fixed, with no controlling register, list the divisor.

Sometimes a divider supports fractional division, in which case there are two
bitfields controlling the overall ratio.

### `muxes` array

Model any functional block that selects between clock signals, as its own entry
in the `muxes[]` array.

List the different input sources in the same order as the bitfield values to
select them. Describe the register and bitfield that controls the Muxer.

When a certain muxer input can be selected, but doesn't have a clock signal
connected to it, the empty source "" should be listed in this position.
Selecting this input effectively turns off the output clock of the muxer.

When a certain input selection is listed as "reserved" in the manual, i.e. that
it shouldn't be used, use a null in the respective position in the input list.

### `plls` array

Model any functional block that multiplies the clock frequency by an integer or
fractional factor as an entry in the `plls[]` array.

Describe the register and bitfields that control the multiplier factor. Describe
the frequency limits of the input and the output signal.

Note: `offset` and `scale` allow flexible encoding of register values.
The structure supports both forward and reverse frequency calculations.

Any dividers that come before the phase detector, or after the pickoff point of
the feedback divider, are not modeled as part of the PLL, but separately as
external dividers in the overall model's divider list. Only a divider that is
located between the VCO and the feedback divider pickoff point, gets modeled as
`post_divider`. Refer to the PLL block diagram to determine where the feedback
divider's input signal is taken from.

Here's a modeling checklist for PLLs:
- Identify the reference input signal
- Determine feedback pickoff point
- Model feedback_integer always, and feedback_fraction if applicable
- Use post_divider only if divider is before feedback pickoff
- Model reference dividers (before phase detector) as external
- Model output dividers (after feedback pickoff point) as external
- Model gates between feedback pickoff point and output dividers as external

### `generators` array

Model any functional block that generates a clock signal as its own entry in the
`generators[]` array.

This includes on-chip oscillators, crystal oscillators, or external clock
inputs.

Model registers and bitfields that control the oscillator (enable/disable)
and/or its frequency, like this:

Provide an array `frequencies` with entries corresponding to the bitfield values
in the register. If a bitfield value turns off the source, use the frequency 0.

Example: Let the oscillator offer three different output frequencies, and one
off state, selected by a 2-bit bitfield. The frequencies array might then look
like this: `frequencies: [0, 12000000, 36000000, 60000000]`

---

## Modeling details

### Frequency Specification Guidelines

- All frequency values must be expressed in **Hz**.
- If source material provides values in kHz or MHz, convert them:
  - `1 kHz = 1,000 Hz`
  - `1 MHz = 1,000,000 Hz`

### Choice of names

- Register and bitfield names are usually obtained directly from the register
  description in the reference manual. If available, also provide as the
  `instance` field the name of the functional block or peripheral that contains
  the register. Preserve the case used in the manual.
- Names should be suitable as identifiers in the most common programming
  languages, i.e. they shouldn't start with a digit, and should contain only
  digits, letters and the underscore. Warn when this is not the case.

### Provide description

- Descriptive texts given in the manual for registers, bitfields etc. should be
  put into `description` fields where appropriate.

---

## Acceptance criteria

- YAML validates against `schemas/clock-tree.schema.yaml`.
- No missing `reg/field/bit` for muxes/dividers/gates.
- All producing nodes with limits include `frequency`/`frequency_limit`.
- A minimal set of kernel examples (at least one timer/serial/storage/USB or ETH).

---

## Example workflow (for a new family)

1. Find relevant documentation of clock tree for the family.\
   There may be machine readable, structured information in a manufacturer's
   SDK. This might be files driving a graphical clock tree editor, or XML files
   documenting the chip as a whole. If nothing suitable is found, the
   information can also be extracted from the relevant reference manual and/or
   datasheet for the chip. In this case, the PDF file must be scanned for either
   textual information, or diagrams depicting the clock tree.
2. Determine clock tree from the documentation.\
   The clock tree is a directed acyclical graph, with the edges representing
   signals, and the nodes representing sources, gates, muxes, PLLs, dividers or
   clock consumers. Those should be gleaned from a clock tree diagram, if found
   in the manual. Where necessary, lines and arrows need to be traced to find
   signal names. If signal names are missing, they may be found in register
   descriptions relating to gates, muxes etc. If nothing can be found, signal
   names can be derived from the name of the source node.
3. Fill in the arrays for signals, generators, gates, muxes, PLLs, dividers,
   from the information found in the previous step.
4. Run validation:
   ```bash
   python tools/validate_clock_specs.py --schema schemas/clock-tree.schema.yaml --docs "models/**/*clocks.y*ml"
   ```
5. Open PR with a short note: RM ID, sections used, and known device caveats.
