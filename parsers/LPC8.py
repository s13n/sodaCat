import sys
import os
p = os.path.abspath("./tools")
sys.path.append(p)
import svd
import transform
from pathlib import Path

subdir = Path("./models/NXP/LPC8")

# models and instances we want to keep
modelSet = [
    'ACOMP', 'CRC', 'MRT', 'WWDT', 'WKT',
    'ADC', 'FLASH_CTRL', 'FTM', 'GPIO', 'I2C', 'I3C', 'INPUTMUX',
    'IOCON', 'PINT', 'PMU', 'SPI', 'SWM', 'SYSCON', 'USART']
instSet = [
    'WWDT', 'WKT', 'NVIC', 'ACOMP', 'CRC', 'MRT0',
    'ADC0', 'DMA0', 'FLASH_CTRL', 'FTM0', 'FTM1', 'GPIO', 'I2C0', 'I3C0',
    'INPUTMUX', 'IOCON', 'PINT', 'PMU', 'SPI0', 'SPI1',
    'SWM0', 'SYSCON', 'USART0', 'USART1', 'USART2']

svdpath = "./svd/LPC865.svd"
header = "# Created from LPC865.svd\n"
root = svd.parse(svdpath)
chip = svd.collateDevice(root)

### Tweak the data to fit our model and fix various problems

# Tweak the NVIC
nvic = { 'name': 'NVIC', 'model': 'NVIC', 'description': 'Nested Vectored Interrupt Controller' }
nvic['baseAddress'] = 3758153984
nvic['parameters'] = [
    { 'name': 'interrupts', 'value': 32 },
    { 'name': 'priobits', 'value': 1 }
]
chip['peripherals'].append(nvic)

# Tweak the ACOMP
acomp = svd.findNamedEntry(chip['peripherals'], 'ACOMP')
acomp['clocks'] = [ { 'name': 'clk' } ]

# Tweak the ADC
adc0 = svd.findNamedEntry(chip['peripherals'], 'ADC0')
adc0['headerStructName'] = 'ADC'
adc0['clocks'] = [ { 'name': 'sync_clk' }, { 'name': 'async_clk' } ]
#adc0['registers'] = transform.createClusterArray(adc0['registers'], r"DAT(\d+)", {'name': 'DAT', 'description': 'Channel data'})
transform.renameEntries(adc0['interrupts'], 'name', r'ADC0_([A-Z_0-9]+)', r'\1')

# Tweak the DMA
dma0 = svd.findNamedEntry(chip['peripherals'], 'DMA0')
dma0['headerStructName'] = 'SmartDMA'
dma0['clocks'] = [ { 'name': 'clk' } ]
transform.renameEntries(dma0['interrupts'], 'name', 'DMA0', 'DMA')
dma0['parameters'] = [
    { 'name': 'max_channel', 'value': 15, 'bits': 5, 'min': 0, 'max': 31, 'description': 'index of last channel' },
]
def dmaChanParams(name, num):
    return { 'name': name, 'value': num, 'bits': 5, 'min': 0, 'max': 31, 'description': 'DMA receive channel' }

# Tweak the FLASH
flash = svd.findNamedEntry(chip['peripherals'], 'FLASH_CTRL')
flash['clocks'] = [ { 'name': 'clk' } ]

