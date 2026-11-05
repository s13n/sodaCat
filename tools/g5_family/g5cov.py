import sys, re, itertools, xml.etree.ElementTree as ET
from pathlib import Path
from ruamel.yaml import YAML
y=YAML(typ='safe'); ROOT=Path(__file__).resolve().parents[2]; D=ROOT/'build/_deps/stm32g5_svd_supplement-src/SVD'
def model_bits(path):
    m=y.load(open(path)); out={}
    def walk(regs, base):
        for r in regs:
            dim=r.get('dim',1); inc=r.get('dimIncrement',0)
            dims=dim if isinstance(dim,list) else [dim]; incs=inc if isinstance(inc,list) else [inc]
            for ix in itertools.product(*[range(d) for d in dims]):
                off=base+r.get('addressOffset',0)+sum(i*s for i,s in zip(ix,incs))
                if 'registers' in r: walk(r['registers'], off)
                else:
                    for f in r.get('fields') or []: out[off]=out.get(off,0)|(((1<<f['bitWidth'])-1)<<f['bitOffset'])
    walk(m['registers'],0); return out
def svd_fields(P,name):
    pe=P[name]
    while pe.find('registers') is None and pe.get('derivedFrom'): pe=P[pe.get('derivedFrom')]
    out=[]
    for el in pe.find('registers').iter('register'):
        dim=int(el.findtext('dim') or '1',0); inc=int(el.findtext('dimIncrement') or '0',0)
        for k in range(dim):
            off=int(el.findtext('addressOffset'),0)+k*inc
            for f in el.iter('field'):
                bo=f.findtext('bitOffset'); bw=f.findtext('bitWidth')
                if bo is None: lsb,msb=int(f.findtext('lsb')),int(f.findtext('msb')); bo,bw=lsb,msb-lsb+1
                out.append((off,el.findtext('name'),f.findtext('name'),int(bo),int(bw)))
    return out
cache={}; gaps={}; tot=ok=0
for cp in sorted((ROOT/'models/ST/G5').rglob('STM32G5*.yaml')):
    chip=y.load(open(cp)); name=chip['name']
    P={p.findtext('name'):p for p in ET.parse(D/f'{name}.svd').getroot().iter('peripheral')}
    rev={}  # canonical instance -> svd name (rename_instances)
    for inst,info in chip['instances'].items():
        svdname = inst if inst in P else {'LPUART1':'LPUART','LPUART1_S':'LPUART_S'}.get(inst)
        if svdname not in P: continue
        mp=chip['models'][info['model']]
        mb=cache.setdefault(mp, model_bits(ROOT/'models'/f'{mp}.yaml'))
        miss=[(r,f) for o,r,f,bo,bw in svd_fields(P,svdname) if (((1<<bw)-1)<<bo) & ~mb.get(o,0)]
        tot+=1
        if miss: gaps.setdefault(mp,{}).setdefault(name,[]).append((inst,len(miss),miss[:4]))
        else: ok+=1
print(f'G5: {ok}/{tot} chip instances fully covered')
for mp,per in sorted(gaps.items()):
    insts=sorted({i for v in per.values() for i,_,_ in v if not i.endswith('_S')})
    ex=next(iter(per.values()))[0]
    print(f'  {mp:22} chips={len(per)} insts={",".join(insts)[:60]}  e.g. {ex[0]} -{ex[1]}: {ex[2]}')
