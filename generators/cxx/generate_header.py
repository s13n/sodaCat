# Unified header generator — dispatches to the appropriate generator based on model content.
#
# Usage: python3 generate_header.py <model.yaml> <model_name> <suffix>
#
# Model type detection:
#   - 'registers' key  → peripheral block header (generate_peripheral_header)
#   - 'instances' key  → chip/SoC integration header (generate_chip_header)
#   - 'signals' key    → clock tree header (generate_clocktree_header)
#   - 'clocks' key     → subfamily model; route to clocktree generator,
#                        which descends into the `clocks:` section.
#
# The C++ namespace for the generated header is read from the model YAML's
# `namespace:` key, falling back to the lowercased innermost containing
# directory name (see _namespace.py).
#
# Each invocation produces both a .hpp header and a .cppm module wrapper.

from ruamel.yaml import YAML
from pathlib import Path
import re
import sys

from _namespace import resolve as _resolve_ns

yaml = YAML(typ='safe')
model = yaml.load(Path(sys.argv[1]))

if not model:
    print(f"No model loaded: {sys.argv[1]}", file=sys.stderr)
    sys.exit(1)

filename = sys.argv[2]+sys.argv[3]
ns = _resolve_ns(sys.argv[1])
# Module names must be valid C++ identifiers; stems like "ESP32-P4" need
# the hyphen replaced.  Prefix with the namespace so that module names are
# globally unique across vendors (e.g. esp32p4.GPIO vs stm32h7.GPIO) — C++20
# module names are a flat global space, and dotted names are legal.
_stem = Path(filename).stem.replace('-', '_')
modid = f'{ns}.{_stem}' if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', ns) else _stem

if 'registers' in model:
    from generate_peripheral_header import PerFormatter, prefixTemplate, postfixTemplate, generate_module
    fmt = PerFormatter()
    prefix = prefixTemplate.substitute(ns=ns)
    postfix = postfixTemplate.substitute(ns=ns)
    txt = fmt.formatPeripheral(model, prefix, postfix)
    print(txt, file=open(filename, mode='w'))
    cppm = Path(filename).with_suffix('.cppm')
    print(generate_module(modid, Path(filename).name), file=open(cppm, mode='w'))

elif 'instances' in model:
    from generate_chip_header import generate_header
    generate_header(sys.argv[1], sys.argv[2], sys.argv[3], modid)

elif 'signals' in model or 'clocks' in model:
    # Both shapes share the clocktree generator; the generator detects
    # `clocks:` and descends into it internally.
    from generate_clocktree_header import generate_header
    generate_header(sys.argv[1], sys.argv[2]+sys.argv[3], modid)

else:
    keys = ', '.join(model.keys())
    print(f"Unknown model type in {sys.argv[1]} (keys: {keys})", file=sys.stderr)
    sys.exit(1)
