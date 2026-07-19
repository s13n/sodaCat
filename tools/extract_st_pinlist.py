#!/usr/bin/env python3
"""
STM32 datasheet pin-list extractor.

Extracts the pin/ball definition and alternate-function tables from an STM32
datasheet PDF into a single CSV, one row per chip pad.

An STM32 datasheet describes a chip's pinout in two parts:

  1. The *pin/ball definition* table (e.g. "Table 8" in the STM32H747
     datasheet).  One row per pad; columns give the pad's position in every
     package the chip is offered in (LQFP176, UFBGA169, ...), the pin name /
     function-after-reset, pin type, I/O structure, notes, the flat list of
     alternate functions, and the additional (analog / direct) functions.

  2. The *alternate function* tables, one per GPIO port (e.g. "Table 9. Port A
     alternate functions" ... "Table 19. Port K alternate functions").  Each
     gives the AF0..AF15 assignment for every pin of that port.  Only GPIO pins
     have these; supply / analog-only pads do not.

This tool merges the two into one semicolon-delimited CSV (";" because commas
are common inside the data):

    Pin name; <package_1>; ...; <package_N>; Pin type; I/O structure; [Notes;]
    AF0; ...; AF15; Alternate functions; Additional functions; Footnotes; Remarks

The flat "Alternate functions" column (ST's own per-pad list) is kept beside the
AF0..AF15 breakdown, since the two are independent datasheet renderings that
occasionally disagree.  "Notes" is dropped when empty (the H7 editors leave it
empty and inline the footnote references instead).  "Footnotes" carries the
datasheet's own footnote references for the pad, resolved to text.  "Remarks"
carries the extractor's editorial notes: AF-source consistency violations and
any non-ASCII characters stripped from a cell.

The AFx columns are populated from the per-port alternate-function tables,
joined to the pin list on the GPIO name (PA0, PC14, ...).  Pads with no
alternate functions (supply pins, and the "_C" direct-analog duplicate pads
such as PA0_C) leave the AFx columns empty.

The tables are located by caption, not by hard-coded table/page numbers, so the
same script works across STM32 families whose datasheets follow this layout.

Design notes:
  * Package names in the pin-list header are printed as rotated (vertical)
    text; pdfplumber reads them character-reversed ("651PSCLW" for "WLCSP156").
    decode_package() reverses them back, guarded by a package-name pattern so a
    non-rotated datasheet is not corrupted.
  * Identifier names are wrapped across lines *without* a separator
    ("TRACE\nCLK"), so cells are de-wrapped by deleting newlines rather than
    joining with a space.
  * Footnote markers ("N5(1)") are stripped from every value; the referenced
    note numbers are aggregated per pad into the Footnotes column (resolved to
    the note text parsed from below the table).
  * The two AF sources are cross-checked per pin; any divergence is recorded in
    that pad's Remarks cell (and counted on stderr) rather than auto-reconciled,
    since it is usually a genuine datasheet defect.

Installation:
    pip install pdfplumber

Usage:
    python3 extract_st_pinlist.py <datasheet.pdf> <out.csv> [--verbose]

Examples:
    python3 tools/extract_st_pinlist.py \\
        "docs/ST/STM32H747xx (Rev.2).pdf" stm32h747_pins.csv
    python3 tools/extract_st_pinlist.py \\
        "docs/ST/STM32H745xx (Rev.2).pdf" stm32h745_pins.csv --verbose
"""

import argparse
import csv
import re
import sys

import pdfplumber

# pdfplumber table settings: STM32 datasheet tables are fully ruled, so pure
# line-based cell detection is both precise and fast.
TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "edge_min_length": 3,
    "intersection_tolerance": 3,
}

# Caption of the pin/ball definition table (part 1).  ST spells it variously
# "pin/ball definition", "pin definition", "pinout description", ...
PIN_TABLE_RE = re.compile(
    r"Table\s+\d+\.\s*.*?pin[\s/]*(?:ball\s*)?(?:definition|description|assignment|out)",
    re.IGNORECASE,
)
# Caption of a per-port alternate-function table (part 2).
AF_TABLE_RE = re.compile(
    r"Table\s+\d+\.\s*Port\s+[A-Z]+\s+alternate\s+function", re.IGNORECASE
)
# A table-of-contents line: caption text followed by dot leaders + page number.
TOC_LINE_RE = re.compile(r"\.\s*\.\s*\.")

# Package-family tokens, used to tell an upright header from a reversed one.
PKG_TOKEN_RE = re.compile(
    r"(WLCSP|UFBGA|TFBGA|LFBGA|UFQFPN|LQFP|VFQFPN|BGA|QFP|QFN|CSP|SOP|DIP)",
    re.IGNORECASE,
)

