# Task: Cross-check models against a reference manual

**Goal**
Compare the sodaCat YAML models for a specific chip or subfamily against its
reference manual (PDF), identify discrepancies, and produce actionable errata
entries and config fixes.

**Context**
SVD files are vendor-provided machine descriptions of peripheral register maps.
They contain bugs — missing registers, wrong field names, absent interrupts,
undocumented registers. Reference manuals (RMs) are the ground truth, but they
are unstructured PDFs that require human or AI interpretation. This task
structures the comparison so it is reproducible and thorough.

**When to use this task**
- When onboarding a new chip family and you want to validate the extracted models
- When a new SVD or RM revision is released and you want to detect drift
- When you suspect SVD bugs in a specific peripheral and want to confirm
- Periodically, to audit existing models against the latest RM revision

**Prerequisites**
- The reference manual PDF is available in `docs/<Vendor>/` (see the
  `nxp-reference-manual-tracking` task for NXP, or `st_maintenance.py` for ST)
- YAML models have been generated for the target family
- The chip/subfamily is configured in the vendor config
  (`svd/ST/STM32.yaml` or `svd/NXP/LPC.yaml`)

---

## Phase 1 — Prepare structured context

The goal of this phase is to extract all relevant data from the YAML models into
a compact, readable summary that can be presented alongside RM pages.

### 1.1 Identify the scope

Decide what to check. Options, from narrowest to broadest:

| Scope | When to use |
|-------|-------------|
| Single block | Suspected bug in one peripheral |
| Single chip | New chip onboarding, spot-check |
| Subfamily | Validate all blocks shared by a group of chips |
| Full family | Comprehensive audit (may need multiple sessions) |

For a single-chip check, the relevant files are:
- Chip model: `models/<Vendor>/<Family>/<Subfamily>/<ChipName>.yaml`
- Block models referenced by the chip model (the `model:` field in each instance)
- The vendor config for interrupt mappings and parameter declarations

### 1.2 Extract the chip summary

From the chip model YAML, extract:
- **Interrupt vector table**: IRQ number → name mapping (the `interrupts:` section)
- **Peripheral instance table**: instance name, base address, model type, interrupts,
  parameters

Format as a readable table. Example:

```
Interrupt vector (LPC865):
  IRQ 0: SPI0.SPI          IRQ 16: ADC0.SEQA
  IRQ 1: SPI1.SPI          IRQ 17: ADC0.SEQB
  ...

Instances:
  SYSCON   @ 0x40048000  model=SYSCON    irqs: BOD(13)
  I2C0     @ 0x40050000  model=I2C       irqs: I2C(8)
  ADC0     @ 0x4001C000  model=ADC       irqs: SEQA(16), SEQB(17), THCMP(18), OVR(19)
  ...
```

### 1.3 Extract block register summaries

For each block model referenced by the chip, produce a register summary:

```
Block: I3C (from models/NXP/LPC8/I3C.yaml)
  0x000  MCONFIG         RW  32  [14 fields]
  0x004  SCONFIG         RW  32  [12 fields]
  ...
  0x07C  SMSGLAST        RO  32  [1 field]
  ...
  0x11C  SMAPCTRL0       RW  32  [2 fields]
```

Include register name, offset, access, size, and field count. For a deeper
check, also list field names and bit positions within each register.

### 1.4 Extract the SVD source list

From the vendor config, note which SVD chip/instance provides each block.
This is important because some workarounds involve switching the SVD source
(e.g. sourcing from LPC864 instead of LPC865 to avoid bugs).

---

## Phase 2 — Compare against the reference manual

This is the AI-heavy phase. Present the structured context from Phase 1
alongside the relevant RM sections and ask for a systematic comparison.

### 2.1 Identify RM sections

For each block, locate the corresponding RM chapter. Typical RM structure:

| RM section | What to compare |
|------------|-----------------|
| Register overview table | Register names, offsets, access, reset values |
| Register detail pages | Field names, bit positions, widths |
| Interrupt chapter | IRQ numbers, interrupt names, sources |
| Memory map chapter | Base addresses, peripheral presence |
| Block diagram / feature overview | Instance count, capabilities |

### 2.2 Compare register maps

For each block, compare the YAML model against the RM:

- **Missing registers**: in RM but not in model
- **Extra registers**: in model but not in RM (may be undocumented or SVD noise)
- **Wrong names**: register or field name differs between SVD and RM
- **Wrong offsets**: register at different offset than RM shows
- **Missing/extra fields**: field present in one but not the other
- **Wrong field positions**: bitOffset or bitWidth differs

### 2.3 Compare interrupt vectors

Compare the chip model's interrupt table against the RM's interrupt chapter:

- **Missing interrupts**: in RM but not in chip model
- **Extra interrupts**: in chip model but not in RM
- **Wrong IRQ numbers**: interrupt assigned to different vector

### 2.4 Compare instances and base addresses

Compare the chip model's instance list against the RM's memory map:

- **Missing peripherals**: in RM but not configured
- **Wrong base addresses**: address doesn't match RM memory map
- **Extra peripherals**: configured but not in RM (may be internal/debug)

### 2.5 Classify each discrepancy

For every difference found, classify it:

