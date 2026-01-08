import sys
import os
import tempfile
p = os.path.abspath("./tools")
sys.path.append(p)
from urllib.request import urlretrieve
import svd
import transform
from pathlib import Path

subdir = Path("./models/ST/H757")

# models and instances we want to keep
modelSet = frozenset({'ADC', 'ADC_Common', 'ART', 'BDMA', 'RCC', 'DAC', 'DMA', 'DMAMUX1', 'DMAMUX2', 'EXTI', 'GPIO', 'I2C',
    'MDMA', 'SAI', 'SPDIFRX', 'SYSCFG', 'BasicTimer', 'GpTimer', 'AdvCtrlTimer', 'LPTIM', 'LPTIMenc', 'USART', 'LPUART',
    'QUADSPI', 'OPAMP', 'DFSDM', 'SPI', 'RTC', 'FMC', 'PWR', 'DBGMCU', 'Flash'})
instSet = frozenset({'MDMA', 'DMA1', 'DMA2', 'BDMA', 'DMAMUX1', 'DMAMUX2', 'RCC', 'ART', 'DBGMCU', 'Flash',
    'ADC1', 'ADC2', 'ADC3', 'ADC3_Common', 'ADC12_Common', 'DAC', 'EXTI', 'SYSCFG',
    'I2C1', 'I2C2', 'I2C3', 'I2C4', 'SAI1', 'SAI2', 'SAI3', 'SAI4', 'SPDIFRX',
    'TIM1', 'TIM2', 'TIM3', 'TIM4', 'TIM5', 'TIM6', 'TIM7', 'TIM8', 'TIM12', 'TIM13', 'TIM14', 'TIM15', 'TIM16', 'TIM17',
    'LPTIM1', 'LPTIM2', 'LPTIM3', 'LPTIM4', 'LPTIM5',
    'GPIOA', 'GPIOB', 'GPIOC', 'GPIOD', 'GPIOE', 'GPIOF', 'GPIOG', 'GPIOH', 'GPIOI', 'GPIOJ', 'GPIOK',
    'USART1', 'USART2', 'USART3', 'UART4', 'UART5', 'USART6', 'UART7', 'UART8', 'LPUART1',
    'QUADSPI', 'OPAMP', 'DFSDM', 'SPI1', 'SPI2', 'SPI3', 'SPI4', 'SPI5', 'SPI6', 'RTC', 'FMC', 'PWR'})

### Read the svd file and do the standard processing on it.

svdpath = './svd/STM32H757_CM4.svd'
header = "# Created from STM32H757_CM4.svd (Rev 1.9)\n"
root = svd.parse(svdpath)
chip = svd.collateDevice(root)

### Tweak the data to fix various problems

# Tweak the ADC naming
adc12common = svd.findNamedEntry(chip['peripherals'], 'ADC12_Common')
transform.renameEntries(adc12common['interrupts'], 'name', 'ADC1_2', 'ADC')
adc3common = svd.findNamedEntry(chip['peripherals'], 'ADC3_Common')
adc3common['headerStructName'] = 'ADC_Common'
adc3 = svd.findNamedEntry(chip['peripherals'], 'ADC3')
adc3['headerStructName'] = 'ADC'
transform.renameEntries(adc3['interrupts'], 'name', 'ADC3', 'ADC')
transform.renameEntries(adc3['interrupts'], 'description', 'ADC3', 'ADC')
adc3common['interrupts'] = adc3.pop('interrupts')   # for uniformity with ADC12

# Convert the register set for the MDMA channels into an array
mdma = svd.findNamedEntry(chip['peripherals'], 'MDMA')
mdma['registers'] = transform.createClusterArray(mdma['registers'], r"MDMA_C(\d+)(.+)", {'name': 'C', 'description': 'MDMA channel'})
transform.renameEntries(mdma['registers'], 'name', 'MDMA_GISR0', 'GISR0')
transform.renameEntries(mdma['registers'], 'displayName', 'MDMA_GISR0', 'GISR0')

