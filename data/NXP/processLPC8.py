import sys
import os
p = os.path.abspath("./tools")
sys.path.append(p)
import svd
from pathlib import Path

subdir = Path("./data/NXP/LPC8")

svdfile = "./svd/LPC865.svd"
tree = svd.parse(svdfile)
chip = svd.collateDevice(tree)

header = "# Created from LPC865.svd\n"

interrupts = svd.collectInterrupts(chip['peripherals'], chip['interruptOffset'])
models, instances = svd.collectModelsAndInstances(chip['peripherals'])

svd.printInstances(instances)
print()
svd.printInterrupts(interrupts)

del chip['peripherals']
chip['instances'] = instances
chip['interrupts'] = interrupts
chip['buses'] = {
    'AHB': { 'addr': 0x50000000, 'size': 0x00014000 },
    'APB': { 'addr': 0x40000000, 'size': 0x00080000 }
}

subdir.mkdir(parents=True, exist_ok=True)
svd.dumpDevice(chip, subdir/'LPC865', header)

for name in models:
    svd.dumpModel(models[name], subdir/name, header)
