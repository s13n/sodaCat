# Model Verification & SVD Lifecycle

This document specifies conditions to check in an automated verification script,
and outlines processes for handling SVD updates and new family onboarding.

## Verification Conditions

### 1. Shared block consistency

For each family block with `uses:`, extract the block from the family's SVD and
compare against the shared model (after applying transforms). Differences should
be reported with enough detail to decide whether they are:
- SVD bugs (already handled by transforms)
- Genuine hardware differences (needs a param or variant)
- New SVD corrections (shared model needs updating)

Comparison should ignore: `source` line, description text differences, field
ordering within a register. It should flag: register name/offset/size changes,
field name/offset/width changes, missing or extra registers/fields.

### 2. Common block consistency

For blocks without `variants`, verify that all subfamilies produce identical
models (after transforms). If they don't, the block needs a variant or param.

### 3. Instance existence

Every instance listed in a block's `instances:` should exist as a peripheral
in at least one SVD file within the family. Flag phantom instances.

### 4. Interrupt name validity

Every raw SVD interrupt name in `interrupts:` mappings should exist in the SVD.
Flag stale interrupt names that no longer match any SVD entry.

### 5. Parameter completeness

Params declared without a `default` must have explicit values for every chip in
the family (via `chip_params`). Flag missing values.

### 6. Parameter type validity

Param values must match their declared type (`int`, `bool`, `string`). Flag
type mismatches.

### 7. No orphan models

Every `.yaml` file under `models/ST/` should correspond to a block defined in
`STM32.yaml` (either as a shared block, family block, or variant block). Flag
files that have no config entry — they may be stale after a unification.

### 8. No missing models

Every block in the config should have a corresponding `.yaml` model file at the
expected path (top-level for shared, family dir for common, subfamily dir for
variants). Flag blocks that have config but no model file.

### 9. Address block sanity

The `addressBlock.size` in the model should be >= the highest register offset +
register size. Flag models where the address block is suspiciously large (e.g.
1024 when actual register span is 12 bytes) or too small (truncates registers).

### 10. Register overlap detection

Flag registers at the same offset that are NOT intentional overlaps (i.e. not
created by `cloneRegister` for union-style alternatives). Intentional overlaps
can be identified by matching `_V2` suffix or by cross-referencing with the
transforms config.

### 11. Field coverage

Within each register, flag gaps between fields (undefined bit ranges) and
overlapping fields. Both may be intentional (reserved bits, union alternatives)
but are worth reporting for review.


## SVD Lifecycle

### SVD update detection

When a new SVD zip replaces an existing one:

1. **Checksum comparison**: detect that the zip has changed (store checksums in
   a manifest file, e.g. `svd/checksums.sha256`).

2. **Peripheral diff**: for each chip in the family, extract all peripherals and
   compare against the current models. Report:
   - New registers or fields added
   - Removed registers or fields
   - Changed offsets, widths, access attributes, reset values
   - New peripherals not yet in config
   - Removed peripherals still in config

3. **Shared block impact**: if the updated SVD belongs to the family that owns a
   shared block's `from` chip, re-extract and diff the shared model. If the
   shared model changes, all `uses:` families should be re-verified (condition 1).

4. **Transform validity**: check that all regex patterns in `renameRegisters` and
   `renameFields` transforms still match at least one target. Flag transforms
   that have become no-ops (the SVD bug they fixed may have been corrected).

### New chip variants in existing families

When ST adds a new chip to an existing family (e.g. STM32H725 added to H7):

1. Add the chip to the appropriate subfamily in `STM32.yaml`
2. Add the chip to `CMakeLists.txt` subfamily list
3. Rebuild and verify — the chip should produce identical models to its subfamily
   peers (any differences indicate the new chip has a different peripheral version)

### New family onboarding

When a new family is released (e.g. STM32V8):

1. **SVD acquisition**: download the SVD zip, add to `svd/ST/` with standard naming
2. **Initial scan**: extract all peripherals from all chips in the zip, catalog
   block types and instance counts
3. **Shared block matching**: compare each peripheral against existing shared
   blocks (WWDG, IWDG, CRC, I2C, etc.). Peripherals that match an existing
   shared model can use `uses:` immediately
4. **Cross-family candidates**: compare remaining peripherals against all existing
   family blocks. Near-matches may become new shared blocks with params
5. **Config skeleton**: generate initial `STM32.yaml` family entry with
   subfamilies, blocks, and interrupt mappings
6. **CMake registration**: add `stm32_add_family()` call to `svd/ST/CMakeLists.txt`
7. **Build & verify**: extract models, run verification conditions 1-11
8. **Reference manual alignment**: verify `from` sources and interrupt names
   against the new family's reference manual
