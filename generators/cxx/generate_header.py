# Unified header generator — dispatches to the appropriate generator based on model content.
#
# Usage: python3 generate_header.py <model.yaml> <namespace> <model_name> <suffix>
#
# Model type detection:
#   - 'registers' key  → peripheral block header (generate_peripheral_header)
#   - 'instances' key  → chip/SoC integration header (generate_chip_header)
#   - 'signals' key    → clock tree header (generate_clocktree_header)
#
# Each invocation produces both a .hpp header and a .cppm module wrapper.

from ruamel.yaml import YAML
from pathlib import Path
import re
import sys

yaml = YAML(typ='safe')
model = yaml.load(Path(sys.argv[1]))

if not model:
    print(f"No model loaded: {sys.argv[1]}", file=sys.stderr)
    sys.exit(1)

filename = sys.argv[3]+sys.argv[4]
# Module names must be valid C++ identifiers; stems like "ESP32-P4" need
# the hyphen replaced.  Prefix with the namespace so that module names are
# globally unique across vendors (e.g. esp32p4.GPIO vs stm32h7.GPIO) — C++20
# module names are a flat global space, and dotted names are legal.
_stem = Path(filename).stem.replace('-', '_')
_ns_arg = sys.argv[2]
# When the namespace argument is a path to a YAML map (e.g. for a chip whose
# peripherals span multiple namespaces), pull the default ('') namespace
# from the map for the module-name prefix.
_nsfile = Path(_ns_arg)
if _nsfile.exists():
    _ns_map = yaml.load(_nsfile)
    _ns = _ns_map.get('', '') if isinstance(_ns_map, dict) else ''
else:
    _ns = _ns_arg
modid = f'{_ns}.{_stem}' if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', _ns) else _stem

if 'registers' in model:
    from generate_peripheral_header import PerFormatter, prefixTemplate, postfixTemplate, generate_module
    fmt = PerFormatter()
    prefix = prefixTemplate.substitute(ns=sys.argv[2])
    postfix = postfixTemplate.substitute(ns=sys.argv[2])
    txt = fmt.formatPeripheral(model, prefix, postfix)
    print(txt, file=open(filename, mode='w'))
    cppm = Path(filename).with_suffix('.cppm')
    print(generate_module(modid, Path(filename).name), file=open(cppm, mode='w'))

elif 'instances' in model:
    from generate_chip_header import generate_header
    generate_header(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], modid)

elif 'signals' in model:
    from generate_clocktree_header import generate_header
    generate_header(sys.argv[1], sys.argv[2], sys.argv[3]+sys.argv[4], modid)

else:
    keys = ', '.join(model.keys())
    print(f"Unknown model type in {sys.argv[1]} (keys: {keys})", file=sys.stderr)
    sys.exit(1)
