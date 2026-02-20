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
a family extractor processes all SVD files in a zip archive at once. The output
is organized into a three-tier directory structure:

- The family directory itself for blocks that are identical across all
  subfamilies (or differ only in parameters).
- A `subfamily/` directory for each subfamily, containing blocks whose
  register-level structure differs between subfamilies in ways that
  cannot be captured by parameters alone.

This approach avoids redundant model files and makes cross-variant differences
immediately visible in the directory layout.

All 17 STM32 families are handled by a single unified script,
`generate_stm32_models.py`. Per-family configuration lives in YAML files under
`families/<CODE>.yaml` (e.g. `families/H7.yaml`, `families/F4.yaml`). Each
config file declares subfamily-to-chip mappings, block-to-instance mappings,
interrupt name mappings, parameter declarations, and optional per-subfamily
variant overrides. Subfamilies are aligned with ST reference manual boundaries
so each subfamily corresponds to exactly one RM.

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
