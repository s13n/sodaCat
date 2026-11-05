"""Derive TimerV2 parameter values for every G5 timer instance from its SVD fields."""
import sys
from pathlib import Path
__file__ = str(Path(__file__).with_name('gaps.py')); sys.argv = ['x']
exec(open(__file__).read().split("chips={'G544'")[0])
P = load('STM32G564')
def fields(n): return {(r.split('_', 1)[-1] if '_' in r else r, f): (bo, bw) for o, r, f, bo, bw in svd_fields(P, n)}
def has(F, reg, f): return any(k[1] == f and k[0].startswith(reg) for k in F)
defaults = dict(width32=False, max_channel=3, has_centerPWM=True, encoder=0, has_xor_input=True, has_etr=True,
                has_dma_burst=True, has_complementary=False, has_dither=True, sms_preload=0, has_uifremap=False,
                has_extended_ocm=False, has_mms2=False, gen=0)
for n in ['TIM1','TIM2','TIM3','TIM4','TIM5','TIM8','TIM9','TIM10','TIM11','TIM12','TIM13','TIM14','TIM15','TIM16','TIM17','TIM20']:
    F = fields(n); regs = {k[0] for k in F}
    v = {}
    v['width32'] = F.get(('CNT', 'CNT'), (0, 16))[1] >= 31
    v['max_channel'] = max(int(r[3:]) for r in regs if r.startswith('CCR') and r[3:].isdigit()) - 1
    v['has_centerPWM'] = has(F, 'CR1', 'CMS')
    v['encoder'] = 3 if has(F, 'ECR', 'IBLK') else 2 if 'ECR' in regs else 1 if has(F, 'SMCR', 'SMS') else 0
    v['has_xor_input'] = has(F, 'CR2', 'TI1S')
    v['has_etr'] = has(F, 'SMCR', 'ETF')
    v['has_dma_burst'] = 'DCR' in regs
    v['has_complementary'] = 'BDTR' in regs
    v['has_dither'] = has(F, 'CR1', 'DITHEN')
    v['sms_preload'] = 2 if has(F, 'SMCR', 'SMSPS') else 1 if has(F, 'SMCR', 'SMSPE') else 0
    v['has_uifremap'] = has(F, 'CR1', 'UIFREMAP')
    v['has_extended_ocm'] = any(k[1] == 'OC1M_1' for k in F)
    v['has_mms2'] = has(F, 'CR2', 'MMS2')
    v['gen'] = 1
    diff = {k: x for k, x in v.items() if defaults[k] != x}
    print(f'{n}: ' + '{' + ', '.join(f'{k}: {str(x).lower()}' for k, x in diff.items()) + '}')
