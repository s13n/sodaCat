# Task: Unify a peripheral block into a cross-family shared model

**Goal**
Take a peripheral block type that exists across multiple STM32 families and
produce a single parameterized YAML model in `models/ST/`, referenced by all
families via `uses:` in `extractors/STM32.yaml`.

**When to use this task**
The block should meet most of these criteria:
- Present on 3+ families (ideally 5+)
- Register maps are >80% identical across families
- Differences are parametric (fields present/absent, register variants) rather
  than architectural (completely different register layouts)
- The resulting parameter count stays reasonable (<~15)
- The block is high-value (commonly used, many instances per chip)

**When NOT to use this task**
- Blocks on only 1-2 families (not enough sharing benefit)
- Blocks where each family has a fundamentally different register layout (e.g.
  RCC, Flash) -- these must remain per-family or per-subfamily
- Blocks that are already trivially identical with no parameters needed (just
  make them shared with no params, no need for this full process)

---

## Phase 1 -- Survey and compare

### 1.1 Identify candidate families

List every family that has the block type in its `blocks:` section. Note the
source chip (`from:`) and instance list for each.

### 1.2 Extract and compare register maps

For each family, extract the block from its source SVD and compare:
- Register names and offsets
- Field names, offsets, and widths within each register
- Presence/absence of entire registers
- EnumeratedValues differences (usually ignorable noise)

Use `tools/compare_peripherals.py` or manual diff. Group the families by
similarity -- you'll typically find 2-4 "generations" of the IP block.

### 1.3 Classify every difference

For each difference found, classify it as one of:

| Category | Action |
|----------|--------|
| **SVD bug** (RM contradicts SVD) | Fix with a `transforms:` entry; document in `svd/SVD_ERRATA.md` |
| **Generation difference** (newer IP adds fields/registers) | Candidate for a boolean or enum parameter |
| **Instance difference** (some instances lack registers) | Candidate for an instance-level parameter |
| **Cosmetic** (description wording, enum value names) | Ignore -- use the superset source's text |
| **Architectural** (different register layout) | Cannot unify; must remain a separate variant |

### 1.4 Produce a comparison document

Create a `<BlockType>_comparison.md` document (in the project root, as a
working file) with:
- A per-family table showing every instance and its parameter values
- Convention: `(parenthesized)` = default, bare = explicit override
- A parameter legend mapping abbreviations to full parameter names
- A detailed section per parameter documenting the register/field effects

See `GpTimer_comparison.md` for the reference format.

---

## Phase 2 -- Choose superset source and define parameters

### 2.1 Select the source chip

