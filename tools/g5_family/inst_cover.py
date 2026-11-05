from pathlib import Path
import sys
sys.argv=['x']; exec(open(Path(__file__).with_name('gaps.py')).read().split("chips={'G544'")[0])
P=load('STM32G564')
def bits(P,n):
    b={}
    for o,r,f,bo,bw in svd_fields(P,n): b[o]=b.get(o,0)|(((1<<bw)-1)<<bo)
    return b
for sup,sub in (('TIM9','TIM10'),('TIM15','TIM16'),('TIM1','TIM2'),('TIM2','TIM9'),('TIM1','TIM15')):
    A,B=bits(P,sup),bits(P,sub)
    miss=[(o,r,f) for o,r,f,bo,bw in svd_fields(P,sub) if (((1<<bw)-1)<<bo) & ~A.get(o,0)]
    print(f'{sup} covers {sub}? missing {len(miss)}:', [f'{r}.{f}' for o,r,f in miss][:10])
