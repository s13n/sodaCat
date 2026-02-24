# Task: Update STM32 SVD archives and reconcile changes

**Goal**
Download updated SVD zip archives from st.com, re-extract models, audit
transforms for no-ops, and clean up any transforms that are no longer needed
because ST fixed the underlying SVD bug.

**When to use this task**
- Periodically (e.g. monthly) to stay current with ST's SVD releases
- After ST publishes a new reference manual revision that likely comes with
  SVD fixes
- When onboarding a new family (the download script will fetch any registered
  family whose zip file is missing locally)

---

## Phase 1 -- Check for updates

Run a read-only check to see what changed without downloading anything:

```bash
cmake --build <build_dir> --target check-stm32-svds
```

This queries ST's SVD metadata API and compares remote version strings against
the `svd.version` fields in `svd/ST/STM32.yaml`. The output shows each family
as one of:
- **up to date** — local version matches remote
- **vX.Y -> vX.Z** — an update is available
- **new download** — registered in STM32.yaml but zip file missing locally
- **not registered** — archive exists on st.com but no family entry in STM32.yaml

If everything is up to date, stop here.

---

## Phase 2 -- Download updates

```bash
cmake --build <build_dir> --target update-stm32-svds
```

This downloads changed archives into `svd/ST/` and updates the `svd.version`
and `svd.date` fields in `svd/ST/STM32.yaml` in-place (using ruamel.yaml to
preserve comments and formatting).

Verify the download succeeded:

```bash
git diff -- svd/ST/STM32.yaml
```

You should see version/date changes for the updated families and nothing else.

---

## Phase 3 -- Re-extract models

The updated zip files invalidate the stamp files, so a regular build
re-extracts:

```bash
cmake --build <build_dir>
```

Or target specific families:

```bash
cmake --build <build_dir> --target rebuild-stm32h7-models
```

Review what changed in the models:

```bash
git diff -- models/ST/
```

Common changes after an SVD update:
- **New/renamed fields** — ST added or renamed register fields
- **Fixed field widths** — a field that was too wide or narrow got corrected
- **New registers** — ST added previously undocumented registers
- **Description text changes** — cosmetic, usually harmless

If the model diff is empty for a family, the SVD update was metadata-only
(e.g. version bump with no register changes).

---

## Phase 4 -- Audit transforms

```bash
cmake --build <build_dir> --target audit-stm32-models
```

Or for a single family:

```bash
cmake --build <build_dir> --target audit-stm32h7-models
```

The audit reports transforms in three categories:

| Category | Meaning | Action |
|----------|---------|--------|
| **NO-OP** | Transform matched nothing — the SVD bug it fixed is gone | Safe to remove |
| **Partially obsolete** | Some effects are now redundant | Review which parts can be simplified |
| **Active** | Transform still has an effect | Keep as-is |

---

## Phase 5 -- Clean up no-op transforms

For each no-op reported by the audit:

1. **Find the corresponding entry in `svd/ST/SVD_ERRATA.md`** and annotate it
   with "Fixed in SVD vX.Y" (the new version you just downloaded).

2. **Remove the transform** from the family's `blocks` section (or from
   `shared_blocks` if it's a cross-family shared block) in `svd/ST/STM32.yaml`.

3. **Re-extract** the affected family to confirm the model is unchanged:
   ```bash
   cmake --build <build_dir> --target rebuild-stm32XX-models
   git diff -- models/ST/
   ```
   The diff should be empty — if removing the transform changes the model,
   the transform was not truly a no-op (the audit may have a false positive
   for partial matches).

4. **For partially obsolete transforms**, simplify them (e.g. narrow a regex
   pattern, remove fixed fields from a patchFields list) rather than removing
   them entirely. Re-extract and verify that the model stays the same for the
   parts that were already correct, and only changes for the parts that are
   now fixed.

---

## Phase 6 -- Verify and commit

1. **Compile test** — ensure generated C++ headers still build:
   ```bash
   cmake --build <build_dir> --target soc-data-test
   ```

2. **Review the full diff** one more time:
   ```bash
   git diff -- svd/ST/STM32.yaml models/ST/
   ```

3. **Commit** in logical groups:
   - SVD version bumps + model changes (the update itself)
   - Transform cleanup (separate commit for traceability)

---

## Reference

- SVD archives and config: `svd/ST/` (see `svd/ST/README.md`)
- Download script: `tools/download_stm32_svds.py`
- Generator with audit mode: `extractors/generate_stm32_models.py --audit`
- SVD errata log: `svd/ST/SVD_ERRATA.md`
- Transform types: documented in `CLAUDE.md` under "Transformation framework"