| Category | Action | Document in |
|----------|--------|-------------|
| **SVD bug** (RM contradicts SVD) | Fix via transform or source switch | `svd/<Vendor>/SVD_ERRATA.md` |
| **RM-only feature** (RM documents it, SVD omits it) | Note as SVD limitation | `SVD_ERRATA.md` |
| **SVD-only feature** (SVD has it, RM doesn't mention it) | Likely undocumented debug reg | `SVD_ERRATA.md` |
| **Extraction bug** (SVD is correct, model is wrong) | Fix the extractor or config | N/A |
| **Cosmetic** (description wording, field ordering) | Ignore | N/A |

**Important**: Always verify against the actual SVD XML before classifying as an
SVD bug. The model is generated from the SVD, but the extraction pipeline may
introduce errors. Check the raw SVD to distinguish SVD bugs from extraction bugs.

The SVD XML files are typically in `build/_deps/` (fetched by CMake) or `svd/`.

---

## Phase 3 — Apply fixes

### 3.1 SVD source switches

If another chip's SVD has a more correct version of the peripheral (as verified
against the RM), switch the source in the vendor config:

```yaml
# Before:
I3C:
  from: LPC865.I3C0

# After (LPC864 SVD is correct, LPC865 has bugs):
I3C:
  from: LPC864.I3C0
```

This is the simplest fix when the alternate SVD is a strict superset or has
correct names/offsets. Always verify that the alternate SVD doesn't introduce
different problems.

### 3.2 Transforms

When a source switch isn't possible (no alternate SVD, or both are buggy),
use inline transforms to patch the model during extraction:

```yaml
transforms:
  - {type: patchRegisters, registers: [{name: MISSING_REG, addressOffset: 0x24, ...}]}
  - {type: renameRegisters, pattern: WRONG_NAME, replacement: RIGHT_NAME}
  - {type: patchFields, register: REG, fields: [{name: MISSING_FIELD, bitOffset: 0, ...}]}
```

### 3.3 Missing interrupts

For interrupts present in the RM but absent from all available SVDs, there is
no automated fix — the SVD simply doesn't declare them. Document in errata and
note that they must be added manually if needed.

### 3.4 Rebuild and verify

```bash
cmake --build build --target rebuild-<family>-models
cmake --build build --target soc-data-test
```

Spot-check the regenerated models to confirm fixes took effect.

### 3.5 Update errata

Add all confirmed SVD bugs to `svd/<Vendor>/SVD_ERRATA.md`, following the
existing format. Group by family and subfamily. Include:
- The SVD version (so fixes can be detected when a new SVD is released)
- The RM reference (document number and revision)
- What the SVD says vs what the RM says
- How it was worked around (source switch, transform, or unfixed)

---

## Worked example: LPC86x (UM11607 Rev. 3)

This example documents the actual process used to validate the LPC865 models.

**Scope**: Single chip (LPC865), all peripherals.

**Findings**:

| Peripheral | Issue | Classification | Fix |
|------------|-------|---------------|-----|
| SYSCON | LPOSCCTRL missing at 0x024 | SVD bug (LPC865 only) | Source from LPC864 |
| SYSCON | EXTTRACECMD at 0x0FC undocumented | SVD-only feature | Source from LPC864 (drops it) |
| I3C | Register at 0x07C named SMSGMAPADDR | SVD bug (LPC865 only) | Source from LPC864 (has SMSGLAST) |
| I3C | SMAPCTRL0 missing at 0x11C | SVD bug (LPC865 only) | Source from LPC864 |
| Interrupts | IRQ 11 (ACMP) absent | SVD bug (both LPC864, LPC865) | Unfixed (no SVD source has it) |
| Interrupts | IRQ 22-23 (GPIO_HS) absent | SVD bug (both LPC864, LPC865) | Unfixed |

**Key lesson**: The LPC865 SVD was significantly buggier than LPC864 for the
same chip family. Comparing across SVD variants within the same family is a
valuable technique — one chip's SVD may have bugs that another's doesn't.

---

## Tips

1. **Start with interrupts and memory map.** These are the most structured RM
   sections and the easiest to compare systematically. Register-level checks
   are more time-consuming.

2. **Check the SVD, not just the model.** When you find a discrepancy, always
   check the raw SVD XML to determine whether it's an SVD bug or an extraction
   bug. The model is derived from the SVD, so a model bug could come from either.

3. **Compare across SVD variants.** If multiple chips in the same family have
   separate SVD files, compare them. One may be more correct than another
   (as with LPC864 vs LPC865).

4. **Undocumented registers are common.** Registers present in the SVD but
   absent from the RM are not necessarily bugs — they may be debug/test registers
   or reserved for future use. Note them in errata but don't remove them unless
   they conflict with documented registers.

5. **RM revisions matter.** Always note which RM revision you checked against.
   A discrepancy found against Rev. 1 may be fixed in Rev. 3.

---

## Reference

- SVD errata: `svd/ST/SVD_ERRATA.md`, `svd/NXP/SVD_ERRATA.md`
- RM tracking (NXP): `tools/check_nxp_manuals.py`, task `nxp-reference-manual-tracking`
- RM tracking (ST): `tools/st_maintenance.py manuals`
- Local RM stash: `docs/ST/`, `docs/NXP/`
- SVD XML sources: `build/_deps/` (fetched by CMake), `svd/ST/` (zip archives)
- Vendor configs: `svd/ST/STM32.yaml`, `svd/NXP/LPC.yaml`
- Transforms: `CLAUDE.md` "Transformation framework" section