# Convert the register set for the BDMA channels into an array
bdma = svd.findNamedEntry(chip['peripherals'], 'BDMA')
transform.renameEntries(bdma['registers'], 'name', r'BDMA_([A-Z_0-9]+)', r'\1')
transform.renameEntries(bdma['registers'], 'displayName', r'BDMA_([A-Z_0-9]+)', r'\1')
bdma['registers'] = transform.createClusterArray(bdma['registers'], r"C(.+?)(\d+)$", {'name': 'C', 'description': 'BDMA channel'})
transform.renameEntries(bdma['interrupts'], 'name', r'BDMA_([A-Z_0-9]+)', r'\1')

# Convert the register set for the DMA channels into an array
dma1 = svd.findNamedEntry(chip['peripherals'], 'DMA1')
dma1['headerStructName'] = 'DMA'
dma2 = svd.findNamedEntry(chip['peripherals'], 'DMA2')
dma1['registers'] = transform.createClusterArray(dma1['registers'], r"S(\d+)(.+)", {'name': 'S', 'description': 'DMA stream'})
transform.renameEntries(dma1['interrupts'], 'name', r'[A-Z0-9]+_([A-Z_0-9]+)', r'\1')
transform.renameEntries(dma2['interrupts'], 'name', r'[A-Z0-9]+_([A-Z_0-9]+)', r'\1')

# Tweak the I2C naming
i2c1 = svd.findNamedEntry(chip['peripherals'], 'I2C1')
i2c1['headerStructName'] = 'I2C'
transform.renameEntries(i2c1['interrupts'], 'name', r'I2C1_([A-Z_0-9]+)', r'\1')
transform.renameEntries(i2c1['interrupts'], 'description', 'I2C1', 'I2C')
i2c2 = svd.findNamedEntry(chip['peripherals'], 'I2C2')
transform.renameEntries(i2c2['interrupts'], 'name', r'I2C2_([A-Z_0-9]+)', r'\1')
i2c3 = svd.findNamedEntry(chip['peripherals'], 'I2C3')
transform.renameEntries(i2c3['interrupts'], 'name', r'I2C3_([A-Z_0-9]+)', r'\1')
i2c4 = svd.findNamedEntry(chip['peripherals'], 'I2C4')
transform.renameEntries(i2c4['interrupts'], 'name', r'I2C4_([A-Z_0-9]+)', r'\1')

# Tweak the SAI ports
sai4 = svd.findNamedEntry(chip['peripherals'], 'SAI4')
sai4['headerStructName'] = 'SAI'
transform.renameEntries(sai4['interrupts'], 'name', 'SAI4', 'SAI')
transform.renameEntries(sai4['interrupts'], 'description', 'SAI4', 'SAI')
sai1 = svd.findNamedEntry(chip['peripherals'], 'SAI1')
transform.renameEntries(sai1['interrupts'], 'name', 'SAI1', 'SAI')
sai2 = svd.findNamedEntry(chip['peripherals'], 'SAI2')
transform.renameEntries(sai2['interrupts'], 'name', 'SAI2', 'SAI')
sai3 = svd.findNamedEntry(chip['peripherals'], 'SAI3')
transform.renameEntries(sai3['interrupts'], 'name', 'SAI3', 'SAI')

# Tweak the TIM1 & TIM8
tim1 = svd.findNamedEntry(chip['peripherals'], 'TIM1')
tim1['headerStructName'] = 'AdvCtrlTimer'
transform.renameEntries(tim1['interrupts'], 'name', r'TIM\d?_([A-Z_0-9]+)', r'\1')
transform.renameEntries(tim1['interrupts'], 'description', 'TIM1', 'TIM')
tim8 = svd.findNamedEntry(chip['peripherals'], 'TIM8')
transform.renameEntries(tim8['interrupts'], 'name', r'TIM8_([0-9_A-Z]+)', r'\1')
transform.renameEntries(tim8['interrupts'], 'name', r'([_A-Z]+)_TIM\d+', r'\1')

