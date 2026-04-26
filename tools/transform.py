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

    
def createClusterArray(reglist:list, pattern:str, cluster:dict, template=0, dimIndex:list=None):
    """Convert a register list into a cluster array.

    This can be used to convert a linear list of registers of several identical
    subsystems into a cluster array, by giving a pattern to identify the registers
    that belong to a cluster. For example consider a DMA controller with several
    identical channels.

    The pattern given is a regex pattern with two captures:
    - The array index that this register belongs to. Numeric by default; when
      `dimIndex` is supplied, this capture is an alphanumeric instance name
      which must appear in the list (non-members are skipped).
    - The register name inside the cluster (can't be numerical)

    The initial dict to which the registers will be added is passed in cluster.
    This dict must include the cluster name, and should include a description.

    The template parameter selects which instance to use as the prototype for
    the cluster's register set. For numeric indices it is a zero-based int
    (default 0); with named `dimIndex` it may be an int (position into the
    list) or a str (instance name looked up in the list).

    When `dimIndex` is given, the cluster is emitted with `name` as
    `<cluster_name>_%s` (bare %s) and a comma-list `dimIndex` attribute so the
    generator produces one flat struct member per instance (CLK_GPOUT0,
    CLK_REF, ...). Without `dimIndex`, the original `<cluster_name>[%s]` form
    is used.

    The initial register list is passed in reglist, and the function returns the modified
    register list that should be used to replace it.
    """
    pat = re.compile(pattern)
    named = dimIndex is not None
    if named:
        name_to_pos = {n: i for i, n in enumerate(dimIndex)}
        if isinstance(template, str):
            if template not in name_to_pos:
                raise ValueError(f"template '{template}' not in dimIndex {dimIndex}")
            template = name_to_pos[template]

    def indexName(reg, pat):
        match = pat.search(reg['name'])
        if not match:
            return None, None
        if named:
            pos = name_to_pos.get(match.group(1))
            if pos is None:
                return None, None
            return pos, match.group(2)
        try:
            index = int(match.group(1))
            return index, match.group(2)
        except ValueError:
            return int(match.group(2)), match.group(1)
    
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
        if named:
            cluster['name'] += "_%s"
            cluster['dimIndex'] = ','.join(dimIndex)
        else:
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
        first_match_pos = None
        for r in reglist:
            index, regname = indexName(r, pat)
            # fill the cluster with registers from the template instance
            if regname:         # register belongs to cluster
                if first_match_pos is None:
                    first_match_pos = len(registers)
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
        # insert the cluster where the first matched register used to be
        if first_match_pos is None:
            first_match_pos = len(registers)
        registers.insert(first_match_pos, cluster)
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
    """Convert registers into a 2D array with list-valued dim/dimIncrement.

    Two input shapes are accepted, distinguished by the regex's capture-group
    count:

    - **2 groups (scalar grid)**: a flat grid of identically-structured
      scalar registers with two numeric indices (e.g. QMEM0_0, QMEM0_1, ...,
      QMEM3_15). Both row and column indices are read from the regex.

    - **1 group (stack of 1D arrays)**: N already-1D-array registers sharing
      field shape, dim, and dimIncrement (e.g. DESCRIPTOR0_[%s] and
      DESCRIPTOR1_[%s] each with dim=8). The capture group supplies the row
      index; the inner dimension is taken from each matched array's existing
      dim/dimIncrement.

    Both modes produce the same output: one register named `name[%s][%s]`
    with dim=[rows, cols] and dimIncrement=[rowStride, colStride].

    The template parameter selects the prototype: (row, col) for scalar mode,
    (row, _) for stacking mode (the column component is unused).
    """
    pat = re.compile(pattern)
    if pat.groups == 1:
        return _stack1DArrays(reglist, pat, pattern, name, template)
    if pat.groups == 2:
        return _fuseScalarGrid(reglist, pat, pattern, name, template)
    print(f'create2DArray: pattern must have 1 or 2 capture groups, got {pat.groups}')
    return reglist