# A footnote reference marker, e.g. "N5(1)" or "VDD50USB(5)".  Only "(digits)"
# is a footnote; "(OSC32_IN)" in a pin name is the function-after-reset, kept.
FOOTNOTE_RE = re.compile(r"\((\d+)\)")

# Reversed column-header tokens ("Pin type"->"epyt niP", ...) that pdfplumber
# reads at the bottom of every pin-table page.  Used as a sentinel to stop
# scanning a page for footnote text.
REV_HEADER_TOKENS = {"epyt", "niP", "erutcurts", "setoN", "O/I"}

# A GPIO pin name: port letter A..K (or Z, for safety) plus a bit number.
GPIO_RE = re.compile(r"P[A-Z]\d+")
# The "_C" direct-analog duplicate pads (PA0_C, PC2_C, ...) share a GPIO name
# with a real digital pad but carry no alternate functions of their own.
ANALOG_DUP_RE = re.compile(r"P[A-Z]\d+_")

NUM_AF = 16  # AF0..AF15


def cell(text):
    """Normalise a raw pdfplumber cell.

    ST wraps long identifiers across lines with no separator, so newlines are
    deleted rather than turned into spaces ("TRACE\\nCLK" -> "TRACECLK").  The
    "-" placeholder ST uses for "none" collapses to the empty string.  Stray
    non-ASCII glyphs (e.g. a spurious "µ" that pdfplumber occasionally injects
    at a wrap point, seen in "SPI5_µMISO") are dropped: these tables are pure
    ASCII identifiers, so anything outside printable ASCII is an artifact.
    """
    if not text:
        return ""
    t = text.replace("\r", "").replace("\n", "")
    t = "".join(ch for ch in t if 32 <= ord(ch) <= 126)
    t = re.sub(r" {2,}", " ", t).strip()
    return "" if t == "-" else t


def decode_package(raw):
    """Recover a package name from a (possibly rotated) header cell.

    Rotated headers come out character-reversed; reverse them back, but only
    when that yields something more package-like than the original, so a
    datasheet that prints the header upright is left untouched.
    """
    s = raw.replace("\n", "").strip()
    rev = s[::-1]
    fwd_hit = bool(PKG_TOKEN_RE.search(s))
    rev_hit = bool(PKG_TOKEN_RE.search(rev))
    if rev_hit and not fwd_hit:
        return rev
    if fwd_hit and not rev_hit:
        return s
    # Ambiguous (both or neither match): ST rotates these headers, so the
    # reversed reading is the right default.
    return rev


def find_region(pdf, verbose=False):
    """Locate the page span covering the pin table + all AF tables.

    Returns (start_page_idx, end_page_idx) inclusive, or (None, None).
    TOC entries (dot-leader lines) are ignored so only body captions count.
    """
    pin_pages, af_pages = [], []
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        for line in text.splitlines():
            if TOC_LINE_RE.search(line):
                continue
            if PIN_TABLE_RE.search(line):
                pin_pages.append(i)
            elif AF_TABLE_RE.search(line):
                af_pages.append(i)
    if not pin_pages:
        print("ERROR: could not find a pin/ball definition table caption.",
              file=sys.stderr)
        return None, None
    if not af_pages:
        print("WARNING: no 'Port X alternate functions' table captions found; "
              "AF columns will be empty.", file=sys.stderr)
    start = min(pin_pages)
    end = max(af_pages) if af_pages else max(pin_pages)
    if verbose:
        print(f"  pin-table caption pages: {sorted(set(pin_pages))}", file=sys.stderr)
        print(f"  AF-table caption pages:  {sorted(set(af_pages))}", file=sys.stderr)
        print(f"  scanning pages {start + 1}..{end + 1}", file=sys.stderr)
    return start, end


def classify_tables(pdf, start, end, verbose=False):
    """Extract every ruled table in [start, end] and bucket the fragments.

    A fragment is a pin-list fragment if its header mentions "Pin/ball name",
    an AF fragment if its header mentions both "AF0" and "AF15".  Everything
    else (legends, characteristics tables that happen to fall in the span) is
    ignored.
    """
    pin_frags, af_frags, pin_pages, af_pages = [], [], [], []
    for idx in range(start, end + 1):
        for tbl in pdf.pages[idx].find_tables(TABLE_SETTINGS):
            ext = tbl.extract()
            if not ext:
                continue
            head = " ".join(cell(c) for row in ext[:2] for c in row if c)
            if "Pin/ball name" in head:
                pin_frags.append(ext)
                pin_pages.append(idx)
            elif "AF0" in head and "AF15" in head:
                af_frags.append(ext)
                af_pages.append(idx)
    if verbose:
        print(f"  found {len(pin_frags)} pin-table fragment(s), "
              f"{len(af_frags)} AF-table fragment(s)", file=sys.stderr)
    return pin_frags, af_frags, pin_pages, af_pages


