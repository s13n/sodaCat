# Functions to manipulate the data structure.
# (C) 2024 Stefan Heinzmann
import re
import sys
from ruamel.yaml.comments import CommentedSeq
    
def renameEntries(array:list, key, pattern:str, replacement):
    """In all entries of array, replace the value of given key using regular expression matching.
    
    Go through the array, and apply a regex substitution to the given key of each entry.    
    """
    pat = re.compile(pattern)
    for e in array:
        if key in e:
            e[key] = pat.sub(replacement, e[key])

    
def createClusterArray(reglist:list, pattern:str, cluster:dict, template:int=0):
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

    The template parameter selects which instance index to use as the prototype
    for the cluster's register set (default 0). Use a non-zero index when some
    instances have additional registers (e.g. enhanced DMA channels with TR3/BR2).

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
        # Compute stride from the template and its nearest neighbor.
        # Search from neighbor into template (template is the superset, so name matches succeed).
        neighbor = template + 1 if template + 1 < len(instances) else template - 1
        cluster['dimIncrement'] = abs(findDimIncrement(instances[neighbor], instances[template]))
        fmt = "Registers {} become cluster array {}: Address offset = {}  Increment = {}  Count = {}"
        print(fmt.format(pattern, cluster['name'], cluster['addressOffset'], cluster['dimIncrement'], cluster['dim']))
        # we now move the affected registers from the reglist array to the cluster array
        cluster['registers'] = []
        registers = []
        for i,r in enumerate(reglist):
            index, regname = indexName(r, pat)
            # fill the cluster with registers from the template instance
            if regname:         # register belongs to cluster
                if index == template:
                    r['name'] = regname
                    if 'displayName' in r:
                        r['displayName'] = regname
                    if 'alternateRegister' in r:
                        _, altname = indexName({'name': r['alternateRegister']}, pat)
                        if altname:
                            r['alternateRegister'] = altname
                    r['addressOffset'] = (r['addressOffset'] if isinstance(r['addressOffset'], int) else int(r['addressOffset'], 0)) - cluster['addressOffset'] - template * cluster['dimIncrement']
                    cluster['registers'].append(r)
            else:               # register doesn't belong to cluster
                registers.append(r)
        # we append the new cluster
        registers.append(cluster)
        reglist = registers
    else:
        print('Register set unsuitable for cluster')        

    return reglist

def createArray(reglist:list, pattern:str, name:str, template:int=0):
    """Convert numbered registers into a single register array with dim/dimIncrement.

    This collapses a sequence of identically-structured registers with numbered
    names (e.g. FGCLUT0, FGCLUT1, ..., FGCLUT255) into a single register with
    dim/dimIncrement properties (e.g. FGCLUT[%s] with dim=256, dimIncrement=4).

    The pattern is a regex with one capture group for the zero-based array index.
    The name parameter specifies the base name for the resulting array register.
    The template parameter selects which instance to use as prototype (default 0).
    """
    pat = re.compile(pattern)

    # Collect matching registers with their indices
    matches = []  # (index, register)
    for r in reglist:
        m = pat.match(r['name'])
        if m:
            try:
                matches.append((int(m.group(1)), r))
            except ValueError:
                pass

    if len(matches) < 2:
        print(f'Register set unsuitable for array: only {len(matches)} matches for {pattern}')
        return reglist

    matches.sort(key=lambda x: x[0])

    # Calculate dimIncrement from first two consecutive instances
    def addr(r):
        v = r['addressOffset']
        return v if isinstance(v, int) else int(v, 0)

    dimIncrement = addr(matches[1][1]) - addr(matches[0][1])

    # Find template instance
    tmpl_reg = next((r for idx, r in matches if idx == template), matches[0][1])

    # Modify template in place
    tmpl_reg['name'] = name + '[%s]'
    if 'displayName' in tmpl_reg:
        tmpl_reg['displayName'] = name + '[%s]'
    tmpl_reg['dim'] = len(matches)
    tmpl_reg['dimIncrement'] = dimIncrement
    # Adjust addressOffset to the start of the array (index 0)
    tmpl_reg['addressOffset'] = addr(tmpl_reg) - template * dimIncrement

    fmt = "Registers {} become array {}: Address offset = {}  Increment = {}  Count = {}"
    print(fmt.format(pattern, tmpl_reg['name'], addr(tmpl_reg), dimIncrement, len(matches)))

    # Build result: non-matched registers + array register at end
    matched_ids = set(id(r) for _, r in matches)
    result = [r for r in reglist if id(r) not in matched_ids]
    result.append(tmpl_reg)
    return result


def create2DArray(reglist:list, pattern:str, name:str, template:tuple=(0,0)):
    """Convert numbered registers into a 2D register array with list-valued dim/dimIncrement.

    This collapses a grid of identically-structured registers with two numeric
    indices (e.g. QMEM0_0, QMEM0_1, ..., QMEM3_15) into a single register with
    dim=[rows, cols] and dimIncrement=[rowStride, colStride] (e.g. QMEM[%s][%s]
    with dim=[4, 16], dimIncrement=[64, 4]).

    The pattern is a regex with two capture groups for the zero-based row and
    column indices. The name parameter specifies the base name for the resulting
    array register. The template parameter selects which (row, col) instance to
    use as prototype (default (0, 0)).
    """
    pat = re.compile(pattern)

    # Collect matching registers with their (row, col) indices
    matches = {}  # (row, col) -> register
    for r in reglist:
        m = pat.match(r['name'])
        if m:
            try:
                row, col = int(m.group(1)), int(m.group(2))
                matches[(row, col)] = r
            except ValueError:
                pass

    if len(matches) < 4:
        print(f'Register set unsuitable for 2D array: only {len(matches)} matches for {pattern}')
        return reglist

    rows = max(r for r, c in matches) + 1
    cols = max(c for r, c in matches) + 1

    if len(matches) != rows * cols:
        print(f'Incomplete 2D array for {pattern}: expected {rows}x{cols}={rows*cols}, got {len(matches)}')
        return reglist

    def addr(r):
        v = r['addressOffset']
        return v if isinstance(v, int) else int(v, 0)

    # Calculate strides from adjacent elements
    colStride = addr(matches[(0, 1)]) - addr(matches[(0, 0)])
    rowStride = addr(matches[(1, 0)]) - addr(matches[(0, 0)])

    # Find template instance
    tmpl_reg = matches.get(template, matches[(0, 0)])

    # Modify template in place
    tmpl_reg['name'] = name + '[%s][%s]'
    if 'displayName' in tmpl_reg:
        tmpl_reg['displayName'] = name + '[%s][%s]'
    dim = CommentedSeq([rows, cols])
    dim.fa.set_flow_style()
    inc = CommentedSeq([rowStride, colStride])
    inc.fa.set_flow_style()
    tmpl_reg['dim'] = dim
    tmpl_reg['dimIncrement'] = inc

    fmt = "Registers {} become 2D array {}: Address offset = {}  Dims = {}x{}  Increments = {},{}"
    print(fmt.format(pattern, tmpl_reg['name'], addr(tmpl_reg), rows, cols, rowStride, colStride))

    # Build result: non-matched registers + array register at end
    matched_ids = set(id(r) for r in matches.values())
    result = [r for r in reglist if id(r) not in matched_ids]
    result.append(tmpl_reg)
    return result


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
