import sys
import os
p = os.path.abspath("./tools")
sys.path.append(p)
import svd
import transform
from pathlib import Path

subdir = Path("./data/NXP/LPC8")

# models and instances we want to keep
modelSet = frozenset({
#    'ACOMP', 'CRC', 'MRT', 'WWDT', 'WKT',
    'ADC', 'DMA', 'FLASH_CTRL', 'FTM0', 'FTM1', 'GPIO', 'I2C', 'I3C', 'INPUTMUX',
    'IOCON', 'PINT', 'PMU', 'SPI', 'SWM', 'SYSCON', 'USART'})
instSet = frozenset({
#    'ACOMP', 'CRC', 'MRT0', 'WWDT', 'WKT',
    'ADC0', 'DMA0', 'FLASH_CTRL', 'FTM0', 'FTM1', 'GPIO', 'I2C0', 'I3C0',
    'INPUTMUX', 'IOCON', 'PINT', 'PMU', 'SPI0', 'SPI1',
    'SWM0', 'SYSCON', 'USART0', 'USART1', 'USART2'})

svdpath = "./svd/LPC865.svd"
header = "# Created from LPC865.svd\n"
root = svd.parse(svdpath)
chip = svd.collateDevice(root)

### Tweak the data to fix various problems

# Tweak the ADC naming
adc0 = svd.findNamedEntry(chip['peripherals'], 'ADC0')
adc0['headerStructName'] = 'ADC'
adc0['registers'] = transform.createClusterArray(adc0['registers'], r"DAT(\d+)", {'name': 'DAT', 'description': 'Channel data'})
transform.renameEntries(adc0['interrupts'], 'name', r'ADC0_([A-Z_0-9]+)', r'\1')
transform.renameEntries(adc0['interrupts'], 'description', 'ADC0', 'ADC')

# Tweak the DMA naming
dma0 = svd.findNamedEntry(chip['peripherals'], 'DMA0')
dma0['headerStructName'] = 'DMA'
transform.renameEntries(dma0['interrupts'], 'name', 'DMA0', 'DMA')
transform.renameEntries(dma0['interrupts'], 'description', 'DMA0', 'DMA')

# Tweak the I2C naming
i2c0 = svd.findNamedEntry(chip['peripherals'], 'I2C0')
i2c0['headerStructName'] = 'I2C'
transform.renameEntries(i2c0['interrupts'], 'name', 'I2C0', 'I2C')
transform.renameEntries(i2c0['interrupts'], 'description', 'I2C0', 'I2C')

# Tweak the I3C naming
i3c0 = svd.findNamedEntry(chip['peripherals'], 'I3C0')
i3c0['headerStructName'] = 'I3C'
transform.renameEntries(i3c0['interrupts'], 'name', 'I3C0', 'I3C')
transform.renameEntries(i3c0['interrupts'], 'description', 'I3C0', 'I3C')

# Tweak the MRT naming
mrt0 = svd.findNamedEntry(chip['peripherals'], 'MRT0')
mrt0['headerStructName'] = 'MRT'
transform.renameEntries(mrt0['interrupts'], 'name', 'MRT0', 'MRT')
transform.renameEntries(mrt0['interrupts'], 'description', 'MRT0', 'MRT')

# Tweak the SWM naming
swm0 = svd.findNamedEntry(chip['peripherals'], 'SWM0')
swm0['headerStructName'] = 'SWM'

# Tweak the SPIs
spi0 = svd.findNamedEntry(chip['peripherals'], 'SPI0')
transform.renameEntries(spi0['interrupts'], 'description', 'SPI0', 'SPI')
transform.renameEntries(spi0['interrupts'], 'name', 'SPI0', 'SPI')
spi1 = svd.findNamedEntry(chip['peripherals'], 'SPI1')
transform.renameEntries(spi1['interrupts'], 'name', 'SPI1', 'SPI')

# Tweak the USARTs
usart0 = svd.findNamedEntry(chip['peripherals'], 'USART0')
transform.renameEntries(usart0['interrupts'], 'description', 'USART0', 'USART')
transform.renameEntries(usart0['interrupts'], 'name', 'USART0', 'USART')
usart1 = svd.findNamedEntry(chip['peripherals'], 'USART1')
transform.renameEntries(usart1['interrupts'], 'name', 'USART1', 'USART')
usart2 = svd.findNamedEntry(chip['peripherals'], 'USART2')
transform.renameEntries(usart2['interrupts'], 'name', 'USART2', 'USART')

# Add bus info
chip['buses'] = {
    'AHB': { 'addr': 0x50000000, 'size': 0x00014000 },
    'APB': { 'addr': 0x40000000, 'size': 0x00080000 }
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

subdir.mkdir(parents=True, exist_ok=True)
for name,model in models.items():
    if name in modelSet:
        svd.dumpModel(model, subdir/name, header)
        print('Model dumped: %s' % name)

svd.dumpDevice(chip, subdir/'LPC865', header)
