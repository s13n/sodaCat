#!/usr/bin/env python3
"""Audit a clock-tree spec against its controller block model.

Three tiers of checks:

  Tier A — high-confidence width/count mismatches (errors):
    * mux: number of `inputs:` entries fits in the selector field's bitWidth.
    * mux: if the field has enumeratedValues, the counts agree.
    * divider: if the factor field has enumeratedValues AND the divider has
      a `values:` list, the lengths agree.

  Tier B — coverage audit (informational): fields whose name suggests they
    are clock-tree-relevant but aren't cited anywhere in the spec.
    * `*EN`     — gate-enable candidates
    * `*SEL` / `*SRC` / `*MUX` — selector candidates
    * `*DIV` / `*PRE` / `*PSC` — divider candidates

  Tier C — fuzzy enum-name hints (warnings): when a mux's selector field has
    enum values whose names share no token with the mux's `inputs:` list,
    flag it.  Helps catch misalignment between SVD-derived names and the
    hand-authored canonical signal names without being too noisy.

Resolves the controller block by following any consumer chip's inheritance
chain — the chip's `models:` map (merged across the chain) maps an instance
name to a block YAML.

Usage:
    python3 tools/audit_clock_block.py [--models-root models]
        --docs "models/**/<subfamily>.yaml"
"""

import argparse
import glob
import re
import sys
from pathlib import Path

import yaml


# ============================================================================
# Loading + lookup helpers
# ============================================================================

def _safe_load(path):
    try:
        return yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    except yaml.YAMLError:
        return None


def _clock_content(data):
    """Return the clock-tree content dict, or None if `data` isn't a spec."""
    if not isinstance(data, dict):
        return None
    if 'clocks' in data and isinstance(data['clocks'], dict):
        return data['clocks']
    if 'signals' in data:
        return data
    return None


def _walk_chain(path, models_root):
    """Yield (node_data, node_path) from `path` upward via `inherits:`."""
    cur = path
    seen = set()
    while cur and str(cur) not in seen:
        seen.add(str(cur))
        data = _safe_load(cur)
        if data is None:
            break
        yield data, cur
        parent = data.get('inherits') if isinstance(data, dict) else None
        if not parent:
            break
        cand = models_root / f'{parent}.yaml'
        cur = cand if cand.exists() else None


def _find_consumer(spec_path, models_root):
    """Find any chip YAML that reaches this spec via inherits/clocktree chain.

    Walks every chip's chain (instances: + cpu: discriminator); returns the
    first match.  Used to resolve instance->block when the spec is a shared
    spec with no instances/models of its own.
    """
    target = spec_path.relative_to(models_root).with_suffix('').as_posix()
    for f in models_root.rglob('*.yaml'):
        data = _safe_load(f)
        if not isinstance(data, dict) or 'cpu' not in data:
            continue
        for node, _ in _walk_chain(f, models_root):
            ref = node.get('clocktree') or node.get('inherits')
            if ref == target:
                return f
    return None


def _merged_instances_and_models(start_path, models_root):
    """Walk inherits from start_path, merging instances + models maps.
    Chip-level entries override ancestor entries by key.
    """
    chain = list(_walk_chain(start_path, models_root))
    instances, models = {}, {}
    for node, _ in reversed(chain):  # root-first; near-end wins
        for k, v in (node.get('instances') or {}).items():
            instances[k] = v
        for k, v in (node.get('models') or {}).items():
            models[k] = v
    return instances, models


def _resolve_controller_block(spec_path, content, models_root):
    """Return (block_path, block_data) for the controller instance the spec
    cites, or (None, None) if unresolvable.
    """
    default_inst = content.get('instance') or ''
    if not default_inst:
        return None, None

    # Try the spec itself first (Shape A subfamily YAML with local instances/models).
    spec_data = _safe_load(spec_path) or {}
    insts = spec_data.get('instances') or {}
    models = spec_data.get('models') or {}

    if default_inst not in insts:
        # Need a consumer chip's view to resolve.
        consumer = _find_consumer(spec_path, models_root)
        if consumer is None:
            return None, None
        insts, models = _merged_instances_and_models(consumer, models_root)

    inst = insts.get(default_inst)
    if not inst:
        return None, None
    model_name = inst.get('model')
    if not model_name:
        return None, None
    rel = models.get(model_name, model_name)
    block_path = models_root / f'{rel}.yaml'
    if not block_path.exists():
        return None, None
    return block_path, _safe_load(block_path)


