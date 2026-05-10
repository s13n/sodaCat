"""Namespace resolver for model YAML files.

Reads the optional `namespace:` key.  If absent, falls back to the
lowercased innermost containing directory name (sanitized to a valid
C++ identifier).  This keeps namespaces self-describing for generated
models while allowing hand-maintained models to omit the key as long
as their directory name is acceptable as the namespace.
"""
import re
from pathlib import Path
from ruamel.yaml import YAML

_yaml = YAML(typ='safe')


def resolve(model_path):
    """Return the C++ namespace for the model at `model_path`."""
    p = Path(model_path)
    try:
        d = _yaml.load(p)
    except Exception:
        d = None
    if d and isinstance(d, dict) and d.get('namespace'):
        return d['namespace']
    return re.sub(r'[^a-z0-9_]', '_', p.parent.name.lower())
