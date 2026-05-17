#!/usr/bin/env python3
"""Re-extract RM0399 chapter-14 routing tables into 4-column CSVs.

Output: docs/ST/RM0399/table-{102..107}.csv, each with columns
    src_instance,src_signal,dst_signal,dst_instance

Pipeline per table:
  1. pdf_table_extractor: line-based table read with --forward-fill on the
     instance and destination-signal columns (merged cells in those columns
     mean "shared by every row of the merge", i.e. one source signal feeding
     several destinations or several source signals feeding one destination).
  2. Drop NC rows (entries describing destination ports that are not wired).
  3. Expand "X or Y(n)" compound source rows into one row per alternative.
  4. Collapse stray whitespace inside signal names. pdfplumber occasionally
     splits a cell's word at the line-wrap boundary, leaving artefacts like
     `lptim2_ext_trg 0` (should be `lptim2_ext_trg0`) or `mu x3` (should be
     `mux3`). Signal names in these tables are SVD-style identifiers with no
     legitimate internal whitespace, so collapsing is safe.

Re-run after a RM0399 revision bump:
    python3 tools/extract_rm0399_chapter14.py
"""

import csv
import re
import sys
from pathlib import Path

# Pull the extractor in as a library; it lives next to this script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pdf_table_extractor

PDF_PATH = Path('docs/ST/RM0399 - STM32H745 STM32H755 STM32H747 STM32H757 (Rev. 4).pdf')
OUT_DIR = Path('docs/ST/RM0399')

# Per-table page ranges, inclusive of both endpoints. Tight bounds so the
# extractor never sees prose-as-table on the following section's heading
# page (pdfplumber's line-based table detection finds dubious 18-column
# "tables" on body-text pages).
TABLES = {
    102: ('Peripherals interconnect matrix details',   617, 632),
    103: ('EXTI wakeup inputs',                        634, 636),
    104: ('EXTI pending requests clear inputs',        637, 637),
    105: ('MDMA',                                      639, 640),
    106: ('DMAMUX1, DMA1 and DMA2 connections',        641, 645),
    107: ('DMAMUX2 and BDMA connections',              646, 648),
}

# Columns are referenced before --drop-columns trims them. The chapter-14
# tables share a fixed left-half schema: src Domain / Bus / Peripheral /
# Signal / dst Signal / dst Peripheral. (Tables 102, 103 add Type / Target
# / Comment to the right, the others add Bus / Domain / Comment — all
# dropped.)
FORWARD_FILL = '2,4,5'
DROP_COLUMNS = '0,1,6..'

OR_FOOTNOTE_RE = re.compile(r'\s*\(\d+\)\s*$')


def split_or_row(row):
    """Split "X or Y" compound source rows into N single-source rows.

    Returns a list of rows. Non-OR rows pass through unchanged."""
    src_peri, src_sig, dst_sig, dst_peri = row
    peri_clean = OR_FOOTNOTE_RE.sub('', src_peri)
    if ' or ' not in peri_clean and ' or ' not in src_sig:
        return [row]
    peris = [p.strip() for p in peri_clean.split(' or ')]
    sigs = [s.strip() for s in src_sig.split(' or ')]
    if len(peris) != len(sigs):
        # Asymmetric "or" — bail out, leave the row alone with a warning.
        print(f"  warn: asymmetric OR ({len(peris)} peris, {len(sigs)} sigs): {row}")
        return [row]
    return [[p, s, dst_sig, dst_peri] for p, s in zip(peris, sigs)]


def normalize_signal(s):
    """Collapse internal whitespace in a signal-name cell."""
    return re.sub(r'\s+', '', s) if s else s


def is_nc(row):
    """NC ("not connected") rows describe missing wiring, not real routes.

    Drop the row if any of (src_peri, src_sig, dst_sig) is bare 'NC', or
    if src_peri is the DMAMUX-internal request-generator pseudo-source
    (those describe DMAMUX's own runtime-configurable inputs, not chip
    wiring)."""
    src_peri, src_sig, dst_sig, dst_peri = row
    if any(c == 'NC' for c in (src_peri, src_sig, dst_sig)):
        return True
    if 'internal (Request generator)' in src_peri:
        return True
    return False


def extract_one(table_num, title, start_page, end_page):
    out = OUT_DIR / f'table-{table_num}.csv'
    raw = OUT_DIR / f'.table-{table_num}.tmp.csv'
    print(f'\n=== Table {table_num}: {title} (p.{start_page}-{end_page}) ===')

    ok = pdf_table_extractor.extract_table_from_pdf(
        pdf_path=str(PDF_PATH),
        start_page=start_page,
        end_page=end_page,
        output_csv=str(raw),
        skip_header_rows=2,
        drop_columns_spec=DROP_COLUMNS,
        forward_fill_spec=FORWARD_FILL,
    )
    if not ok:
        print(f'  ✗ extractor failed')
        return

    with open(raw) as f:
        rows = list(csv.reader(f))
    raw.unlink()

    # Drop header rows: the first two rows are the two-line header
    # ('','','Destination','' / 'Peripheral','Signal','Signal','Peripheral').
    data = rows[2:]

    # NC drop, OR split, signal-name whitespace fix.
    cleaned = []
    for row in data:
        if len(row) != 4:
            print(f'  warn: expected 4 cols, got {len(row)}: {row}')
            continue
        if is_nc(row):
            continue
        for expanded in split_or_row(row):
            expanded[1] = normalize_signal(expanded[1])
            expanded[2] = normalize_signal(expanded[2])
            cleaned.append(expanded)

    with open(out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['src_instance', 'src_signal', 'dst_signal', 'dst_instance'])
        w.writerows(cleaned)
    print(f'  → {out} ({len(cleaned)} routes)')


def main():
    if not PDF_PATH.exists():
        print(f'PDF not found: {PDF_PATH}')
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for num, (title, p0, p1) in TABLES.items():
        extract_one(num, title, p0, p1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
