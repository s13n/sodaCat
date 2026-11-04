"""Per chip instance: do the model's (offset, bitOffset, bitWidth) positions equal the chip SVD's?"""
import sys, subprocess, re
from pathlib import Path
from ruamel.yaml import YAML
exec(open('tools/h5_restructure/h5_layouts.py').read().split('# per base peripheral TYPE')[0])
y = YAML(typ='safe', pure=True)
rev = sys.argv[1]   # 'HEAD' or 'WORK'
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
tot = ok = 0; bad = {}
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
        if model_pos(f'models/{mp}.yaml') == svd_pos(dev, inst): ok += 1
        else: bad.setdefault(name, []).append(inst)
print(f'{rev}: {ok}/{tot} chip instances have a model whose field positions match the chip SVD')
for n, v in sorted(bad.items()): print(f'   {n}: {len(v):3} mismatching: ' + ' '.join(sorted(v)[:14]) + (' ...' if len(v) > 14 else ''))
