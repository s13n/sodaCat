import sys
import sys
import os
import tempfile
p = os.path.abspath("./tools")
sys.path.append(p)
from urllib.request import urlretrieve
import svd
import transform
from pathlib import Path

subdir = Path("./models/ST/C031")

# models and instances we want to keep
modelSet = frozenset({'ADC', 'RCC', 'DMA', 'DMAMUX', 'EXTI', 'GPIO', 'I2C',
    'SYSCFG', 'BasicTimer', 'GpTimer', 'AdvCtrlTimer', 'LPTIM', 'USART', 'SPI', 'RTC'})
instSet = frozenset({'DMA', 'DMAMUX', 'RCC', 'ADC', 'EXTI', 'SYSCFG', 'I2C',
    'TIM1', 'TIM3', 'TIM14', 'TIM16', 'TIM17', 'GPIOA', 'GPIOB', 'GPIOC', 'GPIOD', 'GPIOF',
    'USART1', 'USART2', 'SPI', 'RTC'})

### Read the svd file and do the standard processing on it.

svdpath = './svd/STM32C031.svd'
header = "# Created from STM32C031.svd (Rev 1.4)\n"
root = svd.parse(svdpath)
chip = svd.collateDevice(root)

### Tweak the data to fix various problems

# Tweak the ADC naming

# Convert the register set for the DMA channels into an array
dma = svd.findNamedEntry(chip['peripherals'], 'DMA')
dma['registers'] = transform.createClusterArray(dma['registers'], r"S(\d+)(.+)", {'name': 'S', 'description': 'DMA stream'})
transform.renameEntries(dma['interrupts'], 'name', r'[A-Z0-9]+_([A-Z_0-9]+)', r'\1')

# Tweak the I2C naming
i2c = svd.findNamedEntry(chip['peripherals'], 'I2C')
transform.renameEntries(i2c['interrupts'], 'name', r'I2C1_([A-Z_0-9]+)', r'\1')
transform.renameEntries(i2c['interrupts'], 'description', 'I2C1', 'I2C')

# Tweak the TIM1
tim1 = svd.findNamedEntry(chip['peripherals'], 'TIM1')
tim1['headerStructName'] = 'AdvCtrlTimer'
transform.renameEntries(tim1['interrupts'], 'name', r'TIM\d?_([A-Z_0-9]+)', r'\1')
transform.renameEntries(tim1['interrupts'], 'description', 'TIM1', 'TIM')

# Tweak the TIM2, TIM3, TIM4, TIM5, TIM12, TIM13, TIM14, TIM15, TIM16 and TIM17
tim3 = svd.findNamedEntry(chip['peripherals'], 'TIM3')
tim3['headerStructName'] = 'GpTimer'
transform.renameEntries(tim3['interrupts'], 'name', 'TIM3', 'TIM')
transform.renameEntries(tim3['interrupts'], 'description', 'TIM3', 'TIM')
tim3['parameters'] = [
    { 'name': 'wide',     'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Counter is 32-bit' },
    { 'name': 'channels', 'value': 4, 'bits': 3, 'min': 1, 'max': 4, 'description': 'Number of capture/compare channels' },
    { 'name': 'rep',      'value': 0, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Repetition counter present' },
    { 'name': 'compl1',   'value': 0, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Complementary output on first channel' },
    { 'name': 'bkin',     'value': 0, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Break input supported' },
    { 'name': 'trigger',  'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Trigger events supported' },
    { 'name': 'encoder',  'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Quadrature encoder support' },
]
tim5pars = [('wide', 1), ('channels', 4), ('rep', 0), ('compl1', 0), ('bkin', 0), ('trigger', 1), ('encoder', 1)]
tim12pars = [('wide', 0), ('channels', 2), ('rep', 0), ('compl1', 0), ('bkin', 0), ('trigger', 1), ('encoder', 0)]
tim13pars = [('wide', 0), ('channels', 1), ('rep', 0), ('compl1', 0), ('bkin', 0), ('trigger', 0), ('encoder', 0)]
tim15pars = [('wide', 0), ('channels', 2), ('rep', 1), ('compl1', 1), ('bkin', 1), ('trigger', 1), ('encoder', 0)]
tim16pars = [('wide', 0), ('channels', 1), ('rep', 1), ('compl1', 1), ('bkin', 1), ('trigger', 0), ('encoder', 0)]

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
]
usartpars =  [('syncmode', 1), ('smartcard', 1), ('irdaSIR', 1), ('lin', 1), ('rxTimeout', 1), ('modbus', 1), ('autobaud', 1), ('prescaler', 1)]
uartpars =   [('syncmode', 0), ('smartcard', 0), ('irdaSIR', 1), ('lin', 1), ('rxTimeout', 1), ('modbus', 1), ('autobaud', 1), ('prescaler', 1)]
lpuartpars = [('syncmode', 0), ('smartcard', 0), ('irdaSIR', 0), ('lin', 0), ('rxTimeout', 0), ('modbus', 0), ('autobaud', 0), ('prescaler', 1)]

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

# Tweak the GPIO naming
gpioa = svd.findNamedEntry(chip['peripherals'], 'GPIOA')
gpioa['headerStructName'] = 'GPIO'

# Tweak the EXTI
exti = svd.findNamedEntry(chip['peripherals'], 'EXTI')
transform.renameEntries(exti['interrupts'], 'description', r'(?s:.)*(M7 Send)', r'\1')

# Tweak the RTC
rtc = svd.findNamedEntry(chip['peripherals'], 'RTC')
transform.renameEntries(rtc['interrupts'], 'name', r'RTC_([_A-Z]+)', r'\1')
rtc['registers'] = transform.createClusterArray(rtc['registers'], r"RTC_BKP(\d+)(.+?)$", {'name': 'BKP', 'description': 'Backup registers'})
transform.renameEntries(rtc['registers'], 'name', r'RTC_([0-9_A-Z]+)', r'\1')

# Add bus info
chip['buses'] = {
    'IOPORT': { 'addr': 0x50000000, 'size': 0x10000000 },
    'AHB': { 'addr': 0x40020000, 'size': 0x0FFE0000 },
    'APB': { 'addr': 0x40000000, 'size': 0x00020000 },
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

svd.dumpDevice(chip, subdir/'C031', header)
