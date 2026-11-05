"""Per chip instance: do the model's (offset, bitOffset, bitWidth) positions equal the chip SVD's?

Usage: model_vs_svd.py HEAD|WORK [--covers]
  --covers: only require every SVD field's bits to be covered by model fields
            at the same offset (superset models may carry more, and may split
            or widen fields), and split results by family/shared block.  The
            per-instance report is (-missing fields/total).
"""
import sys, subprocess, re
from pathlib import Path
from ruamel.yaml import YAML
exec(open('tools/h5_restructure/h5_layouts.py').read().split('# per base peripheral TYPE')[0])
y = YAML(typ='safe', pure=True)
rev = sys.argv[1]   # 'WORK' or any git rev (e.g. HEAD, 393327a6^)
covers = '--covers' in sys.argv[2:]
def read(path):
    if rev == 'WORK': return y.load((ROOT / path).read_text())
    return y.load(subprocess.run(['git', '-C', str(ROOT), 'show', f'{rev}:{path}'], capture_output=True, text=True, check=True).stdout)
def expand(dim, inc):
    if isinstance(dim, list):
        import itertools
        return [sum(i * s for i, s in zip(ix, inc)) for ix in itertools.product(*[range(d) for d in dim])]
    return [i * (inc or 0) for i in range(dim or 1)]
def model_pos(path):
    d = read(path); out = set()
    def walk(regs, off0):
        for r in regs:
            for o in expand(r.get('dim'), r.get('dimIncrement')):
                off = off0 + r.get('addressOffset', 0) + o
                if 'registers' in r: walk(r['registers'], off)
                else:
                    for f in r.get('fields') or []: out.add((off, f['bitOffset'], f['bitWidth']))
    walk(d.get('registers') or [], 0); return out
def svd_pos(dev, name):
    pe = dev[name]
    while pe.find('registers') is None and pe.get('derivedFrom'): pe = dev[pe.get('derivedFrom')]
    out = set()
    def walk(node, off0):
        for el in node:
            dim = int(el.findtext('dim') or '1', 0); inc = int(el.findtext('dimIncrement') or '0', 0)
            for k in range(dim):
                off = off0 + int(el.findtext('addressOffset'), 0) + k * inc
                if el.tag == 'cluster': walk(el, off)
                elif el.tag == 'register':
                    for f in (el.find('fields') if el.find('fields') is not None else []):
                        bo, bw = f.findtext('bitOffset'), f.findtext('bitWidth')
                        if bo is None: lsb, msb = int(f.findtext('lsb')), int(f.findtext('msb')); bo, bw = lsb, msb-lsb+1
                        out.add((off, int(bo), int(bw)))
    if pe.find('registers') is not None: walk(pe.find('registers'), 0)
    return out
chips = sorted(p for p in (ROOT/'models/ST/H5').rglob('STM32H5*.yaml'))
tot = ok = 0; bad = {}; kind_tot = {}; kind_ok = {}; missing = {}
for cp in chips:
    rel = str(cp.relative_to(ROOT)); chip = read(rel); name = chip['name']; dev = device(name)
    models = dict(chip.get('models') or {}); insts = dict(chip.get('instances') or {})
    node = chip
    while node.get('inherits'):
        node = read(f"models/{node['inherits']}.yaml"); models = {**(node.get('models') or {}), **models}; insts = {**(node.get('instances') or {}), **insts}
    for inst, info in insts.items():
        if inst not in dev or not isinstance(info, dict) or 'model' not in info: continue
        mp = models.get(info['model'])
        if not mp: continue
        tot += 1
        kind = 'family' if mp.startswith('ST/H5/') else 'shared'
        kind_tot[kind] = kind_tot.get(kind, 0) + 1
        m, s_ = model_pos(f'models/{mp}.yaml'), svd_pos(dev, inst)
        if covers:
            mbits = {}
            for off, bo, bw in m: mbits[off] = mbits.get(off, 0) | (((1 << bw) - 1) << bo)
            gone = {f for f in s_ if ((((1 << f[2]) - 1) << f[1]) & ~mbits.get(f[0], 0))}
            good = not gone
        else: good = m == s_
        if good: ok += 1; kind_ok[kind] = kind_ok.get(kind, 0) + 1
        else:
            bad.setdefault(name, []).append(inst)
            missing.setdefault((kind, mp), {}).setdefault(name, []).append((inst, len(gone if covers else s_ - m), len(s_)))
what = 'covers all fields of' if covers else 'field positions match'
print(f'{rev}: {ok}/{tot} chip instances: model {what} the chip SVD')
for k in sorted(kind_tot): print(f'   {k}: {kind_ok.get(k, 0)}/{kind_tot[k]}')
if covers:
    for (k, mp), per in sorted(missing.items()):
        print(f'  [{k}] {mp}')
        for n, v in sorted(per.items()):
            print(f'      {n}: ' + ' '.join(f'{i}(-{a}/{b})' for i, a, b in sorted(v)))
for n, v in sorted(bad.items()): print(f'   {n}: {len(v):3} mismatching: ' + ' '.join(sorted(v)[:14]) + (' ...' if len(v) > 14 else ''))
