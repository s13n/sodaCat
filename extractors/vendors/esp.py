"""Espressif ESP32 vendor extension for the unified model generator.

Provides SVD access via loose files in a directory and ESP-style source
attribution.  Requires tools/ on sys.path (set up by generate_models.py).
"""

import sys
from pathlib import Path

import svd

# Use config-driven interrupt mapping (raw SVD name -> canonical) instead of
# algorithmic prefix-stripping.  ESP32 interrupt names are idiosyncratic
# (e.g. TG0_T0 for TIMG0 timer 0, PWM0 for MCPWM0).
use_config_interrupt_map = True


def add_cli_args(parser):
    """Add ESP-specific CLI arguments."""
    parser.add_argument('svd_source', type=Path,
                        help='Path to directory containing ESP SVD files')


def validate_args(args):
    """Validate ESP-specific arguments."""
    if not args.svd_source.exists():
        print(f"Error: {args.svd_source} not found")
        sys.exit(1)


def config_path(args):
    """Return path to the ESP32 consolidated YAML config."""
    return Path(__file__).parent.parent.parent / 'svd' / 'ESP' / 'ESP32.yaml'


def open_svd(args, chip_name):
    """Locate and parse an SVD file from the ESP directory.

    ESP naming convention: chip_name 'ESP32-P4' -> 'esp32p4.svd'
    (lowercase, hyphens removed).

    Returns (xml_root, extra_metadata_dict) or None if not found.
    """
    svd_dir = Path(args.svd_source)
    # Normalize: ESP32-P4 -> esp32p4
    normalized = chip_name.lower().replace('-', '')
    svd_path = svd_dir / f"{normalized}.svd"

    if not svd_path.exists():
        # Fallback: try with hyphen preserved
        svd_path = svd_dir / f"{chip_name.lower()}.svd"
        if not svd_path.exists():
            return None

    root = svd.parse(str(svd_path))
    return root, {}


def format_source(name, version, svd_tag=''):
    """Format source attribution string (ESP style)."""
    if version:
        return f"{name} SVD v{version}"
    return f"{name} SVD"


def errata_path():
    """Return the vendor's SVD errata doc path (for audit reports)."""
    return 'svd/ESP/SVD_ERRATA.md'


def get_interrupt_offset(cpu_info):
    """Return interrupt vector offset for RISC-V (no system exception table)."""
    return 0