# Tweak the FTM0 and FTM1
ftm0 = svd.findNamedEntry(chip['peripherals'], 'FTM0')
ftm0['headerStructName'] = 'FTM'
ftm0['clocks'] = [ { 'name': 'main_clk' }, { 'name': 'extclk' } ]
transform.renameEntries(ftm0['interrupts'], 'name', 'FTM0', 'FTM')
ftm0['parameters'] = [
    { 'name': 'max_channel', 'value': 5, 'bits': 3, 'min': 0, 'max': 7, 'description': 'index of last channel' },
    { 'name': 'qdec', 'value': 0, 'bits': 1, 'min': 0, 'max': 1, 'description': 'presence of quadrature decoder' },
    { 'name': 'dither', 'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'support for PWM output dithering' },
    { 'name': 'fault_inputs', 'value': 4, 'bits': 3, 'min': 0, 'max': 7, 'description': 'number of fault inputs' },
    { 'name': 'modulation', 'value': 0, 'bits': 1, 'min': 0, 'max': 1, 'description': 'support for modulation' },
]
ftm1 = svd.findNamedEntry(chip['peripherals'], 'FTM1')
ftm1['@derivedFrom'] = 'FTM0'
ftm1['clocks'] = [ { 'name': 'main_clk' }, { 'name': 'extclk' } ]
transform.renameEntries(ftm1['interrupts'], 'name', 'FTM1', 'FTM')
ftm1['parameters'] = [
    { 'name': 'max_channel', 'value': 3, 'bits': 3, 'min': 0, 'max': 7, 'description': 'index of last channel' },
    { 'name': 'qdec', 'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'presence of quadrature decoder' },
    { 'name': 'dither', 'value': 1, 'bits': 1, 'min': 0, 'max': 1, 'description': 'support for PWM output dithering' },
    { 'name': 'fault_inputs', 'value': 0, 'bits': 3, 'min': 0, 'max': 7, 'description': 'number of fault inputs' },
    { 'name': 'modulation', 'value': 0, 'bits': 1, 'min': 0, 'max': 1, 'description': 'support for modulation' },
]

# Tweak the GPIO
gpio = svd.findNamedEntry(chip['peripherals'], 'GPIO')
gpio['clocks'] = [ { 'name': 'clk0' }, { 'name': 'clk1' } ]

# Tweak the I2C
i2c0 = svd.findNamedEntry(chip['peripherals'], 'I2C0')
i2c0['headerStructName'] = 'I2C'
i2c0['clocks'] = [ { 'name': 'base_clk' }, { 'name': 'busclk' } ]
transform.renameEntries(i2c0['interrupts'], 'name', 'I2C0', 'I2C')
i2c0['parameters'] = [
    dmaChanParams('rx_req', 10),
    dmaChanParams('tx_req', 11),
]

# Tweak the I3C
i3c0 = svd.findNamedEntry(chip['peripherals'], 'I3C0')
i3c0['headerStructName'] = 'I3C'
i3c0['clocks'] = [ { 'name': 'busclk' }, { 'name': 'fclk' }, { 'name': 'clk_slow' }, { 'name': 'clk_slow_tc' } ]
transform.renameEntries(i3c0['interrupts'], 'name', 'I3C0', 'I3C')
i3c0['parameters'] = [
    dmaChanParams('rx_req', 12),
    dmaChanParams('tx_req', 13),
]

# Tweak the IOCON
iocon = svd.findNamedEntry(chip['peripherals'], 'IOCON')
iocon['clocks'] = [ { 'name': 'busclk' }, { 'name': 'clk0' }, { 'name': 'clk1' }, { 'name': 'clk2' }, { 'name': 'clk3' }, { 'name': 'clk4' }, { 'name': 'clk5' }, { 'name': 'clk6' } ]

# Tweak the MRT
mrt0 = svd.findNamedEntry(chip['peripherals'], 'MRT0')
mrt0['headerStructName'] = 'MRT'
mrt0['clocks'] = [ { 'name': 'pclk' } ]
transform.renameEntries(mrt0['interrupts'], 'name', 'MRT0', 'MRT')

# Tweak the PINT
pint = svd.findNamedEntry(chip['peripherals'], 'PINT')
pint['clocks'] = [ { 'name': 'busclk' } ]
transform.renameEntries(pint['interrupts'], 'name', r'PIN_([A-Z_0-9]+)', r'\1')

# Tweak the SPIs
spi0 = svd.findNamedEntry(chip['peripherals'], 'SPI0')
spi0['clocks'] = [ { 'name': 'base_clk' }, { 'name': 'busclk' } ]
transform.renameEntries(spi0['interrupts'], 'name', 'SPI0', 'SPI')
spi0['parameters'] = [
    dmaChanParams('rx_req', 6),
    dmaChanParams('tx_req', 7),
    { 'name': 'ssel_num', 'value': 4, 'bits': 3, 'min': 0, 'max': 4, 'description': 'number of SSEL signals' },
]
spi1 = svd.findNamedEntry(chip['peripherals'], 'SPI1')
transform.renameEntries(spi1['interrupts'], 'name', 'SPI1', 'SPI')
spi1['parameters'] = [
    dmaChanParams('rx_req', 8),
    dmaChanParams('tx_req', 9),
    { 'name': 'ssel_num', 'value': 2, 'bits': 3, 'min': 0, 'max': 4, 'description': 'number of SSEL signals' },
]

# Tweak the SWM
swm0 = svd.findNamedEntry(chip['peripherals'], 'SWM0')
swm0['headerStructName'] = 'SWM'

# Tweak the USARTs
usart0 = svd.findNamedEntry(chip['peripherals'], 'USART0')
usart0['clocks'] = [ { 'name': 'u_clk' }, { 'name': 'busclk' } ]
transform.renameEntries(usart0['interrupts'], 'name', 'USART0', 'USART')
usart0['parameters'] = [
    dmaChanParams('rx_req', 0),
    dmaChanParams('tx_req', 1),
]
usart1 = svd.findNamedEntry(chip['peripherals'], 'USART1')
transform.renameEntries(usart1['interrupts'], 'name', 'USART1', 'USART')
usart1['parameters'] = [
    dmaChanParams('rx_req', 2),
    dmaChanParams('tx_req', 3),
]
usart2 = svd.findNamedEntry(chip['peripherals'], 'USART2')
transform.renameEntries(usart2['interrupts'], 'name', 'USART2', 'USART')
usart2['parameters'] = [
    dmaChanParams('rx_req', 4),
    dmaChanParams('tx_req', 5),
]

# Tweak the WKT
wkt = svd.findNamedEntry(chip['peripherals'], 'WKT')
wkt['clocks'] = [ { 'name': 'bus_clk' }, { 'name': 'default_clk' }, { 'name': 'lp_clk' }, { 'name': 'ext_clk' } ]

# Tweak the WWDT
wwdt = svd.findNamedEntry(chip['peripherals'], 'WWDT')
wwdt['clocks'] = [ { 'name': 'pclk' }, { 'name': 'wdt_clk' } ]

# Add bus info
chip['buses'] = {
    'AHB': { 'addr': 0x50000000, 'size': 0x00014000 },
    'APB': { 'addr': 0x40000000, 'size': 0x00080000 }
}

### Restructure the information

# Collect interrupts going to NVIC
interrupts = svd.collectInterrupts(chip['peripherals'], chip['interruptOffset'])

# Delete unwanted instances and sort others
peripherals_dict = { obj['name']: obj for obj in chip['peripherals'] }
chip['peripherals'] = [peripherals_dict[n] for n in instSet if n in peripherals_dict]

models, instances = svd.collectModelsAndInstances(chip['peripherals'])
del chip['peripherals']
chip['instances'] = instances
chip['interrupts'] = interrupts

### Generate output data

svd.printInstances(instances)
print()
svd.printInterrupts(interrupts)

subdir.mkdir(parents=True, exist_ok=True)
for name,model in models.items():
    if name in dict.fromkeys(modelSet).keys():
        svd.dumpModel(model, subdir/name, header)
        print('Model dumped: %s' % name)

svd.dumpDevice(chip, subdir/'LPC865', header)
