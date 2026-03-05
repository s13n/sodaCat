# Unified header generator — dispatches to the appropriate generator based on model content.
#
# Usage: python3 generate_header.py <model.yaml> <namespace> <model_name> <suffix>
#
# Model type detection:
#   - 'registers' key  → peripheral block header (generate_peripheral_header)
#   - 'instances' key  → chip/SoC integration header (generate_chip_header)
#   - 'signals' key    → clock tree header (generate_clocktree_header)

from ruamel.yaml import YAML
from pathlib import Path
import sys

yaml = YAML(typ='safe')
model = yaml.load(Path(sys.argv[1]))

if not model:
    print(f"No model loaded: {sys.argv[1]}", file=sys.stderr)
    sys.exit(1)

if 'registers' in model:
    from generate_peripheral_header import PerFormatter, prefixTemplate, postfixTemplate
    fmt = PerFormatter()
    prefix = prefixTemplate.substitute(ns=sys.argv[2], mod=sys.argv[3])
    postfix = postfixTemplate.substitute(ns=sys.argv[2])
    txt = fmt.formatPeripheral(model, prefix, postfix)
    print(txt, file=open(sys.argv[3]+sys.argv[4], mode='w'))

elif 'instances' in model:
    from generate_chip_header import generate_header
    generate_header(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])

elif 'signals' in model:
    from generate_clocktree_header import generate_header
    generate_header(sys.argv[1], sys.argv[2], sys.argv[3]+sys.argv[4])

else:
    keys = ', '.join(model.keys())
    print(f"Unknown model type in {sys.argv[1]} (keys: {keys})", file=sys.stderr)
    sys.exit(1)
