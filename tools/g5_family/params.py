from pathlib import Path
import sys
exec(open(Path(__file__).with_name('gaps.py')).read().split("chips={'G544'")[0])
for c in ('STM32G544','STM32G564'):
    P=load(c); F=lambda n: svd_fields(P,n) if n in P else []
    def has(n, reg=None, field=None, off=None):
        for o,r,f,bo,bw in F(n):
            if (reg is None or r.endswith(reg)) and (field is None or f==field) and (off is None or o==off): return (bo,bw)
        return None
    regs=lambda n: sorted({(hex(o),r) for o,r,f,bo,bw in F(n)})
    print('=====',c)
    print('RNG: NSCR osc', [f for o,r,f,bo,bw in F('RNG') if r.endswith('NSCR')], 'HTCR1', bool(has('RNG',reg='HTCR1')), 'NSMR', bool(has('RNG',reg='NSMR')), 'CONFIG1', has('RNG',field='RNG_CONFIG1'), 'ARDIS', bool(has('RNG',field='ARDIS')), 'BUSY', bool(has('RNG',field='BUSY')))
    print('HASH: ALGO', has('HASH',field='ALGO'), 'HR16', bool(has('HASH',reg='HR16')), 'NBWP', has('HASH',field='NBWP'))
    print('PKA regs', regs('PKA')[:6])
    print('CRS TRIM', has('CRS',field='TRIM'))
    print('CRC: IDR', has('CRC',reg='IDR'), 'RTYPE', has('CRC',field='RTYPE_IN'))
    print('TAMP: CR2 bit0', [f for o,r,f,bo,bw in F('TAMP') if r.endswith('CR2') and bo==0], '@0x20', sorted({r for o,r,f,bo,bw in F('TAMP') if o==0x20}), '@0x50', [(f,bo,bw) for o,r,f,bo,bw in F('TAMP') if o==0x50], '@0x54', sorted({r for o,r,f,bo,bw in F('TAMP') if o==0x54}))
    print('RTC regs', [r for h,r in regs('RTC')])
    print('GPIO: HSLVR', bool(has('GPIOA',reg='HSLVR')), 'SECCFGR', bool(has('GPIOA',reg='SECCFGR')), 'BRR', bool(has('GPIOA',reg='BRR')))
    print('ICACHE CRR0', bool(has('ICACHE',reg='CRR0')))
    print('LPTIM: CCR2', bool(has('LPTIM1',reg='CCR2')), 'CFGR2', bool(has('LPTIM1',reg='CFGR2')), 'RCR', bool(has('LPTIM1',reg='RCR')), 'regs', [r for h,r in regs('LPTIM1')])
    print('VREFBUF VRS', has('VREFBUF',field='VRS'))
    print('USB: DDISC', bool(has('USB',field='DDISC')), 'DCD', bool(has('USB',field='DCDEN')))
    print('XSPI regs', len(regs('XSPI1')), 'DCR4' , bool(has('XSPI1',reg='DCR4')), 'HLCR', bool(has('XSPI1',reg='HLCR')), 'CR.MSEL', has('XSPI1',field='MSEL'))
    print('SPI I2SCFGR', {n: bool(has(n,reg='I2SCFGR')) for n in ('SPI1','SPI2','SPI3') if n in P})
    print('GPDMA channels', sorted({r[:2] for o,r,f,bo,bw in F('GPDMA1') if r.startswith('C') and r[1].isdigit()}), '2D(BR2)', sorted({r[:2] for o,r,f,bo,bw in F('GPDMA1') if r.endswith('BR2')}))