def parse_pin_header(frag):
    """From a pin-list fragment, find the column layout and package names.

    Returns (packages, cols) where cols maps semantic column name -> index.
    """
    hdr_i = next(
        (i for i, r in enumerate(frag) if any(cell(c) == "Pin/ball name" for c in r)),
        None,
    )
    if hdr_i is None:
        raise ValueError("pin-table header row not found")
    row0 = frag[hdr_i]
    pin_col = next(
        i for i, c in enumerate(row0) if cell(c).lower().startswith("pin name")
    )
    # The package sub-header sits on the row below "Pin/ball name", in the
    # columns to the left of the pin-name column.
    subhdr = frag[hdr_i + 1]
    packages = [decode_package(subhdr[c] or "") for c in range(pin_col)]
    cols = {
        "pin_name": pin_col,
        "pin_type": pin_col + 1,
        "io_structure": pin_col + 2,
        "notes": pin_col + 3,
        "alt_functions": pin_col + 4,  # flat summary; used for validation only
        "additional": pin_col + 5,
        "packages": list(range(pin_col)),
    }
    return packages, cols


def extract_pins(pin_frags):
    """Collect data rows from all pin-list fragments.

    Returns (packages, cols, rows) where rows is a list of raw cell lists.
    """
    packages, cols = parse_pin_header(pin_frags[0])
    pin_col = cols["pin_name"]
    rows = []
    for frag in pin_frags:
        for r in frag:
            if len(r) <= pin_col:
                continue
            name = cell(r[pin_col])
            # Skip header rows: "Pin name (function...)" and the blank
            # package sub-header row (empty pin-name cell).
            if not name or name.lower().startswith("pin name") or name == "Pin/ball name":
                continue
            rows.append(r)
    return packages, cols, rows


def extract_af_map(af_frags):
    """Build {gpio_name: [AF0..AF15]} from all AF-table fragments.

    Rows are keyed globally by pin name (which encodes the port), so a page
    carrying two ports' tables, or a port table split across pages, both work
    without segmenting by port.  Also returns {gpio_name: [edit_note, ...]}
    recording any non-ASCII characters stripped from an AF cell.
    """
    af_map = {}
    af_edits = {}
    for frag in af_frags:
        hdr = next((r for r in frag if any(cell(c) == "AF0" for c in r)), None)
        if hdr is None:
            continue
        af0 = next(i for i, c in enumerate(hdr) if cell(c) == "AF0")
        pin_c = af0 - 1
        for r in frag:
            if len(r) <= pin_c:
                continue
            pin = cell(r[pin_c])
            if not re.fullmatch(r"P[A-Z]\d+", pin):
                continue  # skips header + peripheral-group rows
            afs, edits = [], []
            for k in range(NUM_AF):
                raw = r[af0 + k] if len(r) > af0 + k else ""
                bad = nonascii_chars(raw or "")
                if bad:
                    edits.append(f"AF{k}: stripped {''.join(bad)!r}")
                afs.append(cell(raw))
            if pin in af_map and af_map[pin] != afs:
                print(f"WARNING: conflicting AF rows for {pin}; keeping first.",
                      file=sys.stderr)
                continue
            af_map[pin] = afs
            if edits:
                af_edits[pin] = edits
    return af_map, af_edits


def norm_list(text):
    """Normalise comma spacing in a flat comma-separated list cell.

    De-wrapping leaves mixed ", " / "," separators (ST breaks the list across
    lines at arbitrary points); collapse them to a consistent ", ".
    """
    return re.sub(r"\s*,\s*", ", ", text)


def strip_footnotes(text):
    """Split footnote markers out of a cell value.

    Returns (clean_text, [note_numbers]).  "N5(1)" -> ("N5", [1]);
    "PC14-OSC32_IN(OSC32_IN)(1)" -> ("PC14-OSC32_IN(OSC32_IN)", [1]).
    """
    nums = [int(n) for n in FOOTNOTE_RE.findall(text)]
    clean = re.sub(r" {2,}", " ", FOOTNOTE_RE.sub("", text)).strip()
    return clean, nums


