#!/usr/bin/env python3
"""Compare peripheral YAMLs and compute structural similarity.

Writes `tools/compare_report.json` and `tools/compare_report.csv`.
"""
import os
import json
import csv
import math
import argparse
from pathlib import Path

try:
    import yaml
except Exception:
    print("PyYAML not installed. Please run: pip install pyyaml")
    raise

ROOT = Path('.')
# Write reports to the current working directory by default
OUT_JSON = Path('compare_report.json')
OUT_CSV = Path('compare_report.csv')


def find_yaml_files(root):
    for p in root.rglob('*.yaml'):
        yield p


def normalize_name(s):
    return s.strip().upper()


def register_signature(reg):
    # produce simple signature for register: name@offset (offset may be missing)
    name = normalize_name(reg.get('name', ''))
    offset = reg.get('addressOffset')
    return f"{name}@{offset}" if offset is not None else name


def field_signature(field):
    # field: NAME:bitWidth@bitOffset
    name = normalize_name(field.get('name', ''))
    bw = field.get('bitWidth')
    bo = field.get('bitOffset')
    return f"{name}:{bw}@{bo}"


def peripheral_fingerprint(path):
    data = yaml.safe_load(path.read_text())
    meta = {}
    meta['path'] = str(path)
    meta['name'] = data.get('name')
    # include raw data for more detailed pair analysis
    meta['raw'] = data
    regs = data.get('registers') or []
    reg_names = set()
    reg_sigs = set()
    field_sigs = set()
    for r in regs:
        # handle dim/register arrays: if 'dim' then we treat single entry
        if 'dim' in r:
            # replicate one prototype
            reg = r.copy()
            sig = register_signature(reg)
            reg_names.add(normalize_name(reg.get('name','')))
            reg_sigs.add(sig)
            for f in reg.get('registers', []) + reg.get('fields', []):
                # nested registers in dim have 'registers'
                if isinstance(f, dict) and 'fields' in f:
                    for ff in f.get('fields', []):
                        field_sigs.add(field_signature(ff))
                else:
                    # field entries
                    if isinstance(f, dict) and 'name' in f:
                        field_sigs.add(field_signature(f))
        else:
            reg = r
            reg_names.add(normalize_name(reg.get('name','')))
            reg_sigs.add(register_signature(reg))
            for f in reg.get('fields', []) or []:
                field_sigs.add(field_signature(f))
            # also consider nested registers (some files use registers: inside dim)
            for sub in reg.get('registers', []) or []:
                reg_names.add(normalize_name(sub.get('name','')))
                reg_sigs.add(register_signature(sub))
                for f in sub.get('fields', []) or []:
                    field_sigs.add(field_signature(f))

    meta['reg_names'] = sorted(reg_names)
    meta['reg_sigs'] = sorted(reg_sigs)
    meta['field_sigs'] = sorted(field_sigs)
    # expose discovered parameters (declared in YAML) and dims
    meta['parameters'] = data.get('parameters', [])
    meta['raw_registers'] = regs
    return meta


def jaccard(a, b):
    if not a and not b:
        return 1.0
    sa = set(a)
    sb = set(b)
    inter = sa & sb
    uni = sa | sb
    return len(inter) / len(uni) if uni else 1.0


def compare(fp_a, fp_b):
    # compute measures
    reg_j = jaccard(fp_a['reg_names'], fp_b['reg_names'])
    field_j = jaccard(fp_a['field_sigs'], fp_b['field_sigs'])
    # offset-aware register signature jaccard
    regsig_j = jaccard(fp_a['reg_sigs'], fp_b['reg_sigs'])
    # weighted score
    score = 0.5 * reg_j + 0.2 * regsig_j + 0.3 * field_j
    return {
        'a': fp_a['path'],
        'b': fp_b['path'],
        # provide name fallback to filename so printed output never shows None
        'name_a': fp_a.get('name') or Path(fp_a['path']).name,
        'name_b': fp_b.get('name') or Path(fp_b['path']).name,
        'reg_jaccard': reg_j,
        'regsig_jaccard': regsig_j,
        'field_jaccard': field_j,
        'score': score,
    }


