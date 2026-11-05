import xml.etree.ElementTree as ET, re
from pathlib import Path
D=Path(__file__).resolve().parents[2]/'build/_deps/stm32g5_svd_supplement-src/SVD'
def load(c):
    r=ET.parse(D/f'{c}.svd').getroot(); return {p.findtext('name'):p for p in r.iter('peripheral')}
def lay(P,name):
    pe=P[name]
    while pe.find('registers') is None and pe.get('derivedFrom'): pe=P[pe.get('derivedFrom')]
    out=set()
    for el in pe.find('registers').iter('register'):
        off=el.findtext('addressOffset'); rn=re.sub(r'^'+re.escape(name.rstrip('0123456789'))+r'\d*_','',el.findtext('name'))
        for f in el.iter('field'):
            out.add((int(off,0), rn, f.findtext('name'), f.findtext('bitOffset'), f.findtext('bitWidth')))
        out.add((int(off,0), rn, None, None, None))
    return out
A=load('STM32G544'); B=load('STM32G564'); A2=load('STM32G534'); B2=load('STM32G553')
for n in sorted(set(A)&set(B)):
    if n.endswith('_S'): continue
    a,b=lay(A,n),lay(B,n)
    if a!=b:
        regs_a={x[1] for x in a}; regs_b={x[1] for x in b}
        print(f'{n:14} differs: G544-only regs {sorted(regs_a-regs_b)[:6]} G564-only regs {sorted(regs_b-regs_a)[:8]} fielddiffs {len(a^b)}')
print('--- within die: G534 vs G544, G553 vs G564')
for X,Y,tag in ((A2,A,'534/544'),(B2,B,'553/564')):
    for n in sorted(set(X)&set(Y)):
        if n.endswith('_S'): continue
        if lay(X,n)!=lay(Y,n): print(f'  {tag} {n} differs ({len(lay(X,n)^lay(Y,n))})')
