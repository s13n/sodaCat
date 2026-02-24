#!/usr/bin/env python3
"""Check for updated STM32 SVD zip archives and download changes.

Usage:
    python3 download_stm32_svds.py <svd_dir> <config_yaml> [--dry-run]

Queries ST's SVD metadata API to get current version numbers, compares
against versions recorded in svd/ST/STM32.yaml, and downloads updated archives
directly from st.com when versions differ.

Phase 1 (cheap):  Fetch ~14 KB JSON metadata, compare version strings.
Phase 2 (on-demand): Download only the archives whose version changed.
"""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

from ruamel.yaml import YAML

ST_SVD_INDEX_URL = ("https://www.st.com/bin/st/selectors/cxst/en."
                    "cxst-cad-grid.html/CL1734.cad_models_and_symbols.svd.json")

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


def _curl_fetch(url, dest):
    """Download url to dest using curl with ST-required headers.

    Returns (success, error_message).
    """
    cmd = ["curl", url, "-L", "-s", "--max-time", "120", "-o", dest]
    for k, v in _ST_HEADERS.items():
        cmd += ["-H", f"{k}: {v}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, f"curl exit {result.returncode}"
    if not os.path.exists(dest) or os.path.getsize(dest) == 0:
        return False, "empty response"
    return True, None


def _fetch_index():
    """Fetch ST's SVD metadata index. Returns list of entry dicts."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        ok, err = _curl_fetch(ST_SVD_INDEX_URL, tmp_path)
        if not ok:
            return None, f"Failed to fetch SVD index: {err}"
        with open(tmp_path) as f:
            data = json.load(f)
    finally:
        os.unlink(tmp_path)

    entries = []
    for row in data["rows"]:
        family = row["localizedDescriptions"]["en"].split()[0]
        version = row["version"]
        path = row["localizedLinks"]["en"]
        ts = row.get("latestUpdate", 0) / 1000
        date = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else "?"
        url = "https://www.st.com" + path
        local_name = os.path.basename(path)
        entries.append({
            "family": family,
            "version": version,
            "url": url,
            "date": date,
            "filename": local_name,
        })
    return entries, None


def _load_config(config_path):
    """Load STM32.yaml and build zip_filename -> family_code lookup."""
    yaml = YAML()
    yaml.width = 4096
    with open(config_path) as f:
        config = yaml.load(f)

    zip_to_code = {}
    for code, family in config.get('families', {}).items():
        svd = family.get('svd', {})
        zip_name = svd.get('zip')
        if zip_name:
            zip_to_code[zip_name] = code

    return config, zip_to_code


def _save_config(config_path, config):
    """Write back STM32.yaml preserving comments and formatting."""
    yaml = YAML()
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    with open(config_path, 'w') as f:
        yaml.dump(config, f)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("svd_dir", help="Directory containing STM32 SVD zip files")
    parser.add_argument("config_yaml", help="Path to STM32.yaml config file")
    parser.add_argument("--dry-run", action="store_true",
                        help="Check for updates without downloading")
    args = parser.parse_args()

    svd_dir = os.path.abspath(args.svd_dir)
    config_path = os.path.abspath(args.config_yaml)

    if not os.path.isdir(svd_dir):
        print(f"Error: {svd_dir} is not a directory", file=sys.stderr)
        return 1
    if not os.path.isfile(config_path):
        print(f"Error: {config_path} not found", file=sys.stderr)
        return 1

    config, zip_to_code = _load_config(config_path)

    # Phase 1: Fetch metadata
    print("Fetching SVD index from st.com...")
    entries, err = _fetch_index()
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    print(f"Found {len(entries)} SVD archives on st.com\n")

    # Match remote entries against registered families
    updated = 0
    unchanged = 0
    new_downloads = 0
    unregistered = 0
    failed = 0

    mode = " (dry run)" if args.dry_run else ""
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
        local_path = os.path.join(svd_dir, filename)
        has_local = os.path.exists(local_path)

        if has_local and local_ver == remote_ver:
            print(f"v{remote_ver}  up to date")
            unchanged += 1
            continue

        if not has_local:
            print(f"v{remote_ver} ({entry['date']})  -- new download{mode}")
        else:
            old_label = f"v{local_ver}" if local_ver else "unknown"
            print(f"{old_label} -> v{remote_ver} ({entry['date']}){mode}")

        if args.dry_run:
            updated += 1
            continue

        # Phase 2: Download the archive
        with tempfile.NamedTemporaryFile(dir=svd_dir, suffix=".tmp", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            ok, err = _curl_fetch(entry["url"], tmp_path)
            if not ok:
                print(f"    DOWNLOAD FAILED: {err}")
                failed += 1
                continue
            shutil.move(tmp_path, local_path)
            tmp_path = None
            svd_cfg['version'] = remote_ver
            svd_cfg['date'] = entry["date"]
            if not has_local:
                new_downloads += 1
            updated += 1
            print(f"    downloaded")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    if not args.dry_run and (updated or new_downloads):
        _save_config(config_path, config)

    print(f"\nSummary: {updated} updated, {unchanged} unchanged,"
          f" {failed} failed, {unregistered} not registered"
          f" (out of {len(entries)} remote archives)")

    if updated and not args.dry_run:
        print("\nNext steps:")
        print("  1. Rebuild models:    cmake --build <dir>")
        print("  2. Audit transforms:  cmake --build <dir> --target audit-stm32-models")
        print("     (detects transforms that became no-ops due to SVD fixes)")
    if unregistered:
        print(f"\n{unregistered} archive(s) on st.com not registered in STM32.yaml.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