def main():
    parser = argparse.ArgumentParser(description='Compare peripheral YAMLs')
    parser.add_argument('--pair', nargs=2, help='Compare two specific files')
    parser.add_argument('--fuse', nargs=2, help='Create fused YAML template and per-device params for two files')
    parser.add_argument('--top', type=int, default=20, help='Top N matches to print')
    parser.add_argument('--min-score', type=float, default=0.0, help='Minimum score to include')
    parser.add_argument('--root', default=str(ROOT), help='Root folder to scan for peripheral YAMLs (default: current folder)')
    parser.add_argument('--fused-name', default=None, help='Optional name for fused output YAML (e.g. CRC.yaml). If omitted the script uses its default naming.')
    args = parser.parse_args()

    root = Path(args.root)
    files = list(find_yaml_files(root))
    fps = []
    for f in sorted(files):
        try:
            fps.append(peripheral_fingerprint(f))
        except Exception as e:
            print(f"Failed to parse {f}: {e}")
    pairs = []
    n = len(fps)
    for i in range(n):
        for j in range(i+1, n):
            cmp = compare(fps[i], fps[j])
            pairs.append(cmp)
    pairs.sort(key=lambda p: p['score'], reverse=True)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open('w') as fh:
        json.dump({'files': fps, 'pairs': pairs}, fh, indent=2)

    with OUT_CSV.open('w', newline='') as fh:
        writer = csv.writer(fh)
        writer.writerow(['name_a','path_a','name_b','path_b','score','reg_jaccard','regsig_jaccard','field_jaccard'])
        for p in pairs:
            writer.writerow([p['name_a'], p['a'], p['name_b'], p['b'], f"{p['score']:.3f}", f"{p['reg_jaccard']:.3f}", f"{p['regsig_jaccard']:.3f}", f"{p['field_jaccard']:.3f}"])

    # print top matches (show full paths to avoid ambiguity) unless pair mode requested
    if args.pair:
        # run detailed pair report
        a_path, b_path = args.pair
        # find matching fps
        fa = next((x for x in fps if x['path'] == a_path or x['path'].endswith(a_path)), None)
        fb = next((x for x in fps if x['path'] == b_path or x['path'].endswith(b_path)), None)
        if not fa or not fb:
            print('One or both files not found under models/NXP: ', args.pair)
            return
        pair_report(fa, fb)
        return
    if args.fuse:
        a_path, b_path = args.fuse
        fa = next((x for x in fps if x['path'] == a_path or x['path'].endswith(a_path)), None)
        fb = next((x for x in fps if x['path'] == b_path or x['path'].endswith(b_path)), None)
        if not fa or not fb:
            print('One or both files not found under root: ', args.fuse)
            return
        fuse_pair(fa, fb, out_dir=root, fused_name=args.fused_name)
        return

    print(f"\nTop {args.top} matches (min-score={args.min_score}):")
    shown = 0
    for p in pairs:
        if p['score'] < args.min_score:
            continue
        print(f"{p['a']} <-> {p['b']}: score={p['score']:.3f} (regs={p['reg_jaccard']:.3f}, reg_sigs={p['regsig_jaccard']:.3f}, fields={p['field_jaccard']:.3f})")
        shown += 1
        if shown >= args.top:
            break