# ============================================================================
# Field walking + ref collection
# ============================================================================

_ARRAY_RE = re.compile(r'\[[^\]]*\]')


def _strip_array(name):
    """Strip `[N]` or `[%s]` subscripts so `C[0].AHB3ENR` matches `C.AHB3ENR`."""
    return _ARRAY_RE.sub('', name or '')


def _walk_fields(entries, prefix=''):
    """Yield (qualified_reg_name, field_dict) for every leaf field."""
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        name = entry.get('name') or entry.get('displayName')
        if not name:
            continue
        base = _strip_array(name)
        qualified = f'{prefix}{base}' if prefix else base
        nested = entry.get('registers')
        if nested is not None:
            yield from _walk_fields(nested, prefix=f'{qualified}.')
            continue
        for fld in entry.get('fields') or []:
            if isinstance(fld, dict) and fld.get('name'):
                yield qualified, fld


def _collect_refs(node, default_instance, out, path=''):
    """Collect every (instance, reg, field, path) referenced from a content tree."""
    if isinstance(node, dict):
        if 'reg' in node:
            out.append({
                'instance': node.get('instance', default_instance),
                'reg': node['reg'],
                'field': node.get('field'),
                'path': path,
            })
        for k, v in node.items():
            _collect_refs(v, default_instance, out, f'{path}.{k}' if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _collect_refs(v, default_instance, out, f'{path}[{i}]')


# ============================================================================
# Per-tier checks
# ============================================================================

def tier_a_checks(content, block_fields):
    """Return [(check, message)] for high-confidence width/count mismatches.

    block_fields: {qualified_reg_name: {field_name: field_dict}}
    """
    errors = []

    def lookup(reg, field):
        rk = _strip_array(reg)
        return block_fields.get(rk, {}).get(field) if field else None

    # Muxes: inputs-list length vs selector field bitWidth + enum count.
    for mux in content.get('muxes') or []:
        ctrl = mux.get('control') or {}
        if 'reg' not in ctrl:
            continue
        fld = lookup(ctrl['reg'], ctrl.get('field'))
        if fld is None:
            continue
        inputs = mux.get('inputs') or []
        # Trim trailing nulls (reserved encodings) for the "fits in field" test.
        trimmed = list(inputs)
        while trimmed and trimmed[-1] is None:
            trimmed.pop()
        max_slots = 1 << fld.get('bitWidth', 0)
        if len(trimmed) > max_slots:
            errors.append((
                'mux-overflow',
                f"mux '{mux['name']}' has {len(trimmed)} active inputs but "
                f"selector field {ctrl['reg']}.{ctrl['field']} is "
                f"{fld.get('bitWidth')}-bit (max {max_slots} encodings)"
            ))
        # Enum-count check fires only when the SVD enumerates the full
        # selector — many vendors list only "active" encodings (e.g. STM32
        # HPRE has 16 logical positions but only 8 enumeratedValues, all
        # in the high half, with the low half implicitly "divide by 1").
        # When the enum is sparse, a length mismatch with the inputs list
        # is normal and not a bug.
        enum_count = len(fld.get('enumeratedValues') or [])
        if enum_count and enum_count == max_slots:
            active = [v for v in inputs if v not in (None, '')]
            if len(active) > enum_count:
                errors.append((
                    'mux-enum-count',
                    f"mux '{mux['name']}': {len(active)} active inputs exceed "
                    f"the {enum_count} enumeratedValues on "
                    f"{ctrl['reg']}.{ctrl['field']}"
                ))

    # Dividers: explicit values: list vs enum count.
    for div in content.get('dividers') or []:
        ctrl = div.get('factor') or {}
        if 'reg' not in ctrl:
            continue
        fld = lookup(ctrl['reg'], ctrl.get('field'))
        if fld is None:
            continue
        # Same sparseness caveat: only check length match when the field's
        # enum is complete (covers every encoding the bit-width allows).
        if 'values' in ctrl and 'enumeratedValues' in fld:
            ev_count = len(fld['enumeratedValues'])
            bit_width = fld.get('bitWidth', 0)
            max_slots = 1 << bit_width
            if ev_count == max_slots and len(ctrl['values']) != ev_count:
                errors.append((
                    'divider-values',
                    f"divider '{div['name']}': values: list has "
                    f"{len(ctrl['values'])} entries but "
                    f"{ctrl['reg']}.{ctrl['field']} has {ev_count} "
                    f"enumeratedValues (field width = {bit_width} bits)"
                ))

    return errors


_GATE_PATTERNS = (re.compile(r'EN$'),)
_MUX_PATTERNS = (re.compile(r'SEL$'), re.compile(r'SRC$'), re.compile(r'MUX$'))
_DIV_PATTERNS = (re.compile(r'DIV$'), re.compile(r'PRE$'), re.compile(r'PSC$'))


def _all_field_paths(block_fields):
    """Iterate (reg, field_name, field_dict) over every (qualified) field."""
    for reg, fdict in block_fields.items():
        for fname, fdata in fdict.items():
            yield reg, fname, fdata


def tier_b_coverage(content, block_fields, cited_set):
    """Return [(category, reg.field, description)] for uncited candidates.

    cited_set: {(stripped_reg, field)} already referenced in the spec.
    """
    out = {'gates': [], 'muxes': [], 'dividers': []}
    for reg, fname, fdata in _all_field_paths(block_fields):
        key = (reg, fname)
        if key in cited_set:
            continue
        desc = (fdata.get('description') or '').strip().replace('\n', ' ')
        if any(p.search(fname) for p in _GATE_PATTERNS):
            out['gates'].append((reg, fname, desc))
        elif any(p.search(fname) for p in _MUX_PATTERNS):
            out['muxes'].append((reg, fname, desc))
        elif any(p.search(fname) for p in _DIV_PATTERNS):
            out['dividers'].append((reg, fname, desc))
    return out


def _tokens(s):
    """Lowercase tokens, split at non-alphanumeric AND letter/digit boundaries.

    `gclkgen0` -> {'gclk', 'gen', '0'} so it overlaps with `GCLK0` -> {'gclk', '0'}.
    """
    parts = re.findall(r'[a-zA-Z]+|\d+', (s or '').lower())
    return set(parts)


def tier_c_hints(content, block_fields):
    """Return [(check, message)] for fuzzy enum-name vs inputs-list hints.

    Heuristics that reduce noise:
      * Skip muxes whose enum is sparse (count < bitWidth's capacity) —
        the SVD listed only some encodings.
      * Within a mux, only flag inputs that diverge when at least one
        other input has a successful match (i.e. the author is broadly
        using SVD names; an isolated divergence is interesting).  If
        every input diverges, the author chose a different convention;
        per-input nags would be pure noise.
    """
    hints = []

    def _matches(inp, enum_tokens):
        toks = _tokens(inp)
        if toks & enum_tokens:
            return True
        return any(
            len(e) >= 3 and len(t) >= 3 and (e in t or t in e)
            for e in enum_tokens for t in toks)

    for mux in content.get('muxes') or []:
        ctrl = mux.get('control') or {}
        if 'reg' not in ctrl:
            continue
        fld = block_fields.get(_strip_array(ctrl['reg']), {}).get(ctrl.get('field'))
        if fld is None or not fld.get('enumeratedValues'):
            continue
        # Sparse-enum guard.
        bit_width = fld.get('bitWidth', 0)
        if len(fld['enumeratedValues']) < (1 << bit_width):
            continue
        # Filter trivial enum names like PSEL_0..PSEL_3.
        if not any(
                re.search(r'[A-Za-z]{3,}', ev.get('name') or '')
                and not re.fullmatch(r'[A-Z]+_\d+', ev.get('name') or '')
                for ev in fld['enumeratedValues']):
            continue

        enum_tokens = set()
        for ev in fld['enumeratedValues']:
            enum_tokens |= _tokens(ev.get('name'))
            enum_tokens |= _tokens(ev.get('description'))

        # Classify each input.
        divergent = []
        any_matched = False
        for i, inp in enumerate(mux.get('inputs') or []):
            if inp in (None, ''):
                continue
            if _matches(inp, enum_tokens):
                any_matched = True
            else:
                divergent.append((i, inp))
        # Only emit hints if the author broadly aligns with SVD names and
        # only a few inputs slipped through differently.
        if any_matched:
            for i, inp in divergent:
                hints.append((
                    'mux-input-hint',
                    f"mux '{mux['name']}' input[{i}]={inp!r} shares no "
                    f"tokens with {ctrl['reg']}.{ctrl['field']} enums "
                    f"({', '.join(repr(ev.get('name')) for ev in fld['enumeratedValues'][:4])}...)"
                ))
    return hints


# ============================================================================
# Driver
# ============================================================================

def audit_one(spec_path, models_root):
    data = _safe_load(spec_path)
    content = _clock_content(data)
    if content is None:
        return None  # not a clock spec

    block_path, block_data = _resolve_controller_block(spec_path, content, models_root)
    if block_data is None:
        return [('no-block', "couldn't resolve the controller block "
                 "(no consumer chip references this spec?)")]

    # Build {qualified_reg: {field_name: field_dict}} index for the block.
    block_fields = {}
    for reg, fld in _walk_fields(block_data.get('registers') or []):
        block_fields.setdefault(reg, {})[fld['name']] = fld

    # Collect cited (reg, field) for coverage check.
    refs = []
    _collect_refs(content, content.get('instance', ''), refs)
    cited_set = {(_strip_array(r['reg']), r['field'])
                 for r in refs if r.get('field')}

    findings = []
    for check, msg in tier_a_checks(content, block_fields):
        findings.append(('A', check, msg))
    coverage = tier_b_coverage(content, block_fields, cited_set)
    for cat, items in coverage.items():
        for reg, fname, desc in items:
            cat_short = {'gates': 'gate', 'muxes': 'mux', 'dividers': 'divider'}[cat]
            findings.append(('B', f'uncited-{cat_short}', f"{reg}.{fname}  {desc[:80]}"))
    for check, msg in tier_c_hints(content, block_fields):
        findings.append(('C', check, msg))
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--models-root', default='models',
                    help="Root of the models tree (default: models)")
    ap.add_argument('-d', '--docs', nargs='+', required=True,
                    help='Clock-spec YAML files or glob patterns')
    args = ap.parse_args()

    models_root = Path(args.models_root).resolve()

    files = []
    for pattern in args.docs:
        files.extend(glob.glob(pattern, recursive=True))
    if not files:
        print('No files matched', file=sys.stderr)
        return 2

    had_errors = False
    for f in sorted(set(files)):
        if not f.endswith(('.yaml', '.yml')):
            continue
        path = Path(f).resolve()
        findings = audit_one(path, models_root)
        if findings is None:
            continue
        rel = path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path
        if not findings:
            print(f"✅ {rel}")
            continue
        # Group by tier
        tiers = {'A': [], 'B': [], 'C': []}
        for tier, check, msg in findings:
            tiers[tier].append((check, msg))
        marker = '❌' if tiers['A'] else '🔍'
        print(f"{marker} {rel}:")
        for tier_label, label_long in (('A', 'error  '), ('B', 'audit  '), ('C', 'hint   ')):
            for check, msg in tiers[tier_label]:
                print(f"   {label_long}│ {check:18s} {msg}")
        if tiers['A']:
            had_errors = True

    return 1 if had_errors else 0


if __name__ == '__main__':
    sys.exit(main())
