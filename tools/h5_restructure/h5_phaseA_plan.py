import json
exec(open('tools/h5_restructure/h5_layouts.py').read().split('# per base peripheral TYPE')[0])
from ruamel.yaml import YAML
cfg = YAML(typ='safe', pure=True).load((ROOT/'svd/ST/STM32.yaml').read_text()); blocks = cfg['families']['H5']['blocks']
CSF = {'H503': ['STM32H503'], 'H52x_H57x': ['STM32H573','STM32H563','STM32H562','STM32H533','STM32H523'],
       'H5Ex_H5Fx': ['STM32H5F5','STM32H5E5','STM32H5F4','STM32H5E4']}
devs = {c: device(c) for cs in CSF.values() for c in cs}
PARTNER = {'FLASH_S': 'Flash'}
fold = {}   # X_S block -> partner
for bt in blocks:
    if bt.endswith('_S'):
        p = PARTNER.get(bt) or bt[:-2]
        assert p in blocks, bt
        fold[bt] = p
insts = {bt: set(bc.get('instances') or []) for bt, bc in blocks.items() if bt not in fold}
for s, p in fold.items(): insts[p] |= set(blocks[s].get('instances') or [])
# SEC_ aliases present on H56x for any instance of the block
sec = {}
for bt, names in insts.items():
    add = set()
    for chip in ('STM32H562', 'STM32H563', 'STM32H573'):
        for n in names:
            if not n.endswith('_S') and f'SEC_{n}' in devs[chip]: add.add(f'SEC_{n}')
    if add: sec[bt] = sorted(add)
def own_inst(dev, names):
    """Non-derived (original) peripheral among the block's instance names."""
    for n in sorted(names, key=lambda n: (n.endswith('_S'), n)):
        if n in dev and dev[n].find('registers') is not None: return n
    for n in sorted(names):
        if n in dev: return n
variants = {}
for bt, bc in blocks.items():
    if bt in fold or 'from' not in bc: continue
    schip, sinst = bc['from'].split('.', 1)
    base = layout(device(schip), sinst)
    names = insts[bt]
    for sf, chips in CSF.items():
        if schip in chips: continue
        for chip in chips:
            n = own_inst(devs[chip], names)
            if n:
                if layout(devs[chip], n) != base: variants.setdefault(bt, {})[sf] = f'{chip}.{n}'
                break
plan = {'fold': fold, 'instances': {bt: sorted(v | set(sec.get(bt, []))) for bt, v in insts.items()},
        'sec_added': sec, 'variants': variants}
json.dump(plan, open('/tmp/h5_phaseA_plan.json', 'w'), indent=1)
print('fold:', len(fold), 'blocks;  SEC_ aliases added to', len(sec), 'blocks;  variants for', len(variants), 'blocks')
for bt, v in variants.items(): print(f'  {bt:11} base {blocks[bt]["from"]:20} variants {v}')
print('SEC_ added:', {k: v for k, v in list(sec.items())[:6]}, '...')