def pair_report(fp_a, fp_b):
    """Print side-by-side diff and propose candidate parameters."""
    print(f"\nPair report for:\n  A: {fp_a['path']}\n  B: {fp_b['path']}")
    # common and exclusive registers
    regs_a = {r for r in fp_a['reg_names']}
    regs_b = {r for r in fp_b['reg_names']}
    common = sorted(regs_a & regs_b)
    only_a = sorted(regs_a - regs_b)
    only_b = sorted(regs_b - regs_a)
    print(f"\nCommon registers ({len(common)}): {common[:10]}{'...' if len(common)>10 else ''}")
    print(f"Only in A ({len(only_a)}): {only_a[:10]}{'...' if len(only_a)>10 else ''}")
    print(f"Only in B ({len(only_b)}): {only_b[:10]}{'...' if len(only_b)>10 else ''}")

    # analyze offsets for common regs
    def name_to_offset(fp):
        offs = {}
        for r in fp.get('raw_registers', []):
            nm = normalize_name(r.get('name',''))
            off = r.get('addressOffset')
            offs[nm] = off
            # also nested registers
            for sub in r.get('registers', []) or []:
                offs[normalize_name(sub.get('name',''))] = sub.get('addressOffset')
        return offs

    offs_a = name_to_offset(fp_a)
    offs_b = name_to_offset(fp_b)
    deltas = []
    for r in common:
        o_a = offs_a.get(r)
        o_b = offs_b.get(r)
        if o_a is not None and o_b is not None:
            deltas.append(o_b - o_a)
    if deltas:
        # if all deltas equal -> simple base offset difference
        if all(d == deltas[0] for d in deltas):
            print(f"\nAll common registers have constant offset delta = {deltas[0]}. Suggest parameter: base_offset_diff={deltas[0]}")
        else:
            # try to find common stride
            from collections import Counter
            cnt = Counter(deltas)
            most, mcount = cnt.most_common(1)[0]
            print(f"\nOffset deltas vary. Most common delta={most} (count={mcount}). Full sample: {deltas[:20]}{'...' if len(deltas)>20 else ''}")
    else:
        print('\nNo common register offsets available to analyze.')

    # detect declared parameters and propose inferred ones
    params_a = {p.get('name'): p for p in fp_a.get('parameters', [])}
    params_b = {p.get('name'): p for p in fp_b.get('parameters', [])}
    print(f"\nDeclared parameters in A: {list(params_a.keys())}")
    print(f"Declared parameters in B: {list(params_b.keys())}")

    # detect register arrays (dim)
    def detect_dims(fp):
        dims = {}
        for r in fp.get('raw_registers', []):
            if 'dim' in r:
                name = normalize_name(r.get('name',''))
                try:
                    dims[name] = int(r.get('dim'))
                except Exception:
                    dims[name] = r.get('dim')
        return dims

    dims_a = detect_dims(fp_a)
    dims_b = detect_dims(fp_b)
    print(f"\nDetected register-array dims in A: {dims_a}")
    print(f"Detected register-array dims in B: {dims_b}")

    # propose parameter if dims differ but rest matches
    proposals = []
    for k in set(list(dims_a.keys())+list(dims_b.keys())):
        if k in dims_a and k in dims_b and dims_a[k] != dims_b[k]:
            proposals.append({'param': k, 'a': dims_a[k], 'b': dims_b[k], 'suggest_name': 'num_'+k.lower()})
    if proposals:
        print('\nProposed parameterizations based on differing array dims:')
        for p in proposals:
            print(f" - {p['suggest_name']}: A={p['a']} B={p['b']}")
    else:
        print('\nNo simple dim-based parameter proposals found.')

    # Detailed per-register field diffs for common registers
    print('\nDetailed field differences for common registers:')

    def collect_fields_for_register(fp, regname):
        """Return list of fields (dict) for a given register name (case-insensitive)."""
        regs = fp.get('raw_registers', [])
        found = []
        for r in regs:
            if normalize_name(r.get('name','')) == regname:
                # direct fields
                for f in r.get('fields', []) or []:
                    found.append(f)
                # nested registers
                for sub in r.get('registers', []) or []:
                    for f in sub.get('fields', []) or []:
                        found.append(f)
            # also possible nested register with same name
            for sub in r.get('registers', []) or []:
                if normalize_name(sub.get('name','')) == regname:
                    for f in sub.get('fields', []) or []:
                        found.append(f)
        return found

    def field_key(f):
        # key by normalized name
        return normalize_name(f.get('name',''))

    for reg in common:
        fa_fields = collect_fields_for_register(fp_a, reg)
        fb_fields = collect_fields_for_register(fp_b, reg)
        ka = {field_key(f): f for f in fa_fields}
        kb = {field_key(f): f for f in fb_fields}
        names_a = set(ka.keys())
        names_b = set(kb.keys())
        common_fields = sorted(names_a & names_b)
        only_a_fields = sorted(names_a - names_b)
        only_b_fields = sorted(names_b - names_a)
        print(f"\nRegister {reg}:")
        if only_a_fields:
            print(f"  Only in A ({len(only_a_fields)}): {only_a_fields}")
        if only_b_fields:
            print(f"  Only in B ({len(only_b_fields)}): {only_b_fields}")
        if not common_fields and not only_a_fields and not only_b_fields:
            print("  (no field info found in either file)")
            continue
        for fn in common_fields:
            a_f = ka[fn]
            b_f = kb[fn]
            a_bo = a_f.get('bitOffset')
            b_bo = b_f.get('bitOffset')
            a_bw = a_f.get('bitWidth')
            b_bw = b_f.get('bitWidth')
            diffs = []
            if a_bo != b_bo:
                diffs.append(f"bitOffset A={a_bo} B={b_bo}")
            if a_bw != b_bw:
                diffs.append(f"bitWidth A={a_bw} B={b_bw}")
            # access differences
            if (a_f.get('access') or '').lower() != (b_f.get('access') or '').lower():
                diffs.append(f"access A={a_f.get('access')} B={b_f.get('access')}")
            # enumerated values count/name diff
            a_en = [ev.get('name') for ev in (a_f.get('enumeratedValues') or [])]
            b_en = [ev.get('name') for ev in (b_f.get('enumeratedValues') or [])]
            if a_en != b_en:
                diffs.append(f"enums A={len(a_en)} B={len(b_en)}")
            if diffs:
                print(f"  Field {fn}: {'; '.join(diffs)}")
            else:
                print(f"  Field {fn}: identical")