Pick the SVD chip that has the **cleanest, most complete** register set:
- Prefer newer-generation chips (they're usually supersets of older ones)
- Prefer chips with fewer known SVD bugs
- Verify against the reference manual -- the SVD is the starting point, not the
  truth
- **Use the original peripheral, not a derivedFrom alias.** For example, prefer
  `USART1` over `UART4` — even when UART4 inherits identical registers via
  derivedFrom, it may lack features (synchronous mode, smartcard) in the actual
  hardware. The original is both more correct and self-documenting.

The source goes into `shared_blocks.<BlockType>.from: <Chip>.<Instance>`.

### 2.2 Define parameters

For each dimension of variation, define a parameter:

| Variation type | Parameter type | Example |
|---------------|---------------|---------|
| Feature present/absent | `bool` | `has_dither: {type: bool, default: false}` |
| Multi-level capability | `int` (enum) | `encoder: {type: int, default: 0}` (0/1/2/3) |
| Numeric property | `int` | `channels: {type: int, default: 4}` |
| Register variant selection | `int` (enum) | `dma_burst: {type: int, default: 1}` (0=none, 1=v1, 2=v2) |

Guidelines:
- **Set defaults to the most common value** -- this minimizes `chip_params`
  entries across all families
- **Use `bool` over `int` when there are exactly two states** (present/absent)
- **Use `int` enums when there are 3+ levels** of a capability
- **Document the register/field effect** of each parameter value -- this is
  critical for the C++ generator to know what to gate
- Parameters for properties not visible in the register map (e.g. channel
  count, counter width) are still valuable as metadata for code generators

### 2.3 Handle register variants

When different generations use different register layouts at different offsets
for the same logical function (e.g. DCR_V1 at 0x48 vs DCR at 0x3DC), include
**both** registers in the superset model with distinct names and use a parameter
to select which one is active.

---

## Phase 3 -- Build the shared model

### 3.1 Add to `shared_blocks` in STM32.yaml

```yaml
shared_blocks:
  BlockType:
    from: SourceChip.Instance
    params:
      - {name: param1, type: bool, default: true, description: What it controls}
      - {name: param2, type: int, default: 0, description: Capability level}
    interrupts:
      RAW_SVD_NAME: CANONICAL_NAME
    transforms:
      - {type: renameRegisters, pattern: ..., replacement: ...}
```

### 3.2 Update each family's block entry

Change each family from `from:` to `uses:`:

```yaml
# Before (per-family extraction):
BlockType:
  from: FamilyChip.Instance
  instances: [INST1, INST2, ...]
  interrupts: { ... }

# After (shared reference) — non-owning families:
BlockType:
  uses: BlockType
  instances: [INST1, INST2, ...]
```

Non-owning families only need `uses:` and `instances:`. The `interrupts:` key
is **not needed** — extraction is skipped for `uses:` blocks, so the interrupt
mapping has no effect. Remove it to avoid dead config.

The **owning family** (the one whose chip is in the shared block's `from:`)
does need `interrupts:` because it performs the actual extraction. If the SVD
interrupt description contains an instance name (e.g. "UART4 Global interrupt"),
use the dict form to override it with a generic description:

```yaml
# After (shared reference) — owning family only:
BlockType:
  uses: BlockType
  instances: [INST1, INST2, ...]
  interrupts:
    UART4: {name: INTR, description: Global interrupt}
```

This prevents instance-specific text from leaking into the shared model.

### 3.3 Add `chip_params` for non-default values

For instances that differ from parameter defaults, add entries under the
family's `chip_params:` section:

```yaml
chip_params:
  _all:
    _all:
      BlockType: {param1: false}    # family-wide override
  SubfamilyA:
    _all:
      INST1: {param2: 2}            # subfamily-wide, specific instance
    SpecificChip:
      INST3: {param2: 3}            # chip-specific override
```

Resolution order (first match wins):
1. Subfamily + chip + instance name
2. Subfamily + chip + block name
3. Subfamily + `_all` + instance name
4. Subfamily + `_all` + block name
5. `_all` + `_all` + instance name
6. `_all` + `_all` + block name
7. Parameter default

### 3.4 Verify RM alignment

For each family, verify against the reference manual that:
- Every instance listed actually exists on the chips in that subfamily
- Interrupt names match the RM's interrupt table
- Parameter values match the RM's register descriptions (not just the SVD)

---

## Phase 4 -- Generate and verify

### 4.1 Build the owning family first

The family whose chip is used in `from:` generates the shared model:

```bash
cmake --build build --target rebuild-stm32XX-models
```

Inspect `models/ST/<BlockType>.yaml`:
- Params section should list all parameters in array format
- Registers should be the complete superset
- No instance-name prefixes on register names

### 4.2 Build all families

```bash
# Build all 17 families (or at minimum, one representative from each
# generation that uses the block)
cmake --build build --target rebuild-stm32c0-models
cmake --build build --target rebuild-stm32f3-models
# ... etc
```

Families with `uses:` should skip extraction for this block and reference
the shared model. Verify no errors.

### 4.3 Compile test

```bash
cmake --build build --target soc-data-test
```

This validates that all generated C++ headers still compile. No output = success.

### 4.4 Spot-check chip models

Pick 2-3 chip models from different families and verify that the `parameters:`
section in the chip YAML has correct resolved values for each instance.

---

## Lessons learned from GpTimer unification

These patterns emerged during the GpTimer work and apply to future blocks:

1. **Start with the comparison, not the implementation.** Understanding all the
   differences before writing any config prevents backtracking.

2. **Newer SVDs are usually better sources.** N6 (STM32N645) had the cleanest
   TIM2 across all families. Older SVDs (F1, L1) tend to have more bugs.

3. **SVDs lie; RMs are ground truth.** Always verify SVD register layouts
   against the reference manual, especially for fields that control optional
   features. Document SVD bugs in `svd/SVD_ERRATA.md`.

4. **Defaults matter.** Choosing the right default for each parameter
   dramatically reduces the amount of `chip_params` config needed. Pick the
   value that applies to the most instances across all families.

5. **Bool vs enum is a design choice.** If you think a capability might gain a
   third level in a future family, use `int` from the start. Converting
   `has_dma_burst: bool` to `dma_burst: int(0,1,2)` mid-stream was extra work.

6. **Register variants need distinct names.** When two generations have the
   same logical register at different offsets (DCR_V1 vs DCR), include both
   with a `_V1` suffix on the older variant and use a parameter to select.

7. **Transforms fix SVD bugs, not hardware differences.** If two families
   genuinely have different registers, that's a parameter. If the SVD is wrong,
   that's a transform.

8. **Instance-level parameters go in `chip_params`, not block `params`.** The
   `params` declaration defines the schema (name, type, default). The values
   come from `chip_params` resolution. A param with a `default` only needs
   `chip_params` entries for instances that differ.

9. **Use the original peripheral, not a derivedFrom alias.** When picking the
   source instance in `from:`, choose the peripheral that *defines* the
   register set in the SVD, not a derivedFrom copy. For example, prefer
   `USART1` over `UART4` even if they have identical registers — `UART4` is
   typically a derivedFrom alias that lacks synchronous/smartcard fields in
   the hardware. Using the original is both more correct and self-documenting.

10. **Interrupt descriptions must be generic.** The shared model's interrupt
    `description:` field must not contain instance-specific names (e.g.
    "UART4 Global interrupt"). Replace with a generic description (e.g.
    "Global interrupt") since the model is shared across many instances and
    families. Use the dict form `{name: INTR, description: Global interrupt}`
    in the owning family's `interrupts:` mapping, and check the generated model
    output after generation.

11. **Non-owning families don't need `interrupts:`.** For families with `uses:`
    that aren't the owning family, extraction is skipped entirely — the
    `interrupts:` mapping has no effect. Only `uses:` and `instances:` are
    needed. Remove `interrupts:` to avoid dead config.

---

## Reference

- Existing shared blocks: `WWDG`, `GpTimer` (in `shared_blocks` section of
  `extractors/STM32.yaml`)
- Comparison document format: `GpTimer_comparison.md`
- SVD errata log: `svd/SVD_ERRATA.md`
- Generator: `extractors/generate_stm32_models.py`
- Schema: `schemas/peripheral.schema.yaml`

### Good next candidates (unverified -- need comparison first)

| Block | Families | Expected complexity | Notes |
|-------|----------|-------------------|-------|
| BasicTimer | ~12 | Very low | Strict subset of GpTimer (TIM6/TIM7); may need only 1-2 params |
| SPI | 17 | Medium | Gen1 (SPI) vs Gen2 (OCTOSPI); may split into two block types |
| I2C | 17 | Medium | v1 (F1/F4/L1) vs v2 (everything else); two distinct register maps |
| USART | 17 | Medium-high | Many generational differences but same core structure |
| DMA | ~15 | High | Multiple architectures (DMA, BDMA, GPDMA); likely too different |
