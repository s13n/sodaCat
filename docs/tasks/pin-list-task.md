# Task: MCU Pin List Specification (YAML) for sodaCat

**Goal**  
Produce a machine-checkable, vendor-agnostic YAML description of an MCU’s pins
that sodaCat can use to generate headers.

**Output format**  
- YAML document conforming to `schemas/pin-list.schema.yaml`
- Place new families under `spec/pin-list/<vendor-or-series>/<family>.yaml`  
  (e.g., `spec/pin-list/st/stm32h7.yaml`)

---

## Modeling guide for pin lists

Refer to the `pin-list.schema.yaml` file for information about required and optional
fields, and how to structure the model.

### General approach

MCUs typically come in families, and each chip in the family may come in several
different packages. The reference or user manual often describes the entire family,
and the differences between the chip members and the package variants must be gleaned
from the datasheets. The first task is thus, to match datasheets to reference manuals,
and collect the set of documents that refer to the same chip family, for which a
common pin list can be compiled.

For the purpose of this task, we will use the term "pad" for the connection of the chip
inside the package, and "pin" for the externally available connection on a specific
package. Thus, the list of pads is a property of the bare chip, whereas the list of pins
is a property of the chip in a specific package. For each package, there is a mapping of
pads to pins, which reflects the wiring of the chip in the package (also called
"bonding").

The result should be a pad list that focuses on the electrical properties of the pads
and their alternate functions, and a separate pin list for each package, which contains
the mapping from pads to pins for this package.

The ordering code for a part typically contains a code for the package, so there will
be a generic part code that describes the chip, and an extended code that also includes
additional information like package, temperature range, tape/reel configuration and so
on. The former can be used to name the pad list, whereas the individual pin lists can
use the extended form.

### Top-level fields

Those list the information sources used, the devices covered and general metadata about
the device tree model. Those may be obtained from the reference manual, user manual
and/or datasheet of the device family.

### `pads` array

Model any externally available signal of the chip ("pad"). This includes:
- Ground and power supply
- Dedicated functions (e.g. reset, clocks, analog functions, crystal oscillators etc.)
- Assignable functions (where there is a register bitfield to select the function)

If a pad doesn't have its own name, use the name of its default function, i.e. the
function that is in force after reset, before it is reprogrammed in the respective
register.

For each pad, where appropriate, list the power supply signal it is associated with.

For each pad, where appropriate, list its electrical type, which includes if it is
input, output, or bidirectional, its voltage tolerance, its drive strength, pullup
or pulldown capability, analog capability and similar.

For each pad, where appropriate, list its state after reset (undefined, input, output
high, output low, etc.)

For each pad with assignable functions, list the alternatives and the
register/bitfield used to select between them.

### `variants` array

Each chip variant in the family gets an entry in this array, including the different
packages.

For each variant, a pin list is generated that contains the pad name for each pin.
The implicit assumption is that a pad that isn't listed here, is unavailable in
this variant of the chip.

The pins are identified with their pin number or ball grid array coordinates.
