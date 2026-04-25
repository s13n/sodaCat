"""NXP MCX vendor extension for the unified model generator.

Provides SVD access via filesystem directory and NXP-style source attribution.
Requires tools/ on sys.path (set up by generate_models.py).
"""

import sys
from pathlib import Path

import svd

# Use config-driven interrupt mapping (raw SVD name → canonical) instead of
# algorithmic prefix-stripping.  MCX interrupt names don't follow the
# instance-prefix pattern that STM32 uses.
use_config_interrupt_map = True

# Re-derive enum value names from descriptions during extraction.  NXP SVDs
# auto-generate enum names by uppercasing the description and truncating at
# 20 characters, producing ugly names and within-field collisions.
simplify_enums = True


def add_cli_args(parser):
    """Add MCX-specific CLI arguments."""
    parser.add_argument('svd_source', type=Path,
                        help='Path to NXP SVD repository checkout')


def validate_args(args):
    """Validate MCX-specific arguments."""
    if not args.svd_source.exists():
        print(f"Error: {args.svd_source} not found")
        sys.exit(1)


def config_path(args):
    """Return path to the MCX consolidated YAML config."""
    return Path(__file__).parent.parent.parent / 'svd' / 'NXP' / 'MCX.yaml'


def open_svd(args, chip_name):
    """Locate and parse an SVD file from the NXP repository.

    NXP repo layout: <svd_dir>/<chip_name>/<chip_name>.xml
    Falls back to .svd extension, then tries dual-core suffixes
    (_cm33_core0, _cm33_core1) for multi-core MCX chips.

    Returns (xml_root, extra_metadata_dict) or None if not found.
    """
    svd_dir = Path(args.svd_source)
    chip_dir = svd_dir / chip_name

    svd_path = None
    for ext in ('.xml', '.svd'):
        candidate = chip_dir / f"{chip_name}{ext}"
        if candidate.exists():
            svd_path = candidate
            break
    if svd_path is None:
        # Dual-core chips: try core-specific suffixes
        for suffix in ('_cm33_core0', '_cm33_core1', '_cm33'):
            for ext in ('.xml', '.svd'):
                candidate = chip_dir / f"{chip_name}{suffix}{ext}"
                if candidate.exists():
                    svd_path = candidate
                    break
            if svd_path is not None:
                break

    if svd_path is None:
        return None

    relpath = svd_path.relative_to(svd_dir).as_posix()
    root = svd.parse(str(svd_path))
    return root, {'svd_path': relpath}


def format_source(name, version, svd_tag=''):
    """Format source attribution string (NXP style: 'path vX.Y (tag)')."""
    parts = [name or 'unknown']
    if version:
        parts.append(f"v{version}")
    if svd_tag:
        parts.append(f"({svd_tag})")
    return ' '.join(parts)


def errata_path():
    """Return the vendor's SVD errata doc path (for audit reports)."""
    return 'svd/NXP/SVD_ERRATA.md'


def get_interrupt_offset(cpu_info):
    """Return interrupt vector offset for Cortex-M (16 system exceptions)."""
    return 16
