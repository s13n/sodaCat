# Functions to manipulate the data structure.
# (C) 2024 Stefan Heinzmann
import copy
import re
import sys
from ruamel.yaml.comments import CommentedSeq
    
def _strip_yaml_metadata(obj):
    """Convert ruamel.yaml CommentedMap/CommentedSeq trees to plain dict/list.

    Transform inputs that come from a ruamel.yaml-parsed family-config file
    carry comment, anchor and flow-style metadata.  When a transform stores
    such an input directly into the emitted block model and the model is
    then dumped, the metadata leaks through -- comments meant for the
    family config end up attached to model entries.  Run inputs through
    this stripper before assigning them to the cluster/register dict so
    only the data crosses the transform boundary.
    """
    if isinstance(obj, dict):
        return {k: _strip_yaml_metadata(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strip_yaml_metadata(v) for v in obj]
    return obj


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

        # Union fields from non-template instances into the cluster prototype.
        # The cluster carries the superset of fields across slots; it's the
        # programmer's responsibility (typically via per-instance params or the
        # surrounding driver contract) to know which fields actually exist on
        # which slot.  RP2040 CLOCKS is the original motivator — CLK_REF_CTRL
        # and CLK_SYS_CTRL have an SRC field that the GPOUT/PERI/USB/ADC/RTC
        # slots don't, and intersecting silently dropped it.
        cluster_subregs = {r['name']: r for r in cluster['registers']}
        merged_into = set()
        for inst_idx, inst_regs in enumerate(instances):
            if inst_idx == template:
                continue
            for entry in inst_regs:
                target = cluster_subregs.get(entry['name'])
                if target is None:
                    # sub-register doesn't exist in the template instance — no
                    # offset to assign within the cluster slot, skip.
                    continue
                target_fields = target.setdefault('fields', [])
                target_by_name = {f['name']: f for f in target_fields}
                for f in entry['reg'].get('fields', []):
                    fname = f['name']
                    existing = target_by_name.get(fname)
                    if existing is None:
                        nb = f.get('bitOffset')
                        nw = f.get('bitWidth', 1)
                        # Treat (bitOffset, bitWidth) as the field's identity.
                        # A new name occupying an identical bit range is a
                        # name-alias for the existing field — skip it.  Keeps
                        # the cluster a superset over distinct bits, not over
                        # distinct names.  (E.g. STM32H7 MDMA per-channel ISRs
                        # carry TEIF, TEIF1, TEIF2, ... all at bit 0 width 1
                        # — aliases, not extra fields.)
                        if any(e.get('bitOffset') == nb and
                               e.get('bitWidth', 1) == nw
                               for e in target_fields):
                            continue
                        target_fields.append(f)
                        target_by_name[fname] = f
                        merged_into.add(id(target))
                    else:
                        eb = existing.get('bitOffset')
                        ew = existing.get('bitWidth', 1)
                        nb = f.get('bitOffset')
                        nw = f.get('bitWidth', 1)
                        if eb != nb or ew != nw:
                            print(f"WARNING: cluster {cluster['name']}.{entry['name']}.{fname}: "
                                  f"bit positions differ across instances ({eb}/{ew} vs {nb}/{nw})")
        # For sub-registers we touched, sort fields by bitOffset so the
        # merged-in entries don't appear out of order.
        for sub in cluster['registers']:
            if id(sub) in merged_into and 'fields' in sub:
                sub['fields'].sort(key=lambda f: f.get('bitOffset', 0))

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

    - **1 group (stack of 1D arrays)**: N already-1D-array registers
      sharing dimIncrement but not necessarily dim or field set. The
      capture group supplies the row index (parsed as decimal first,
      falling back to base 16 so single hex letters A..F work as 10..15).
      The inner dimension is computed from rowStride / colStride, so rows
      with dim < cols leave phantom (reserved) inner indices at the end.
      Fields are unioned across rows under the same contract as
      mergeArrays: same-named fields must share bit position, different-
      named fields must not overlap at the bit level.

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
        if not m:
            continue
        s = m.group(1)
        try:
            row = int(s)
        except ValueError:
            try:
                row = int(s, 16)
            except ValueError:
                continue
        matches[row] = r

    if len(matches) < 2:
        print(f'Register set unsuitable for 2D array: only {len(matches)} 1D-array matches for {pattern}')
        return reglist

    rows = max(matches) + 1
    if set(matches.keys()) != set(range(rows)):
        print(f'create2DArray: outer indices for {pattern} must be 0..N-1, got {sorted(matches)}')
        return reglist

    first = matches[0]
    colStride = first.get('dimIncrement')
    if not isinstance(colStride, int) or not isinstance(first.get('dim'), int):
        print(f"create2DArray: '{first['name']}' is not a 1D array (dim/dimIncrement must be int)")
        return reglist
    for row, r in matches.items():
        if r.get('dimIncrement') != colStride:
            print(f"create2DArray: row {row} dimIncrement {r.get('dimIncrement')} "
                  f"differs from row 0 ({colStride})")
            return reglist
        if not isinstance(r.get('dim'), int):
            print(f"create2DArray: row {row} dim must be int")
            return reglist

    base_addr = _addr(matches[0])
    rowStride = _addr(matches[1]) - base_addr
    if rowStride <= 0 or rowStride % colStride != 0:
        print(f"create2DArray: rowStride {rowStride} not a positive multiple "
              f"of colStride {colStride}")
        return reglist
    cols = rowStride // colStride

    for row in range(rows):
        if _addr(matches[row]) != base_addr + row * rowStride:
            print(f"create2DArray: row {row} of {pattern} breaks linear addressing")
            return reglist
        if matches[row].get('dim') > cols:
            print(f"create2DArray: row {row} dim {matches[row]['dim']} exceeds "
                  f"inferred cols {cols}")
            return reglist

    # Field union across rows (mirrors mergeArrays' bit-disjointness contract).
    merged_fields = []
    bit_owners = {}  # bit -> field name
    for row in range(rows):
        for f in matches[row].get('fields') or []:
            fname = f.get('name')
            offset = f.get('bitOffset', 0)
            width = f.get('bitWidth', 1)
            existing = next((mf for mf in merged_fields if mf.get('name') == fname), None)
            if existing is not None:
                if (existing.get('bitOffset') != offset
                        or existing.get('bitWidth') != width):
                    print(f"create2DArray: field '{fname}' has incompatible position "
                          f"across /{pattern}/ rows: "
                          f"[{existing.get('bitOffset')}:{existing.get('bitWidth')}] "
                          f"vs [{offset}:{width}]")
                    return reglist
                continue
            for b in range(offset, offset + width):
                if b in bit_owners:
                    print(f"create2DArray: field '{fname}' bit {b} overlaps with "
                          f"existing field '{bit_owners[b]}' in /{pattern}/ stack")
                    return reglist
                bit_owners[b] = fname
            merged_fields.append(copy.deepcopy(f))
    merged_fields.sort(key=lambda f: f.get('bitOffset', 0))

    tmpl_row = template[0] if isinstance(template, (tuple, list)) else 0
    tmpl_reg = matches.get(tmpl_row, matches[0])
    tmpl_reg['fields'] = merged_fields
    _emit2DArray(tmpl_reg, name, base_addr, rows, cols, rowStride, colStride)

    fmt = "Arrays {} stacked into 2D array {}: Address offset = {}  Dims = {}x{}  Increments = {},{}"
    print(fmt.format(pattern, tmpl_reg['name'], base_addr, rows, cols, rowStride, colStride))

    matched_ids = set(id(r) for r in matches.values())
    return [r for r in reglist if id(r) not in matched_ids] + [tmpl_reg]


def clusterArrays(reglist:list, pattern:str, name:str, description=None):
    """Group multiple top-level array registers sharing dim/dimIncrement into a cluster array.

    Some SVDs encode per-channel/per-stream registers as separate <dim> arrays
    at adjacent offsets (e.g. LPC43 GPDMA: C%sSRCADDR, C%sDESTADDR, C%sLLI,
    C%sCONTROL, C%sCONFIG, each with dim=8, dimIncrement=32). The natural
    shape is a single cluster of N registers repeating dim times.

    The pattern is a regex with one capture group naming the inner register;
    it is matched against the literal SVD-array name (with `%s` intact). For
    example 'C%s(.+)' matches 'C%sSRCADDR' and captures 'SRCADDR'.

    All matched registers must share dim, dimIncrement, and dimIndex. The
    cluster's base offset is the minimum of the matched registers' offsets;
    each member's offset becomes (orig_offset - base). The cluster is
    inserted at the position of the first matched register.
    """
    pat = re.compile(pattern)

    matches = []  # (member_name, register)
    for r in reglist:
        m = pat.match(r['name'])
        if m:
            matches.append((m.group(1), r))

    if len(matches) < 2:
        print(f'clusterArrays: need 2+ matches, got {len(matches)} for {pattern}')
        return reglist

    first_member, first_reg = matches[0]
    dim = first_reg.get('dim')
    dimIncrement = first_reg.get('dimIncrement')
    dimIndex = first_reg.get('dimIndex')
    if not isinstance(dim, int) or not isinstance(dimIncrement, int):
        print(f"clusterArrays: '{first_reg['name']}' is not a 1D array (dim/dimIncrement must be int)")
        return reglist
    for member_name, r in matches[1:]:
        if r.get('dim') != dim or r.get('dimIncrement') != dimIncrement:
            print(f"clusterArrays: '{r['name']}' dim/dimIncrement differ from '{first_reg['name']}'")
            return reglist
        if r.get('dimIndex') != dimIndex:
            print(f"clusterArrays: '{r['name']}' dimIndex differs from '{first_reg['name']}'")
            return reglist

    base = min(_addr(r) for _, r in matches)

    members = []
    for member_name, r in matches:
        r['name'] = member_name
        if 'displayName' in r:
            r['displayName'] = member_name
        r['addressOffset'] = _addr(r) - base
        for k in ('dim', 'dimIncrement', 'dimIndex'):
            r.pop(k, None)
        members.append(r)

    cluster = {'name': f'{name}[%s]'}
    if description:
        cluster['description'] = description
    cluster['dim'] = dim
    cluster['addressOffset'] = base
    cluster['dimIncrement'] = dimIncrement
    cluster['registers'] = members

    fmt = "Arrays {} clustered into {}: Address offset = {}  Increment = {}  Count = {}"
    print(fmt.format(pattern, cluster['name'], base, dimIncrement, dim))

    matched_ids = set(id(r) for _, r in matches)
    result = []
    inserted = False
    for r in reglist:
        if id(r) in matched_ids:
            if not inserted:
                result.append(cluster)
                inserted = True
        else:
            result.append(r)
    return result


def createCluster2DArray(reglist:list, pattern:str, name:str,
                          addressOffset:int, outerStride:int,
                          innerDim:int, innerStride:int,
                          outerDim:int=None, description:str=None,
                          enumeratedIndices=None):
    """Group flat registers laid out as outer x inner into a 2D cluster array.

    Some peripherals organise registers as `outerStride`-spaced regions
    each holding up to `innerDim` slots at `innerStride` (e.g. LPC43 CCU1:
    11 clock branches at stride 0x100, each up to 32 CFG/STAT pairs at
    stride 8).  This transform takes a regex `pattern` with one capture
    group naming the in-slot member (e.g. `(CFG|STAT)`), computes outer
    and inner indices from each matched register's address, and emits a
    single cluster array with list-valued dim/dimIncrement:

        name[%s][%s]               dim=[outer_dim, innerDim]
                                   dimIncrement=[outerStride, innerStride]
          <member 1>               addressOffset = its in-slot offset
          <member 2>               ...

    Outer dim defaults to max(outer_idx) + 1 (auto-sized to populated
    branches) but can be overridden via `outerDim` to reflect the full
    address space (e.g. CCU1 only populates 11 of 15 possible 0x100-byte
    branches in its 4 KB region; outerDim=15 lets the model accommodate
    the unused trailing branches and stay aligned with CCU2 for shared-
    block usage).  Populated slots don't need to span every (outer, inner)
    — sparse coverage is fine, the emitted array just has reserved
    entries at unpopulated indices.
    All registers with the same member name must share the same in-slot
    offset.  Field sets are unioned per member with the same bit-
    disjointness contract as mergeArrays.
    """
    pat = re.compile(pattern)
    matches = {}      # (outer_idx, inner_idx, member_name) -> register
    member_offsets = {}  # member_name -> in-slot offset

    for r in reglist:
        if not isinstance(r, dict):
            continue
        m = pat.match(r.get('name', ''))
        if not m:
            continue
        addr = _addr(r)
        rel = addr - addressOffset
        if rel < 0:
            continue
        outer_idx, within = divmod(rel, outerStride)
        inner_idx, in_slot = divmod(within, innerStride)
        if inner_idx >= innerDim:
            print(f"createCluster2DArray: '{r['name']}' inner_idx {inner_idx} "
                  f">= innerDim {innerDim}")
            return reglist
        member_name = m.group(1)
        prev = member_offsets.get(member_name)
        if prev is None:
            member_offsets[member_name] = in_slot
        elif prev != in_slot:
            print(f"createCluster2DArray: '{r['name']}' member '{member_name}' "
                  f"at in-slot offset {in_slot}, expected {prev}")
            return reglist
        matches[(outer_idx, inner_idx, member_name)] = r

    if not matches:
        print(f"  WARNING: createCluster2DArray: no registers match '{pattern}'")
        return reglist

    populated_outer = max(o for (o, _, _) in matches) + 1
    if outerDim is None:
        outer_dim = populated_outer
    else:
        if populated_outer > outerDim:
            print(f"createCluster2DArray: populated outer dim {populated_outer} "
                  f"exceeds requested outerDim {outerDim}")
            return reglist
        outer_dim = outerDim

    # Build the cluster's member registers: one per distinct member name,
    # with field union across all populated (outer, inner) instances.
    members = []
    for member_name, in_slot in sorted(member_offsets.items(), key=lambda x: x[1]):
        instances = [r for (_, _, m), r in matches.items() if m == member_name]
        merged_fields = []
        bit_owners = {}
        for inst in instances:
            for f in inst.get('fields') or []:
                fname = f.get('name')
                offset = f.get('bitOffset', 0)
                width = f.get('bitWidth', 1)
                existing = next((mf for mf in merged_fields if mf.get('name') == fname), None)
                if existing is not None:
                    if (existing.get('bitOffset') != offset
                            or existing.get('bitWidth') != width):
                        print(f"createCluster2DArray: field '{fname}' in member "
                              f"'{member_name}' has incompatible position: "
                              f"[{existing.get('bitOffset')}:{existing.get('bitWidth')}] "
                              f"vs [{offset}:{width}]")
                        return reglist
                    continue
                for b in range(offset, offset + width):
                    if b in bit_owners:
                        print(f"createCluster2DArray: field '{fname}' bit {b} "
                              f"in member '{member_name}' overlaps with "
                              f"'{bit_owners[b]}'")
                        return reglist
                    bit_owners[b] = fname
                merged_fields.append(copy.deepcopy(f))
        merged_fields.sort(key=lambda f: f.get('bitOffset', 0))

        proto = copy.deepcopy(instances[0])
        proto['name'] = member_name
        if 'displayName' in proto:
            proto['displayName'] = member_name
        proto['addressOffset'] = in_slot
        proto['fields'] = merged_fields
        for k in ('dim', 'dimIncrement', 'dimIndex'):
            proto.pop(k, None)
        # The first instance's per-pair description (e.g. "CLK_APB3_BUS
        # clock configuration register") is misleading at cluster scope;
        # drop it so the C++ generator inherits the cluster-level one.
        proto.pop('description', None)
        members.append(proto)

    dim = CommentedSeq([outer_dim, innerDim])
    dim.fa.set_flow_style()
    inc = CommentedSeq([outerStride, innerStride])
    inc.fa.set_flow_style()
    cluster = {
        'name': name + '[%s][%s]',
        'addressOffset': addressOffset,
        'dim': dim,
        'dimIncrement': inc,
        'registers': members,
    }
    if description:
        cluster['description'] = description
    if enumeratedIndices is not None:
        cluster['enumeratedIndices'] = _strip_yaml_metadata(enumeratedIndices)

    fmt = ("Registers /{}/ become 2D cluster array {}: "
           "addressOffset=0x{:x} dim=[{},{}] dimIncrement=[{},{}]")
    print(fmt.format(pattern, cluster['name'], addressOffset, outer_dim,
                     innerDim, outerStride, innerStride))

    matched_ids = set(id(r) for r in matches.values())
    return [r for r in reglist if id(r) not in matched_ids] + [cluster]


def createIndexedRegisterArray(reglist:list, pattern:str, name:str,
                                addressOffset:int, stride:int, dim:int,
                                description:str=None,
                                enumeratedIndices=None):
    """Fuse flat registers at strided offsets into a single 1D register array.

    Many clock-controller and similar peripherals expose a flat list of
    same-shape register names (LPC43 CGU's BASE_SAFE_CLK / BASE_USB0_CLK
    / ... / BASE_CGU_OUT1_CLK is the canonical case: 24 registers at
    offsets 0x5C..0xC8, all sharing the same field layout, with a few
    reserved gaps between them).  The natural representation is a single
    register array indexed by an `enumeratedIndices` enum that carries
    the per-slot semantic name.

    All matched registers must lie in `[addressOffset, addressOffset +
    dim*stride)`, must align to `stride`, must hash to distinct slots,
    and must have unioneable field sets (same-named fields share bit
    position, different-named fields must not overlap on the bit level
    -- the same contract `mergeArrays` and `createCluster2DArray` use).
    Slots that no register maps to remain reserved in the emitted array
    and the consumer-side enum simply doesn't name them.

    Pattern carries no capture groups; the regex only filters which
    top-level registers participate.  Indices are derived from address.
    """
    pat = re.compile(pattern)
    matches = {}  # slot -> register
    for r in reglist:
        if not isinstance(r, dict):
            continue
        if not pat.match(r.get('name', '')):
            continue
        addr = _addr(r)
        rel = addr - addressOffset
        if rel < 0 or rel >= dim * stride:
            continue
        if rel % stride:
            print(f"createIndexedRegisterArray: '{r['name']}' at 0x{addr:x} "
                  f"is not aligned to stride {stride}")
            return reglist
        slot = rel // stride
        if slot in matches:
            print(f"createIndexedRegisterArray: '{r['name']}' and "
                  f"'{matches[slot]['name']}' both map to slot {slot}")
            return reglist
        matches[slot] = r

    if not matches:
        print(f"  WARNING: createIndexedRegisterArray: no registers match "
              f"'{pattern}' in [0x{addressOffset:x}, "
              f"0x{addressOffset + dim*stride:x})")
        return reglist

    # Field union across all matched instances; bit-disjointness contract.
    merged_fields = []
    bit_owners = {}
    for slot in sorted(matches):
        r = matches[slot]
        for f in r.get('fields') or []:
            fname = f.get('name')
            offset = f.get('bitOffset', 0)
            width = f.get('bitWidth', 1)
            existing = next((mf for mf in merged_fields if mf.get('name') == fname), None)
            if existing is not None:
                if (existing.get('bitOffset') != offset
                        or existing.get('bitWidth') != width):
                    print(f"createIndexedRegisterArray: field '{fname}' has "
                          f"incompatible position across /{pattern}/ matches: "
                          f"[{existing.get('bitOffset')}:{existing.get('bitWidth')}] "
                          f"vs [{offset}:{width}]")
                    return reglist
                continue
            for b in range(offset, offset + width):
                if b in bit_owners:
                    print(f"createIndexedRegisterArray: field '{fname}' bit {b} "
                          f"overlaps with existing field '{bit_owners[b]}' in "
                          f"/{pattern}/ merge")
                    return reglist
                bit_owners[b] = fname
            merged_fields.append(copy.deepcopy(f))
    merged_fields.sort(key=lambda f: f.get('bitOffset', 0))

    # Inherit register-level scalar attrs from the lowest-slot match,
    # except for `access` which is unioned across matches (the array as a
    # whole supports the broadest access mode any slot does, so a mix of
    # read-only and read-write members yields read-write).
    first = matches[min(matches)]
    array = {'name': name + '[%s]'}
    if description:
        array['description'] = description
    elif first.get('description'):
        array['description'] = first['description']
    array['addressOffset'] = addressOffset
    array['dim'] = dim
    array['dimIncrement'] = stride
    accesses = {r.get('access') for r in matches.values() if r.get('access')}
    if len(accesses) == 1:
        array['access'] = next(iter(accesses))
    elif accesses:
        # Mixed: read-write is a superset of read-only and write-only, so
        # use it whenever any member declares it OR when both halves are
        # represented separately.
        if 'read-write' in accesses or {'read-only', 'write-only'} <= accesses:
            array['access'] = 'read-write'
        else:
            array['access'] = first.get('access')
    for key in ('resetValue', 'resetMask', 'size'):
        if key in first:
            array[key] = first[key]
    array['fields'] = merged_fields
    if enumeratedIndices is not None:
        array['enumeratedIndices'] = _strip_yaml_metadata(enumeratedIndices)

    fmt = ("Registers /{}/ become indexed register array {}: "
           "addressOffset=0x{:x} dim={} stride={} (populated {}/{} slots)")
    print(fmt.format(pattern, array['name'], addressOffset, dim, stride,
                     len(matches), dim))

    matched_ids = set(id(r) for r in matches.values())
    return [r for r in reglist if id(r) not in matched_ids] + [array]


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
