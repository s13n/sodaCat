# Extracting Chip-Level Information from Reference Manuals

A guide for the cases where the SVD doesn't give us what we need.  Reference
manuals (RMs), datasheets (DSs), and user manuals (UMs) hold the canonical
truth for everything the silicon vendor didn't bother to put in their SVD —
clock-tree topology, mux source lists, sometimes corrected interrupt
mappings, memory maps with intent, and so on.  Extracting from PDFs is
fragile compared to SVD parsing, but for narrow, well-bounded targets it's
worth doing.

This is a **method document**, not a recipe.  Every extraction needs human
judgement; the goal here is to give that judgement a place to start.

## When this guide applies

Use it when:

  - The SVD doesn't carry the information you need (e.g. mux input names,
    signal-routing topology, clock-tree semantics).
  - The SVD carries information that's *wrong* and the RM is authoritative
    (we've hit this: STM32 F413/F423 I2C IRQ misattribution, MCXN
    misrepresented USB PHY parameters).
  - You need to cross-check the SVD-derived model against an independent
    source for a slice of the data.

Don't use it when:

  - The SVD already covers the topic adequately.
  - You only need a single value — just hand-author and move on.
  - The source is a diagram rather than a table (see "Pitfalls" below).

## The two-stage pattern

Mirrors how we handle SVDs:

1. **Offline extraction** — done by the maintainer when a new RM revision
   lands.  Produces a structured JSON/CSV artifact.  Committed.
2. **Online consumption** — the main extractor or a validator reads the
   committed artifact.  No PDF parsing in the live path.

PDF parsing is too slow (seconds per page on a 4000-page RM), too dependent
on `pdfplumber` version specifics, and too prone to revision drift to be
part of the build pipeline.  Treat the extracted JSON as the artifact of
record; re-extract only when the RM revision bumps.

## Tools available

  - **`tools/pdf_table_extractor.py`** — pdfplumber-based.  Finds tables by
    caption (`Table N: ...`) or by page range, dumps to CSV, handles
    multi-page tables with header repetition, supports column dropping
    and header-row skipping.  CLI:

    ```
    python3 tools/pdf_table_extractor.py <pdf|url> <out.csv> \
        [--table N] [--pages 87-88] [--skip-header N] [--drop-columns 1,3,5]
    ```

  - **`tools/pdf_diagram_extractor.py`** — PyMuPDF-based block-diagram
    graph extractor.  Output is *much* less reliable than table
    extraction; treat as a starting point, not a finished artifact.

  - **`tools/check_nxp_manuals.py`** — checks tracked NXP RM revisions
    against the local PDFs in `docs/NXP/`.  When you re-extract on a new
    revision, this is the canary that tells you which manuals moved.

## Targets, ranked by value-per-effort

| # | Target | Effort | Value | Notes |
| - | ------ | ------ | ----- | ----- |
| 1 | Memory-map / base-address tables | Low | High | Single well-formed table per RM; cross-checks chip YAMLs' `baseAddress`. |
| 2 | Interrupt vector tables | Medium | High | Multi-page, but cross-checks the per-instance `outputs:` wiring (the IVT view derives from it).  Would have caught F413 / F423 SVD misattribution. |
| 3 | Mux source lists | Low per-table | Medium | Useful when authoring or auditing a clock tree. |
| 4 | Bit-field documentation where SVD is silent | Medium | Low | SVD usually has this. |
| 5 | Pin / alternate-function tables | High | High | Big tables, vendor-specific layout — half-done is worse than nothing. |
| 6 | Clock-tree diagrams | Very high | High | Image OCR territory.  Faster to hand-author from the diagram. |

If you're attempting this for the first time, start with #1.

## The workflow

For any target:

1. **Locate the table.**  Open the RM, find the right section, note:
     - Caption text — `Table 89: Interrupt vector table`.  This is your
       most stable anchor; page numbers move between revisions.
     - Page range — for `--pages` when the caption search is ambiguous.
     - Document ID + revision — `RM0399 rev 4`.  Record this in the
       artifact's header.

2. **Test extraction.**  Run `pdf_table_extractor.py` on a small page
   range first.  Inspect the CSV.  Look for:
     - Merged or split header rows.
     - Cells with embedded newlines (multi-line entries).
     - Footnotes leaking into rows.
     - Multi-page tables where the header repeats — use `--skip-header`.

