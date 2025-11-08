import sys
import os
p = os.path.abspath("./tools")
sys.path.append(p)
import svd
from pathlib import Path

subdir = Path("./data/NXP/iMX8MP8")

svdfile = "./svd/MIMX8MP8_cm7.svd"
header = "# Created from MIMX8MP8_cm7.svd\n"
tree = svd.parse(svdfile)
chip = svd.collateDevice(tree)

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
svd.dumpDevice(chip, subdir/'MIMX8MP8_cm7', header)

for name in models:
    svd.dumpModel(models[name], subdir/name, header)
