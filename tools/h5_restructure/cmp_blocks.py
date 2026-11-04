"""Compare each instance of new chips against its block's `from:` source (raw SVD layout)."""
import re, sys, zipfile, xml.etree.ElementTree as ET
from pathlib import Path
from ruamel.yaml import YAML
ROOT = Path(__file__).resolve().parents[2]
cfg = YAML().load((ROOT/'svd/ST/STM32.yaml').read_text())
fam = cfg['families']['H5']; shared = cfg['shared_blocks']
ZIP = zipfile.ZipFile(ROOT/'svd/ST/stm32h5-svd.zip'); SUPP = ROOT/'build/_deps/stm32h5_svd_supplement-src/CMSIS/SVD'
_cache = {}
def device(chip):
    if chip not in _cache:
        p = SUPP/f'{chip}.svd'
        data = p.read_bytes() if p.exists() else next((ZIP.read(n) for n in ZIP.namelist() if n.endswith(f'/{chip}.svd')), None)
        if data is None: _cache[chip] = None
        else:
            r = ET.fromstring(data); _cache[chip] = {pe.findtext('name'): pe for pe in r.iter('peripheral')}
    return _cache[chip]
def layout(chip, inst):
    d = device(chip); pe = d.get(inst) if d else None
    if pe is None: return None
    while pe.find('registers') is None and pe.get('derivedFrom'): pe = d[pe.get('derivedFrom')]
    out = set()
    def walk(node, base):
        for el in node:
            if el.tag == 'register':
                off = base + int(el.findtext('addressOffset'), 0)
                rn = re.sub(r'^' + re.escape(inst.rstrip('0123456789')) + r'\d*_', '', el.findtext('name'))
                fs = el.find('fields')
                out.add((rn, off, '', 0, 0))
                for f in (fs if fs is not None else []):
                    if f.tag != 'field': continue
                    bo, bw = f.findtext('bitOffset'), f.findtext('bitWidth')
                    if bo is None:
                        lsb, msb = int(f.findtext('lsb')), int(f.findtext('msb')); bo, bw = lsb, msb - lsb + 1
                    out.add((rn, off, f.findtext('name'), int(bo), int(bw)))
            elif el.tag == 'cluster':
                walk(el, base + int(el.findtext('addressOffset'), 0))
    walk(pe.find('registers'), 0)
    return out
new_chips = sys.argv[1:]
rows = []
for bt, bc in fam['blocks'].items():
    bc = dict(bc); 
    if 'uses' in bc: bc = {**dict(shared.get(bc['uses'], {})), **bc}
    src = bc.get('from'); insts = list(bc.get('instances') or [])
    if not src or '.' not in src: continue
    schip, sinst = src.split('.', 1)
    ref = layout(schip, sinst)
    for chip in new_chips:
        for inst in insts:
            lay = layout(chip, inst)
            if lay is None or ref is None: continue
            if lay != ref:
                rows.append((bt, chip, inst, src, len(ref - lay), len(lay - ref), sorted(ref - lay)[:3], sorted(lay - ref)[:3]))
            break   # first present instance is representative
for r in rows:
    print(f'{r[0]:14} {r[1]} {r[2]:8} vs {r[3]:22} missing={r[4]:3} extra={r[5]:3}  e.g. -{r[6][:2]} +{r[7][:2]}')
print(len(rows), 'block(s) differ')
