# Task: Add a new vendor to the model database

**Goal**
Build a config-driven SVD extraction pipeline for a new microcontroller vendor,
producing YAML block models and chip models in `models/<Vendor>/` with the same
quality and structure as the existing STM32 database.

**Prerequisites**
- Vendor SVD files are available (zip archives, loose files, or a git repository)
- At least two chip families from the vendor are available for cross-family
  comparison (enables `shared_blocks` analysis)
- Familiarity with the STM32 pipeline: `svd/ST/STM32.yaml`,
  `cmake/stm32-extraction.cmake`, `extractors/generate_stm32_models.py`

---

## Phase 1 -- Reconnaissance

### 1.1 Understand the vendor's SVD source

Determine how the vendor distributes SVD files:

| Distribution model | Example | Implication |
|---|---|---|
| Zip archives per family | ST (stm32h7-svd.zip) | Store in `svd/<Vendor>/`, reference by filename |
| Per-chip files in a git repo | NXP (mcux-soc-svd on GitHub) | Use CMake FetchContent, reference by tag |
| Per-chip files on a download page | Raspberry Pi | Store loose files in `svd/<Vendor>/` or `svd/` |
| Embedded in SDK packages | Various | Extract once, store in `svd/<Vendor>/` |

Note the file extension: most vendors use `.svd`, but some use `.xml`. The
parser (`tools/svd.py:parse()`) is extension-agnostic.

### 1.2 Map the family structure

For each product line, identify:
- **Families** -- groups of chips sharing a common peripheral set and CPU core
  (e.g. STM32H7, LPC8xx, RP2040)
- **Subfamilies** -- chips within a family that share all block models, differing
  only in memory size, package, or peripheral instance count
- **Chips** -- individual SVD files within each subfamily

A good subfamily boundary is where the set of peripheral blocks changes. Within
a subfamily, only parameters (channel counts, DMA assignments, flash size) vary.

### 1.3 Survey peripheral blocks

For each family, list all peripherals in a representative SVD file. Classify:
- Which peripherals are unique to this family
- Which peripherals appear across multiple families (shared block candidates)
- Which peripherals have the same name but different register layouts across
  families (require separate per-family models)

### 1.4 Compare cross-family candidates

For each potential shared block, extract from two or more families and compare:
- Register names and offsets (must be identical for `shared_blocks`)
- Field definitions (must be identical)
- Register count (superset is OK with params; offset shifts are NOT OK)

Classify differences per the categories in `tasks/shared-block-unification.md`
section 1.3.

### 1.5 Check for vendor-specific architectural patterns

Some vendors have architectural features that affect the extraction pipeline:

- **Shared peripheral buses** (e.g. NXP Flexcomm: I2C/SPI/USART instances muxed
  onto shared slots, sharing interrupts and DMA channels)
- **Register address offsets within a bus** (e.g. Flexcomm I2C at +0x800 from
  bus base -- makes register maps incompatible even when fields are identical)
- **Instance-prefixed register names** (common in ST SVDs: `GPIOA_MODER`,
  `ADC1_ISR`; the auto-strip in the generator handles most patterns)
- **Nonstandard interrupt naming** (interrupt names that don't follow the
  `INSTANCE_FUNCTION` convention)

Document these patterns -- they drive generator adaptations.

---

## Phase 2 -- Infrastructure scaffolding

### 2.1 CMake extraction module

Create `cmake/<vendor>-extraction.cmake`, modeled on `cmake/stm32-extraction.cmake`.

The module provides:
- `<vendor>_add_family(ID <id> CODE <code> DISPLAY <name> ...)` -- registers a
  family and creates extraction/rebuild/audit targets
- `<vendor>_print_families()` -- prints a summary of registered families

Adapt for the vendor's SVD distribution model:

**Zip-based** (like ST): Add a `ZIP <filename>` parameter. The zip file is the
`MAIN_DEPENDENCY` for the extraction command.

```cmake
<vendor>_add_family(ID xx CODE XX DISPLAY "Name" ZIP file.zip)
```