def nonascii_chars(text):
    """Return the sorted set of non-printable-ASCII chars that cell() drops.

    Newlines/carriage returns are excluded — those are line wraps, not an
    editorial change.  Everything else outside printable ASCII (e.g. a stray
    "µ") is a real edit worth recording.
    """
    return sorted({ch for ch in text.replace("\r", "").replace("\n", "")
                   if not 32 <= ord(ch) <= 126})


def extract_footnotes(pdf, first_idx, last_idx):
    """Parse the numbered note block printed below the pin table.

    Notes look like "1. <text>" and wrap onto following lines until the next
    sequential number.  The block starts at the bottom of the last pin-table
    page and can spill onto the following (non-table) page before the AF tables
    begin, so all pages in [first_idx, last_idx] are scanned.  Page furniture
    (running headers, page numbers, the reversed rotated-header block) is
    skipped so it is not appended to a note body.  Returns {number: text}.
    """
    notes = {}
    cur = None
    started = False
    for idx in range(first_idx, last_idx + 1):
        for line in (pdf.pages[idx].extract_text() or "").splitlines():
            s = line.strip()
            if s in REV_HEADER_TOKENS:
                break  # reached the rotated column-header block: rest is furniture
            if (not s or re.match(r"^\d+/\d+\b", s) or re.search(r"DS\d+\s+Rev", s)
                    or re.fullmatch(r"\d+", s) or "Pin descriptions" in s):
                continue  # page number / footer / stray layout number / running header
            m = re.match(r"^\s*(\d{1,2})\.\s+(.*)", line)
            # Only a *sequential* number starts a new note, so "3.3 V" inside a
            # note body is treated as continuation, not a new note.
            if m and int(m.group(1)) == (cur + 1 if cur is not None else 1):
                cur = int(m.group(1))
                notes[cur] = m.group(2).strip()
                started = True
            elif started and cur is not None:
                notes[cur] = (notes[cur] + " " + s).strip()
    return notes


def function_tokens(text):
    """Split a function list into its individual signal names.

    The two datasheet tables render multi-function entries differently: the
    per-port AF tables separate alternatives with "/" ("JTMS/SWDIO",
    "SPI2_MOSI/I2S2_SDO"), while the pin list's flat summary uses "," between
    functions and sometimes "-" for combined SWJ names ("JTMS-SWDIO").  Split on
    all three so the two can be compared token-for-token.
    """
    return {t.strip() for t in re.split(r"[,/\-]", text) if t.strip()}


def af_tokens(afs):
    """Flatten AFx cell values into the set of individual function names."""
    out = set()
    for v in afs:
        out |= function_tokens(v)
    return out


