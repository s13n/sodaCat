import sys
import os
p = os.path.abspath("./tools")
sys.path.append(p)
import svd
import transform
from pathlib import Path

subdir = Path("./models/NXP/LPC54")

# models and instances we want to keep
modelSet = [
    'SYSCON', 'IOCON', 'GINT0', 'PINT', 'INPUTMUX', 'CTIMER',
    'WWDT', 'MRT', 'UTICK0', 'OTPC', 'RTC', 'RIT', 'SMARTCARD0', 'PUF', 'ASYNC_SYSCON',
    'SPIFI0', 'EMC', 'SmartDMA', 'LCD', 'USB0', 'SCT', 'FLEXCOMM0', 'I2C', 'SPI', 'USART'
    'GPIO', 'DMIC0', 'ENET', 'USBHSD', 'CRC_ENGINE', 'I2S0', 'SDIF', 'CAN',
    'ADC', 'AES0', 'USBFSH', 'USBHSH', 'SHA0', 'ITM', 'SystemControl', 'SysTick', 'ETM']
instSet = [
    'SYSCON', 'IOCON', 'GINT0', 'GINT1', 'PINT', 'INPUTMUX', 'CTIMER0', 'CTIMER1', 'CTIMER2', 'CTIMER3', 'CTIMER4',
    'WWDT', 'MRT0', 'UTICK0', 'OTPC', 'RTC', 'RIT', 'SMARTCARD0', 'SMARTCARD1', 'PUF', 'ASYNC_SYSCON',
    'SPIFI0', 'EMC', 'DMA0', 'LCD', 'USB0', 'SCT0',
    'FLEXCOMM0', 'FLEXCOMM1', 'FLEXCOMM2', 'FLEXCOMM3', 'FLEXCOMM4', 'FLEXCOMM5', 'FLEXCOMM6', 'FLEXCOMM7', 'FLEXCOMM8', 'FLEXCOMM9', 'FLEXCOMM10',
    'I2C0', 'I2C1', 'I2C2', 'I2C3', 'I2C4', 'I2C5', 'I2C6', 'I2C7', 'I2C8', 'I2C9',
    'SPI0', 'SPI1', 'SPI2', 'SPI3', 'SPI4', 'SPI5', 'SPI6', 'SPI7', 'SPI8', 'SPI9', 'SPI10',
    'USART0', 'USART1', 'USART2', 'USART3', 'USART4', 'USART5', 'USART6', 'USART7', 'USART8', 'USART9',
    'GPIO', 'DMIC0', 'ENET', 'USBHSD', 'CRC_ENGINE', 'I2S0', 'I2S1', 'SDIF', 'CAN0', 'CAN1',
    'ADC0', 'AES0', 'USBFSH', 'USBHSH', 'ITM', 'SystemControl', 'SysTick', 'NVIC', 'ETM']

svdpath = "./svd/LPC54S018.svd"
header = "# Created from LPC54S018.svd\n"
root = svd.parse(svdpath)
chip = svd.collateDevice(root)

### Tweak the data to fit our model and fix various problems

# Tweak the NVIC
nvic = { 'name': 'NVIC', 'model': 'NVIC', 'description': 'Nested Vectored Interrupt Controller' }
nvic['baseAddress'] = 3758153984
nvic['parameters'] = [
    { 'name': 'interrupts', 'value': 59 },
    { 'name': 'priobits', 'value': 3 }
]
chip['peripherals'].append(nvic)

# Tweak the ADC
adc0 = svd.findNamedEntry(chip['peripherals'], 'ADC0')
adc0['headerStructName'] = 'ADC'
adc0['clocks'] = [ { 'name': 'sync_clk' }, { 'name': 'async_clk' } ]
adc0['registers'] = transform.createClusterArray(adc0['registers'], r"DAT(\d+)", {'name': 'DAT', 'description': 'Channel data'})
transform.renameEntries(adc0['interrupts'], 'name', r'ADC0_([A-Z_0-9]+)', r'\1')

# Tweak the CAN
can0 = svd.findNamedEntry(chip['peripherals'], 'CAN0')
can0['headerStructName'] = 'CAN'
transform.renameEntries(can0['interrupts'], 'name', 'CAN0', 'CAN')

# Tweak the CTIMER
ctimer0 = svd.findNamedEntry(chip['peripherals'], 'CTIMER0')
ctimer0['headerStructName'] = 'CTIMER'
ctimer1 = svd.findNamedEntry(chip['peripherals'], 'CTIMER1')
ctimer2 = svd.findNamedEntry(chip['peripherals'], 'CTIMER2')
ctimer3 = svd.findNamedEntry(chip['peripherals'], 'CTIMER3')
ctimer4 = svd.findNamedEntry(chip['peripherals'], 'CTIMER4')

# Tweak the DMA
dma0 = svd.findNamedEntry(chip['peripherals'], 'DMA0')
dma0['headerStructName'] = 'SmartDMA'
dma0['clocks'] = [ { 'name': 'clk' } ]
transform.renameEntries(dma0['interrupts'], 'name', 'DMA0', 'DMA')
dma0['parameters'] = [
    { 'name': 'max_channel', 'value': 31, 'bits': 5, 'min': 0, 'max': 31, 'description': 'index of last channel' },
]
def dmaChanParams(name, num):
    return { 'name': name, 'value': num, 'bits': 5, 'min': 0, 'max': 31, 'description': 'DMA receive channel' }

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

# Tweak the I2S
i2s0 = svd.findNamedEntry(chip['peripherals'], 'I2S0')
i2s0['headerStructName'] = 'I2S'
i2s1 = svd.findNamedEntry(chip['peripherals'], 'I2S1')

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

# Tweak the RTC
rtc = svd.findNamedEntry(chip['peripherals'], 'RTC')
rtc['clocks'] = [ { 'name': 'bus_clk' }, { 'name': 'default_clk' }, { 'name': 'lp_clk' }, { 'name': 'ext_clk' } ]

# Tweak the SCT
sct0 = svd.findNamedEntry(chip['peripherals'], 'SCT0')
sct0['headerStructName'] = 'SCT'

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
flexcomm0 = svd.findNamedEntry(chip['peripherals'], 'FLEXCOMM0')
flexcomm0['headerStructName'] = 'FLEXCOMM'

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

svd.dumpDevice(chip, subdir/'LPC54S018', header)
