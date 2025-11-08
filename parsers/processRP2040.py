import sys
import os
import tempfile
p = os.path.abspath("./tools")
sys.path.append(p)
import svd
import transform
import re
from pathlib import Path

subdir = Path("./data/Raspberry/RP2040")

### Read the svd file and do the standard processing on it.

svdpath = 'svd/RP2040.svd'
header = "# Created from RP2040.svd (Rev 0)\n"
root = svd.parse(svdpath)
chip = svd.collateDevice(root)

# Collect interrupts going to NVIC
interrupts = svd.collectInterrupts(chip['peripherals'], chip['interruptOffset'])

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
#    if name in modelSet:
        svd.dumpModel(model, subdir/name, header)

svd.dumpDevice(chip, subdir/'RP2040', header)
