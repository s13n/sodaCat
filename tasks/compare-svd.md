# Task: Compare generated SVD against original vendor SVD

**Goal**
Generate a "fixed" SVD from the sodaCat models and structurally compare it
against the original vendor SVD to review what the extraction pipeline changed.

**When to use this task**
- After adding or modifying transforms for a family
- After onboarding a new family, to verify the models look correct
- When investigating discrepancies between sodaCat models and vendor SVD

---

## Prerequisites

The following Python packages are needed (both are already in
`requirements-dev.txt`):

```bash
pip install svdtools ruamel.yaml
```

## Step 1 — Generate SVD from models

Pick the chip model to compare and generate an SVD file:

```bash
python3 generators/svd/generate_svd.py models/ST/<Family>/<Subfamily>/<Chip>.yaml \
    -o /tmp/<Chip>_generated.svd
```

Example:

```bash
python3 generators/svd/generate_svd.py models/ST/C5/C59x_C5A3/STM32C5A3.yaml \
    -o /tmp/STM32C5A3_generated.svd
```

## Step 2 — Extract the original vendor SVD

For STM32, the original SVDs are in zip archives under `svd/ST/`. Extract the
matching chip:

```bash
unzip -p svd/ST/<family>-svd.zip SVD/<Chip>.svd > /tmp/<Chip>_original.svd
```

Example:

```bash
unzip -p svd/ST/stm32c5-svd.zip SVD/STM32C5A3.svd > /tmp/STM32C5A3_original.svd
```

**Tip:** Use `unzip -l svd/ST/<family>-svd.zip` to list available SVD files
if unsure of the exact filename inside the archive.

## Step 3 — Generate memory maps and diff

Use `svdtools mmap` to produce a text-based memory map of each file (one line
per peripheral/register/field with address, name, access type and description),
then diff the two:

```bash
python3 -c "import svdtools.mmap; print(svdtools.mmap.main('/tmp/<Chip>_original.svd'))" \
    > /tmp/<Chip>_original.mmap
python3 -c "import svdtools.mmap; print(svdtools.mmap.main('/tmp/<Chip>_generated.svd'))" \
    > /tmp/<Chip>_generated.mmap
diff /tmp/<Chip>_original.mmap /tmp/<Chip>_generated.mmap
```

## Interpreting the diff

Expected differences (these are intentional model improvements):
- **Register name prefix stripping**: `TIM_CR1` → `CR1`, `GPIOA_MODER` → `MODER`
- **Superset fields**: the model is a superset of all variants, so registers may
  have fields not present in a specific chip's SVD
- **Renamed alternates**: e.g. `CCMR1_ALTERNATE1` → `CCMR1_Input`/`CCMR1_Output`
- **Fixed field names/widths**: transforms that correct known SVD bugs
- **Missing peripherals**: peripherals not listed in the family config's `blocks`
  section are intentionally omitted

Unexpected differences to investigate:
- Registers at wrong offsets
- Missing registers that should be present
- Field bit positions that don't match
- Peripherals present in the original but absent from the generated SVD without
  a known reason

## Notes

- The memory map comparison covers register layout (names, offsets, fields,
  access types). It does not cover reset values or enumerated values.
- For a quick line-count overview, use `wc -l /tmp/<Chip>_*.mmap` — the
  generated file is typically larger due to superset fields.
- To optionally validate the generated SVD against the CMSIS-SVD XSD schema,
  add `--validate` to the generate command (requires `lxml`).
