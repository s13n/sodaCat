# Unified header generator — dispatches to the appropriate generator based on model content.
#
# Usage: python3 generate_header.py <model.yaml> <model_name> <suffix>
#
# Model type detection:
#   - 'registers' key  → peripheral block header (generate_peripheral_header)
#   - 'cpu' key        → chip/SoC integration header (generate_chip_header).
#                        Subfamily YAMLs now also carry an `instances:` map
#                        (the subfamily-common subset) but no `cpu:` — only
#                        chips have one, so it's the reliable discriminator.
#   - 'signals' key    → clock tree header (generate_clocktree_header)
#   - 'clocks' key     → subfamily model; route to clocktree generator,
#                        which descends into the `clocks:` section.
#   - 'inherits:'/'instances:'/'models:' without 'cpu:' →
#                        subfamily passthrough; no header emitted at this
#                        tier (the CMake macro walks `inherits:` to find a
#                        parent that carries the topology, and the chip
#                        header generator walks the chain to assemble the
#                        merged instance view).
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

# Optional `--endian <native|big|little>` flag (default native).  Strip it
# from argv up front so the downstream positional-argument indexing — and the
# argv handed to the chip/clocktree generators — is unaffected.  Only the
# peripheral path consumes it; chip MMIO and clock trees are always native.
endian = 'native'
if '--endian' in sys.argv:
    _i = sys.argv.index('--endian')
    endian = sys.argv[_i + 1]
    if endian not in ('native', 'big', 'little'):
        print(f"--endian must be native/big/little, got {endian!r}", file=sys.stderr)
        sys.exit(1)
    del sys.argv[_i:_i + 2]

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
    fmt = PerFormatter(endian=endian)
    prefix = prefixTemplate.substitute(ns=ns)
    postfix = postfixTemplate.substitute(ns=ns)
    txt = fmt.formatPeripheral(model, prefix, postfix)
    print(txt, file=open(filename, mode='w'))
    cppm = Path(filename).with_suffix('.cppm')
    print(generate_module(modid, Path(filename).name), file=open(cppm, mode='w'))

elif 'cpu' in model:
    from generate_chip_header import generate_header
    generate_header(sys.argv[1], sys.argv[2], sys.argv[3], modid)

elif 'signals' in model or 'clocks' in model:
    # Both shapes share the clocktree generator; the generator detects
    # `clocks:` and descends into it internally.
    from generate_clocktree_header import generate_header
    generate_header(sys.argv[1], sys.argv[2]+sys.argv[3], modid)

elif ('inherits' in model or 'instances' in model or 'models' in model):
    # Subfamily passthrough: this file only contributes an `inherits:`
    # link and/or a subfamily-common `instances:`/`models:` map; no real
    # C++ content is emitted at this level (the CMake macro will already
    # have followed `inherits:` to a parent that carries the topology).
    # Still write trivial placeholder .hpp/.cppm files so the CMake
    # custom-command output contract is satisfied — without them ninja
    # complains about missing build outputs.
    with open(filename, 'w') as f:
        f.write(f"// generated header file, please don't edit.\n"
                f"// subfamily passthrough — no C++ content at this tier.\n"
                f"#pragma once\n")
    cppm = Path(filename).with_suffix('.cppm')
    with open(cppm, 'w') as f:
        f.write(f"// generated module file, please don't edit.\n"
                f"// subfamily passthrough — no C++ content at this tier.\n"
                f"module;\n"
                f"export module {modid};\n")

else:
    keys = ', '.join(model.keys())
    print(f"Unknown model type in {sys.argv[1]} (keys: {keys})", file=sys.stderr)
    sys.exit(1)