**FetchContent-based** (like NXP): No ZIP parameter. FetchContent clones at
configure time; all families share the checkout directory. The config YAML is
the primary dependency (no MAIN_DEPENDENCY since there's no single input file).

```cmake
# In svd/<Vendor>/CMakeLists.txt:
FetchContent_Declare(<vendor>_svd
    GIT_REPOSITORY <url>
    GIT_TAG        <tag>
    GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(<vendor>_svd)
set(<VENDOR>_SVD_DIR "${<vendor>_svd_SOURCE_DIR}" CACHE PATH "...")
```

Generator invocation:

```cmake
COMMAND ${Python3_EXECUTABLE} ${<VENDOR>_GENERATOR}
        ${FAM_CODE} <svd_source> ${<VENDOR>_MODELS_DIR}
```

Where `<svd_source>` is a zip path or the SVD directory, depending on the model.

### 2.2 Vendor SVD directory

Create `svd/<Vendor>/CMakeLists.txt`:
- Include the extraction cmake module
- Set up SVD source access (FetchContent, or just reference local zips)
- Register families via `<vendor>_add_family()` calls
- Add aggregate targets (audit-all, check-svds, update-svds)

Wire it into the build: add `add_subdirectory(<Vendor>)` to `svd/CMakeLists.txt`.

### 2.3 Consolidated config file

Create `svd/<Vendor>/<Config>.yaml` with the same two-level schema as
`svd/ST/STM32.yaml`:

```yaml
shared_blocks:
  <BlockType>:
    from: <Chip>.<Instance>      # Which SVD to extract from
    interrupts: {<raw>: <canonical>}
    params: [{name, type, default?, description?}]
    transforms: [...]            # Fix SVD bugs

families:
  <FamilyCode>:
    svd:
      <metadata>                 # zip/version/date or repo/tag
    subfamilies:
      <SubfamilyName>:
        chips: [<Chip1>, <Chip2>, ...]
    blocks:
      <BlockType>:
        from: <Chip>.<Instance>  # OR uses: <SharedBlockName>
        instances: [<Inst1>, <Inst2>, ...]
        interrupts: {<raw>: <canonical>}
        params: [...]
        transforms: [...]
        variants:                # Optional per-subfamily overrides
          <Subfamily>: {from: ..., transforms: [...]}
    chip_params:
      _all:
        _all:
          <Instance>: {<param>: <value>}
      <Subfamily>:
        <Chip>:
          <Instance>: {<param>: <value>}
```

Start with one family and minimal blocks to validate the pipeline end-to-end.
Add the second family and shared blocks once the basics work.

### 2.4 SVD errata file

Create `svd/<Vendor>/SVD_ERRATA.md`. Document known bugs as transforms are added.

---

## Phase 3 -- Generator script

Create `extractors/generate_<vendor>_models.py`, adapted from
`extractors/generate_stm32_models.py`.

### 3.1 Reusable functions (copy from STM32 generator)

These functions are vendor-agnostic and can be reused verbatim:

| Function | Purpose |
|---|---|
| `_parse_block_cfg()` | Normalize YAML block config to plain dict |
| `_resolve_chip_param()` | 7-level parameter resolution cascade |
| `_resolve_block_config()` | Merge variant overrides for a subfamily |
| `_resolve_uses_config()` | Merge shared block defaults into family block |
| `_select_block_entry()` | Choose best SVD source for a block |
| `_select_subfamily_entry()` | Choose best SVD within a subfamily |
| `_strip_instance_prefix()` | Auto-strip register name prefixes |
| `_inject_params()` | Insert params into block model dict |
| `_inject_source()` | Insert source attribution |
| `_apply_transforms()` | Dispatch transform list (rename, patch, clone) |
| `_patch_fields()` | Apply field-level patches |
| `_patch_registers()` | Apply register-level patches |
| `_build_canonical_interrupts()` | Collect canonical interrupt names from config |
| `_resolve_interrupt_name()` | Map raw SVD interrupt to canonical name |
| `_build_instance_to_block()` | Instance-to-block-type mapping |
| `_get_param_decls()` | Get param declarations with uses: indirection |
| All `_audit_*` functions | Transform audit support |

Consider extracting these into a shared `tools/model_generator.py` module to
avoid duplication. However, for the initial implementation, copying and adapting
is simpler -- refactor once both generators stabilize.

### 3.2 Vendor-specific adaptations

**SVD file access:** Replace the zip-extraction pattern in Pass 1 with whatever
the vendor's distribution model requires:

```python
# Zip-based:
svd_content = svd.extractFromZip(zip_path, chip_name)

# Loose files:
svd_path = svd_dir / chip_name / f"{chip_name}.xml"  # or .svd
root = svd.parse(str(svd_path))
```

**Config file location:** The STM32 generator derives it from `zip_path.parent`.
For other models, derive from the script location or pass as an argument:

```python
config_file = Path(__file__).parent.parent / 'svd' / '<Vendor>' / '<Config>.yaml'
```

**CLI arguments:**

```python
parser.add_argument('family_code')
parser.add_argument('svd_source', type=Path)  # zip path or SVD directory
parser.add_argument('output_dir', type=Path)
parser.add_argument('--audit', action='store_true')
```

**Source attribution:** Adapt the source string format:

```python
# ST:   "STM32H723 SVD v2.0"
# NXP:  "LPC865 SVD (MCUX_2.16.100)"
```

**Vendor-specific interrupt handling:** If the vendor has shared interrupt
vectors (like NXP Flexcomm), extend the interrupt resolution logic or use
explicit per-slot entries in the config's `interrupts` mapping.

### 3.3 Three-pass architecture (same for all vendors)

- **Pass 1:** Collect blocks from SVD files. For each subfamily, for each chip:
  read SVD, call `svd.processChip()`, auto-strip instance prefixes, accumulate
  block data + lightweight chip summaries.
- **Pass 2:** Write block YAML models. Config-driven placement: shared blocks to
  `models/<Vendor>/`, family blocks to `models/<Vendor>/<Family>/`, variant
  blocks to subfamily subdirectories.
- **Pass 3:** Write chip YAML models. For each chip: resolve interrupts via
  config mapping, resolve params via 7-level cascade, assemble instances, write
  to `models/<Vendor>/<Family>/<Subfamily>/<Chip>.yaml`.

---

## Phase 4 -- Iterative buildout

### 4.1 Validate with the first family

Start with the simpler family (fewer peripherals, no architectural quirks):
1. Configure and build: `cmake --build . --target <vendor><id>-models`
2. Compare output models against any existing legacy models
3. Verify register names, offsets, fields match expectations
4. Check chip model: instances, base addresses, interrupts, parameters

### 4.2 Add the second family and shared blocks

1. Add the second family's config to the YAML
2. Move confirmed-identical blocks into `shared_blocks`
3. Update both families to use `uses:` for shared blocks
4. Re-extract both families, verify shared models are written once

### 4.3 Fill in all blocks and chip_params

For each family:
1. Add all block definitions (translate from legacy scripts or reference manuals)
2. Add interrupt mappings for all instances
3. Add parameter declarations and chip_params overrides
4. Verify chip models have correct per-instance parameters

### 4.4 Add remaining families

Repeat the pattern: add config, extract, compare, verify. Each new family may
reveal additional shared block candidates or require new transforms.

---

## Phase 5 -- Cleanup

### 5.1 Remove legacy artifacts

Once the new pipeline is validated:
- Delete legacy per-chip extractor scripts
- Delete loose SVD files that are now fetched automatically
- Delete any hand-crafted intermediate models (fused models, JSON sidecars)
- Update `.gitignore` if needed

### 5.2 Wire into test suite

Add `generate_header()` calls in `test/CMakeLists.txt` for the new vendor's
models to validate that the generated C++ headers compile correctly.

### 5.3 Document

Update `svd/<Vendor>/README.md` with:
- Available CMake targets and how to use them
- SVD update workflow
- Links to vendor SVD source

---

## Reference: existing infrastructure files

| File | Role |
|---|---|
| `cmake/stm32-extraction.cmake` | CMake module template (targets, stamp files) |
| `svd/ST/CMakeLists.txt` | Family registration template |
| `svd/ST/STM32.yaml` | Config schema reference (shared_blocks + families) |
| `extractors/generate_stm32_models.py` | Generator template (three-pass architecture) |
| `tools/svd.py` | SVD parser + model writer (vendor-agnostic) |
| `tools/transform.py` | Register/field transform helpers (vendor-agnostic) |
| `svd/ST/SVD_ERRATA.md` | Errata tracking format |
| `tasks/shared-block-unification.md` | Cross-family block comparison methodology |