3. **Normalize.**  Convert the CSV to a canonical JSON the consumer expects.
   Keep the normalization in a small Python script *committed alongside the
   data* (e.g. `tools/extract_<vendor>_<topic>.py`) so the path from PDF
   to JSON is reproducible.

4. **Add a source header.**  Every extracted artifact carries a small
   header so future maintainers know its provenance:

    ```yaml
    source:
      document_id: RM0399
      revision: '4'
      table: 'Table 89: Interrupt vector table'
      extracted_with: tools/pdf_table_extractor.py
      extracted_on: 2026-05-12
    ```

5. **Commit the artifact.**  PDFs themselves typically don't go in the
   repo (size, vendor terms); the extracted JSON does.

6. **Wire to consumer.**  Update the validator or extractor that should
   read the JSON.  Don't put PDF parsing in the consumer.

## Scriptable vs. judgement

**Scriptable:** column extraction, header detection, footer trimming,
column-name normalisation, value parsing (hex / decimal), de-duplication.

**Needs judgement:**

  - Ambiguous caption matches (which `Table 89` did you mean?).
  - Mapping table columns to canonical schema fields (`Position` vs
    `IRQ#` vs `Vector`).
  - Resolving disagreements (SVD says X, RM says Y — which is right?
    Usually RM, but not always; check both, ask the maintainer).
  - `see Note 3` rows that depend on a footnote elsewhere.
  - Detecting partial extractions (a multi-page table that lost rows
    because the layout changed in this revision).

Write the script for the scriptable parts; flag the judgement parts as
comments in the output so the human reviewer can see them.

## Pitfalls

  - **Revision drift.**  A new RM revision changes layout, sometimes
    renumbers tables.  Expect 10-30% manual cleanup on revision bumps.
    Anchor by caption text whenever possible.
  - **Vendor inconsistency.**  ST RMs, NXP UMs, Microchip DSs each use
    distinct table styles.  Per-vendor extraction logic is the norm,
    not the exception.
  - **Multi-page tables.**  `pdfplumber.extract_tables()` runs per-page;
    multi-page tables need post-processing to stitch.  The included
    extractor handles header repetition but not all stitching cases.
  - **Diagrams.**  Clock-tree topology, block diagrams, mux fan-out
    pictures — image OCR is the only option and the output is usually
    unusable without heavy manual cleanup.  Usually faster to read the
    diagram and hand-author the YAML.
  - **"Reserved" rows.**  Don't drop them automatically; they often
    encode silicon-fixed positions worth preserving in the model.

## Worked example skeleton — memory map

For a concrete starting case:

1. RM0399 (STM32H7) §1.4 "Memory map and register boundary addresses",
   Table 8.
2. `python3 tools/pdf_table_extractor.py RM0399.pdf /tmp/h7_memmap.csv \
       --table 8 --pages 100..115`
3. Inspect the CSV.  Typical columns: `Boundary address | Peripheral |
   Bus | Register map`.
4. Normalise (Python ~30 lines) to:

    ```yaml
    source: { document_id: RM0399, revision: '4', table: 'Table 8: ...' }
    peripherals:
      ADC1:     { base: 0x40022000, bus: AHB1 }
      ADC2:     { base: 0x40022100, bus: AHB1 }
      ...
    ```

5. Cross-check against `models/ST/H7/<subfamily>/<subfamily>.yaml`'s
   `instances.*.baseAddress`.  Discrepancies are interesting: SVD bug,
   chip-yaml typo, or RM table revised.

When this example is actually implemented, add the script as
`tools/extract_st_memmap.py` and link it from this section.

## When to grow this document

Each new extraction adds:

  - A target-specific recipe — which table, which RM section, which
    columns, any per-vendor quirks.
  - An example of the resulting JSON shape.
  - Lessons learned (which steps surprised you).

Treat this as a living document.  The goal is for the next person
(human or AI) attempting an extraction not to start at zero.

## See also

  - `tools/pdf_table_extractor.py`, `tools/pdf_diagram_extractor.py`.
  - `tools/check_nxp_manuals.py` — RM revision tracking.
  - `docs/design/subfamily-model.md` — where many of the extracted
    facts ultimately consume.
