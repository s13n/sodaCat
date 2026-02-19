# Convert between SVD file and internalized data structure.
# (C) 2024 Stefan Heinzmann

import xmltodict
from ruamel.yaml import YAML
import re
from pathlib import Path

def _safe_int(s, base=0):
    """Parse integer string, handling leading zeros that Python 3 int(base=0) rejects."""
    if isinstance(s, int):
        return s
    try:
        return int(s, base=base)
    except ValueError:
        # Strip leading zeros from bare decimal values (e.g. '072', '00000010')
        return int(s.lstrip('0') or '0')

def parse(filename:str):
    """ read a SVD file and return it as a data structure """
    with open(filename, 'r') as file:
        return xmltodict.parse(file.read())

def toNumber(tbl:dict, keys:list):
    """ In a table, in-place convert all listed keys into a number. """
    for k in keys:
        if k in tbl:
            v = re.sub(r'^#', '0b', tbl[k].lower())
            tbl[k] = _safe_int(v)

def toBoolean(tbl:dict, keys:list):
    """ In a table, in-place convert all listed keys into a boolean. """
    for k in keys:
        if k in tbl:
            if tbl[k]:
                tbl[k] = True
            else:
                tbl[k] = False

def asArray(tbl):
    """ return as an array of tables, even if tbl is only a single table
        if tbl is already an array, return it. If it is associative, wrap it in an array. """
    return tbl if isinstance(tbl, list) else ([ tbl ] if tbl else [])

def findNamedEntry(array:list, name:str):
    """ Go through an array and try to find an entry with the given name.
        If not found, or the first parameter isn't an array, returns nil. """
#    return next(e for e in array if e.get('name') == name)
    for e in array:
        if e.get('name') == name:
            return e

def collateInterrupts(peripheral:dict, offset:int):
    """ Go through the interrupts of this peripheral and collate them into an array. """
    peripheral['interrupts'] = asArray(peripheral.get('interrupt'))
    if 'interrupt' in peripheral:
        del peripheral['interrupt']
    for i in peripheral['interrupts']:
        assert i and i.get('value') and i.get('name')
        i['value'] = _safe_int(i['value'])
    if "interrupts" in peripheral and not peripheral.get("interrupts"):
        del peripheral["interrupts"]

def collateEnums(field:dict):
    """ go through the field and collate the enums into an array
        the data structure is modified in place. """
    if field.get('enumeratedValues'):
        field['enumeratedValues'] = asArray(field['enumeratedValues'].get('enumeratedValue'))
        for e in field['enumeratedValues']:
            # we need to treat the values specially, because they may contain don't care bits
            val = re.sub(r'^#', '0b', e['value'].lower())
            if val[0:2] == "0b":
                v = val.replace("x", "0")
                e['value'] = _safe_int(v)
                if val != v:  # value has "don't care" bits
                    v = val[2:].replace("0", "1").replace("x", "0")
                    e['valuemask'] = int(v, base=2)
            else:
                e['value'] = _safe_int(val)

def collateFields(fields:dict):
    """ Go through the register and collate the fields into an array
        The bit ranges are converted to bitOffset/bitWidth style for uniformity
        The list of fields is returned sorted according to bitOffset. """
    fld = asArray(fields.get('field'))
    flds = []
    for f in fld:
        if f.get('bitRange'):
            m = re.match(r'\[([^:]+):([^\]]+)\]', f['bitRange'])
            f['msb'], f['lsb'] = m.group(1,2)
            del f['bitRange']
        if f.get('msb') and f.get('lsb'):
            f['bitOffset'] = f['lsb']
            f['bitWidth'] = str(_safe_int(f['msb']) - _safe_int(f['lsb']) + 1);
            del f['msb']
            del f['lsb']
        if f.get('bitWidth'):
            f['bitWidth'] = _safe_int(f['bitWidth'])
        else:
            f['bitWidth'] = 1
        toNumber(f, [ "bitOffset", "dim", "dimIncrement" ])
        collateEnums(f)
        flds.append(f)
    if 'field' in fields:
        del fields['field']
    flds.sort(key=lambda x: x['bitOffset'])
    return flds if flds else None   # return nil instead of empty table

def collateRegisters(cluster:dict):
    """ Go through the cluster and collate the registers.
        The registers section of a peripheral is a cluster and follows its structure.
        On input, a cluster may contain an array named "register" and/or an array named "cluster".
        The latter contains all clusters at that level, and each of them gets processed recursively.
        Either register or cluster might be an array (when the "dim" element is present).
        Both register and cluster arrays in the cluster are removed.
        The register list is returned as an array that is sorted in place for increasing addresses.
        In the returned list, the distinction between a cluster and a single register is through
        the presence or absence of an entry "registers". """
    reg, clu = asArray(cluster.get('register')), asArray(cluster.get('cluster'))
    regs = []
    ints = [ "addressOffset", "size", "resetMask", "resetValue", "dim", "dimIncrement" ]
    for r in reg:
        toNumber(r, ints)
        r['fields'] = collateFields(r.get('fields', {}))
        regs.append(r)
    if 'register' in cluster:
        del cluster['register']
    for c in clu:
        toNumber(c, ints)
        c['registers'] = collateRegisters(c)
        regs.append(c)
    if 'cluster' in cluster:
        del cluster['cluster']
    regs.sort(key=lambda x: x['addressOffset'])
    return regs

