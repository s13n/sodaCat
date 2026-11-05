import sys, re, xml.etree.ElementTree as ET, itertools
from pathlib import Path
from ruamel.yaml import YAML
D=Path(__file__).resolve().parents[2]/'build/_deps/stm32g5_svd_supplement-src/SVD'; M=Path(__file__).resolve().parents[2]/'models/ST'; y=YAML(typ='safe')
def load(c):
    r=ET.parse(D/f'{c}.svd').getroot(); return {p.findtext('name'):p for p in r.iter('peripheral')}
def svd_fields(P,name):
    pe=P[name]
    while pe.find('registers') is None and pe.get('derivedFrom'): pe=P[pe.get('derivedFrom')]
    out=[]
    def walk(node, base):
        for el in node:
            if el.tag=='cluster':
                dim=int(el.findtext('dim') or '1',0); inc=int(el.findtext('dimIncrement') or '0',0)
                for k in range(dim): walk(el, base+int(el.findtext('addressOffset'),0)+k*inc)
                continue
            if el.tag!='register': continue
            dim=int(el.findtext('dim') or '1',0); inc=int(el.findtext('dimIncrement') or '0',0)
            for k in range(dim):
                off=base+int(el.findtext('addressOffset'),0)+k*inc
                rn=re.sub(r'^\w+?_','',el.findtext('name')).replace('%s',str(k)) if '_' in el.findtext('name') else el.findtext('name')
                for f in el.iter('field'):
                    bo=f.findtext('bitOffset'); bw=f.findtext('bitWidth')
                    if bo is None: lsb,msb=int(f.findtext('lsb')),int(f.findtext('msb')); bo,bw=lsb,msb-lsb+1
                    out.append((off,rn,f.findtext('name'),int(bo),int(bw)))
    walk(pe.find('registers'),0); return out
def model_bits(m):
    out={}
    def walk(regs, base):
        for r in regs:
            dim=r.get('dim',1); inc=r.get('dimIncrement',0)
            dims=dim if isinstance(dim,list) else [dim]; incs=inc if isinstance(inc,list) else [inc]
            for ix in itertools.product(*[range(d) for d in dims]):
                off=base+r.get('addressOffset',0)+sum(i*s for i,s in zip(ix,incs))
                if 'registers' in r: walk(r['registers'], off)
                else:
                    for f in r.get('fields') or []: out[off]=out.get(off,0)|(((1<<f['bitWidth'])-1)<<f['bitOffset'])
    walk(m.get('registers') or [],0); return out
chips={'G544':load('STM32G544'),'G564':load('STM32G564')}
for spec in sys.argv[1:]:
    periph,model=spec.split('=')
    mb=model_bits(y.load(open(M/f'{model}.yaml')))
    for tag,P in chips.items():
        if periph not in P: continue
        miss=[(hex(o),r,n,bo,bw) for o,r,n,bo,bw in svd_fields(P,periph) if (((1<<bw)-1)<<bo) & ~mb.get(o,0)]
        regs={}
        for o,r,n,bo,bw in miss: regs.setdefault(f'{r}@{o}',[]).append(f'{n}[{bo}:{bw}]')
        print(f'{periph:8}->{model:10} {tag}: {len(miss)} missing', '; '.join(f"{k}: {' '.join(v[:5])}{'…' if len(v)>5 else ''}" for k,v in list(regs.items())[:6]))
