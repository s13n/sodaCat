import sys
import os
p = os.path.abspath("./tools")
sys.path.append(p)
import svd
import transform
import re
from pathlib import Path

subdir = Path("./models/Microchip/SAMV71")

# models and instances we want to keep
modelSet = frozenset({
    'NVIC' })
instSet = frozenset({
    'NVIC' })

svdpath = './svd/ATSAMV71Q21B.svd'
header = "# Created from ATSAMV71Q21B.svd (Rev 0)\n"
root = svd.parse(svdpath)
chip = svd.collateDevice(root)

### Tweak the data to fit our model and fix various problems

# fiddle interrupt naming
for per in chip['peripherals']:
    if per['name'] == 'AFEC0': per['headerStructName'] = 'AFEC'
    if per['name'] == 'I2SC0': per['headerStructName'] = 'I2SC'
    if per['name'] == 'MCAN0': per['headerStructName'] = 'MCAN'
    if per['name'] == 'PIOA': per['headerStructName'] = 'PIO'
    if per['name'] == 'PWM0': per['headerStructName'] = 'PWM'
    if per['name'] == 'SPI0': per['headerStructName'] = 'SPI'
    if per['name'] == 'TWIHS0': per['headerStructName'] = 'TWIHS'
    if per['name'] == 'UART0': per['headerStructName'] = 'UART'
    if per['name'] == 'USART0': per['headerStructName'] = 'USART'
    if tc := re.match(r'TC(\d+)', per['name']):
        transform.renameEntries(per['interrupts'], "name", "TC(\d+)", lambda m: 'INT%d' % (int(m.group(1)) % 3))
        per['headerStructName'] = 'TC'
    transform.renameEntries(per.get('interrupts',[]), 'name', r"\w+_(\w+)", r"\1")
    transform.renameEntries(per.get('interrupts',[]), 'name', per['name'], 'INT')

# Tweak the NVIC
nvic = svd.findNamedEntry(chip['peripherals'], 'NVIC')
nvic['parameters'] = [
    { 'name': 'priobits', 'value': 2, 'bits': 3, 'min': 0, 'max': 7, 'description': 'number of priority bits - 1' },
    { 'name': 'interrupts', 'value': 74, 'bits': 10, 'min': 0, 'max': 1008, 'description': 'number of interrupts' },
]

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

svd.dumpDevice(chip, subdir/'SAMV71', header)