def collatePeripherals(device:dict):
    """ go through the device and collate the peripherals into an array
        the data structure is modified in place. """
    if device['peripherals']:
        per = device['peripherals']
        device['peripherals'] = asArray(per['peripheral'])
        for p in device['peripherals']:
            toNumber(p, [ "baseAddress", "size", "resetMask", "resetValue", "dim", "dimIncrement" ])
            p['registers'] = collateRegisters(p.get('registers', {}))
            collateInterrupts(p, device['interruptOffset'])
            # we now go through the list of address blocks
            p['addressBlocks'] = asArray(p.get('addressBlock'))
            if 'addressBlock' in p:
                del p['addressBlock']
            for b in p['addressBlocks']:
                toNumber(b, [ "offset", "size" ])
            if 'addressBlocks' in p and not p['addressBlocks']:
                del p['addressBlocks']

def collateCpu(device:dict):
    """ go through the device CPU section and collate all its information
        the data structure is modified in place. """
    cpu = device['cpu']
    if cpu:
        toNumber(cpu, [ "nvicPrioBits" ])
        toBoolean(cpu, [ "mpuPresent", "fpuPresent", "vendorSystickConfig" ])
    device['interruptOffset'] = 16     #TODO: Make this dependent on CPU type
    device['interrupts'] = device.get('interrupts', [])

def collateDevice(root:dict):
    """ go through the device and collate all its information
        the data structure is modified in place. """
    toNumber(root['device'], [ "addressUnitBits", "width", "size", "resetMask", "resetValue" ])
    collateCpu(root['device'])
    collatePeripherals(root['device'])
    return root['device']

def collectInterrupts(peripherals:list, offset:int):
    """ go through the list of peripherals and return interrupt info as a sorted dict.
        The returned dict is indexed by interrupt number. Note that the index is not
        necessarily contiguous, so a list doesn't fit here.
        Each entry is an array of interrupt sources as text in the format
        "<peripheral_name>.<interrupt_name>", with the meaning that those
        interrupt sources are ored into one interrupt vector. """
    ints = {}
    for p in peripherals:
        for intr in p.get('interrupts', []):
            v = intr['value'] + offset
            if not v in ints:
                ints[v] = []
            ints[v].append(p['name'] + "." + intr['name'])
    return dict(sorted(ints.items()))

def collectModelsAndInstances(peripherals:list):
    """ Go through the list of peripherals and return model and instance dicts.
        The first returned dict is indexed by model name, the second by peripheral name. """
    models, ins = {}, {}
    n = 0
    for per in peripherals:
        name = per['name']
        assert isinstance(per['baseAddress'], int)
        ins[name] = { 'id': n, 'baseAddress': per['baseAddress'], 'interrupts': [], 'parameters': [] }
        n += 1
        if '@derivedFrom' in per:
            base = findNamedEntry(peripherals, per['@derivedFrom'])
            model = base.get('headerStructName', base['name'])
            ins[name]['model'] = model
            ins[name]['version'] = per.get('version', base.get('version'))
            ins[name]['description'] = per.get('description', base.get('description'))
        else:
            model = per.get('headerStructName', name)
            ins[name]['model'] = model
            ins[name]['version'] = per.get('version')
            ins[name]['description'] = per.get('description')
            del per['baseAddress']
            models[model] = per
        for i in per.get('interrupts', []):
            ins[name]['interrupts'].append({ 'name': i['name'], 'value': i['value'] })
            del i['value']
        for p in per.get('parameters', []):
            ins[name]['parameters'].append({ 'name': p['name'], 'value': p['value'] })
            del p['value']

    # we can't rename the models within the loop above, because it relies on the instance names
    for k, m in models.items():
        m['name'] = k
    return models, ins

def printInstances(instances:dict):
    """ Print a list of peripheral instances, sorted according to base address. """
    print("List of peripheral instances, sorted according to base address:")
    instIx = []
    for name,instance in instances.items():
        instIx.append({ 'name': name, 'addr': instance['baseAddress'] })
    instIx.sort(key=lambda x: x['addr'])
    fmt1 = '{:16}: {:16} ({:3}) at 0x{:08x} ({}/D{}) -- {}'
    fmt2 = '{:16}: {:16} ({:3}) at 0x{:08x} -- {}'
    for ix in instIx:
        inst = instances[ix['name']]
        if 'bus' in inst and type(inst.domain) == "number":
            print(fmt1.format(ix['name'], inst['model'], inst['id'], inst['baseAddress'], inst['bus'], inst['domain'], inst['description']))
        else:
            print(fmt2.format(ix['name'], inst['model'], inst['id'], inst['baseAddress'], inst['description']))

def printInterrupts(interrupts:dict):
    """ Print a list of interrupts, sorted according to exception number. """
    print("List of interrupts, sorted according to exception number:")
    for i in interrupts:
        s = None
        for src in interrupts[i]:
            s = (s + ", " + src) if s else src
        print("{:3}: {}".format(i, s))

def dumpModel(model:dict, filename:Path, comment:str):
    """ write a YAML file for a model """
    file = open(str(filename) + ".yaml", "w")
    if comment:
        file.write(comment + "\n")
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.dump(model, file)
    file.close()

def dumpPeripheral(device:dict, name:str, filename:Path, comment:str):
    """ write a YAML file for a peripheral """
    per = findNamedEntry(device['peripherals'], name)
    # propagate defaults from device level to peripheral level
    per['size'] = per.get('size', device['size'])
    per['access'] = per.get('access', device['access'])
    per['protection'] = per.get('protection', device['protection'])
    per['resetValue'] = per.get('resetValue', device['resetValue'])
    per['resetMask'] = per.get('resetMask', device['resetMask'])
    dumpModel(per, filename, comment)

def dumpDevice(device:dict, filename:Path, header:str):
    """ write a YAML file for the entire device """
    file = open(str(filename) + ".yaml", "w")
    if header:
        file.write(header)
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.dump(device, file)
    file.close()
