"""STM32 vendor extension for the unified model generator.

Provides SVD access via zip archives and STM32-style source attribution.
Requires tools/ on sys.path (set up by generate_models.py).
"""

import os
import sys
import tempfile
from pathlib import Path

import svd


def add_cli_args(parser):
    """Add STM32-specific CLI arguments."""
    parser.add_argument('svd_source', type=Path,
                        help='Path to SVD zip archive')


def validate_args(args):
    """Validate STM32-specific arguments."""
    if not args.svd_source.exists():
        print(f"Error: {args.svd_source} not found")
        sys.exit(1)


def config_path(args):
    """Return path to the STM32 consolidated YAML config."""
    return args.svd_source.parent / 'STM32.yaml'


def open_svd(args, chip_name):
    """Extract and parse an SVD file from the zip archive.

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
    """Format source attribution string (STM32 style: 'ChipName SVD vX.Y')."""
    if version:
        return f"{name} SVD v{version}"
    return f"{name} SVD"


def errata_path():
    """Return the vendor's SVD errata doc path (for audit reports)."""
    return 'svd/ST/SVD_ERRATA.md'
