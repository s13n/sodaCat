from pathlib import Path
import sys, re
sys.argv=['x']; exec(open(Path(__file__).with_name('gaps.py')).read().split("chips={'G544'")[0])
P=load('STM32G564')
m=y.load(open(M/'TimerV2.yaml'))
def mfields(m):
    out={}
    def walk(regs, base):
        for r in regs:
            if 'registers' in r: walk(r['registers'], base+r.get('addressOffset',0)); continue
            o=base+r.get('addressOffset',0)
            for f in r.get('fields') or []: out.setdefault(o,[]).append((r['name'],f['name'],f['bitOffset'],f['bitWidth']))
    walk(m['registers'],0); return out
MF=mfields(m)
bits=lambda bo,bw: set(range(bo,bo+bw))
for inst in sys.argv[1:] or ['TIM1','TIM2','TIM15','TIM16','TIM9','TIM10']:
    pass
for inst in ['TIM1','TIM2','TIM15','TIM16','TIM9','TIM10']:
    kinds={'add':[], 'rename':[], 'widen':[], 'conflict':[]}
    for o,rn,n,bo,bw in svd_fields(P,inst):
        mf=MF.get(o,[])
        b=bits(bo,bw)
        ov=[x for x in mf if bits(x[2],x[3])&b]
        if not ov: kinds['add'].append(f'{rn}.{n}'); continue
        if len(ov)==1 and bits(ov[0][2],ov[0][3])==b:
            if ov[0][1]!=n: kinds['rename'].append(f'{rn}.{n}|{ov[0][1]}')
            continue
        if all(bits(x[2],x[3])<=b for x in ov) and len(ov)==1 and ov[0][2]==bo: kinds['widen'].append(f'{rn}.{n} {ov[0][1]}[{ov[0][3]}]->{bw}'); continue
        if all(bits(x[2],x[3])<=b for x in ov) and set().union(*[bits(x[2],x[3]) for x in ov])==b: continue
        if len(ov)==1 and b<=bits(ov[0][2],ov[0][3]): continue
        kinds['conflict'].append(f'{rn}.{n}[{bo}:{bw}] vs '+','.join(f'{x[0]}.{x[1]}[{x[2]}:{x[3]}]' for x in ov))
    print(f'== {inst}: add {len(kinds["add"])}, rename {len(kinds["rename"])}, widen {len(kinds["widen"])}, conflict {len(kinds["conflict"])}')
    for k in ('conflict','widen'):
        for x in kinds[k][:12]: print('   ',k,x)
