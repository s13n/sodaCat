"""Field-level diff of one block across the H52x_H57x layout groups (incl. H543/H553).

Usage: h5_diff.py <SVD peripheral base name> [reference chip, default STM32H573]
Prints, per layout group, registers/fields that differ from the reference chip's
layout.  Register-name prefixes and secure aliases are normalised as in h5_layouts.
"""
import sys
exec(open(__file__.replace('h5_diff.py', 'h5_layouts.py')).read().split('# per base peripheral TYPE')[0])
CHIPS = ['STM32H523', 'STM32H533', 'STM32H543', 'STM32H553', 'STM32H562', 'STM32H563', 'STM32H573']
base = sys.argv[1]; ref_chip = sys.argv[2] if len(sys.argv) > 2 else 'STM32H573'
def find(dev):
    for n in (base, base + '1', 'SEC_' + base):
        if n in dev and (dev[n].find('registers') is not None or dev[n].get('derivedFrom')): return n
lays = {}
for c in CHIPS:
    dev = device(c); n = find(dev)
    lays[c] = layout(dev, n) if n else None
groups = {}
for c, l in lays.items(): groups.setdefault(l, []).append(c)
def regs(l): return {(off, rn): {f[0]: f[1:] for f in fl} for off, rn, fl in l}
ref = regs(lays[ref_chip])
for l, cs in groups.items():
    tag = '+'.join(c[7:] for c in cs)
    if l is None: print(f'== {tag}: absent'); continue
    if ref_chip in cs: print(f'== {tag}: reference'); continue
    r = regs(l); print(f'== {tag} vs {ref_chip[7:]}')
    byoff_ref = {o: n for o, n in ref}; byoff = {o: n for o, n in r}
    for o in sorted(set(byoff) | set(byoff_ref)):
        a, b = byoff_ref.get(o), byoff.get(o)
        if b is None: print(f'   -{o:#05x} {a}  (only in ref)'); continue
        if a is None:
            print(f'   +{o:#05x} {b}: ' + ' '.join(f'{k}[{v[0]}:{v[1]}]' for k, v in sorted(r[(o, b)].items(), key=lambda x: x[1]))); continue
        fa, fb = ref[(o, a)], r[(o, b)]
        nm = '' if a == b else f' (ref name {a})'
        d = []
        for k in sorted(set(fa) | set(fb), key=lambda k: (fa.get(k) or fb.get(k))):
            if fa.get(k) == fb.get(k): continue
            if k not in fb: d.append(f'-{k}[{fa[k][0]}:{fa[k][1]}]')
            elif k not in fa: d.append(f'+{k}[{fb[k][0]}:{fb[k][1]}]')
            else: d.append(f'~{k}[{fa[k][0]}:{fa[k][1]}→{fb[k][0]}:{fb[k][1]}]')
        if d or nm: print(f'   {o:#05x} {b}{nm}: ' + ' '.join(d))
