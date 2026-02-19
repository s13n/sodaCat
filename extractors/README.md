# Model extraction

Model extraction is the process of converting vendor-provided machine-readable
hardware descriptions into the YAML data models used by sodaCat. The primary
source format is CMSIS-SVD (System View Description), an XML schema that
describes the programmer's view of a microcontroller: its peripherals,
registers, bit fields and interrupts. The extractors are Python scripts in this
folder.

The extraction step is deliberately separated from code generation. Extractors
produce a vendor-neutral, normalized YAML representation of the hardware, while
generators (in the `generators/` folder) consume those YAML models to produce
source code for specific programming languages.

## Per-chip extractors

The simplest form of extractor is a script that processes a single SVD file and
writes one or more YAML block models. These scripts use the `svd` and
`transform` libraries from `tools/` to parse the SVD XML, normalize the data
structures, and apply transformations such as register array detection and
interrupt name cleanup.

Examples: `STM32H757.py`, `RP2040.py`, `LPC8.py`, `SAMV71.py`.

## Family extractors

For chip families where the same peripheral block appears across many variants,
a family extractor processes all SVD files in a zip archive at once. It hashes
the register structure of each peripheral block and compares them across
subfamily groupings to determine which blocks are identical and which differ.
The output is organized into a three-tier directory structure:

- The family directory itself for blocks that are identical across all subfamilies.
- A `subfamily/` directory for each subfamily, containing blocks that
  differ from the common set or are absent in other subfamilies.

This approach avoids redundant model files and makes cross-variant differences
immediately visible in the directory layout.

Examples: `generate_stm32h7_models.py`, `generate_stm32h5_models.py`,
`generate_stm32n6_models.py`.

## Transformation configuration

Some families require non-trivial transformations that go beyond what the
generic `svd.collateDevice()` provides: renaming registers and interrupts to
remove instance-specific prefixes, converting flat register lists into arrays,
adding per-instance capability parameters, or handling special cases like
dual-core register clustering.

These transformations can be specified declaratively in a YAML configuration
file (e.g. `stm32h7-transforms.yaml`) and executed by the
`TransformationEngine` from `tools/generic_transform.py`. Family-specific
transformation logic that cannot be expressed declaratively lives in a
companion Python module (e.g. `stm32h7_transforms.py`).