def _addr(r):
    v = r['addressOffset']
    return v if isinstance(v, int) else int(v, 0)


def _emit2DArray(tmpl_reg, name, base_addr, rows, cols, rowStride, colStride):
    """Rewrite tmpl_reg in place as a 2D array register."""
    tmpl_reg['name'] = name + '[%s][%s]'
    if 'displayName' in tmpl_reg:
        tmpl_reg['displayName'] = name + '[%s][%s]'
    dim = CommentedSeq([rows, cols])
    dim.fa.set_flow_style()
    inc = CommentedSeq([rowStride, colStride])
    inc.fa.set_flow_style()
    tmpl_reg['dim'] = dim
    tmpl_reg['dimIncrement'] = inc
    tmpl_reg['addressOffset'] = base_addr


def _fuseScalarGrid(reglist, pat, pattern, name, template):
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

    colStride = _addr(matches[(0, 1)]) - _addr(matches[(0, 0)])
    rowStride = _addr(matches[(1, 0)]) - _addr(matches[(0, 0)])

    tmpl_reg = matches.get(tuple(template), matches[(0, 0)])
    base_addr = _addr(matches[(0, 0)])
    _emit2DArray(tmpl_reg, name, base_addr, rows, cols, rowStride, colStride)

    fmt = "Registers {} become 2D array {}: Address offset = {}  Dims = {}x{}  Increments = {},{}"
    print(fmt.format(pattern, tmpl_reg['name'], base_addr, rows, cols, rowStride, colStride))

    matched_ids = set(id(r) for r in matches.values())
    return [r for r in reglist if id(r) not in matched_ids] + [tmpl_reg]


def _stack1DArrays(reglist, pat, pattern, name, template):
    """Stack N already-1D-array registers into a single 2D array."""
    matches = {}  # row -> register (must be a 1D array)
    for r in reglist:
        m = pat.match(r['name'])
        if m:
            try:
                matches[int(m.group(1))] = r
            except ValueError:
                pass

    if len(matches) < 2:
        print(f'Register set unsuitable for 2D array: only {len(matches)} 1D-array matches for {pattern}')
        return reglist

    rows = max(matches) + 1
    if set(matches.keys()) != set(range(rows)):
        print(f'create2DArray: outer indices for {pattern} must be 0..N-1, got {sorted(matches)}')
        return reglist

    first = matches[0]
    cols = first.get('dim')
    colStride = first.get('dimIncrement')
    if not isinstance(cols, int) or not isinstance(colStride, int):
        print(f"create2DArray: '{first['name']}' is not a 1D array (dim/dimIncrement must be int)")
        return reglist

    def field_sig(reg):
        return tuple(
            (f.get('name'), f.get('bitOffset'), f.get('bitWidth'))
            for f in reg.get('fields', [])
        )

    sig0 = field_sig(first)
    for row, r in matches.items():
        if r.get('dim') != cols or r.get('dimIncrement') != colStride:
            print(f"create2DArray: '{r['name']}' dim/dimIncrement differ from row 0")
            return reglist
        if field_sig(r) != sig0:
            print(f"create2DArray: '{r['name']}' field shape differs from row 0")
            return reglist

    base_addr = _addr(matches[0])
    rowStride = _addr(matches[1]) - base_addr
    for row in range(rows):
        if _addr(matches[row]) != base_addr + row * rowStride:
            print(f"create2DArray: row {row} of {pattern} breaks linear addressing")
            return reglist

    tmpl_row = template[0] if isinstance(template, (tuple, list)) else 0
    tmpl_reg = matches.get(tmpl_row, matches[0])
    _emit2DArray(tmpl_reg, name, base_addr, rows, cols, rowStride, colStride)

    fmt = "Arrays {} stacked into 2D array {}: Address offset = {}  Dims = {}x{}  Increments = {},{}"
    print(fmt.format(pattern, tmpl_reg['name'], base_addr, rows, cols, rowStride, colStride))

    matched_ids = set(id(r) for r in matches.values())
    return [r for r in reglist if id(r) not in matched_ids] + [tmpl_reg]


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
