import re, zipfile, xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ZIP = zipfile.ZipFile(ROOT/'svd/ST/stm32h5-svd.zip'); SUPP = ROOT/'build/_deps/stm32h5_svd_supplement-src/CMSIS/SVD'
SUBF = {'H503': ['STM32H503'], 'H52x': ['STM32H523','STM32H533'], 'H56x': ['STM32H562','STM32H563','STM32H573'],
        'H54x': ['STM32H543','STM32H553'], 'H5Ex': ['STM32H5E4','STM32H5E5','STM32H5F4','STM32H5F5']}
def device(chip):
    p = SUPP/f'{chip}.svd'
    data = p.read_bytes() if p.exists() else next(ZIP.read(n) for n in ZIP.namelist() if n.endswith(f'/{chip}.svd'))
    r = ET.fromstring(data); return {pe.findtext('name'): pe for pe in r.iter('peripheral')}
def canon(name):
    """(base peripheral, alias) for X / X_S / SEC_X."""
    if name.startswith('SEC_'): return name[4:], 'sec'
    if name.endswith('_S'): return name[:-2], 'sec'
    return name, 'ns'
def layout(dev, name):
    pe = dev[name]
    while pe.find('registers') is None and pe.get('derivedFrom'): pe = dev[pe.get('derivedFrom')]
    base, _ = canon(name); pfx = base.rstrip('0123456789')
    out = []
    def walk(node, off0):
        for el in node:
            if el.tag == 'register':
                off = off0 + int(el.findtext('addressOffset'), 0)
                rn = re.sub(r'^(SEC_)?' + re.escape(pfx) + r'\d*_', '', el.findtext('name'))
                fl = []
                for f in (el.find('fields') if el.find('fields') is not None else []):
                    bo, bw = f.findtext('bitOffset'), f.findtext('bitWidth')
                    if bo is None: lsb, msb = int(f.findtext('lsb')), int(f.findtext('msb')); bo, bw = lsb, msb-lsb+1
                    fl.append((f.findtext('name'), int(bo), int(bw)))
                out.append((off, rn, tuple(sorted(fl))))
            elif el.tag == 'cluster': walk(el, off0 + int(el.findtext('addressOffset'), 0))
    walk(pe.find('registers'), 0)
    return tuple(sorted(out))
# per base peripheral TYPE (strip trailing digits): layouts by (subfamily, chip, alias)
by_type = defaultdict(dict)
alias_mismatch = []
for sf, chips in SUBF.items():
    for chip in chips:
        dev = device(chip)
        seen = {}
        for name in dev:
            base, alias = canon(name)
            if dev[name].find('registers') is None and not dev[name].get('derivedFrom'): continue
            lay = layout(dev, name)
            typ = base.rstrip('0123456789') or base
            by_type[typ][(sf, chip, name)] = lay
            if alias == 'sec' and base in seen and seen[base] != lay: alias_mismatch.append((chip, base))
            if alias == 'ns': seen[base] = lay
        for name in dev:
            base, alias = canon(name)
            if alias == 'sec' and base in seen:
                if layout(dev, name) != seen[base] and (chip, base) not in alias_mismatch: alias_mismatch.append((chip, base))
import json
print('chips where X and its secure alias differ:', len(alias_mismatch), sorted(set(b for _, b in alias_mismatch))[:20])
rows = []
for typ, d in sorted(by_type.items()):
    distinct = {}
    for k, lay in d.items(): distinct.setdefault(lay, []).append(k)
    per_sf = defaultdict(set)
    for i, (lay, ks) in enumerate(distinct.items()):
        for sf, chip, n in ks: per_sf[sf].add(i)
    rows.append((typ, len(distinct), {sf: len(v) for sf, v in per_sf.items()}))
multi = [r for r in rows if r[1] > 1]
print(f'{len(rows)} peripheral types; {len(multi)} with >1 layout across H5')
for typ, n, psf in multi:
    print(f'  {typ:10} {n} layouts   within-subfamily: ' + ' '.join(f'{sf}:{k}' for sf, k in psf.items()))
