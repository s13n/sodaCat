import sys
import os
import re
from pathlib import Path

p = os.path.abspath("./tools")
sys.path.append(p)
import svd
import transform

subdir = Path("./models/Microchip/SAMV71")

# Block-level models we want to dump
modelSet = frozenset({
    'ACC', 'AES', 'AFEC', 'CHIPID', 'DACC', 'EFC', 'GMAC', 'GPBR',
    'HSMCI', 'I2SC', 'ICM', 'ISI', 'MATRIX', 'MCAN', 'MLB',
    'PIO', 'PMC', 'PWM', 'QSPI', 'RSTC', 'RSWDT', 'RTC', 'RTT',
    'SMC', 'SPI', 'SSC', 'SUPC', 'TC', 'TRNG', 'TWIHS',
    'UART', 'USART', 'USBHS', 'UTMI', 'WDT', 'XDMAC',
})

# Peripheral instances we want on the chip (NVIC handled separately, ARM
# core peripherals dropped — their models live in models/ARM/ already).
instSet = frozenset({
    'ACC', 'AES', 'AFEC0', 'AFEC1', 'CHIPID', 'DACC', 'EFC', 'GMAC', 'GPBR',
    'HSMCI', 'I2SC0', 'I2SC1', 'ICM', 'ISI', 'MATRIX', 'MCAN0', 'MCAN1', 'MLB',
    'PIOA', 'PIOB', 'PIOC', 'PIOD', 'PIOE', 'PMC', 'PWM0', 'PWM1', 'QSPI',
    'RSTC', 'RSWDT', 'RTC', 'RTT', 'SMC', 'SPI0', 'SPI1', 'SSC', 'SUPC',
    'TC0', 'TC1', 'TC2', 'TC3', 'TRNG', 'TWIHS0', 'TWIHS1', 'TWIHS2',
    'UART0', 'UART1', 'UART2', 'UART3', 'UART4', 'USART0', 'USART1', 'USART2',
    'USBHS', 'UTMI', 'WDT', 'XDMAC', 'NVIC',
})

svdpath = './svd/Microchip/ATSAMV71Q21B.svd'
header = "# Created from ATSAMV71Q21B.svd (Rev 0)\n"
root = svd.parse(svdpath)
chip = svd.collateDevice(root)

### Tweak the data to fit our model and fix various problems

# Map each base instance to the canonical block-type name; derivedFrom
# instances inherit their model from the base via collectModelsAndInstances.
group_names = {
    'AFEC0':  'AFEC',
    'I2SC0':  'I2SC',
    'MCAN0':  'MCAN',
    'PIOA':   'PIO',
    'PWM0':   'PWM',
    'SPI0':   'SPI',
    'TWIHS0': 'TWIHS',
    'UART0':  'UART',
    'USART0': 'USART',
}

for per in chip['peripherals']:
    name = per['name']
    if name == 'NVIC':
        # Cross-vendor licensed-IP reference to the existing ARM core model.
        per['headerStructName'] = 'ARM/NVIC'
    elif name in group_names:
        per['headerStructName'] = group_names[name]
    elif re.match(r'TC\d+$', name):
        # The four TC instances each carry three timer-channel interrupts;
        # canonicalise them to INT0/INT1/INT2 within each instance.
        per['headerStructName'] = 'TC'
        transform.renameEntries(per['interrupts'], 'name', r'TC(\d+)',
                                lambda m: 'INT%d' % (int(m.group(1)) % 3))

    # Strip "<word>_" prefix from interrupt names: GMAC_Q1 → Q1, MCAN0_INT0 → INT0.
    transform.renameEntries(per.get('interrupts', []), 'name', r'\w+_(\w+)', r'\1')

    # GMAC: strip the GMAC_ prefix from cluster names and drop the
    # range-form dimIndex on SA (the schema requires a comma list, and
    # dim=4 alone is unambiguous).
    if name == 'GMAC':
        for reg in per.get('registers', []):
            if isinstance(reg.get('name'), str) and reg['name'].startswith('GMAC_'):
                reg['name'] = reg['name'][len('GMAC_'):]
            if reg.get('dimIndex') == '1-4':
                del reg['dimIndex']
    # Map the bare instance-name interrupt to INT (e.g. ACC → INT, AFEC0 → INT, GMAC → INT).
    transform.renameEntries(per.get('interrupts', []), 'name', f'^{re.escape(name)}$', 'INT')

### Restructure the information

# Collect interrupts going to NVIC (run before instance filtering so ARM core
# vectors like SCB.CCW/FPU.IXC remain in the chip's interrupts table).
interrupts = svd.collectInterrupts(chip['peripherals'], chip['interruptOffset'])

# Configure the NVIC instance — model registered under 'NVIC' so this becomes
# the canonical block model, with priority-bit and interrupt-count parameters.
nvic = svd.findNamedEntry(chip['peripherals'], 'NVIC')
nvic['parameters'] = [
    {'name': 'priobits', 'value': 3, 'bits': 3, 'min': 0, 'max': 7,
     'description': 'number of priority bits - 1'},
    {'name': 'interrupts', 'value': len(interrupts), 'bits': 10, 'min': 0, 'max': 1008,
     'description': 'number of interrupts'},
]
nvic['interrupts'] = []  # NVIC has no interrupt of its own

# Drop unwanted instances (ARM core peripherals, LOCKBIT, ...)
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
for name, model in models.items():
    if name in modelSet:
        svd.dumpModel(model, subdir/name, header)
        print('Model dumped: %s' % name)

svd.dumpDevice(chip, subdir/'SAMV71', header)
