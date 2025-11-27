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
tim16pars = [('wide', 0), ('channels', 2), ('rep', 1), ('compl1', 1), ('bkin', 1), ('trigger', 0), ('encoder', 0)]

tim14 = svd.findNamedEntry(chip['peripherals'], 'TIM14')
tim14['@derivedFrom'] = 'TIM3'
tim14['parameters'] = [{'name': n, 'value': v} for n,v in tim13pars]
transform.renameEntries(tim14['interrupts'], 'name', 'TIM14', 'TIM')
transform.renameEntries(tim14['interrupts'], 'description', 'TIM14', 'TIM')

tim16 = svd.findNamedEntry(chip['peripherals'], 'TIM16')
tim16['@derivedFrom'] = 'TIM3'
tim16['parameters'] = [{'name': n, 'value': v} for n,v in tim16pars]
transform.renameEntries(tim16['interrupts'], 'name', 'TIM16', 'TIM')
transform.renameEntries(tim16['interrupts'], 'description', 'TIM16', 'TIM')

tim17 = svd.findNamedEntry(chip['peripherals'], 'TIM17')
tim17['@derivedFrom'] = 'TIM3'
tim17['parameters'] = [{'name': n, 'value': v} for n,v in tim16pars]
transform.renameEntries(tim17['interrupts'], 'name', 'TIM17', 'TIM')
transform.renameEntries(tim17['interrupts'], 'description', 'TIM17', 'TIM')

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
    { 'name': 'rxTimeout', 'value': 0, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Receiver timeout interrupt' },
    { 'name': 'modbus',    'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Modbus communication' },
    { 'name': 'autobaud',  'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Auto baud rate detection' },
    { 'name': 'prescaler', 'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'Prescaler' },
]
basicpars =   [('syncmode', 1), ('smartcard', 0), ('irdaSIR', 0), ('lin', 0), ('rxTimeout', 0), ('modbus', 0), ('autobaud', 0), ('prescaler', 0)]

usart2 = svd.findNamedEntry(chip['peripherals'], 'USART2')
transform.renameEntries(usart2['interrupts'], 'name', 'USART2', 'USART')
usart2['parameters'] = [{'name': n, 'value': v} for n,v in basicpars]

# Tweak the SPI ports
spi1 = svd.findNamedEntry(chip['peripherals'], 'SPI1')
spi1['headerStructName'] = 'SPI'
transform.renameEntries(spi1['interrupts'], 'name', 'SPI1', 'SPI')
transform.renameEntries(spi1['interrupts'], 'description', 'SPI1', 'SPI')
spi1['parameters'] = [
    { 'name': 'i2smode', 'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'I2S mode support' },
    { 'name': 'width32', 'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': '32 bit data size support' },
]

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

## TODO:
# - USB
# - FDCAN
# - CRC
# - IRTIM

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
