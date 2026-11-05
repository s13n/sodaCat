from pathlib import Path
exec(open(Path(__file__).with_name('gaps.py')).read().split("chips={'G544'")[0])
for c in ('STM32G544','STM32G564'):
    P=load(c); F=lambda n: svd_fields(P,n) if n in P else []
    names=lambda n: {f'{r}.{f}' for o,r,f,bo,bw in F(n)}
    print('==',c)
    x=names('XSPI1'); print(' XSPI CAL*:', sorted(r for r in {s.split('.')[0] for s in x} if r.startswith('CAL')), 'MAXTRAN:', [s for s in x if 'MAXTRAN' in s])
    i=names('IWDG'); print(' IWDG:', sorted(i))
    w=[(r,f,bo,bw) for o,r,f,bo,bw in F('WWDG') if f.startswith('WDGTB')]; print(' WWDG WDGTB:', w)
    u=names('USART1'); print(' USART1 AUTOCR:', [s for s in u if s.startswith('AUTOCR')][:3])
    l=names('LPTIM1'); print(' LPTIM COUNTRST:', [s for s in l if 'COUNTRST' in s or 'RSTARE' in s])
