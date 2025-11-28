import sys
import os
p = os.path.abspath("./tools")
sys.path.append(p)
import svd
import transform
from pathlib import Path

subdir = Path("./models/Raspberry/RP2350")

# models and instances we want to keep
modelSet = [
    'RESETS', 'PSM', 'CLOCKS', 'TICKS', 'PADS_BANK0', 'PADS_QSPI',
    'IO_QSPI', 'IO_BANK0', 'SYSINFO', 'SHA256', 'HSTX_FIFO', 'HSTX_CTRL', 'EPPB', 'PPB',
    'QMI', 'XIP_CTRL', 'XIP_AUX', 'SYSCFG', 'XOSC',
    'PLL', 'ACCESSCTRL', 'UART', 'ROSC', 'POWMAN', 'WATCHDOG', 'DMA',
    'TIMER', 'PWM', 'ADC', 'I2C', 'SPI', 'PIO',
    'BUSCTRL', 'SIO', 'BOOTRAM', 'CORESIGHT_TRACE', 'USB', 'TRNG', 'GLITCH_DETECTOR',
    'OTP', 'OTP_DATA', 'OTP_DATA_RAW', 'TBMAN', 'USB_DPRAM', 'SPARE_IRQ']
instSet = [
    'RESETS', 'PSM', 'CLOCKS', 'TICKS', 'PADS_BANK0', 'PADS_QSPI',
    'IO_QSPI', 'IO_BANK0', 'SYSINFO', 'SHA256', 'HSTX_FIFO', 'HSTX_CTRL', 'EPPB', 'PPB',
    'PPB_NS', 'QMI', 'XIP_CTRL', 'XIP_AUX', 'SYSCFG', 'XOSC',
    'PLL_SYS', 'PLL_USB', 'ACCESSCTRL', 'UART0', 'UART1', 'ROSC', 'POWMAN', 'WATCHDOG', 'DMA',
    'TIMER0', 'TIMER1', 'PWM', 'ADC', 'I2C0', 'I2C1', 'SPI0', 'SPI1', 'PIO0', 'PIO1', 'PIO2',
    'BUSCTRL', 'SIO', 'SIO_NS', 'BOOTRAM', 'CORESIGHT_TRACE', 'USB', 'TRNG', 'GLITCH_DETECTOR',
    'OTP', 'OTP_DATA', 'OTP_DATA_RAW', 'TBMAN', 'USB_DPRAM', 'SPARE_IRQ']

### Read the svd file and do the standard processing on it.
svdpath = 'svd/RP2350.svd'
header = "# Created from RP2350.svd (Rev 0.1)\n"
root = svd.parse(svdpath)
chip = svd.collateDevice(root)

### Tweak the data to fit our model and fix various problems

# Tweak the I2Cs
i2c0 = svd.findNamedEntry(chip['peripherals'], 'I2C0')
i2c0['headerStructName'] = 'I2C'
transform.renameEntries(i2c0['interrupts'], 'name', 'I2C0_IRQ', 'IRQ')
i2c1 = svd.findNamedEntry(chip['peripherals'], 'I2C1')
transform.renameEntries(i2c1['interrupts'], 'name', 'I2C1_IRQ', 'IRQ')

# Tweak the PIOs
pio0 = svd.findNamedEntry(chip['peripherals'], 'PIO0')
pio0['headerStructName'] = 'PIO'
transform.renameEntries(pio0['interrupts'], 'name', 'PIO0_IRQ_0', 'IRQ_0')
transform.renameEntries(pio0['interrupts'], 'name', 'PIO0_IRQ_1', 'IRQ_1')
pio1 = svd.findNamedEntry(chip['peripherals'], 'PIO1')
transform.renameEntries(pio1['interrupts'], 'name', 'PIO1_IRQ_0', 'IRQ_0')
transform.renameEntries(pio1['interrupts'], 'name', 'PIO1_IRQ_1', 'IRQ_1')
pio2 = svd.findNamedEntry(chip['peripherals'], 'PIO2')
transform.renameEntries(pio2['interrupts'], 'name', 'PIO2_IRQ_0', 'IRQ_0')
transform.renameEntries(pio2['interrupts'], 'name', 'PIO2_IRQ_1', 'IRQ_1')

# Tweak the PLLs
pll_sys = svd.findNamedEntry(chip['peripherals'], 'PLL_SYS')
pll_sys['headerStructName'] = 'PLL'

# Tweak the SPIs
spi0 = svd.findNamedEntry(chip['peripherals'], 'SPI0')
spi0['headerStructName'] = 'SPI'
transform.renameEntries(spi0['interrupts'], 'name', 'SPI0_IRQ', 'IRQ')
spi1 = svd.findNamedEntry(chip['peripherals'], 'SPI1')
transform.renameEntries(spi1['interrupts'], 'name', 'SPI1_IRQ', 'IRQ')

# Tweak the TIMERs
timer0 = svd.findNamedEntry(chip['peripherals'], 'TIMER0')
timer0['headerStructName'] = 'TIMER'
transform.renameEntries(timer0['interrupts'], 'name', 'TIMER0_IRQ_0', 'IRQ_0')
transform.renameEntries(timer0['interrupts'], 'name', 'TIMER0_IRQ_1', 'IRQ_1')
transform.renameEntries(timer0['interrupts'], 'name', 'TIMER0_IRQ_2', 'IRQ_2')
transform.renameEntries(timer0['interrupts'], 'name', 'TIMER0_IRQ_3', 'IRQ_3')
timer1 = svd.findNamedEntry(chip['peripherals'], 'TIMER1')
transform.renameEntries(timer1['interrupts'], 'name', 'TIMER1_IRQ_0', 'IRQ_0')
transform.renameEntries(timer1['interrupts'], 'name', 'TIMER1_IRQ_1', 'IRQ_1')
transform.renameEntries(timer1['interrupts'], 'name', 'TIMER1_IRQ_2', 'IRQ_2')
transform.renameEntries(timer1['interrupts'], 'name', 'TIMER1_IRQ_3', 'IRQ_3')

# Tweak the UARTs
uart0 = svd.findNamedEntry(chip['peripherals'], 'UART0')
uart0['headerStructName'] = 'UART'
transform.renameEntries(uart0['interrupts'], 'name', 'UART0_IRQ', 'IRQ')
uart1 = svd.findNamedEntry(chip['peripherals'], 'UART1')
transform.renameEntries(uart1['interrupts'], 'name', 'UART1_IRQ', 'IRQ')

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

svd.dumpDevice(chip, subdir/'RP2350', header)
