#!/usr/bin/env python3
"""ST resource maintenance: check and update SVD archives and reference manuals.

Subcommands:
  svd       Check for updated SVD zip archives on st.com.
  manuals   Check reference manual revisions against local PDFs.

Both subcommands query ST's lightweight metadata API (~14-26 KB) to get
current version numbers without downloading large files.

Usage:
    python3 tools/st_maintenance.py svd
    python3 tools/st_maintenance.py svd --download
    python3 tools/st_maintenance.py manuals
    python3 tools/st_maintenance.py manuals --fetch
    python3 tools/st_maintenance.py manuals --fetch --download
    python3 tools/st_maintenance.py manuals --fetch --update-config
    python3 tools/st_maintenance.py manuals --fetch --only RM0490 RM0433
    python3 tools/st_maintenance.py manuals --scan-local --update-config
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ruamel.yaml import YAML

# ============================================================================
# Shared infrastructure
# ============================================================================

# HTTP headers required by ST's CDN (derived from modm-ext/cmsis-svd-stm32-zip).
_ST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Sec-Fetch-Site': 'none',
    'Accept-Encoding': 'identity',
    'Sec-Fetch-Mode': 'navigate',
    'Host': 'www.st.com',
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                   'AppleWebKit/605.1.15 (KHTML, like Gecko) '
                   'Version/17.2 Safari/605.1.15'),
    'Accept-Language': 'en-GB,en;q=0.9',
    'Sec-Fetch-Dest': 'document',
    'Connection': 'keep-alive',
}

_SCRIPT_DIR = Path(__file__).parent
_DEFAULT_CONFIG = _SCRIPT_DIR.parent / 'svd' / 'ST' / 'STM32.yaml'
_DEFAULT_SVD_DIR = _SCRIPT_DIR.parent / 'svd' / 'ST'
_DEFAULT_DOCS_DIR = _SCRIPT_DIR.parent / 'docs' / 'ST'


def _curl_fetch(url, dest, timeout=30):
    """Download url to dest using curl with ST-required headers.

    Returns (success, error_message).
    """
    cmd = ["curl", url, "-L", "-s", "--max-time", str(timeout), "-o", dest]
    for k, v in _ST_HEADERS.items():
        cmd += ["-H", f"{k}: {v}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, f"curl exit {result.returncode}"
    if not os.path.exists(dest) or os.path.getsize(dest) == 0:
        return False, "empty response"
    return True, None


def _fetch_st_index(url):
    """Fetch a JSON metadata index from ST's selector API.

    Returns (list_of_row_dicts, None) or (None, error_message).
    """
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        ok, err = _curl_fetch(url, tmp_path)
        if not ok:
            return None, f"Failed to fetch index: {err}"
        with open(tmp_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON from index: {e}"
    finally:
        os.unlink(tmp_path)
    return data["rows"], None


def _load_config(config_path):
    """Load STM32.yaml with ruamel.yaml (roundtrip-safe)."""
    yaml = YAML()
    yaml.width = 4096
    with open(config_path) as f:
        return yaml.load(f)


def _save_config(config_path, config):
    """Write back STM32.yaml preserving formatting."""
    yaml = YAML()
    yaml.width = 4096
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    with open(config_path, 'w') as f:
        yaml.dump(config, f)


# ============================================================================
# SVD subcommand
# ============================================================================

_SVD_INDEX_URL = ("https://www.st.com/bin/st/selectors/cxst/en."
                  "cxst-cad-grid.html/CL1734."
                  "cad_models_and_symbols.svd.json")


def cmd_svd(args):
    """Check for updated STM32 SVD zip archives and optionally download."""
    config_path = args.config
    svd_dir = args.svd_dir

    if not config_path.is_file():
        print(f"Error: {config_path} not found", file=sys.stderr)
        return 1
    if not svd_dir.is_dir():
        print(f"Error: {svd_dir} is not a directory", file=sys.stderr)
        return 1

    config = _load_config(config_path)

    # Build zip_filename -> family_code lookup
    zip_to_code = {}
    for code, family in config.get('families', {}).items():
        svd = family.get('svd', {})
        zip_name = svd.get('zip')
        if zip_name:
            zip_to_code[zip_name] = code

    # Phase 1: Fetch metadata
    print("Fetching SVD index from st.com...")
    rows, err = _fetch_st_index(_SVD_INDEX_URL)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    print(f"Found {len(rows)} SVD archives on st.com\n")

    # Match remote entries against registered families
    updated = 0
    unchanged = 0
    unregistered = 0
    failed = 0

    entries = []
    for row in rows:
        family = row["localizedDescriptions"]["en"].split()[0]
        version = row["version"]
        path = row["localizedLinks"]["en"]
        ts = row.get("latestUpdate", 0) / 1000
        date = (datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                if ts else "?")
        entries.append({
            "family": family,
            "version": version,
            "url": "https://www.st.com" + path,
            "date": date,
            "filename": os.path.basename(path),
        })

    mode = "" if args.download else " (dry run)"
    for entry in sorted(entries, key=lambda e: e["family"]):
        filename = entry["filename"]
        remote_ver = entry["version"]
        family_code = zip_to_code.get(filename)

        sys.stdout.write(f"  {entry['family']:<12s} {filename:<28s} ")
        sys.stdout.flush()

        if family_code is None:
            print(f"v{remote_ver} ({entry['date']})  -- not registered")
            unregistered += 1
            continue

        family_cfg = config['families'][family_code]
        svd_cfg = family_cfg.get('svd', {})
        local_ver = svd_cfg.get('version')
        local_path = svd_dir / filename
        has_local = local_path.exists()

        if has_local and local_ver == remote_ver:
            print(f"v{remote_ver}  up to date")
            unchanged += 1
            continue

        if not has_local:
            print(f"v{remote_ver} ({entry['date']})  -- new download{mode}")
        else:
            old_label = f"v{local_ver}" if local_ver else "unknown"
            print(f"{old_label} -> v{remote_ver} ({entry['date']}){mode}")

        if not args.download:
            updated += 1
            continue

        # Phase 2: Download the archive
        with tempfile.NamedTemporaryFile(
                dir=str(svd_dir), suffix=".tmp", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            ok, dl_err = _curl_fetch(entry["url"], tmp_path, timeout=120)
            if not ok:
                print(f"    DOWNLOAD FAILED: {dl_err}")
                failed += 1
                continue
            shutil.move(tmp_path, str(local_path))
            tmp_path = None
            svd_cfg['version'] = remote_ver
            svd_cfg['date'] = entry["date"]
            updated += 1
            print(f"    downloaded")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    if args.download and updated:
        _save_config(config_path, config)

    print(f"\nSummary: {updated} updated, {unchanged} unchanged,"
          f" {failed} failed, {unregistered} not registered"
          f" (out of {len(entries)} remote archives)")

    if updated and args.download:
        print("\nNext steps:")
        print("  1. Rebuild models:    cmake --build <dir>")
        print("  2. Audit transforms:  cmake --build <dir>"
              " --target audit-stm32-models")
        print("     (detects transforms that became no-ops due to SVD fixes)")
    if unregistered:
        print(f"\n{unregistered} archive(s) on st.com"
              " not registered in STM32.yaml.")
    return 1 if failed else 0


# ============================================================================
# Manuals subcommand
# ============================================================================

_RM_INDEX_URL = ("https://www.st.com/bin/st/selectors/cxst/en."
                 "cxst-cad-grid.html/CL1734."
                 "technical_literature.reference_manual.json")


def _parse_rm_rev(rev_str):
    """Parse a revision string into a comparable integer."""
    try:
        return int(str(rev_str).strip())
    except (ValueError, AttributeError):
        return 0


def _collect_config_manuals(config):
    """Extract ref_manual entries from all subfamilies in a loaded config."""
    manuals = {}
    for family_code, family_cfg in (config.get('families') or {}).items():
        for sf_name, sf_cfg in (family_cfg.get('subfamilies') or {}).items():
            rm = sf_cfg.get('ref_manual')
            if not rm:
                continue
            name = rm.get('name', '')
            if name in manuals:
                manuals[name]['subfamilies'].append(sf_name)
                continue
            manuals[name] = {
                'subfamilies': [sf_name],
                'family': family_code,
                'rev': (str(rm.get('rev', ''))
                        if rm.get('rev') is not None else ''),
                'date': (str(rm.get('date', ''))
                         if rm.get('date') is not None else ''),
                'url': rm.get('url', ''),
            }
    return manuals


def _scan_local_pdfs(docs_dir):
    """Scan docs directory for PDFs and extract RM number + revision."""
    pattern = re.compile(
        r'^(RM\d+)\s+-\s+(.+?)\s+\(Rev\.?\s*(\d+)\)\.pdf$'
    )
    local = {}
    unmatched = []

    for pdf in sorted(docs_dir.glob('*.pdf')):
        m = pattern.match(pdf.name)
        if m:
            local[m.group(1)] = {
                'filename': pdf.name,
                'description': m.group(2),
                'rev': m.group(3).strip(),
                'path': pdf,
            }
        else:
            unmatched.append(pdf.name)

    return local, unmatched


def _extract_pdf_revision(pdf_data):
    """Extract revision number and date from the first page of a PDF.

    Returns (rev_str, date_str) or (None, None) on failure.
    Requires PyMuPDF (fitz).
    """
    try:
        import fitz
    except ImportError:
        print("Warning: PyMuPDF (fitz) not installed,"
              " cannot extract PDF revision", file=sys.stderr)
        return None, None

    try:
        doc = fitz.open(stream=pdf_data, filetype='pdf')
        text = doc[0].get_text()[:2000]
        doc.close()
    except Exception as e:
        print(f"Warning: Failed to parse PDF: {e}", file=sys.stderr)
        return None, None

    rev_match = re.search(r'RM\d+\s+Rev\s+(\d+)', text)
    rev = rev_match.group(1) if rev_match else None

    date_match = re.search(
        r'(January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s+(\d{4})', text
    )
    date_str = None
    if date_match:
        month_names = {
            'January': '01', 'February': '02', 'March': '03', 'April': '04',
            'May': '05', 'June': '06', 'July': '07', 'August': '08',
            'September': '09', 'October': '10', 'November': '11',
            'December': '12',
        }
        month = month_names[date_match.group(1)]
        year = date_match.group(2)
        date_str = f"{year}-{month}"

    return rev, date_str


def _fetch_pdf(url, session, timeout=(10, 60), retries=3):
    """Download a PDF from url.

    Returns (rev_str, date_str, pdf_bytes) or (None, None, None) on failure.
    """
    last_error = None
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            break
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    else:
        err_msg = str(last_error)
        if 'timed out' in err_msg.lower():
            print(f" timeout", file=sys.stderr)
        else:
            print(f" error: {err_msg}", file=sys.stderr)
        return None, None, None

    if not resp.headers.get('Content-Type', '').startswith('application/pdf'):
        print(f"  Not a PDF (Content-Type:"
              f" {resp.headers.get('Content-Type')})", file=sys.stderr)
        return None, None, None

    rev, date = _extract_pdf_revision(resp.content)
    return rev, date, resp.content


def _save_pdf(pdf_data, docs_dir, rm_name, description, rev):
    """Save a downloaded PDF to docs_dir with the standard naming."""
    filename = f"{rm_name} - {description} (Rev. {rev}).pdf"
    dest = docs_dir / filename
    dest.write_bytes(pdf_data)
    return dest


def _update_rm_config(config_path, updates):
    """Write rev and date back to ref_manual entries in the YAML config.

    updates: dict of {rm_name: {'rev': str, 'date': str}}
    """
    config = _load_config(config_path)

    changed = 0
    for family_code, family_cfg in (config.get('families') or {}).items():
        for sf_name, sf_cfg in (family_cfg.get('subfamilies') or {}).items():
            rm = sf_cfg.get('ref_manual')
            if not rm:
                continue
            name = rm.get('name', '')
            if name not in updates:
                continue
            upd = updates[name]
            if upd.get('rev'):
                rm['rev'] = upd['rev']
                changed += 1
            if upd.get('date'):
                rm['date'] = upd['date']

    if changed:
        _save_config(config_path, config)
        print(f"\nUpdated {changed} ref_manual entries in {config_path}")


def _fetch_rm_index():
    """Fetch the RM metadata index and normalize entries.

    Returns dict of {rm_name: {'rev': str, 'date': str, 'url': str}}
    or (None, error_message).
    """
    rows, err = _fetch_st_index(_RM_INDEX_URL)
    if err:
        return None, err

    result = {}
    for row in rows:
        title = row.get("title", "")
        if not title.startswith("RM"):
            continue
        ver_str = row.get("version", "")
        # Normalize "5.0" -> "5" (ST RM versions are integers)
        rev = ver_str.split('.')[0] if '.' in ver_str else ver_str
        ts = row.get("latestUpdate", 0) / 1000
        date = (datetime.datetime.fromtimestamp(ts).strftime("%Y-%m")
                if ts else "")
        link = row.get("localizedLinks", {}).get("en", "")
        url = "https://www.st.com" + link if link else ""
        result[title] = {'rev': rev, 'date': date, 'url': url}
    return result, None


def cmd_manuals(args):
    """Check reference manual revisions and optionally download updates."""
    config_path = args.config

    if not config_path.is_file():
        print(f"Error: Config not found: {config_path}", file=sys.stderr)
        return 1
    if not args.docs_dir.is_dir():
        print(f"Error: Docs directory not found: {args.docs_dir}",
              file=sys.stderr)
        return 1

    config = _load_config(config_path)
    all_config_manuals = _collect_config_manuals(config)
    local_pdfs, unmatched_files = _scan_local_pdfs(args.docs_dir)

    # Filter to --only if specified
    if args.only:
        only_set = set(args.only)
        config_manuals = {k: v for k, v in all_config_manuals.items()
                         if k in only_set}
    else:
        config_manuals = all_config_manuals

    # Scan local PDFs for revision info (extract from page 0)
    local_revs = {}
    if args.scan_local:
        for rm_name, local in sorted(local_pdfs.items()):
            if args.only and rm_name not in set(args.only):
                continue
            rev, date = _extract_pdf_revision(local['path'].read_bytes())
            if rev:
                local_revs[rm_name] = {'rev': rev, 'date': date or ''}
                if rev != local['rev']:
                    print(f"  {rm_name}: filename says Rev {local['rev']},"
                          f" PDF says Rev {rev}")
        if args.update_config and local_revs:
            _update_rm_config(config_path, local_revs)

    # Fetch remote revisions if requested
    remote_revs = {}
    if args.fetch:
        print("Fetching RM index from st.com...")
        index, err = _fetch_rm_index()
        if err:
            print(f"Error: {err}", file=sys.stderr)
            return 1
        print(f"Found {len(index)} reference manuals on st.com\n")

        for rm_name in sorted(config_manuals):
            if rm_name in index:
                remote_revs[rm_name] = index[rm_name]

    # Compare and classify
    up_to_date = []
    updates = []
    missing = []
    config_updates = {}

    for rm_name, info in sorted(config_manuals.items()):
        local = local_pdfs.get(rm_name)
        remote = remote_revs.get(rm_name)

        # Determine the "known latest" revision
        if remote:
            known_rev = remote['rev']
            known_date = remote['date']
        elif info['rev']:
            known_rev = info['rev']
            known_date = info['date']
        else:
            if not local:
                missing.append((rm_name, info, None))
            else:
                up_to_date.append((rm_name, info, local, None))
            continue

        # Track for config update
        if remote and (remote['rev'] != info.get('rev', '') or
                       remote['date'] != info.get('date', '')):
            config_updates[rm_name] = {
                'rev': remote['rev'], 'date': remote['date']
            }

        if not local:
            missing.append((rm_name, info, known_rev))
        elif _parse_rm_rev(known_rev) > _parse_rm_rev(local['rev']):
            updates.append((rm_name, info, local, known_rev))
        else:
            up_to_date.append((rm_name, info, local, known_rev))

    # Untracked: local files not in config (always use full config)
    all_config_names = set(all_config_manuals.keys())
    untracked = [(rm, local_pdfs[rm]) for rm in sorted(local_pdfs)
                 if rm not in all_config_names]

    # Handle downloads
    if args.download:
        import requests
        session = requests.Session()
        session.headers.update({
            'User-Agent': _ST_HEADERS['User-Agent'],
        })

        to_download = []
        for rm_name, info, local, known_rev in updates:
            remote = remote_revs.get(rm_name)
            url = (remote or {}).get('url', '') or info.get('url', '')
            if url:
                desc = local['description'] if local else rm_name
                to_download.append((rm_name, url, desc, known_rev, local))
        for rm_name, info, known_rev in missing:
            remote = remote_revs.get(rm_name)
            url = (remote or {}).get('url', '') or info.get('url', '')
            if url and known_rev:
                sfs = ', '.join(info['subfamilies'])
                to_download.append((rm_name, url, sfs, known_rev, None))

        for i, (rm_name, url, desc, rev, local) in enumerate(to_download):
            print(f"  Downloading {rm_name}...", end='', flush=True)
            _, _, pdf_data = _fetch_pdf(
                url, session, timeout=(10, args.timeout))
            if pdf_data:
                dest = _save_pdf(pdf_data, args.docs_dir, rm_name, desc, rev)
                print(f" {dest.name}")
                if local and local['path'].name != dest.name:
                    local['path'].unlink()
                    print(f"  Removed old: {local['path'].name}")
            else:
                print(" failed")
            if i < len(to_download) - 1 and args.delay > 0:
                time.sleep(args.delay)

        session.close()
        if to_download:
            print()

    # Print results
    if up_to_date:
        print("UP TO DATE:")
        for rm_name, info, local, known_rev in up_to_date:
            sfs = ', '.join(info['subfamilies'])
            rev_str = local['rev']
            print(f"  {rm_name}  Rev. {rev_str:>3}  {sfs}")

    if updates:
        print("\nUPDATE AVAILABLE:")
        for rm_name, info, local, known_rev in updates:
            sfs = ', '.join(info['subfamilies'])
            print(f"  {rm_name}  Rev. {local['rev']:>3} -> {known_rev}"
                  f"  {sfs}")

    if missing:
        print("\nMISSING:")
        for rm_name, info, known_rev in missing:
            sfs = ', '.join(info['subfamilies'])
            rev_display = f"Rev. {known_rev}" if known_rev else "Rev. ?"
            print(f"  {rm_name}  {rev_display:>8}  {sfs}")

    if untracked or unmatched_files:
        print("\nUNTRACKED:")
        for rm_name, local in untracked:
            print(f"  {rm_name}  Rev. {local['rev']:>3}  {local['filename']}")
        for filename in unmatched_files:
            print(f"  (no RM#)          {filename}")

    # Update config if requested
    if args.update_config and config_updates:
        _update_rm_config(config_path, config_updates)

    # Summary
    total = len(config_manuals)
    print(f"\n{len(up_to_date)}/{total} up to date", end="")
    if updates:
        print(f", {len(updates)} update(s) available", end="")
    if missing:
        print(f", {len(missing)} missing", end="")
    print()

    return 1 if updates or missing else 0


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # --- svd subcommand ---
    svd_p = subparsers.add_parser(
        'svd',
        help='Check/download STM32 SVD zip archives',
        description='Query ST metadata API for SVD archive versions, '
                    'compare against STM32.yaml, and optionally download.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    svd_p.add_argument(
        '--svd-dir', type=Path, default=_DEFAULT_SVD_DIR,
        help='Directory containing STM32 SVD zip files')
    svd_p.add_argument(
        '--config', type=Path, default=_DEFAULT_CONFIG,
        help='Path to STM32.yaml config file')
    svd_p.add_argument(
        '--download', action='store_true',
        help='Download updated archives (default: check only)')

    # --- manuals subcommand ---
    rm_p = subparsers.add_parser(
        'manuals',
        help='Check/download ST reference manual PDFs',
        description='Compare local reference manual PDFs against revision '
                    'data in STM32.yaml and optionally fetch current '
                    'revisions from st.com.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    rm_p.add_argument(
        '--config', type=Path, default=_DEFAULT_CONFIG,
        help='Path to STM32.yaml config file')
    rm_p.add_argument(
        '--docs-dir', type=Path, default=_DEFAULT_DOCS_DIR,
        help='Path to local reference manual directory')
    rm_p.add_argument(
        '--fetch', action='store_true',
        help='Query ST metadata API for current revision numbers (~26 KB)')
    rm_p.add_argument(
        '--download', action='store_true',
        help='Download new/updated PDFs to docs dir (implies --fetch)')
    rm_p.add_argument(
        '--update-config', action='store_true',
        help='Write discovered rev/date back to config YAML')
    rm_p.add_argument(
        '--scan-local', action='store_true',
        help='Extract rev/date from local PDFs (uses PyMuPDF, no network)')
    rm_p.add_argument(
        '--only', nargs='+', metavar='RM',
        help='Only check these specific RM numbers (e.g., RM0490 RM0433)')
    rm_p.add_argument(
        '--delay', type=float, default=2.0,
        help='Delay between PDF downloads in seconds (default: 2.0)')
    rm_p.add_argument(
        '--timeout', type=int, default=60,
        help='Read timeout for PDF downloads in seconds (default: 60)')

    args = parser.parse_args()

    if args.command == 'svd':
        return cmd_svd(args)

    # manuals: resolve flag implications
    if args.download:
        args.fetch = True
    if args.update_config and not args.scan_local:
        args.fetch = True
    return cmd_manuals(args)


if __name__ == '__main__':
    sys.exit(main())
