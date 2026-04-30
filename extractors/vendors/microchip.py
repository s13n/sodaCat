"""Microchip ATSAM vendor extension for the unified model generator.

Provides SVD access via Microchip CMSIS Device Family Pack archives
(`.atpack` files renamed to `.zip`) stored in svd/Microchip/.  Requires
tools/ on sys.path (set up by generate_models.py).
"""

import os
import sys
import tempfile
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
                        help='Path to a Microchip DFP zip archive (.atpack renamed to .zip)')


def validate_args(args):
    """Validate Microchip-specific arguments."""
    if not args.svd_source.exists():
        print(f"Error: {args.svd_source} not found")
        sys.exit(1)


def config_path(args):
    """Return path to the Microchip consolidated YAML config."""
    return args.svd_source.parent / 'Microchip.yaml'


def open_svd(args, chip_name):
    """Extract and parse an SVD file from the DFP zip archive.

    The Microchip pack layout nests SVDs under various subdirectories
    (e.g. samv71b/svd/, CA80/svd/, svd/), but extractFromZip matches by
    suffix so the chip name alone is sufficient.

    Returns (xml_root, extra_metadata_dict) or None if not found.
    """
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