def fuse_pair(fp_a, fp_b, out_dir='models/NXP', fused_name=None):
    """Create a fused YAML template and per-device parameter JSON files.

    Strategy:
    - Use fp_a as the reference layout.
    - Compute offset_delta = offset_b - offset_a for common registers and
      propose a numeric parameter `offset_B` = offset_delta to map B -> A.
    - Detect registers present only in A or only in B; if a group (like FIFOs)
      appears only in one, propose a boolean parameter `has_<group>`.
    - Emit a fused YAML containing:
      - `parameters` section listing inferred parameters and defaults
      - `variants` mapping with per-device parameter values
      - `registers` listing common registers (with reference offsets) and
        conditional registers annotated with `conditional_on`.
    - Write per-device params JSON files.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    file_a = Path(fp_a['path'])
    file_b = Path(fp_b['path'])
    name_a = file_a.stem
    name_b = file_b.stem
    folder_a = file_a.parent.name
    folder_b = file_b.parent.name

    # compute common and exclusive registers
    regs_a = {r for r in fp_a['reg_names']}
    regs_b = {r for r in fp_b['reg_names']}
    common = sorted(regs_a & regs_b)
    only_a = sorted(regs_a - regs_b)
    only_b = sorted(regs_b - regs_a)

    # compute offset deltas for common regs
    def name_to_offset(fp):
        offs = {}
        for r in fp.get('raw_registers', []):
            nm = normalize_name(r.get('name',''))
            off = r.get('addressOffset')
            offs[nm] = off
            for sub in r.get('registers', []) or []:
                offs[normalize_name(sub.get('name',''))] = sub.get('addressOffset')
        return offs

    offs_a = name_to_offset(fp_a)
    offs_b = name_to_offset(fp_b)
    deltas = [offs_b[r] - offs_a[r] for r in common if offs_a.get(r) is not None and offs_b.get(r) is not None]
    offset_param = None
    if deltas and all(d == deltas[0] for d in deltas):
        offset_param = deltas[0]

    # detect a contiguous block of registers unique to one side to suggest boolean
    # Here we heuristically consider "FIFO" in register name as group
    has_fifo = any('FIFO' in r for r in only_a + only_b)
    fifo_in_a = any('FIFO' in r for r in only_a)
    fifo_in_b = any('FIFO' in r for r in only_b)

    # determine which variant has the smaller offsets overall (baseline)
    def min_offset(offs):
        vals = [v for v in offs.values() if v is not None]
        return min(vals) if vals else None

    min_a = min_offset(offs_a)
    min_b = min_offset(offs_b)
    # choose baseline: the variant with smaller min offset (or A if unknown)
    if min_a is None and min_b is None:
        baseline = 'A'
    elif min_b is None:
        baseline = 'A'
    elif min_a is None:
        baseline = 'B'
    else:
        baseline = 'A' if min_a <= min_b else 'B'

    # Build fused YAML structure
    fused = {}
    # If both peripherals share the same base name, use that name for the fused
    if name_a == name_b:
        fused_name = name_a
    else:
        fused_name = f"FUSED_{name_a}_{name_b}"
    fused['name'] = fused_name
    fused['description'] = f"Fused peripheral template for {name_a} ({folder_a}) and {name_b} ({folder_b})."
    # Merge declared parameters from both source files (preserve superset)
    params_a_raw = fp_a.get('raw', {}).get('parameters', []) or []
    params_b_raw = fp_b.get('raw', {}).get('parameters', []) or []
    param_map = {}
    def add_param_entry(p):
        name = p.get('name')
        if not name:
            return
        if name not in param_map:
            # copy relevant fields: name, bits, min, max, description, default if any
            entry = {'name': name}
            if 'bits' in p:
                entry['bits'] = p.get('bits')
            if 'min' in p:
                entry['min'] = p.get('min')
            if 'max' in p:
                entry['max'] = p.get('max')
            if 'description' in p:
                entry['description'] = p.get('description')
            if 'default' in p:
                entry['default'] = p.get('default')
            param_map[name] = entry
        else:
            # merge numeric ranges
            e = param_map[name]
            if 'bits' in p:
                e['bits'] = max(e.get('bits', 0), p.get('bits'))
            if 'min' in p:
                e['min'] = min(e.get('min', p.get('min')), p.get('min'))
            if 'max' in p:
                e['max'] = max(e.get('max', p.get('max')), p.get('max'))
            if 'description' not in e and 'description' in p:
                e['description'] = p.get('description')

    for p in params_a_raw + params_b_raw:
        add_param_entry(p)

    # Add inferred parameters using same bitfield pattern
    # Only expose offset parameter when a non-zero constant delta exists
    if offset_param is not None and int(offset_param) != 0:
        # choose a sensible signed range for offset parameter
        if 'offset_B' not in param_map:
            param_map['offset_B'] = {'name': 'offset_B', 'bits': 16, 'min': -32768, 'max': 32767, 'description': f'Offset to add to variant B addresses to map to reference {name_a}.', 'default': int(offset_param)}
        else:
            param_map['offset_B']['default'] = int(offset_param)
    if has_fifo:
        if 'has_fifo' not in param_map:
            param_map['has_fifo'] = {'name': 'has_fifo', 'bits': 1, 'min': 0, 'max': 1, 'description': 'Enable FIFO register block', 'default': 1}
        else:
            param_map['has_fifo']['default'] = param_map['has_fifo'].get('default', 1)

    # Build fused['parameters'] list from param_map preserving order
    fused['parameters'] = list(param_map.values())

    # variants with parameter values for A and B
    # Build per-variant parameter values: use default if available, else a sensible fallback
    def param_default_value(p):
        if 'default' in p:
            return p['default']
        if 'min' in p:
            return p['min']
        return 0

    # For offset_B: set baseline variant to 0, other variant to detected delta
    variants_map = {}
    variants_map[folder_a] = {}
    variants_map[folder_b] = {}
    for p in fused['parameters']:
        name = p['name']
        if name == 'offset_B':
            # baseline variant mapped to 0; other variant mapped to detected delta
            variants_map[folder_a][name] = 0
            variants_map[folder_b][name] = int(offset_param)
        elif name == 'has_fifo':
            variants_map[folder_a][name] = 1 if fifo_in_a else 0
            variants_map[folder_b][name] = 1 if fifo_in_b else 0
        else:
            v = param_default_value(p)
            variants_map[folder_a][name] = v
            variants_map[folder_b][name] = v

    fused['variants'] = variants_map

    # registers: include common registers with reference offsets (from A), and
    # include exclusive registers annotated with conditional_on
    regs_out = []
    # helper to find raw register dict by name
    def find_raw(fp, name):
        for r in fp.get('raw_registers', []):
            if normalize_name(r.get('name','')) == name:
                return r
            for sub in r.get('registers', []) or []:
                if normalize_name(sub.get('name','')) == name:
                    return sub
        return None

    for rname in common:
        raw_a = find_raw(fp_a, rname)
        raw_b = find_raw(fp_b, rname)
        # Determine baseline offset for this register
        if baseline == 'A':
            ref_off = None
            if raw_a and 'addressOffset' in raw_a:
                ref_off = raw_a['addressOffset']
            elif raw_b and 'addressOffset' in raw_b and offset_param is not None:
                ref_off = raw_b['addressOffset'] - offset_param
        else:
            ref_off = None
            if raw_b and 'addressOffset' in raw_b:
                ref_off = raw_b['addressOffset']
            elif raw_a and 'addressOffset' in raw_a and offset_param is not None:
                ref_off = raw_a['addressOffset'] + offset_param

        # start with fields merged from both variants
        fa_fields = {normalize_name(f.get('name','')): dict(f) for f in (raw_a.get('fields', []) if raw_a else [])}
        fb_fields = {normalize_name(f.get('name','')): dict(f) for f in (raw_b.get('fields', []) if raw_b else [])}
        all_field_keys = list(dict.fromkeys(list(fa_fields.keys()) + list(fb_fields.keys())))
        merged_fields = []
        for fk in all_field_keys:
            if fk in fa_fields and fk in fb_fields:
                # prefer A's definition but keep it unchanged
                merged_fields.append(fa_fields[fk])
            elif fk in fa_fields:
                f = fa_fields[fk]
                # field present only in A -> annotate present_when
                if has_fifo and (fifo_in_a != fifo_in_b):
                    f['present_when'] = 'has_fifo == true' if fifo_in_a else 'has_fifo == false'
                else:
                    f['present_when'] = f"variant == '{folder_a}'"
                merged_fields.append(f)
            else:
                f = fb_fields[fk]
                # field present only in B -> annotate present_when
                if has_fifo and (fifo_in_a != fifo_in_b):
                    f['present_when'] = 'has_fifo == true' if fifo_in_b else 'has_fifo == false'
                else:
                    f['present_when'] = f"variant == '{folder_b}'"
                merged_fields.append(f)

        # build output register dict: prefer A's register dict then B's
        raw = raw_a or raw_b
        out_r = dict(raw) if raw else {'name': rname}
        # remove original addressOffset if present and set addressOffset_ref to baseline mapping
        out_r.pop('addressOffset', None)
        if ref_off is not None:
            out_r['addressOffset'] = ref_off
        # replace fields with merged list
        out_r['fields'] = merged_fields
        regs_out.append(out_r)

    # exclusive blocks
    for rname in only_a:
        raw = find_raw(fp_a, rname)
        out_r = dict(raw) if raw else {'name': rname}
        # present_when: tie to has_fifo if FIFO group differs between variants
        if has_fifo and (fifo_in_a != fifo_in_b):
            # registers unique to A where FIFO was in A -> present when has_fifo == true
            present_expr = 'has_fifo == true' if fifo_in_a else 'has_fifo == false'
            out_r['present_when'] = present_expr
        else:
            # fallback: present when folder_a variant is selected
            out_r['present_when'] = f"variant == '{folder_a}'"
        if 'addressOffset' in out_r:
            # map to baseline offsets
            raw_off = out_r.pop('addressOffset')
            if baseline == 'A':
                # A is baseline, keep as-is
                out_r['addressOffset'] = raw_off
            elif offset_param is not None:
                # subtract delta to map into baseline
                out_r['addressOffset'] = raw_off + offset_param
            else:
                out_r['addressOffset'] = raw_off
        regs_out.append(out_r)

    for rname in only_b:
        raw = find_raw(fp_b, rname)
        out_r = dict(raw) if raw else {'name': rname}
        if has_fifo and (fifo_in_a != fifo_in_b):
            present_expr = 'has_fifo == true' if fifo_in_b else 'has_fifo == false'
            out_r['present_when'] = present_expr
        else:
            out_r['present_when'] = f"variant == '{folder_b}'"
        if 'addressOffset' in out_r:
            raw_off = out_r.pop('addressOffset')
            if baseline == 'B':
                out_r['addressOffset'] = raw_off
            elif offset_param is not None:
                out_r['addressOffset'] = raw_off - offset_param
            else:
                out_r['addressOffset'] = raw_off
        regs_out.append(out_r)

    fused['registers'] = regs_out

    # write fused yaml and per-device params
    # fused filename: allow caller to override via fused_name, else use existing behavior
    if fused_name:
        fused_fname = fused_name
    else:
        if name_a == name_b:
            fused_fname = f"{name_a}.yaml"
        else:
            fused_fname = f"fused_{name_a}_{name_b}.yaml"
    fused_path = out_dir / fused_fname
    # param files include the folder/family to avoid collisions
    params_a_path = out_dir / f"{name_a}_{folder_a}_params.json"
    params_b_path = out_dir / f"{name_b}_{folder_b}_params.json"

    import yaml as _yaml
    fused_path.write_text(_yaml.safe_dump(fused, sort_keys=False))
    params_a = fused['variants'][folder_a]
    params_b = fused['variants'][folder_b]
    params_a_path.write_text(json.dumps(params_a, indent=2))
    params_b_path.write_text(json.dumps(params_b, indent=2))

    print(f"\nWrote fused template: {fused_path}")
    print(f"Wrote params for {folder_a} ({name_a}): {params_a_path}")
    print(f"Wrote params for {folder_b} ({name_b}): {params_b_path}")


if __name__ == '__main__':
    main()