def merge(packages, cols, pin_rows, af_map, af_edits, notes, verbose=False):
    """Join AF assignments onto pin rows; return (header, rows) for CSV.

    Footnote markers ("N5(1)", ...) are stripped from every value and the
    referenced note numbers are aggregated per pad into a "Footnotes" column,
    resolved to the note text from `notes` when available.  A final "Remarks"
    column records, per pad, any editorial action: a consistency violation
    between the two AF sources, or a non-ASCII character stripped from a cell.

    List separators inside cells use ", " / " | " rather than ";" so the CSV
    can be written with a ";" delimiter (commas are common in the data) without
    forcing quotes.
    """
    # The flat "Alternate functions" column (ST's own per-pad AF list) is kept
    # alongside the AF0..AF15 breakdown, not dropped as redundant: the two are
    # independent datasheet renderings that occasionally disagree (a defect in
    # one is filled by the other), so keeping both maximises fidelity and lets
    # a maintainer reconcile the flagged discrepancies recorded in Remarks.
    header = (
        ["Pin name"]
        + packages
        + ["Pin type", "I/O structure", "Notes"]
        + [f"AF{i}" for i in range(NUM_AF)]
        + ["Alternate functions", "Additional functions", "Footnotes", "Remarks"]
    )
    notes_col = len(packages) + 3  # index of "Notes" in each output row
    out_rows = []
    used_af = set()
    n_discrepancies = 0
    for r in pin_rows:
        fn = []       # footnote numbers referenced anywhere in this row
        remarks = []  # editorial notes for this pad

        def clean(idx, listcol=False):
            """Read cell `idx`: normalise, strip footnotes, record edits/refs."""
            raw = r[idx] if idx < len(r) else ""
            bad = nonascii_chars(raw or "")
            if bad:
                remarks.append(f"stripped {''.join(bad)!r}")
            v = cell(raw)
            if listcol:
                v = norm_list(v)
            v, nums = strip_footnotes(v)
            fn.extend(nums)
            return v

        name = clean(cols["pin_name"])
        key_m = GPIO_RE.match(name)
        key = key_m.group(0) if key_m else None
        is_analog_dup = bool(ANALOG_DUP_RE.match(name))
        pkg_vals = [clean(c) for c in cols["packages"]]
        pin_type = clean(cols["pin_type"])
        io_structure = clean(cols["io_structure"])
        pin_notes = clean(cols["notes"])
        alt_summary = clean(cols["alt_functions"], listcol=True)
        additional = clean(cols["additional"], listcol=True)

        afs = [""] * NUM_AF
        if key and not is_analog_dup and key in af_map:
            afs = []
            for v in af_map[key]:
                v, nums = strip_footnotes(v)
                fn.extend(nums)
                afs.append(v)
            used_af.add(key)
            remarks.extend(af_edits.get(key, ()))
            # Cross-check the flat summary against the AF-table union.  A
            # difference is either an extraction artifact or a genuine
            # datasheet inconsistency between the two tables; record it for
            # human review rather than trying to auto-reconcile.
            summary_tok = function_tokens(alt_summary)
            af_tok = af_tokens(afs)
            if summary_tok and summary_tok != af_tok:
                n_discrepancies += 1
                s_only = ", ".join(sorted(summary_tok - af_tok)) or "none"
                a_only = ", ".join(sorted(af_tok - summary_tok)) or "none"
                remarks.append(
                    f"AF mismatch — only in Table 8 summary [{s_only}], "
                    f"only in AF table [{a_only}]"
                )

        fn = sorted(set(fn))
        footnotes = " | ".join(
            f"{n}: {notes[n]}" if n in notes else str(n) for n in fn
        )
        out_rows.append(
            [name] + pkg_vals
            + [pin_type, io_structure, pin_notes]
            + afs
            + [alt_summary, additional, footnotes, " | ".join(remarks)]
        )

    # ST's "Notes" column is where the datasheet would carry footnote numbers,
    # but the H7 editors put the references inline in the data instead, leaving
    # it empty.  Drop it when nothing uses it, keep it when a family does.
    if all(not row[notes_col] for row in out_rows):
        del header[notes_col]
        for row in out_rows:
            del row[notes_col]
        if verbose:
            print("  dropped empty 'Notes' column", file=sys.stderr)

    unmatched_af = sorted(set(af_map) - used_af)
    if unmatched_af:
        print(f"WARNING: {len(unmatched_af)} AF-table pin(s) had no pin-list "
              f"row: {unmatched_af}", file=sys.stderr)
    if n_discrepancies:
        print(f"NOTE: {n_discrepancies} pin(s) where the Table 8 AF summary "
              f"differs from the per-port AF tables (see the Remarks column).",
              file=sys.stderr)
    if verbose:
        print(f"  {len(out_rows)} pads, {len(used_af)} with alternate functions",
              file=sys.stderr)
    return header, out_rows


def main():
    ap = argparse.ArgumentParser(
        description="Extract an STM32 datasheet pin list (+ alternate functions) to CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("pdf_path", help="Path to the STM32 datasheet PDF")
    ap.add_argument("csv_path", help="Path to the output CSV file")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="Print detection and validation detail to stderr")
    args = ap.parse_args()

    print(f"Opening {args.pdf_path} ...", file=sys.stderr)
    with pdfplumber.open(args.pdf_path) as pdf:
        start, end = find_region(pdf, args.verbose)
        if start is None:
            return 1
        pin_frags, af_frags, pin_pages, af_pages = classify_tables(
            pdf, start, end, args.verbose)
        if not pin_frags:
            print("ERROR: no pin-list table fragments extracted.", file=sys.stderr)
            return 1
        packages, cols, pin_rows = extract_pins(pin_frags)
        af_map, af_edits = extract_af_map(af_frags)
        # The footnote block starts on the last pin-table page and may spill
        # onto the gap page(s) before the AF tables begin.
        fn_last = (min(af_pages) - 1) if af_pages else max(pin_pages)
        notes = extract_footnotes(pdf, max(pin_pages), max(max(pin_pages), fn_last))

    print(f"Packages: {packages}", file=sys.stderr)
    if args.verbose and notes:
        print(f"  footnotes: {sorted(notes)}", file=sys.stderr)
    header, rows = merge(packages, cols, pin_rows, af_map, af_edits, notes,
                         args.verbose)

    with open(args.csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(header)
        w.writerows(rows)

    print(f"Wrote {len(rows)} pads x {len(header)} columns to {args.csv_path}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
