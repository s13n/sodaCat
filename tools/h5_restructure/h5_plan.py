import sys
exec(open('tools/h5_restructure/h5_layouts.py').read().split('# per base peripheral TYPE')[0])
from ruamel.yaml import YAML
cfg = YAML().load((ROOT/'svd/ST/STM32.yaml').read_text()); blocks = cfg['families']['H5']['blocks']
CSF = {'H503': ['STM32H503'], 'H52x_H57x': ['STM32H523','STM32H533','STM32H543','STM32H553','STM32H562','STM32H563','STM32H573'],
       'H5Ex_H5Fx': ['STM32H5E4','STM32H5E5','STM32H5F4','STM32H5F5']}
devs = {c: device(c) for cs in CSF.values() for c in cs}
# fold: block key X and X_S → one entry; instance names incl. aliases
folded = {}
for bt, bc in blocks.items():
    key = bt[:-2] if bt.endswith('_S') and bt[:-2] in blocks else bt
    folded.setdefault(key, {'cfg': [], 'insts': set()})
    folded[key]['cfg'].append(bt); folded[key]['insts'].update(bc.get('instances') or [])
rows = []
for key, f in folded.items():
    bases = {canon(i)[0] for i in f['insts']}
    per_sf = {}
    for sf, chips in CSF.items():
        lays = {}
        for chip in chips:
            dev = devs[chip]
            for n in dev:
                if canon(n)[0] in bases and (dev[n].find('registers') is not None or dev[n].get('derivedFrom')):
                    lays.setdefault(layout(dev, n), set()).add(chip); break   # first matching instance per chip
        per_sf[sf] = lays
    shape = {sf: len(l) for sf, l in per_sf.items() if l}
    uses = [blocks[b].get('uses') for b in f['cfg'] if blocks[b].get('uses')]
    rows.append((key, f['cfg'], uses, shape, per_sf))
import json
multi = [r for r in rows if r[3].get('H52x_H57x', 0) > 1]
print(f"{len(rows)} blocks after folding; {sum(1 for r in rows if len(r[1]) > 1)} had a separate _S block")
print(f"blocks with >1 layout inside H52x_H57x: {len(multi)}")
for key, cfgs, uses, shape, per_sf in sorted(multi, key=lambda r: -r[3]['H52x_H57x']):
    groups = ' | '.join('+'.join(sorted(c[7:] for c in chips)) for chips in per_sf['H52x_H57x'].values())
    print(f"  {key:11} {'uses '+uses[0] if uses else 'family':16} layouts {shape}  H52x_H57x groups: {groups}")
single = [r[0] for r in rows if r[3].get('H52x_H57x', 0) <= 1]
print('one layout per subfamily (Phase A only):', ' '.join(sorted(single)))