# Tweak the TIM2, TIM3, TIM4, TIM5, TIM12, TIM13, TIM14, TIM15, TIM16 and TIM17
tim2 = svd.findNamedEntry(chip['peripherals'], 'TIM2')
tim2['headerStructName'] = 'GpTimer'
transform.renameEntries(tim2['interrupts'], 'name', 'TIM2', 'TIM')
transform.renameEntries(tim2['interrupts'], 'description', 'TIM2', 'TIM')
tim2['parameters'] = [
    { 'name': 'wide',     'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Counter is 32-bit' },
    { 'name': 'chan_max', 'value': 3, 'bits': 2, 'min': 0, 'max': 3, 'description': 'Index of last capture/compare channel' },
    { 'name': 'rep',      'value': 0, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Repetition counter present' },
    { 'name': 'compl1',   'value': 0, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Complementary output on first channel' },
    { 'name': 'bkin',     'value': 0, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Break input supported' },
    { 'name': 'trigger',  'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Trigger events supported' },
    { 'name': 'encoder',  'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Quadrature encoder support' },
]
tim3pars = [('wide', 0), ('chan_max', 3), ('rep', 0), ('compl1', 0), ('bkin', 0), ('trigger', 1), ('encoder', 1)]
tim5pars = [('wide', 1), ('chan_max', 3), ('rep', 0), ('compl1', 0), ('bkin', 0), ('trigger', 1), ('encoder', 1)]
tim12pars = [('wide', 0), ('chan_max', 1), ('rep', 0), ('compl1', 0), ('bkin', 0), ('trigger', 1), ('encoder', 0)]
tim13pars = [('wide', 0), ('chan_max', 0), ('rep', 0), ('compl1', 0), ('bkin', 0), ('trigger', 0), ('encoder', 0)]
tim15pars = [('wide', 0), ('chan_max', 1), ('rep', 1), ('compl1', 1), ('bkin', 1), ('trigger', 1), ('encoder', 0)]
tim16pars = [('wide', 0), ('chan_max', 0), ('rep', 1), ('compl1', 1), ('bkin', 1), ('trigger', 0), ('encoder', 0)]

tim3 = svd.findNamedEntry(chip['peripherals'], 'TIM3')
tim3['parameters'] = [{'name': n, 'value': v} for n,v in tim3pars]
transform.renameEntries(tim3['interrupts'], 'name', 'TIM3', 'TIM')
transform.renameEntries(tim3['interrupts'], 'description', 'TIM3', 'TIM')

tim4 = svd.findNamedEntry(chip['peripherals'], 'TIM4')
tim4['parameters'] = [{'name': n, 'value': v} for n,v in tim3pars]
transform.renameEntries(tim4['interrupts'], 'name', 'TIM4', 'TIM')
transform.renameEntries(tim4['interrupts'], 'description', 'TIM4', 'TIM')

tim5 = svd.findNamedEntry(chip['peripherals'], 'TIM5')
tim5['parameters'] = [{'name': n, 'value': v} for n,v in tim5pars]
transform.renameEntries(tim5['interrupts'], 'name', 'TIM5', 'TIM')
transform.renameEntries(tim5['interrupts'], 'description', 'TIM5', 'TIM')

tim12 = svd.findNamedEntry(chip['peripherals'], 'TIM12')
tim12['parameters'] = [{'name': n, 'value': v} for n,v in tim12pars]
tim12['interrupts'] = [{ 'name': 'TIM', 'description': 'TIM global interrupt' }]
tim12['interrupts'][0]['value'] = svd.findNamedEntry(tim8['interrupts'], 'BRK')['value']

tim13 = svd.findNamedEntry(chip['peripherals'], 'TIM13')
tim13['parameters'] = [{'name': n, 'value': v} for n,v in tim13pars]
tim13['interrupts'] = [{ 'name': 'TIM', 'description': 'TIM global interrupt' }]
tim13['interrupts'][0]['value'] = svd.findNamedEntry(tim8['interrupts'], 'UP')['value']

tim14 = svd.findNamedEntry(chip['peripherals'], 'TIM14')
tim14['parameters'] = [{'name': n, 'value': v} for n,v in tim13pars]
tim14['interrupts'] = [{ 'name': 'TIM', 'description': 'TIM global interrupt' }]
tim14['interrupts'][0]['value'] = svd.findNamedEntry(tim8['interrupts'], 'TRG_COM')['value']

#TODO: The timers 15-17 have some registers that are missing in TIM2, so we need to fix the model

tim15 = svd.findNamedEntry(chip['peripherals'], 'TIM15')
tim15['@derivedFrom'] = 'TIM2'
tim15['parameters'] = [{'name': n, 'value': v} for n,v in tim15pars]
transform.renameEntries(tim15['interrupts'], 'name', 'TIM15', 'TIM')
transform.renameEntries(tim15['interrupts'], 'description', 'TIM15', 'TIM')

tim16 = svd.findNamedEntry(chip['peripherals'], 'TIM16')
tim16['@derivedFrom'] = 'TIM2'
tim16['parameters'] = [{'name': n, 'value': v} for n,v in tim16pars]
transform.renameEntries(tim16['interrupts'], 'name', 'TIM16', 'TIM')
transform.renameEntries(tim16['interrupts'], 'description', 'TIM16', 'TIM')

tim17 = svd.findNamedEntry(chip['peripherals'], 'TIM17')
tim17['@derivedFrom'] = 'TIM2'
tim17['parameters'] = [{'name': n, 'value': v} for n,v in tim16pars]
transform.renameEntries(tim17['interrupts'], 'name', 'TIM17', 'TIM')
transform.renameEntries(tim17['interrupts'], 'description', 'TIM17', 'TIM')

# Tweak the TIM6 & TIM7
tim6 = svd.findNamedEntry(chip['peripherals'], 'TIM6')
tim6['headerStructName'] = 'BasicTimer'
transform.renameEntries(tim6['interrupts'], 'name', 'TIM6_DAC', 'TIM')
transform.renameEntries(tim6['interrupts'], 'description', 'TIM6', 'TIM')
tim7 = svd.findNamedEntry(chip['peripherals'], 'TIM7')
transform.renameEntries(tim7['interrupts'], 'name', 'TIM7', 'TIM')
transform.renameEntries(tim7['interrupts'], 'description', 'TIM7', 'TIM')

# Tweak the LPTIM instances
lptim1 = svd.findNamedEntry(chip['peripherals'], 'LPTIM1')
lptim1['headerStructName'] = 'LPTIMenc'
transform.renameEntries(lptim1['interrupts'], 'description', 'LPTIM1', 'LPTIM')
transform.renameEntries(lptim1['interrupts'], 'name', 'LPTIM1', 'LPTIM')
lptim2 = svd.findNamedEntry(chip['peripherals'], 'LPTIM2')
transform.renameEntries(lptim2['interrupts'], 'name', 'LPTIM2', 'LPTIM')
lptim3 = svd.findNamedEntry(chip['peripherals'], 'LPTIM3')
lptim3['headerStructName'] = 'LPTIM'
transform.renameEntries(lptim3['interrupts'], 'description', 'LPTIM3', 'LPTIM')
transform.renameEntries(lptim3['interrupts'], 'name', 'LPTIM3', 'LPTIM')
lptim4 = svd.findNamedEntry(chip['peripherals'], 'LPTIM4')
transform.renameEntries(lptim4['interrupts'], 'name', 'LPTIM4', 'LPTIM')
lptim5 = svd.findNamedEntry(chip['peripherals'], 'LPTIM5')
transform.renameEntries(lptim5['interrupts'], 'name', 'LPTIM5', 'LPTIM')

# Tweak the USARTs
usart1 = svd.findNamedEntry(chip['peripherals'], 'USART1')
usart1['headerStructName'] = 'USART'
transform.renameEntries(usart1['interrupts'], 'description', 'USART1', 'USART')
transform.renameEntries(usart1['interrupts'], 'name', 'USART1', 'USART')
usart1['parameters'] = [
    { 'name': 'syncmode',  'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Synchronous mode (Master/Slave)' },
    { 'name': 'smartcard', 'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Smartcard mode' },
    { 'name': 'irdaSIR',   'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'IrDA SIR ENDEC block' },
    { 'name': 'lin',       'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'LIN mode' },
    { 'name': 'rxTimeout', 'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Receiver timeout interrupt' },
    { 'name': 'modbus',    'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Modbus communication' },
    { 'name': 'autobaud',  'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Auto baud rate detection' },
    { 'name': 'prescaler', 'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Prescaler' },
    { 'name': 'lpbaud',    'value': 0, 'bits': 1, 'min': 0, 'max': 1, 'description': 'BRR has 20-bit LPUART format' },
]
usartpars =  [('syncmode', 1), ('smartcard', 1), ('irdaSIR', 1), ('lin', 1), ('rxTimeout', 1), ('modbus', 1), ('autobaud', 1), ('prescaler', 1), ('lpbaud', 0)]
uartpars =   [('syncmode', 0), ('smartcard', 0), ('irdaSIR', 1), ('lin', 1), ('rxTimeout', 1), ('modbus', 1), ('autobaud', 1), ('prescaler', 1), ('lpbaud', 0)]
lpuartpars = [('syncmode', 0), ('smartcard', 0), ('irdaSIR', 0), ('lin', 0), ('rxTimeout', 0), ('modbus', 0), ('autobaud', 0), ('prescaler', 1), ('lpbaud', 1)]

usart2 = svd.findNamedEntry(chip['peripherals'], 'USART2')
transform.renameEntries(usart2['interrupts'], 'name', 'USART2', 'USART')
usart2['parameters'] = [{'name': n, 'value': v} for n,v in usartpars]

usart3 = svd.findNamedEntry(chip['peripherals'], 'USART3')
transform.renameEntries(usart3['interrupts'], 'name', 'USART3', 'USART')
usart3['parameters'] = [{'name': n, 'value': v} for n,v in usartpars]

usart4 = svd.findNamedEntry(chip['peripherals'], 'UART4')
transform.renameEntries(usart4['interrupts'], 'name', 'UART4', 'USART')
usart4['parameters'] = [{'name': n, 'value': v} for n,v in uartpars]

usart5 = svd.findNamedEntry(chip['peripherals'], 'UART5')
transform.renameEntries(usart5['interrupts'], 'name', 'UART5', 'USART')
usart5['parameters'] = [{'name': n, 'value': v} for n,v in uartpars]

usart6 = svd.findNamedEntry(chip['peripherals'], 'USART6')
transform.renameEntries(usart6['interrupts'], 'name', 'USART6', 'USART')
usart6['parameters'] = [{'name': n, 'value': v} for n,v in usartpars]

usart7 = svd.findNamedEntry(chip['peripherals'], 'UART7')
transform.renameEntries(usart7['interrupts'], 'name', 'UART7', 'USART')
usart7['parameters'] = [{'name': n, 'value': v} for n,v in uartpars]

usart8 = svd.findNamedEntry(chip['peripherals'], 'UART8')
transform.renameEntries(usart8['interrupts'], 'name', 'UART8', 'USART')
usart8['parameters'] = [{'name': n, 'value': v} for n,v in uartpars]

lpuart1 = svd.findNamedEntry(chip['peripherals'], 'LPUART1')
lpuart1['@derivedFrom'] = 'USART1'
transform.renameEntries(lpuart1['interrupts'], 'name', 'LPUART', 'USART')
lpuart1['parameters'] = [{'name': n, 'value': v} for n,v in lpuartpars]

# Tweak the SPI ports
spi1 = svd.findNamedEntry(chip['peripherals'], 'SPI1')
spi1['headerStructName'] = 'SPI'
transform.renameEntries(spi1['interrupts'], 'name', 'SPI1', 'SPI')
transform.renameEntries(spi1['interrupts'], 'description', 'SPI1', 'SPI')
spi1['parameters'] = [
    { 'name': 'i2smode', 'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'I2S mode support' },
    { 'name': 'width32', 'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': '32 bit data size support' },
]
spi2pars = [('i2smode', 1), ('width32', 1)]
spi4pars = [('i2smode', 0), ('width32', 0)]

spi2 = svd.findNamedEntry(chip['peripherals'], 'SPI2')
transform.renameEntries(spi2['interrupts'], 'name', 'SPI2', 'SPI')
spi2['parameters'] = [{'name': n, 'value': v} for n,v in spi2pars]

spi3 = svd.findNamedEntry(chip['peripherals'], 'SPI3')
transform.renameEntries(spi3['interrupts'], 'name', 'SPI3', 'SPI')
spi3['parameters'] = [{'name': n, 'value': v} for n,v in spi2pars]

spi4 = svd.findNamedEntry(chip['peripherals'], 'SPI4')
transform.renameEntries(spi4['interrupts'], 'name', 'SPI4', 'SPI')
spi4['parameters'] = [{'name': n, 'value': v} for n,v in spi4pars]

spi5 = svd.findNamedEntry(chip['peripherals'], 'SPI5')
transform.renameEntries(spi5['interrupts'], 'name', 'SPI5', 'SPI')
spi5['parameters'] = [{'name': n, 'value': v} for n,v in spi4pars]

spi6 = svd.findNamedEntry(chip['peripherals'], 'SPI6')
transform.renameEntries(spi6['interrupts'], 'name', 'SPI6', 'SPI')
spi6['parameters'] = [{'name': n, 'value': v} for n,v in spi4pars]

# Tweak the DAC (get the interrupt number from TIM6)
dac = svd.findNamedEntry(chip['peripherals'], 'DAC')
dac['headerStructName'] = 'DAC'
dac['interrupts'] = [{ 'name': 'DAC', 'description': 'DAC underrun' }]
dac['interrupts'][0]['value'] = svd.findNamedEntry(tim6['interrupts'], 'TIM')['value']

# Tweak the GPIO naming
gpioa = svd.findNamedEntry(chip['peripherals'], 'GPIOA')
gpioa['headerStructName'] = 'GPIO'
gpioa['parameters'] = [
    { 'name': 'pins', 'value': 0b1111111111111111, 'bits': 16, 'min': 0, 'max': 0xFFFF, 'description': 'pins present' },
]
gpiopars = [('pins', 0b1111111111111111)]
gpiob = svd.findNamedEntry(chip['peripherals'], 'GPIOB')
gpiob['parameters'] = [{'name': n, 'value': v} for n,v in gpiopars]
gpioc = svd.findNamedEntry(chip['peripherals'], 'GPIOC')
gpioc['parameters'] = [{'name': n, 'value': v} for n,v in gpiopars]
gpiod = svd.findNamedEntry(chip['peripherals'], 'GPIOD')
gpiod['parameters'] = [{'name': n, 'value': v} for n,v in gpiopars]
gpioe = svd.findNamedEntry(chip['peripherals'], 'GPIOE')
gpioe['parameters'] = [{'name': n, 'value': v} for n,v in gpiopars]
gpiof = svd.findNamedEntry(chip['peripherals'], 'GPIOF')
gpiof['parameters'] = [{'name': n, 'value': v} for n,v in gpiopars]
gpiog = svd.findNamedEntry(chip['peripherals'], 'GPIOG')
gpiog['parameters'] = [{'name': n, 'value': v} for n,v in gpiopars]
gpioh = svd.findNamedEntry(chip['peripherals'], 'GPIOH')
gpioh['parameters'] = [{'name': n, 'value': v} for n,v in gpiopars]
gpioi = svd.findNamedEntry(chip['peripherals'], 'GPIOI')
gpioi['parameters'] = [{'name': n, 'value': v} for n,v in gpiopars]
gpioj = svd.findNamedEntry(chip['peripherals'], 'GPIOJ')
gpioj['parameters'] = [{'name': n, 'value': v} for n,v in gpiopars]
gpiok = svd.findNamedEntry(chip['peripherals'], 'GPIOK')
gpiok['parameters'] = [{'name': 'pins', 'value': 0b11111111}]

# Tweak the EXTI
exti = svd.findNamedEntry(chip['peripherals'], 'EXTI')
transform.renameEntries(exti['interrupts'], 'description', r'(?s:.)*(M7 Send)', r'\1')

# Tweak the DFSDM
dfsdm = svd.findNamedEntry(chip['peripherals'], 'DFSDM')
transform.renameEntries(dfsdm['interrupts'], 'name', r'DFSDM1_([0-9_A-Z]+)', r'\1')
transform.renameEntries(dfsdm['interrupts'], 'description', 'DFSDM1', 'DFSDM')
dfsdm['registers'] = transform.createClusterArray(dfsdm['registers'], r"CH(\d+)(.+?)$", {'name': 'CH', 'description': 'DFSDM channel'})
dfsdm['registers'] = transform.createClusterArray(dfsdm['registers'], r"DFSDM_FLT(\d+)(.+?)$", {'name': 'FLT', 'description': 'DFSDM filter'})

# Tweak the QUADSPI
quadspi = svd.findNamedEntry(chip['peripherals'], 'QUADSPI')
quadspi['parameters'] = [
    { 'name': 'dual', 'value': 0, 'bits': 1, 'min': 0, 'max': 1, 'description': 'dual mode supported' },
    { 'name': 'fifo32', 'value': 0, 'bits': 1, 'min': 0, 'max': 1, 'description': 'FIFO size is 32 bytes instead of 16 bytes' },
    { 'name': 'logsize', 'value': 28, 'bits': 5, 'min': 0, 'max': 31, 'description': 'log2 of size of memory mapped area' },
    { 'name': 'base', 'value': 0x90, 'bits': 8, 'min': 0, 'max': 0xFF, 'description': '(base address >> 24) of memory mapped area' },
]

# Tweak the RTC
rtc = svd.findNamedEntry(chip['peripherals'], 'RTC')
transform.renameEntries(rtc['interrupts'], 'name', r'RTC_([_A-Z]+)', r'\1')
rtc['registers'] = transform.createClusterArray(rtc['registers'], r"RTC_BKP(\d+)(.+?)$", {'name': 'BKP', 'description': 'Backup registers'})
transform.renameEntries(rtc['registers'], 'name', r'RTC_([0-9_A-Z]+)', r'\1')

# Tweak the RCC
rcc = svd.findNamedEntry(chip['peripherals'], 'RCC')
d1ccipr = svd.findNamedEntry(rcc['registers'], 'D1CCIPR')
d1ccipr['fields'].append({ 'name': 'DSISRC', 'bitOffset': 8, 'description': 'DSI kernel clock source selection'})
c1_apb3enr = svd.findNamedEntry(rcc['registers'], 'C1_APB3ENR')
c1_apb3enr['fields'].append({ 'name': 'DSIEN', 'bitOffset': 4, 'description': 'DSI peripheral clocks enable'})

# Add bus info
chip['buses'] = {
    'AHB1': { 'addr': 0x40020000, 'size': 0x000A0000, 'domain': 2 },
    'APB1': { 'addr': 0x40000000, 'size': 0x0000D400, 'domain': 2 },
    'AHB2': { 'addr': 0x48020000, 'size': 0x00003400, 'domain': 2 },
    'APB2': { 'addr': 0x40010000, 'size': 0x00007800, 'domain': 2 },
    'AHB3': { 'addr': 0x51000000, 'size': 0x01009400, 'domain': 1 },
    'APB3': { 'addr': 0x50000000, 'size': 0x00004000, 'domain': 1 },
    'AHB4': { 'addr': 0x58020000, 'size': 0x00007400, 'domain': 3 },
    'APB4': { 'addr': 0x58000000, 'size': 0x00006800, 'domain': 3 }
}

### Restructure the information

# Collect interrupts going to NVIC
interrupts = svd.collectInterrupts(chip['peripherals'], chip['interruptOffset'])

# Delete unwanted instances
chip['peripherals'] = [p for p in chip['peripherals'] if p['name'] in instSet]

models, instances = svd.collectModelsAndInstances(chip['peripherals'])
del chip['peripherals']
chip['instances'] = instances
chip['interrupts'] = interrupts

### Generate output data

svd.printInstances(instances)
print()
svd.printInterrupts(interrupts)
#print("\nComparing registers of DMAMUX1 with DMAMUX2:")
#transform.compareRegisters(models['DMAMUX1']['registers'], models['DMAMUX2']['registers'], True)

subdir.mkdir(parents=True, exist_ok=True)
for name,model in models.items():
    if name in modelSet:
        svd.dumpModel(model, subdir/name, header)

svd.dumpDevice(chip, subdir/'H757', header)
