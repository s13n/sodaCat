"""Microchip ATSAM vendor extension for the unified model generator.

Provides SVD access via in-tree files in svd/Microchip/.  Requires tools/
on sys.path (set up by generate_models.py).
"""

import sys
from pathlib import Path

import svd

# Use config-driven interrupt mapping (raw SVD name -> canonical) instead of
# algorithmic prefix-stripping.  SAMV71 interrupt names don't follow the
# instance-prefix pattern (e.g. GMAC's queue interrupts are GMAC_Q1..Q5,
# and TC0–TC11 spread across four TC instances need a mod-3 mapping to
# INT0/INT1/INT2 within each instance).
use_config_interrupt_map = True


def add_cli_args(parser):
    """Add Microchip-specific CLI arguments."""
    parser.add_argument('svd_source', type=Path,
                        help='Path to directory containing Microchip SVD files')


def validate_args(args):
    """Validate Microchip-specific arguments."""
    if not args.svd_source.exists():
        print(f"Error: {args.svd_source} not found")
        sys.exit(1)


def config_path(args):
    """Return path to the Microchip consolidated YAML config."""
    return Path(__file__).parent.parent.parent / 'svd' / 'Microchip' / 'Microchip.yaml'


def open_svd(args, chip_name):
    """Locate and parse an SVD file from the Microchip directory.

    Naming convention: chip_name as-is (e.g. ATSAMV71Q21B -> ATSAMV71Q21B.svd).

    Returns (xml_root, extra_metadata_dict) or None if not found.
    """
    svd_dir = Path(args.svd_source)
    svd_path = svd_dir / f"{chip_name}.svd"
    if not svd_path.exists():
        return None
    root = svd.parse(str(svd_path))
    return root, {}


def format_source(name, version, svd_tag=''):
    """Format source attribution string."""
    if version:
        return f"{name} SVD Rev {version}"
    return f"{name} SVD"


def errata_path():
    """Return the vendor's SVD errata doc path (for audit reports)."""
    return 'svd/Microchip/SVD_ERRATA.md'


def get_interrupt_offset(cpu_info):
    """Return interrupt vector offset for Cortex-M (16 system exceptions)."""
    return 16
