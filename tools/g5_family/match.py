import sys, re, glob, xml.etree.ElementTree as ET
from pathlib import Path
from ruamel.yaml import YAML
D=Path(__file__).resolve().parents[2]/'build/_deps/stm32g5_svd_supplement-src/SVD'; M=Path(__file__).resolve().parents[2]/'models/ST'
y=YAML(typ='safe')
def svd_bits(pe, P):
    while pe.find('registers') is None and pe.get('derivedFrom'): pe=P[pe.get('derivedFrom')]
    out={}
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
                for f in el.iter('field'):
                    bo=f.findtext('bitOffset'); bw=f.findtext('bitWidth')
                    if bo is None: lsb,msb=int(f.findtext('lsb')),int(f.findtext('msb')); bo,bw=lsb,msb-lsb+1
                    out[off]=out.get(off,0)|(((1<<int(bw))-1)<<int(bo))
    if pe.find('registers') is not None: walk(pe.find('registers'),0)
    return out
def model_bits(m):
    out={}
    def walk(regs, base):
        for r in regs:
            dim=r.get('dim',1); inc=r.get('dimIncrement',0)
            dims=dim if isinstance(dim,list) else [dim]; incs=inc if isinstance(inc,list) else [inc]
            import itertools
            for ix in itertools.product(*[range(d) for d in dims]):
                off=base+r.get('addressOffset',0)+sum(i*s for i,s in zip(ix,incs))
                if 'registers' in r: walk(r['registers'], off)
                else:
                    for f in r.get('fields') or []: out[off]=out.get(off,0)|(((1<<f['bitWidth'])-1)<<f['bitOffset'])
    walk(m.get('registers') or [],0); return out
models={}
for p in M.rglob('*.yaml'):
    try: d=y.load(open(p))
    except Exception: continue
    if isinstance(d,dict) and d.get('registers'): models[str(p.relative_to(M))[:-5]]=model_bits(d)
chip=sys.argv[1]; r=ET.parse(D/f'{chip}.svd').getroot(); P={p.findtext('name'):p for p in r.iter('peripheral')}
pc=lambda x: bin(x).count('1')
seen={}
for name,pe in P.items():
    if name.endswith('_S'): continue
    s=svd_bits(pe,P); tot=sum(pc(v) for v in s.values())
    if tot==0: print(f'{name:14} (no fields)'); continue
    key=tuple(sorted(s.items()))
    if key in seen: print(f'{name:14} = {seen[key]}'); continue
    seen[key]=name
    sc=[]
    for mn,mb in models.items():
        cov=sum(pc(v & mb.get(o,0)) for o,v in s.items())/tot
        extra=sum(pc(v & ~s.get(o,0)) for o,v in mb.items())
        sc.append((cov,-extra,mn,extra))
    sc.sort(reverse=True)
    best=sc[:3]
    print(f'{name:14} bits={tot:5} ' + ' | '.join(f'{mn} {cov:.0%} +{ex}' for cov,_,mn,ex in best))
