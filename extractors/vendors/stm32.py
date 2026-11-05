"""STM32 vendor extension for the unified model generator.

Provides SVD access via zip archives and STM32-style source attribution.
Requires tools/ on sys.path (set up by generate_models.py).

SVD supplements: when ST's archive lags behind new parts, a family's `svd:`
entry in STM32.yaml can list them under `supplement:`
({repo, tag, path, chips: {<chip>: <sha256>}}).  CMake fetches the repo and
passes `--svd-supplement <dir>`; the listed chips are then read from there
(checksum-verified) instead of the zip.

A family with no archive on st.com yet (e.g. G5, published only as ST's
GitHub DFP) has no `svd.zip`: CMake then passes the svd/ST directory as
`svd_source`, and every chip must come from the supplement.
"""

import hashlib
import os
import sys
import tempfile
from pathlib import Path

from ruamel.yaml import YAML

import svd


use_config_interrupt_map = True


def family_namespace(family_code):
    """STM32 chips use the convention `stm32<family>` (e.g. H7 → stm32h7)."""
    return f'stm32{family_code.lower()}'


def family_label(family_code, subfamily_name):
    """STM32 marketing family label (`STM32H7`); used as `family:` in
    extractor-emitted subfamily YAMLs."""
    return f'STM32{family_code}'


def add_cli_args(parser):
    """Add STM32-specific CLI arguments."""
    parser.add_argument('svd_source', type=Path,
                        help='Path to SVD zip archive, or the svd/ST directory '
                             'for a family whose SVDs all come from its '
                             'svd.supplement')
    parser.add_argument('--svd-supplement', type=Path, metavar='DIR',
                        help='Directory with the SVDs listed under the '
                             "family's svd.supplement in STM32.yaml")


def validate_args(args):
    """Validate STM32-specific arguments."""
    if not args.svd_source.exists():
        print(f"Error: {args.svd_source} not found")
        sys.exit(1)
    family = YAML(typ='safe', pure=True).load(config_path(args).read_text())[
        'families'].get(args.family_code) or {}
    supp = (family.get('svd') or {}).get('supplement')
    args.supplement = supp
    if supp is None:
        if args.svd_source.is_dir():
            print(f"Error: {args.family_code} has neither an SVD archive nor "
                  f"an svd.supplement in STM32.yaml")
            sys.exit(1)
        return
    if args.svd_supplement is None or not args.svd_supplement.is_dir():
        print(f"Error: STM32.yaml lists an SVD supplement for "
              f"{args.family_code} ({supp['repo']} {supp['tag']}); pass its "
              f"{supp['path']} directory with --svd-supplement")
        sys.exit(1)
    if args.svd_source.is_dir():
        return                          # supplement-only family, no archive
    for chip in supp['chips']:
        if svd.extractFromZip(args.svd_source, chip) is not None:
            print(f"Note: {args.svd_source.name} now contains {chip}; it can "
                  f"be dropped from the {args.family_code} svd.supplement")


def config_path(args):
    """Return path to the STM32 consolidated YAML config."""
    base = args.svd_source if args.svd_source.is_dir() else args.svd_source.parent
    return base / 'STM32.yaml'


def open_svd(args, chip_name):
    """Extract and parse an SVD file from the zip archive.

    Returns (xml_root, extra_metadata_dict) or None if not found.
    """
    supp = args.supplement
    if supp and chip_name in supp['chips']:
        return _open_supplement(args, supp, chip_name)
    if args.svd_source.is_dir():
        return None                     # supplement-only family
    svd_content = svd.extractFromZip(args.svd_source, chip_name)
    if svd_content is None:
        return None
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.svd', delete=False) as tf:
        tf.write(svd_content)
        temp_path = tf.name
    try:
        root = svd.parse(temp_path)
    finally:
        os.unlink(temp_path)
    return root, {}


def _open_supplement(args, supp, chip_name):
    """Parse a supplement SVD after checking it against the pinned sha256."""
    path = args.svd_supplement / f'{chip_name}.svd'
    if not path.is_file():
        print(f"Error: {path} not found (svd.supplement {supp['tag']})")
        sys.exit(1)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != supp['chips'][chip_name]:
        print(f"Error: {path} sha256 {digest} does not match STM32.yaml "
              f"({supp['chips'][chip_name]})")
        sys.exit(1)
    repo = supp['repo'].removesuffix('.git').rsplit('/', 1)[-1]
    return svd.parse(str(path)), {'svd_path': f"{repo} {supp['tag']}/{chip_name}"}


def format_source(name, version, svd_tag=''):
    """Format source attribution string (STM32 style: 'ChipName SVD vX.Y')."""
    if version:
        return f"{name} SVD v{version}"
    return f"{name} SVD"


def errata_path():
    """Return the vendor's SVD errata doc path (for audit reports)."""
    return 'svd/ST/SVD_ERRATA.md'


def get_interrupt_offset(cpu_info):
    """Return interrupt vector offset for Cortex-M (16 system exceptions)."""
    return 16
