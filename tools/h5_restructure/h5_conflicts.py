"""Find bits whose meaning differs between the dies of H52x_H57x (incl. H543/H553).

For every block with more than one layout inside H52x_H57x, compare each die
group's SVD layout with every other group's, register by register (matched by
offset), and classify every pair of overlapping fields with different
(name, bitOffset, bitWidth):

  widen   same name, same LSB, different width (superset = wider field)
  split   one field exactly covers several fields of the other, or vice versa
  rename  different name, identical bit range
  moved   same name at a different position in the same register
  clash   partial overlap that is none of the above
And per register offset:
  regname different register names at one offset
  regmove same register name at different offsets

Only `moved`, `clash` and `regname` can need a union; `rename`/`split` are
naming questions, `widen` is a superset.
"""
import sys, re
from collections import defaultdict
exec(open(__file__.replace('h5_conflicts.py', 'h5_layouts.py')).read().split('# per base peripheral TYPE')[0])
from ruamel.yaml import YAML
cfg = YAML(typ='safe').load((ROOT/'svd/ST/STM32.yaml').read_text()); blocks = cfg['families']['H5']['blocks']
CHIPS = ['STM32H523','STM32H533','STM32H543','STM32H553','STM32H562','STM32H563','STM32H573']
devs = {c: device(c) for c in CHIPS}
def norm(n): return re.sub(r'[^A-Z0-9]', '', n.upper())
results = defaultdict(lambda: defaultdict(set))   # block -> kind -> {text}
for bt, bc in blocks.items():
    bases = {canon(i)[0] for i in (bc.get('instances') or [])}
    if not bases: continue
    lays = {}
    for chip in CHIPS:
        dev = devs[chip]
        for n in sorted(dev):
            if canon(n)[0] in bases and (dev[n].find('registers') is not None or dev[n].get('derivedFrom')):
                lays.setdefault(layout(dev, n), []).append(chip[7:]); break
    if len(lays) < 2: continue
    groups = [('+'.join(cs), {off: (rn, fl) for off, rn, fl in l}) for l, cs in lays.items()]
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            (ga, A), (gb, B) = groups[i], groups[j]
            pair = f'{ga} vs {gb}'
            na_ = {norm(rn): off for off, (rn, _) in A.items()}; nb_ = {norm(rn): off for off, (rn, _) in B.items()}
            for rn in set(na_) & set(nb_):
                if na_[rn] != nb_[rn]: results[bt]['regmove'].add(f'{A[na_[rn]][0]} @{na_[rn]:#05x} vs @{nb_[rn]:#05x}  ({pair})')
            for off in sorted(set(A) & set(B)):
                (ra, fa), (rb, fb) = A[off], B[off]
                if norm(ra) != norm(rb): results[bt]['regname'].add(f'{off:#05x} {ra} | {rb}  ({pair})')
                fa = {f[0]: (f[1], f[2]) for f in fa}; fb = {f[0]: (f[1], f[2]) for f in fb}
                bits = lambda p: set(range(p[0], p[0] + p[1]))
                for n in set(fa) & set(fb):
                    if fa[n] != fb[n]:
                        if fa[n][0] == fb[n][0]: results[bt]['widen'].add(f'{rb}.{n} {fa[n][1]}→{fb[n][1]} bits')
                        else: results[bt]['moved'].add(f'{rb}.{n} @{fa[n][0]}:{fa[n][1]} vs @{fb[n][0]}:{fb[n][1]}  ({pair})')
                # overlaps between differently named fields
                for na, pa in fa.items():
                    if na in fb and fb[na] == pa: continue
                    ov = [nb for nb, pb in fb.items() if nb != na and bits(pa) & bits(pb)]
                    if not ov: continue
                    if na in fb and fb[na] != pa: continue   # reported as moved/widen
                    if len(ov) == 1 and fb[ov[0]] == pa:
                        results[bt]['rename'].add(f'{rb}[{pa[0]}:{pa[1]}] {na} | {ov[0]}'); continue
                    cover = set().union(*(bits(fb[nb]) for nb in ov))
                    if cover == bits(pa) and all(bits(fb[nb]) <= bits(pa) for nb in ov):
                        results[bt]['split'].add(f'{rb}[{pa[0]}:{pa[1]}] {na} | {"+".join(sorted(ov))}'); continue
                    if len(ov) == 1 and bits(pa) <= bits(fb[ov[0]]):
                        # na lies inside a wider field of B: check whether B's field is split in A
                        nb = ov[0]; inside = [x for x, p in fa.items() if bits(p) & bits(fb[nb])]
                        if set().union(*(bits(fa[x]) for x in inside)) == bits(fb[nb]) and all(bits(fa[x]) <= bits(fb[nb]) for x in inside):
                            continue   # reported from the other side as split
                    if len(ov) == 1 and norm(ov[0]) == norm(na): continue
                    # widen with a rename: same LSB, one contains the other
                    if len(ov) == 1 and fb[ov[0]][0] == pa[0]:
                        results[bt]['widen'].add(f'{rb}.{na}|{ov[0]} {pa[1]}→{fb[ov[0]][1]} bits (renamed)'); continue
                    results[bt]['clash'].add(f'{rb}: {na}[{pa[0]}:{pa[1]}] vs ' + ', '.join(f'{nb}[{fb[nb][0]}:{fb[nb][1]}]' for nb in ov) + f'  ({pair})')
kinds = ['regmove', 'moved', 'clash', 'regname', 'widen', 'split', 'rename']
print('block'.ljust(10), ' '.join(k.rjust(7) for k in kinds))
for bt in sorted(results):
    print(bt.ljust(10), ' '.join(str(len(results[bt][k])).rjust(7) for k in kinds))
for bt in sorted(results):
    for k in kinds:
        for t in sorted(results[bt][k]): print(f'{bt:10} {k:7} {t}')
