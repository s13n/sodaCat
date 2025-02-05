# Functions to manipulate the data structure.
# (C) 2024 Stefan Heinzmann
import re
import sys
    
def renameEntries(array:list, key, pattern:str, replacement):
    """In all entries of array, replace the value of given key using regular expression matching.
    
    Go through the array, and apply a regex substitution to the given key of each entry.    
    """
    pat = re.compile(pattern)
    for e in array:
        if key in e:
            e[key] = pat.sub(replacement, e[key])

    
def createClusterArray(reglist:list, pattern:str, cluster:dict):
    """Convert a register list into a cluster array.
    
    This can be used to convert a linear list of registers of several identical
    subsystems into a cluster array, by giving a pattern to identify the registers
    that belong to a cluster. For example consider a DMA controller with several
    identical channels.

    The pattern given is a regex pattern with two captures:
    - The array index that this register belongs to (must be zero-based numerical)
    - The register name inside the cluster (can't be numerical)

    The initial dict to which the registers will be added is passed in cluster.
    This dict must include the cluster name, and should include a description.

    The initial register list is passed in reglist, and the function returns the modified
    register list that should be used to replace it.
    """
    pat = re.compile(pattern)
    
    def indexName(reg, pat):
        match = pat.search(reg['name'])
        if match:
            try:
                index = int(match.group(1))
                return index, match.group(2)
            except ValueError as ex:
                return int(match.group(2)), match.group(1)
        return None, None
    
    def findDimIncrement(a:list, b:list):
        """ figure out what the address increment is """
        reg0 = a[0]
        reg1 = next(x for x in b if x['name'] == reg0['name'])
        addr0 = reg0['reg']['addressOffset']
        addr1 = reg1['reg']['addressOffset']
        return (addr1 if isinstance(addr1, int) else int(addr1, 0)) - (addr0 if isinstance(addr0, int) else int(addr0, 0))

    addressOffset = sys.maxsize
    instances = []
    for r in reglist:
        index, regname = indexName(r, pat)
        # fill the instances table
        if regname:
            while index >= len(instances):
                instances.append([])
            instances[index].append({ 'name': regname, 'reg': r })
            addressOffset = min(addressOffset, r['addressOffset'] if isinstance(r['addressOffset'], int) else int(r['addressOffset'], 0))
    
    if (len(instances) >= 2) and all(instances):     # at least 2 instances starting with index 0
        cluster = cluster or {}
        cluster['name'] += "[%s]"
        cluster['dim'] = len(instances)
        cluster['addressOffset'] = addressOffset
        cluster['dimIncrement'] = findDimIncrement(instances[0], instances[1])
        fmt = "Registers {} become cluster array {}: Address offset = {}  Increment = {}  Count = {}"
        print(fmt.format(pattern, cluster['name'], cluster['addressOffset'], cluster['dimIncrement'], cluster['dim']))
        # we now move the affected registers from the reglist array to the cluster array
        cluster['registers'] = []
        registers = []
        for i,r in enumerate(reglist):
            index, regname = indexName(r, pat)
            # fill the cluster with registers at index 0
            if regname:         # register belongs to cluster
                if index == 0:  # we only user registers from the first index
                    r['name'] = regname
                    if 'displayName' in r:
                        r['displayName'] = regname
                    r['addressOffset'] = (r['addressOffset'] if isinstance(r['addressOffset'], int) else int(r['addressOffset'], 0)) - cluster['addressOffset']
                    cluster['registers'].append(r)
            else:               # register doesn't belong to cluster
                registers.append(r)
        # we append the new cluster
        registers.append(cluster)
        reglist = registers
    else:
        print('Register set unsuitable for cluster')        

    return reglist

def compareRegisters(left:dict, right:dict, includeDescription=False):
    """Compare two register lists and generate a list of differences.
    """
    regs1 = iter(sorted(left, key=lambda r:r['addressOffset']))
    regs2 = iter(sorted(right, key=lambda r:r['addressOffset']))
    diffs = 0
    r1 = next(regs1, {})
    r2 = next(regs2, {})
    while r1 or r2:         # iterate until both lists exhausted
        r1addr = r1.get('addressOffset', 0xFFFFFFFF)
        r2addr = r2.get('addressOffset', 0xFFFFFFFF)
        if r1addr < r2addr:
            print("right misses register %s at offset %x" % (r1['name'], r1addr))
            diffs += 1
            r1 = next(regs1, {})
            continue
        if r1addr > r2addr:
            print("left misses register %s at offset %x" % (r2['name'], r2addr))
            diffs += 1
            r2 = next(regs2, {})
            continue
        for k in frozenset(r1.keys()) | frozenset(r2.keys()):
            if k == 'description' and not includeDescription:
                continue
            if not k in r1:
                print("left register %s at offset %x misses item %s" % (r1['name'], r1addr, k))
                diffs += 1
            if not k in r2:
                print("left register %s at offset %x misses item %s" % (r1['name'], r1addr, k))
                diffs += 1
            if r1[k] != r2[k]:
                print("register %s at offset %x differs in item %s: %s - %s" % (r1['name'], r1addr, k, r1[k], r2[k]))
                diffs += 1
        r1 = next(regs1, {})
        r2 = next(regs2, {})
    return diffs
