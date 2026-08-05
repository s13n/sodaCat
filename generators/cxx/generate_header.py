"""Unified C++20 header generator for sodaCat models.

Usage: python3 generate_header.py <model.yaml> <model_name> <suffix>
                                  [--endian <native|big|little>]

Each invocation writes both a `.hpp` header and a `.cppm` module wrapper.
The generated formatting is deliberately rough — it is meant to be fine
tuned with clang-format or a similar tool, which does that job far better
than any amount of care taken here.

Model type detection, in this order:
  - `registers` key   → peripheral block header
  - `cpu` key         → chip/SoC integration header.  Subfamily YAMLs also
                        carry an `instances:` map (the subfamily-common
                        subset) but no `cpu:` — only chips have one, so it
                        is the reliable discriminator.
  - `signals`/`clocks` key
                      → clock tree header.  `clocks:` is the subfamily
                        form; the formatter descends into it.
  - `inherits:`/`instances:`/`models:` without `cpu:`
                      → subfamily passthrough; no C++ content exists at
                        this tier (the CMake macro has already followed
                        `inherits:` to a parent carrying the topology, and
                        the chip formatter walks the chain to assemble the
                        merged instance view).  Placeholder files are still
                        written so the CMake custom-command output
                        contract is satisfied.

The C++ namespace comes from the model's `namespace:` key, falling back to
the lowercased innermost containing directory name.

Layout of this file:
  1. shared helpers    — YAML loading, model lookup, array-axis and
                         `enumeratedIndices` normalisation, `inherits:`
                         chain merging, module-name derivation, output
  2. peripheral blocks — PerFormatter
  3. chips             — ChipFormatter
  4. clock trees       — ClockFormatter
  5. main()            — argument handling and dispatch

Namespaces are used liberally, because they help avoid ambiguities when the
naming of registers, fields and/or enumerators overlaps — which is
frequently the case.  Users avoid the resulting verbosity with `using
namespace <...>` directives.  That is also why *bitfield-value*
enumerations are unscoped enums inside a namespace: automatic conversion to
integer is desirable for use with bitwise operators.  *Index* enumerations
(the schema's `enumeratedIndices` on register/cluster arrays) are emitted as
`enum class` instead — for array subscripts we want the opposite property,
so `arr[3]` is rejected and only the named enumerator is accepted.
"""

from itertools import pairwise, product
from pathlib import Path
from string import Template
from typing import NamedTuple
import re
import sys

from ruamel.yaml import YAML


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_yaml = YAML(typ='safe')
_models = {}


def load(path):
    """Load a model YAML, memoised on the resolved path.

    All three formatters resolve the same block models repeatedly (for the
    namespace, the parameter order, the register layout), so the cache turns
    that into one read per file.  Results must be treated as read-only.
    """
    key = str(Path(path).resolve())
    if key not in _models:
        _models[key] = _yaml.load(Path(path))
    return _models[key]


def try_load(path):
    """Like load(), but returns None when the file can't be read or parsed."""
    try:
        return load(path)
    except Exception:
        return None


def find_model(start_dir, relpath):
    """Walk up from start_dir until <ancestor>/<relpath>.yaml exists.

    Returns the path, or None when nothing matches.  Model references
    (`models:` values, `inherits:`, `clocktree:`) are relative to the models
    root, which is always some ancestor of the referring file — searching
    upwards locates it without having to know the root's name.
    """
    target = Path(relpath + '.yaml')
    p = Path(start_dir).resolve()
    while True:
        candidate = p / target
        if candidate.is_file():
            return candidate
        if p.parent == p:
            return None
        p = p.parent


def namespace_of(model_path):
    """Return the C++ namespace for the model at `model_path`.

    Reads the optional `namespace:` key.  If absent, falls back to the
    lowercased innermost containing directory name (sanitized to a valid
    C++ identifier).  This keeps namespaces self-describing for generated
    models while allowing hand-maintained models to omit the key as long
    as their directory name is acceptable as the namespace.
    """
    p = Path(model_path)
    d = try_load(p)
    if isinstance(d, dict) and d.get('namespace'):
        return d['namespace']
    return re.sub(r'[^a-z0-9_]', '_', p.parent.name.lower())


def module_id(namespace, filename):
    """Derive the C++20 module name for a generated header.

    Module names must be valid C++ identifiers, so stems like "ESP32-P4"
    need the hyphen replaced.  The namespace prefix keeps module names
    globally unique across vendors (e.g. esp32p4.GPIO vs stm32h7.GPIO) —
    C++20 module names form a flat global space, and dotted names are legal.
    """
    stem = Path(filename).stem.replace('-', '_')
    return (f'{namespace}.{stem}'
            if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', namespace) else stem)


class Axes(NamedTuple):
    """Normalised array geometry of a register or cluster entry."""
    dims: list      # element count per axis; empty when the entry is scalar
    incs: list      # byte stride per axis
    multi: bool     # True when the model used list-valued dim (N-D extension)

    @property
    def total(self):
        """Total element count (1 for a scalar entry)."""
        n = 1
        for d in self.dims:
            n *= d
        return n


def axes_of(entry):
    """Normalise an entry's dim/dimIncrement to per-axis lists."""
    dim = entry.get('dim', 1)
    inc = entry.get('dimIncrement', 0)
    if isinstance(dim, list):
        return Axes(list(dim), list(inc), True)
    if dim > 1:
        return Axes([dim], [inc], False)
    return Axes([], [], False)


def index_enums_of(entry):
    """`enumeratedIndices` normalised to a per-axis list (empty when absent).

    The schema allows a single object for 1D arrays and a list — one entry
    per axis, trailing axes implicit — for multi-axis arrays.
    """
    e = entry.get('enumeratedIndices')
    if e is None:
        return []
    return [e] if isinstance(e, dict) else list(e)


def inherits_chain(node, node_path):
    """[(node, path), ...] from `node` up through its `inherits:` ancestors."""
    chain = []
    while node is not None:
        chain.append((node, node_path))
        parent = node.get('inherits')
        if not parent:
            break
        parent_path = find_model(Path(node_path).parent, parent)
        if parent_path is None:
            break
        node, node_path = load(parent_path), str(parent_path)
    return chain


def merge_inherited(node, node_path, *keys):
    """Merge the named top-level maps across the `inherits:` chain.

    Walks root-first, so entries declared by `node` itself are applied last
    and win over ancestor entries with the same key.  Each result is sorted
    by key, keeping emission order stable regardless of which tier
    materialises a given entry.
    """
    merged = [{} for _ in keys]
    for ancestor, _ in reversed(inherits_chain(node, node_path)):
        for out, key in zip(merged, keys):
            out.update(ancestor.get(key) or {})
    return [dict(sorted(m.items())) for m in merged]


def emit(hpp_path, header, module):
    """Write a generated header and its `.cppm` module wrapper."""
    path = Path(hpp_path)
    path.write_text(header)
    path.with_suffix('.cppm').write_text(module)


HWREG_MODULE = Template("""// File was generated, do not edit!
module;

#include "hwreg.hpp"

export module $mod;
$imports
#define EXPORT export
#include "$header"
#undef EXPORT
""")


def hwreg_module(mod, header, imports=()):
    """`.cppm` wrapper for a peripheral or chip header.

    hwreg.hpp goes into the global module fragment: its types are shared
    infrastructure that is not meant to cross the module boundary.  A chip
    lists the peripheral modules it integrates as `imports`; a peripheral
    block has none, and the substitution then collapses to a blank line.
    """
    return HWREG_MODULE.substitute(
        mod=mod, header=header,
        imports=''.join(f'import {i};\n' for i in imports))


# ---------------------------------------------------------------------------
# Peripheral block headers
# ---------------------------------------------------------------------------

# Names that must not appear as identifiers in generated C++ code.
# C++ keywords are reserved by the language; NULL is a ubiquitous C macro that
# conflicts if left as an enum value name.  Any matching name gets a trailing
# underscore appended (e.g. NULL → NULL_).
_RESERVED_NAMES = {
    # C++ keywords (C++20)
    'alignas', 'alignof', 'and', 'and_eq', 'asm', 'auto',
    'bitand', 'bitor', 'bool', 'break',
    'case', 'catch', 'char', 'char8_t', 'char16_t', 'char32_t', 'class',
    'compl', 'concept', 'const', 'consteval', 'constexpr', 'constinit',
    'const_cast', 'continue', 'co_await', 'co_return', 'co_yield',
    'decltype', 'default', 'delete', 'do', 'double', 'dynamic_cast',
    'else', 'enum', 'explicit', 'export', 'extern',
    'false', 'float', 'for', 'friend',
    'goto',
    'if', 'inline', 'int',
    'long',
    'mutable',
    'namespace', 'new', 'noexcept', 'not', 'not_eq', 'nullptr',
    'operator', 'or', 'or_eq',
    'private', 'protected', 'public',
    'register', 'reinterpret_cast', 'requires', 'return',
    'short', 'signed', 'sizeof', 'static', 'static_assert', 'static_cast',
    'struct', 'switch',
    'template', 'this', 'thread_local', 'throw', 'true', 'try', 'typedef',
    'typeid', 'typename',
    'union', 'unsigned', 'using',
    'virtual', 'void', 'volatile',
    'wchar_t', 'while',
    'xor', 'xor_eq',
    # Common macros that collide with user identifiers
    'NULL',
}

PER_PREFIX = Template("""// File was generated, do not edit!
#pragma once

#ifndef EXPORT
#include "hwreg.hpp"
#define EXPORT
#endif

namespace $ns {""")

PER_POSTFIX = Template("""} // namespace $ns

#undef EXPORT""")

PER_ENUM      = Template('\n\t/** $description */\n\t$name = $value,')
PER_ENUMS     = Template('\ninline namespace ${name}_ {\nEXPORT enum ${sname}_${name} : $type {$enums\n};\n} // namespace ${name}_\n')
PER_REG_ENUMS = Template('\ninline namespace ${name}_ {$enums} // namespace ${name}_\n')
PER_BITFIELD  = Template('\n\t/** $description */\n\t$type $name:$width;')
PER_RES_BITS  = Template('\n\t$type _$res:$width;\t// reserved')
PER_RES_BYTES = Template('\n\tuint8_t _$res[$bytes];\t// reserved')
PER_TYPE      = Template('HwReg<struct $name$endian>')
PER_FIELD     = Template('\n\t/** $description */\n\t$type $name;')
PER_FIELDS    = Template('\n/** $description */\nEXPORT struct $name {$fields\n};\n')
PER_REGISTERS = Template('\n$types\n/** $description */\nEXPORT struct $name {$regs\n}; // size = $size\n')
PER_ADDRESS   = Template('\t$type$usage;\t// offset = $offset, size = $size\n')
PER_PARAMETER = Template('\tuint16_t $name:$bits;\t//!< $description\n')
PER_HEADER    = Template("""
$prefix
namespace ${name} {$enums
$types
/** $description */
EXPORT struct $name {$regs
}; // size = $size
$inputs
/** Integration of peripheral in the SoC. */
EXPORT struct Intgr {
$params$blocks};
} // namespace ${name}
$postfix""")


def _safe_name(name: str) -> str:
    """Return name unchanged, or with a trailing underscore if it is reserved,
    or with an 'e' prefix if it starts with a digit."""
    if name and name[0].isdigit():
        return 'e' + name
    return name + '_' if name in _RESERVED_NAMES else name


def _parse_array_dims(reg):
    """Determine array dimensions for HwArray code generation.

    Returns a list of (count, base) tuples (outermost first), or None if the
    register is not an array, or if it uses non-numeric / non-sequential
    labels that HwArray can't represent — in which case the caller falls
    back to the comma-separated-fields form.
    """
    axes = axes_of(reg)
    if axes.multi:
        # Multi-dimensional array (sodaCat extension): always 0-based.
        return [(d, 0) for d in axes.dims]
    if not axes.dims:
        return None                          # single register
    dimIndex = reg.get('dimIndex', '')
    if not dimIndex:
        return [(axes.dims[0], 0)]
    tokens = [t.strip() for t in dimIndex.split(',')]
    try:
        ints = [int(t) for t in tokens]
    except ValueError:
        return None                          # letter or named labels
    if ints != list(range(ints[0], ints[0] + len(ints))):
        return None                          # non-sequential
    return [(len(ints), ints[0])]


def _wrap_array_type(elem_type, dims, idx_types=None):
    """Wrap elem_type in nested HwArray<...> for each dimension.

    `idx_types`, if provided, is a list aligned with `dims`: for axis k,
    None means "no index enum" and a string means the C++ scoped-enum
    type name (e.g. 'Branch') to instantiate as the HwArray's Idx
    parameter.  When idx is non-None the Base parameter is emitted
    explicitly so the positional template-argument list reaches Idx.
    """
    for k in range(len(dims) - 1, -1, -1):
        count, base = dims[k]
        idx = idx_types[k] if idx_types and k < len(idx_types) else None
        if idx is not None:
            elem_type = f'HwArray<{elem_type}, {count}, {base}, {idx}>'
        elif base != 0:
            elem_type = f'HwArray<{elem_type}, {count}, {base}>'
        else:
            elem_type = f'HwArray<{elem_type}, {count}>'
    return elem_type


def _format_index_enum(enum_obj, axis_dim):
    """Emit a scoped enum-class declaration for one array axis."""
    # Smallest unsigned integer type that holds [0, axis_dim).
    underlying = ('std::uint8_t' if axis_dim <= 256 else
                  'std::uint16_t' if axis_dim <= 65536 else 'std::uint32_t')
    desc = enum_obj.get('description') or ''
    lines = ['']
    if desc:
        lines.append(f'/** {desc} */')
    lines.append(f'EXPORT enum class {enum_obj["name"]} : {underlying} {{')
    for v in enum_obj['values']:
        vdesc = v.get('description') or ''
        if vdesc:
            lines.append(f'\t/** {vdesc} */')
        lines.append(f'\t{v["name"]} = {v["value"]},')
    lines.append('};\n')
    return '\n'.join(lines)


class PerFormatter:
    def __init__(self, endian='native'):
        # Storage endianness of the register block, threaded into the
        # HwReg<R, E> template's second argument.  This is an integration
        # fact, not a model property: a 16-bit register reaches host memory
        # in host byte order over a native-word SPI transfer, but MSB-first
        # (big-endian) over an I2C byte stream — the same device, different
        # bus.  `native` (the default) emits no endian argument so generated
        # output is byte-identical to the pre-endianness generator.
        if endian not in ('native', 'big', 'little'):
            raise ValueError(f"endian must be native/big/little, got {endian!r}")
        self.endian_suffix = '' if endian == 'native' else f', std::endian::{endian}'

    def formatEnumList(self, enums: list):
        """ Generate enumerator list """
        return ''.join(
            PER_ENUM.substitute(name=_safe_name(e.get('name', '')),
                                value=e.get('value', 1),
                                description=e.get('description') or '')
            for e in enums)

    def formatFieldList(self, fields: list, wordType: str, sname: str = ''):
        """ Generate bitfield list

        `sname` is the enclosing struct (register) name; it qualifies enum
        type names so that two registers with same-named fields produce
        distinct C++ enum types (e.g. CNTL_IE vs MASK_IE rather than two
        unrelated `IE_e`).
        Returns:
        - the formatted list of bitfields as a multiline string
        - the formatted list of enum definitions as a multiline string
        """
        entries = []
        for field in fields:
            enum = ''
            if 'enumeratedValues' in field:
                txt = self.formatEnumList(field['enumeratedValues'])
                if txt:
                    enum = PER_ENUMS.substitute(
                        sname=sname, name=_safe_name(field.get('name', '')),
                        enums=txt, type=wordType)
            width = field.get('bitWidth', 1)
            txt = PER_BITFIELD.substitute(
                name=_safe_name(field.get('name', '')), type=wordType,
                width=width, description=field.get('description') or '')
            entries.append([txt, field['bitOffset'], width, enum])

        entries.sort(key=lambda f: f[1])    # sort fields by increasing offset
        txt = ''
        enums = ''
        res = 0
        pos = 0
        for line, offset, width, enum in entries:
            enums += enum
            if offset > pos:
                txt += PER_RES_BITS.substitute(type=wordType, res=res,
                                               width=offset - pos)
                res += 1
                pos = offset
            txt += line
            pos += width
        return txt, enums

    def formatRegisterList(self, reglist: list, padToSize: int, defaultSize: int,
                           structPrefix: str = '', blockName: str = ''):
        """ Generate structs and instances for a list of registers
        Returns four values (in this order):
        1. All the type definitions for the registers as a multiline string
        2. The formatted list of registers as a multiline string
        3. The size of the register list in the address space of the controller
        4. The list of enumeration definitions

        structPrefix is prepended to struct/enum type names to avoid collisions
        when multiple clusters have identically-named registers.

        blockName is the peripheral struct name; when a top-level register's
        bitfield struct would carry the same name, we append `_` so the two
        don't redeclare each other in `namespace ${blockName}`.  Only applies
        at the top level (`structPrefix == ''`); cluster-nested registers are
        already namespaced by the prefix.  The trailing-underscore convention
        matches `_safe_name()` and the inline-namespace naming used elsewhere
        in this generator.
        """
        enums = ''
        structs = ''
        entries = []
        for reg in reglist:
            addressOffset = reg['addressOffset']
            description = reg.get('description') or ''
            axes = axes_of(reg)
            # If the entry carries enumeratedIndices, emit one scoped-enum
            # declaration per axis and remember the type names so they can
            # be threaded into the HwArray template instantiation.
            idx_types = None
            idx_enums = index_enums_of(reg)
            if idx_enums:
                axis_dims = axes.dims or [1]
                idx_types = []
                for axis, e in enumerate(idx_enums):
                    if e is None:
                        idx_types.append(None)
                    else:
                        enums += _format_index_enum(e, axis_dims[axis])
                        idx_types.append(e['name'])
                # Pad trailing axes with None.
                idx_types += [None] * (len(axis_dims) - len(idx_types))

            if 'registers' in reg:
                dimIndex = reg.get('dimIndex', '')
                # Derive the struct type name: strip [%s] or %s, drop trailing _
                name = reg['name'].replace('[%s]', '').replace('%s', '').rstrip('_')
                if not structPrefix and blockName and name == blockName:
                    name = name + '_'
                dimInc = reg.get('dimIncrement', 0)
                # For 2D cluster arrays (list-valued dimIncrement), the
                # cluster contents fill the innermost stride; the outer
                # stride is consumed by the inner-array repetition.
                padSize = dimInc if isinstance(dimInc, int) else dimInc[-1]
                # Inner registers inherit the enclosing block's default word
                # size (`defaultSize`, in bytes) rather than a hardcoded 4.
                # Top-level registers already inherit the model's `size:`, so a
                # cluster member must too — otherwise a sub-32-bit device (e.g.
                # a 16-bit-register codec) gets oversized cluster elements whose
                # footprint exceeds the array stride.  For 32-bit blocks this is
                # identical to the previous behaviour.
                types, regs, size, enum = self.formatRegisterList(
                    reg['registers'], padSize, defaultSize,
                    structPrefix + name + '_')
                enums += enum
                structs += PER_REGISTERS.substitute(
                    name=name, regs=regs, types=types, description=description,
                    size=size)
                dims = _parse_array_dims(reg)
                if dims is not None:
                    field_type = _wrap_array_type('struct ' + name, dims, idx_types)
                    field_name = reg['name'].replace('[%s]', '').replace('%s', '')
                    line = PER_FIELD.substitute(name=field_name, type=field_type,
                                                description=description)
                elif dimIndex:
                    # Letter or named labels — keep expanded comma-separated fields.
                    names = ','.join(reg['name'] % item for item in dimIndex.split(','))
                    line = PER_FIELD.substitute(name=names, type='struct ' + name,
                                                description=description)
                else:
                    line = PER_FIELD.substitute(name=reg['name'], type='struct ' + name,
                                                description=description)
                entries.append([line, addressOffset, size * axes.total])
            else:
                dimIndex = reg.get('dimIndex', "")
                dims = _parse_array_dims(reg)
                if dims is None and dimIndex:
                    # Letter or named labels — keep expanded comma-separated fields.
                    # Disambiguate the bitfield struct name when multiple
                    # dimIndex arrays share a prefix in the same scope (e.g.
                    # SFSP1_[%s] alongside SFSP1_%s with dimIndex 18,19,20
                    # — both would otherwise reduce to `SFSP1_`).  Include
                    # the first dimIndex token in the struct name.
                    tokens = dimIndex.split(",")
                    typeName = structPrefix + reg['name'] % tokens[0]
                    names = ",".join(reg['name'] % item for item in tokens)
                else:
                    # Single register, or HwArray-wrapped array.
                    names = reg['name'].replace('[%s]', '').replace('%s', '')
                    typeName = structPrefix + names
                # Avoid clashing the bitfield struct name with the peripheral
                # struct (both end up at namespace scope).
                if not structPrefix and blockName and typeName == blockName:
                    typeName = typeName + '_'
                size = reg.get('size', defaultSize * 8)
                wordType = reg.get('dataType', 'uint%s_t' % size)
                if 'fields' in reg and reg['fields']:
                    fields, enum = self.formatFieldList(reg['fields'], wordType,
                                                        sname=typeName)
                    if enum:
                        enums += PER_REG_ENUMS.substitute(name=typeName, enums=enum)
                    structs += PER_FIELDS.substitute(name=typeName, fields=fields,
                                                     description=description)
                    regType = PER_TYPE.substitute(name=typeName,
                                                  endian=self.endian_suffix)
                else:
                    regType = wordType
                    # A fieldless integer register is normally emitted as a bare
                    # uintN_t, which has no byte-order slot.  When a non-native
                    # endianness was requested it must still be byte-swapped on
                    # access, so wrap it in HwReg<uintN_t, E>.  Author-specified
                    # dataTypes are left untouched — they opted into a concrete
                    # representation the generator shouldn't second-guess.
                    if self.endian_suffix and 'dataType' not in reg:
                        regType = f'HwReg<{wordType}{self.endian_suffix}>'
                if dims is not None:
                    regType = _wrap_array_type(regType, dims, idx_types)
                line = PER_FIELD.substitute(name=names, type=regType,
                                            description=description)
                entries.append([line, addressOffset, (size >> 3) * axes.total])

        entries.sort(key=lambda r: r[1])
        entries.append(['', 0xFFFFFFFF, 0])     # dummy
        txt = ''
        res = 0
        pos = 0
        union = False
        for this, following in pairwise(entries):
            if not union and this[1] == following[1]:
                union = True
                txt += '\n\tunion {'
            if this[1] > pos:
                txt += PER_RES_BYTES.substitute(res=res, bytes=this[1] - pos)
                res += 1
                pos = this[1]
            txt += this[0]
            # Advance `pos` once per union (on close) or once per non-union
            # register.  A union of N overlapping registers occupies the
            # space of one member at offset `this[1]`; advancing per-member
            # would over-count by (N-1)*size bytes and shrink the next gap.
            if union:
                if this[1] != following[1]:
                    union = False
                    txt += '\n\t};'
                    pos += this[2]
            else:
                pos += this[2]
        if padToSize > pos:
            txt += PER_RES_BYTES.substitute(res=res, bytes=padToSize - pos)
            pos = padToSize
        return structs, txt, pos, enums

    def formatInputs(self, inputs: list):
        """Emit `enum class Input` from the block's `inputs:` declaration.

        Returns '' when the block declares no inputs.  Otherwise emits a
        scoped enum-class with one enumerator per input slot in declaration
        order; the chip-side per-block Connection table is indexed by
        size_t(Input::<slot_name>).  Underlying type is uint8_t (more than
        256 input slots per block is implausible — the assert in the chip
        formatter catches the overflow case if it ever happens).
        """
        if not inputs:
            return ''
        lines = ['',
                 '/** External input slots this block accepts at its on-chip-interconnect boundary. */',
                 'EXPORT enum class Input : std::uint8_t {']
        for inp in inputs:
            desc = inp.get('description') or ''
            if desc:
                lines.append(f'\t/** {desc} */')
            lines.append(f'\t{_safe_name(inp["name"])},')
        lines.append('};')
        lines.append('')
        return '\n'.join(lines)

    def formatIntegrationList(self, per: dict):
        """ Generate definitions for the parameterization of a peripheral """
        blocks = ''
        for block in per.get('addressBlocks', []):
            type = (f'HwPtr<struct {per["name"]} volatile> '
                    if block['usage'] == 'registers' else 'std::span<std::byte> ')
            blocks += PER_ADDRESS.substitute(block, type=type)
        params = ''
        for par in per.get('params', []):
            desc = par.get('description') or ''
            ptype = par.get('type', 'int')   # `type:` is optional; defaults to int
            if 'bits' in par:
                # Explicit bit-width wins over any derivation; some authors
                # round up (e.g. bits: 16, max: 32767) for alignment reasons.
                params += PER_PARAMETER.substitute(par, description=desc)
            elif ptype == 'bool':
                params += PER_PARAMETER.substitute(par, bits=1, description=desc)
            elif ptype == 'int' and 'max' in par:
                params += PER_PARAMETER.substitute(par, bits=par['max'].bit_length() or 1,
                                                   description=desc)
            else:
                ctype = {'string': 'const char*'}.get(ptype, 'uint32_t')
                params += f'\t{ctype} {par["name"]};\t//!< {desc}\n'
        return blocks, params

    def formatPeripheral(self, per: dict, namespace: str):
        """ Generate definitions for a peripheral """
        defaultSize = per.get('size', 32) >> 3
        types, regs, size, enums = self.formatRegisterList(
            per['registers'], 0, defaultSize, blockName=per.get('name', ''))
        blocks, params = self.formatIntegrationList(per)
        return PER_HEADER.substitute(
            per, blocks=blocks, params=params,
            inputs=self.formatInputs(per.get('inputs', [])),
            regs=regs, enums=enums, types=types,
            description=per.get('description') or '', size=size,
            prefix=PER_PREFIX.substitute(ns=namespace),
            postfix=PER_POSTFIX.substitute(ns=namespace))


# ---------------------------------------------------------------------------
# Chip / SoC integration headers
# ---------------------------------------------------------------------------

CHIP_PREFIX = Template("""// File was generated, do not edit!
#pragma once

#ifndef EXPORT
$incl
#include "hwreg.hpp"
#define EXPORT
#endif

$conn_enum

namespace $ns {

EXPORT constexpr Exception interruptOffset = $interruptOffset;\t//!< Exception number of first interrupt
EXPORT constexpr Exception interruptCount = $interruptCount;\t//!< Total number of exceptions (interrupts + system exceptions)
""")

# The line of trailing blanks is an accident of the original template, kept
# so generated output stays byte-identical; clang-format drops it downstream.
CHIP_POSTFIX = Template('\n' + ' ' * 27 + '\n'
                        '} // namespace $ns\n'
                        '\n'
                        '#undef EXPORT\n')

CHIP_PARAM = Template('\n\t.$name = ${value}u,')
CHIP_INCL  = Template('\n#   include "$ns/$model$incl_suffix"')
CHIP_DECL  = Template("""
/** Integration parameters for $name */
EXPORT constexpr struct $ns::${model}::Intgr i_$name = {$params$init};
""")


class ChipFormatter:
    """Emits a chip's integration header from its (merged) instance view.

    The chip's `instances:`/`models:` maps are merged with every ancestor
    reached via `inherits:`, so entries lifted to the subfamily (or
    shared-spec) tier feed into the per-chip view while chip-level entries
    override them by key.
    """

    def __init__(self, chip, chip_path):
        self.chip = chip
        self.dir = Path(chip_path).parent
        self.instances, self.models = merge_inherited(
            chip, chip_path, 'instances', 'models')
        self._blocks = {}       # model name → (params, defaults, inputs)

    def blockPath(self, model_name):
        """Locate a referenced block model's YAML file."""
        return find_model(self.dir, self.models.get(model_name, model_name))

    def blockDecl(self, model_name):
        """Return (param_names, param_defaults, input_names) declared by
        the block model.

        param_names is the authoritative source for designated-initializer
        order; chip-side lists are sorted to match before emission.

        param_defaults is a {name: value} map for params that declare a
        default; chip instances that don't override such a param fall
        back to the default at integration-emission time.

        input_names is the ordered list of declared input slot names when
        the block has an `inputs:` section, or None when the block omits
        the key entirely.  Used by the destination resolver to map a
        named-input destination (e.g. `HRTIM_Master.bm_ck1`) to its
        position in the per-block Input enum.

        Returns (None, {}, None) when the block YAML can't be located, in
        which case callers preserve chip-side order with no default
        fallback — that's the ad-hoc-runs case outside the standard
        models tree.  Under CMake the file is always present
        (ensure_model() downloads it ahead of header generation).
        """
        if model_name not in self._blocks:
            path = self.blockPath(model_name)
            if path is None:
                decl = (None, {}, None)
            else:
                block = load(path)
                params = block.get('params', [])
                inputs = block.get('inputs')
                decl = ([p['name'] for p in params],
                        {p['name']: p['default'] for p in params if 'default' in p},
                        [i['name'] for i in inputs] if inputs is not None else None)
            self._blocks[model_name] = decl
        return self._blocks[model_name]

    def createParameters(self, instance_name, instance):
        """Emit designated initialisers for an instance's params.

        Chip-yaml `parameters:` overrides take precedence; any param
        declared by the block model with a default that the chip yaml
        didn't override falls back to the default.  Params with neither
        a chip override nor a block default are silently skipped (the
        struct member is then default-initialised by C++ — caller's
        responsibility to ensure that's acceptable).
        """
        param_order, param_defaults, _ = self.blockDecl(instance['model'])
        chip_params = instance.get('parameters', [])
        by_name = {p['name']: p['value'] for p in chip_params}
        if param_order is None:
            # Block model not located — preserve chip-side order, no
            # default fallback (we don't know the param declarations).
            merged = [(p['name'], p['value']) for p in chip_params]
        else:
            unknown = set(by_name) - set(param_order)
            if unknown:
                raise ValueError(
                    f"chip instance '{instance_name}' (model '{instance['model']}'): "
                    f"parameter(s) {sorted(unknown)!r} not declared by block model"
                )
            merged = []
            for n in param_order:
                if n in by_name:
                    merged.append((n, by_name[n]))
                elif n in param_defaults:
                    merged.append((n, param_defaults[n]))
        params = ''
        for name, v in merged:
            if isinstance(v, bool):
                params += f"\n\t.{name} = {'true' if v else 'false'},"
            elif isinstance(v, str):
                params += f'\n\t.{name} = "{v}",'
            else:
                params += CHIP_PARAM.substitute(name=name, value=v)
        return params

    def collectConnections(self):
        """Walk the merged instance set and collect:

        - `enumerators` — ordered list of Connection enumerator names, one
          per wired (instance, signal) pair.  Instance-major,
          signal-secondary order; matches the order they appear in the
          merged instances (already sorted by key) and each instance's
          declared output order.
        - `target_routes` — {target_prefix: [(enum_name, port_int), ...]}.
          target_prefix is the part of the destination string up to its
          final dot (a single instance name like `NVIC` or a two-level
          form like `TIM2.ITR`).  port_int is the integer slot index.
          For destinations of the named-input form `<inst>.<input_name>`
          (e.g. `HRTIM_Master.bm_ck1`), the named input is resolved via
          the destination block's `inputs:` list into its declaration
          index, which then plays the same role as a literal integer
          port for downstream emission.
        - `target_input_names` — {target_prefix: [name, ...]} only for
          prefixes whose destination block declares an `inputs:` list.
          Used to size the per-target array to match the block's full
          Input enum length rather than max(port)+1 (so the C++ table is
          safely indexable by any Input enumerator the block declares —
          slots the chip doesn't wire become NONE), and to annotate each
          slot's initializer with the matching Input enum value name as a
          line-end comment.

        Malformed destinations (no dot, unresolved name) are silently
        skipped; the validator in tools/validate_chip_connections.py is the
        place that flags those.
        """
        enumerators = []
        seen = set()
        target_routes = {}
        target_input_names = {}
        for inst_name, inst in self.instances.items():
            for sig_name, dests in (inst.get('connections') or {}).items():
                if not dests:
                    continue
                enum_name = f"{inst_name}_{sig_name}"
                if enum_name not in seen:
                    enumerators.append(enum_name)
                    seen.add(enum_name)
                for dest in dests:
                    prefix, _, port_str = dest.rpartition('.')
                    if not prefix:
                        continue
                    try:
                        port = int(port_str)
                    except ValueError:
                        # Non-integer tail: must be a named input on a block
                        # that declares `inputs:`.  Only the 2-part form
                        # (instance.input_name) qualifies — 3-part forms
                        # (instance.subport.<tail>) require integer tails.
                        if '.' in prefix:
                            continue
                        target = self.instances.get(prefix)
                        if not target or not target.get('model'):
                            continue
                        input_names = self.blockDecl(target['model'])[2]
                        if input_names is None or port_str not in input_names:
                            continue
                        port = input_names.index(port_str)
                        target_input_names[prefix] = input_names
                    target_routes.setdefault(prefix, []).append((enum_name, port))
        return enumerators, target_routes, target_input_names

    def emitConnectionEnum(self, enumerators):
        """Emit the chip-specific Connection enum definition.

        Reopens `namespace hwreg` (the forward declaration in hwreg.hpp
        lives there) so the enumerators belong to the same type peripheral
        headers reference.  NONE=0 is reserved as the "no connection"
        sentinel; subsequent enumerators take sequential values from 1.

        Wrapped in `extern "C++"` so that when this block is consumed
        from inside a module purview (via the .cppm's `#include` of the
        .hpp), the linkage-specification forces global-module attachment
        — matching the forward declaration in hwreg.hpp regardless of
        whether the .hpp is included directly or imported as a module.
        Outside a module purview the linkage-spec is a harmless no-op.

        Even a chip with zero wired outputs still needs a complete
        Connection type so its Intgr fields can default-initialise.
        """
        lines = ['\tNONE = 0,']
        lines += [f'\t{name} = {i},' for i, name in enumerate(enumerators, start=1)]
        # `inline` matches hwreg.hpp's opening declaration; without it, GCC/Clang
        # warn about reopening an inline namespace as non-inline.
        return (
            'extern "C++" {\n'
            'inline namespace hwreg {\n'
            'enum class Connection : uint16_t {\n'
            + '\n'.join(lines) + '\n'
            '};\n'
            '} // namespace hwreg\n'
            '} // extern "C++"\n'
            'EXPORT using hwreg::Connection;\n'
        )

    def emitTargetTables(self, enumerators, target_routes, target_input_names):
        """Emit per-target route tables in shapes inferred from the data.

        Pair-list (`RouteEntry[]`, sorted by Connection) when any port has
        more than one source within the target; direct array
        (`Connection[]`, slots default to Connection::NONE) otherwise.

        Array sizing rule:
          * When the target block declares `inputs:` (target_input_names
            has an entry), size the table to the full Input enum length
            so any `Input::xxx` indexing is well-defined.  Each slot
            initializer gets a line-end comment with the Input enum
            value name for that slot.
          * Otherwise (integer-port target — NVIC, DMAMUX, EXTI, TIM
            sub-ports), size to max(port)+1 as before; slot comments
            are omitted (the integer position carries no extra info).

        Tables are emitted at chip namespace scope.  Pair-list rows are
        sorted by the enumerator's declaration index (= its enum value),
        then by port so the order is total and reproducible; a Connection
        listed on several ports of one target therefore resolves to its
        lowest port (the most specific mux setting).  Table
        identifiers preserve the manufacturer's case (`c_NVIC`,
        `c_TIM2_ITR`); dots in dotted prefixes collapse to underscores.
        """
        enum_index = {name: i for i, name in enumerate(enumerators)}
        chunks = []
        # Stable target ordering by prefix for reproducible output.
        for prefix in sorted(target_routes):
            routes = target_routes[prefix]
            ports = [p for _, p in routes]
            table_id = 'c_' + prefix.replace('.', '_')
            if len(ports) != len(set(ports)):
                # Deduplicate identical (conn, port) rows, then sort.
                # The port is part of the key so that a Connection reaching
                # this target on more than one port (e.g. a comparator output
                # available both alone and OR'd with its sibling) gets a
                # total, reproducible order.  Without it the tie would keep
                # set-iteration order, which varies with PYTHONHASHSEED and
                # silently changes which port resolve() returns.
                body = ''.join(
                    f'\n\t{{Connection::{n}, {p}}},'
                    for n, p in sorted(set(routes),
                                       key=lambda r: (enum_index[r[0]], r[1])))
                chunks.append(
                    f'\nEXPORT constexpr RouteEntry {table_id}[] = {{{body}\n}};\n')
            else:
                # Direct array: size to declared input count if the
                # target block has an Input enum, else to max(port)+1.
                input_names = target_input_names.get(prefix)
                size = len(input_names) if input_names is not None else max(ports) + 1
                slots = [None] * size
                for name, port in routes:
                    slots[port] = name
                body_lines = []
                for i, n in enumerate(slots):
                    line = f'\tConnection::{n if n else "NONE"},'
                    if input_names is not None and i < len(input_names):
                        line += f'\t// {input_names[i]}'
                    body_lines.append(line)
                chunks.append(
                    f'\nEXPORT constexpr Connection {table_id}[{size}] = {{\n'
                    + '\n'.join(body_lines) + '\n};\n')
        return ''.join(chunks)

    def createIntegration(self, namespace, incl_suffix):
        """ create list of integration structs.

        Returns (decl, includes, model_to_ns) where model_to_ns maps each
        referenced peripheral model name to its C++ namespace — read from
        the referenced block YAML's own `namespace:` key (with directory-
        based fallback via namespace_of).
        """
        model_to_ns = {}
        decl = ''
        for k, i in self.instances.items():
            m = i['model']
            if m not in model_to_ns:
                block_path = self.blockPath(m)
                model_to_ns[m] = namespace_of(block_path) if block_path else namespace
            decl += CHIP_DECL.substitute(
                i, name=k, ns=model_to_ns[m],
                params=self.createParameters(k, i),
                init='\n\t.registers = %#Xu\n' % i['baseAddress'])
        includes = ''.join(
            CHIP_INCL.substitute(model=m, ns=ns, incl_suffix=incl_suffix)
            for m, ns in model_to_ns.items())
        return decl, includes, model_to_ns

    def interruptCount(self):
        """Number of exception vectors, derived from every instance's
        `NVIC.<vector>` destinations across the chip + its `inherits:` chain.

        Vectors are absolute (NVIC's own input numbering), so the count is
        just the highest one wired anywhere, plus one.  A chip that wires
        nothing falls back to its `interruptOffset:` (the first vector past
        the Cortex-M system exceptions).
        """
        highest = self.chip.get('interruptOffset', 0) - 1
        for inst in self.instances.values():
            for dests in (inst.get('connections') or {}).values():
                for dest in dests:
                    target, dot, port = dest.partition('.')
                    if not dot or target != 'NVIC':
                        continue
                    try:
                        highest = max(highest, int(port))
                    except ValueError:
                        continue
        return highest + 1

    def createHeader(self, namespace, incl_suffix):
        """Return (header text, list of module names to import)."""
        decl, incl, model_to_ns = self.createIntegration(namespace, incl_suffix)
        enumerators, target_routes, target_input_names = self.collectConnections()
        header = (CHIP_PREFIX.substitute(
                      self.chip, ns=namespace, incl=incl,
                      interruptCount=self.interruptCount(),
                      conn_enum=self.emitConnectionEnum(enumerators))
                  + self.emitTargetTables(enumerators, target_routes,
                                          target_input_names)
                  + decl
                  + CHIP_POSTFIX.substitute(ns=namespace))
        return header, [f'{ns}.{m}' for m, ns in model_to_ns.items()]


# ---------------------------------------------------------------------------
# Clock tree headers
# ---------------------------------------------------------------------------
#
# Flyweight architecture: the header carries compact descriptor tables per
# clock-tree element type, and register access is encoded as data (byte
# offset + bit position + bit width) rather than as generated lambdas.

# Element type registry: (type key, descriptor C++ type, frequency function).
# Declaration order fixes the type indices used by the emitted signal table;
# types that end up with no descriptors are skipped at emission.
CLOCK_TYPES = [
    ('gate',         'clocktree::GateDesc',        'clocktree::gate_freq'),
    ('gate_inv',     'clocktree::GateInvDesc',     'clocktree::gate_inv_freq'),
    ('passthrough',  'uint8_t',                    'clocktree::passthrough_freq'),
    ('gen_fixed',    'clocktree::GenFixedDesc',    'clocktree::gen_fixed_freq'),
    ('gen_external', 'clocktree::GenExternalDesc', 'clocktree::gen_external_freq'),
    ('table_div',    'clocktree::TableDivDesc',    'clocktree::table_div_freq'),
    ('linear_div',   'clocktree::LinearDivDesc',   'clocktree::linear_div_freq'),
    ('fixed_div',    'clocktree::FixedDivDesc',    'clocktree::fixed_div_freq'),
    ('mux',          'clocktree::MuxDesc',         'clocktree::mux_freq'),
    ('pll',          'clocktree::PllDesc',         'clocktree::pll_freq'),
]

# Element keys whose value is a {instance, reg, field} citation.
CLOCK_CITATIONS = ['control', 'factor', 'denominator',
                   'feedback_integer', 'feedback_fraction', 'post_divider']

CLOCK_MODULE = Template("""// File was generated, do not edit!
module;

#include <cstdint>
#include <span>

export module $mod;

#define EXPORT export
#include "$header"
#undef EXPORT
""")


def collect_registers(reg_list, base_offset, regs):
    """Recursively collect registers, handling clusters (dim/dimIncrement).

    Cluster and dim>1 expansion emits two name forms when `dimIndex` is
    present: numeric (CLK_0.CTRL) and dimIndex-token (CLK_REF.CTRL).
    Clocktree YAMLs can then reference clustered registers by the
    manufacturer's logical name (REF, SYS, ...) while the peripheral
    model keeps its array structure.

    Multi-dimensional arrays (list-valued dim/dimIncrement, e.g. LPC43
    CCU's CLK[%s][%s]) are expanded to a name per (i, j, ...) tuple by
    sequentially substituting %s placeholders — clocktree YAMLs reference
    such registers as CLK[0][0].CFG, CLK[3][15].CFG, etc.  dimIndex
    tokens are only applied to 1D arrays; multi-dim entries support per-
    axis enumeratedIndices substitutions (so LPC43 CGU's BASE_CLK[%s] can
    be referenced as BASE_CLK[SAFE].CLK_SEL once `enumeratedIndices` on
    the array names slot 0 SAFE).  Each axis substitutes one of: the
    numeric index, the dimIndex token (1D arrays only), or any
    enumeratedIndices enumerator name pointing at that index.  Names are
    emitted as the cross-product across axes; aliases at the same index
    each get their own name form.
    """
    for reg in reg_list:
        name = reg['name']
        offset = reg['addressOffset'] + base_offset
        sub_regs = reg.get('registers')       # non-empty for a cluster
        dims, incs, _ = axes_of(reg)

        dim_index = reg.get('dimIndex')
        if isinstance(dim_index, str):
            dim_tokens = [t.strip() for t in dim_index.split(',')]
        elif isinstance(dim_index, list):
            dim_tokens = [str(t).strip() for t in dim_index]
        else:
            dim_tokens = None

        # Build per-axis {value: [enumerator_name, ...]} maps so each axis
        # can be addressed by its enumeratedIndices name(s) in addition to
        # the numeric index.
        enum_axis_maps = []
        for e in index_enums_of(reg):
            if not isinstance(e, dict):
                enum_axis_maps.append(None)
                continue
            m = {}
            for v in e.get('values') or []:
                m.setdefault(v.get('value'), []).append(v.get('name'))
            enum_axis_maps.append(m)

        def _instance_names(indices):
            """Return all name forms (numeric + dimIndex + enumeratedIndices)
            for one (multi-)dim instance."""
            # Per-axis substitution alternatives: every axis lists the
            # numeric index plus any aliases that map to that index.
            per_axis_subs = []
            for k, idx in enumerate(indices):
                subs = [str(idx)]
                if len(indices) == 1 and dim_tokens and idx < len(dim_tokens):
                    subs.append(dim_tokens[idx])
                if k < len(enum_axis_maps) and enum_axis_maps[k] is not None:
                    subs.extend(enum_axis_maps[k].get(idx, []))
                per_axis_subs.append(subs)
            names = []
            for combo in product(*per_axis_subs):
                n = name
                for c in combo:
                    n = n.replace('%s', c, 1)
                names.append(n)
            return names

        if sub_regs:
            # This is a register cluster — expand each dimension instance
            # under qualified names (CLK_0.CTRL, CLK_REF.CTRL, ...).  Bare
            # sub-register names (CTRL, DIV, ...) are deliberately not
            # registered: they'd collide across cluster instances and the
            # last write would silently win.
            for indices in (product(*(range(d) for d in dims)) if dims else [()]):
                cluster_offset = offset + sum(i * inc for i, inc in zip(indices, incs))
                cluster_names = _instance_names(indices) if indices else [name]
                # Recurse so nested clusters/arrays inside this cluster
                # are themselves expanded with proper offsets.
                inner_regs = {}
                collect_registers(sub_regs, cluster_offset, inner_regs)
                for cn in cluster_names:
                    for sr_key, entry in inner_regs.items():
                        regs[f"{cn}.{sr_key}"] = entry
        else:
            # Plain register, possibly with dim
            fields = {f['name']: {'bitOffset': f['bitOffset'],
                                  'bitWidth': f.get('bitWidth', 1)}
                      for f in reg.get('fields', [])}
            if dims:
                for indices in product(*(range(d) for d in dims)):
                    entry = {'addressOffset':
                             offset + sum(i * inc for i, inc in zip(indices, incs)),
                             'fields': fields}
                    for rn in _instance_names(indices):
                        regs[rn] = entry
            else:
                regs[name] = {'addressOffset': offset, 'fields': fields}


class ClockFormatter:
    """Builds the descriptor tables of one clock tree and emits its header.

    Register citations in the clock-tree spec ({instance, reg, field}) are
    resolved against the peripheral block models, which requires a
    chip-shaped model to supply both the instance→block-model map and the
    instances' base addresses.
    """

    def __init__(self, model, model_path):
        self.model = model
        self.path = model_path
        self.dir = Path(model_path).parent
        # Subfamily-shaped files carry the clock-tree content under a
        # `clocks:` key; legacy clock-tree files have the same fields at the
        # top level.  Flatten by looking content up here — the top-level
        # header keys (version, family, devices, ...) still come from
        # `model`.
        self.content = model.get('clocks', model)
        self.instance = self.content.get('instance', '')
        # The empty signal occupies index 0; an unresolved reference maps
        # there, which the runtime reads as "undriven".
        self.signals = [{'name': '_', 'description': 'Empty signal'}]
        self.signals += self.content.get('signals', [])
        self.signal_index = {s['name']: i for i, s in enumerate(self.signals)}
        self.by_name = {s['name']: s for s in self.signals}

        # When the input yaml itself carries instances:, it IS the
        # chip-shaped model — use it directly.  This matters for subfamily
        # yamls that embed a clocks: section: their devices: field lists the
        # child chips, which would otherwise make the devices filter reject
        # the subfamily yaml and pick a child chip whose instances: lacks
        # the entries lifted to the subfamily tier (e.g. LPC43xx's CCU1).
        if 'instances' in model:
            self.chip, self.chip_path = model, model_path
        else:
            self.chip, self.chip_path = self.findChip(model.get('devices'))

        self.periph = {}        # instance name → {'base':, 'regs':}
        self.descs = {key: [] for key, _, _ in CLOCK_TYPES}
        self.elements = {}      # output signal → (type key, desc index, input offset)
        self.inputs = []        # flat pool of input signal IDs (uint8_t)
        self.values = []        # flat pool of divider table values (uint32_t)
        self.value_tables = {}  # tuple(values) → (offset, size)
        self.state = {}         # state name → (slot index, default)

    # -- model resolution ---------------------------------------------------

    def findChip(self, devices=None):
        """Find the chip model that supplies peripheral base addresses.

        The chip model has an 'instances' key with a baseAddress per
        peripheral.  When `devices` is non-empty, only a chip yaml whose
        `name` is in that list qualifies — required when the search subtree
        contains multiple chip yamls (e.g. models/Raspberry/RP/ with both
        RP2040 and RP2350) and the caller knows which one the clocktree is
        associated with.
        """
        wanted = set(devices) if devices else None

        def candidate(f):
            data = try_load(f)
            if data and 'instances' in data and (wanted is None
                                                 or data.get('name') in wanted):
                return data
            return None

        # Search self.dir and its ancestors...
        d = self.dir
        while d != d.parent:
            for f in d.glob("*.yaml"):
                data = candidate(f)
                if data:
                    return data, str(f)
            d = d.parent
        # ...then fall back to a subtree scan, since the chip model may live
        # in a subdirectory (e.g. LPC43xx/LPC4330.yaml).
        for f in self.dir.rglob("*.yaml"):
            data = candidate(f)
            if data:
                return data, str(f)
        return None, None

    def peripheral(self, instance):
        """Register/field layout of one peripheral instance, cached by name.

        Resolves the model file via the chip's instance→model→relpath map
        (instances[<instance>].model → models[<model>] → relpath), so an
        instance like PLL_SYS resolves to the PLL block model rather than
        looking for a non-existent PLL_SYS.yaml.  Falls back to a bare
        <instance>.yaml lookup for ad-hoc invocation outside a chip context.
        """
        if instance not in self.periph:
            path = None
            if self.chip:
                info = self.chip.get('instances', {}).get(instance)
                if isinstance(info, dict) and info.get('model'):
                    model = info['model']
                    path = find_model(
                        self.dir, self.chip.get('models', {}).get(model, model))
            if path is None:
                path = find_model(self.dir, instance)
            if path is None:
                raise FileNotFoundError(
                    f"Cannot find model file {instance}.yaml starting from {self.dir}")
            regs = {}
            collect_registers(load(path).get('registers', []), 0, regs)
            self.periph[instance] = {'regs': regs, 'base': None}
        return self.periph[instance]

    def resolveBaseAddresses(self):
        """Fill in the base address of every peripheral loaded so far.

        Walks the `inherits:` chain so instances lifted to the subfamily
        (or shared-spec) tier are still discoverable when the clock tree
        references them.  Chip entries override ancestor entries by name.

        The chip lookup is deliberately repeated without the `devices:`
        filter used for instance→block-model resolution: a subfamily-shaped
        input may cite instances that only its child chip yamls declare.
        """
        chip, chip_path = self.findChip()
        if not chip:
            return
        instances, = merge_inherited(chip, chip_path, 'instances')
        for name, info in instances.items():
            if name in self.periph and isinstance(info, dict):
                self.periph[name]['base'] = info.get('baseAddress', 0)

    def bitAddr(self, instance, reg_name, field_name):
        """Return (word_addr, bit, width) for a register field."""
        periph = self.peripheral(instance)
        reg = periph['regs'].get(reg_name)
        if reg is None:
            raise KeyError(f"Register {reg_name} not found in {instance}")
        field = reg['fields'].get(field_name)
        if field is None:
            raise KeyError(f"Field {field_name} not found in {instance}.{reg_name}")
        if periph['base'] is None:
            raise ValueError(f"Base address not found for {instance}")
        byte_addr = periph['base'] + reg['addressOffset']
        # Word offset relative to Cortex-M peripheral base 0x40000000
        return ((byte_addr - 0x40000000) >> 2,
                field['bitOffset'], field['bitWidth'])

    def citation(self, cite, with_width=False):
        """Format a BitAddr / FieldAddr initializer from a {instance, reg,
        field} citation, defaulting the instance to the tree's own."""
        w, b, width = self.bitAddr(cite.get('instance', self.instance),
                                   cite['reg'], cite['field'])
        return (f"{{{w}, {b}, {width}}}", width) if with_width else f"{{{w}, {b}}}"

    # -- pools --------------------------------------------------------------

    def addInputs(self, *signal_names):
        """Add input signal IDs to the pool, return the start offset."""
        offset = len(self.inputs)
        self.inputs += [self.signal_index.get(n, 0) for n in signal_names]
        return offset

    def internValues(self, values):
        """Add a value table to the pool (deduplicating), return (offset, size)."""
        key = tuple(values)
        if key not in self.value_tables:
            self.value_tables[key] = (len(self.values), len(values))
            self.values.extend(values)
        return self.value_tables[key]

    def stateSlot(self, name, default=0):
        """Index of a runtime-settable state word, allocating on first use."""
        if name not in self.state:
            self.state[name] = (len(self.state), default)
        return self.state[name][0]

    def addElement(self, output_signal, type_key, desc, input_offset):
        """Append a descriptor to its type's list and record the signal mapping."""
        descs = self.descs[type_key]
        self.elements[output_signal] = (type_key, len(descs), input_offset)
        descs.append(desc)

    # -- descriptor builders ------------------------------------------------

    def buildGenerator(self, gen):
        """Build a generator descriptor: (type key, descriptor, input offset)."""
        ctrl = gen.get('control')
        output = gen.get('output', '')
        # A generator's nominal frequency is declared on its output signal.
        nominal = self.by_name.get(output, {}).get('nominal')
        input_offset = self.addInputs()     # generators have no inputs

        if ctrl is None:
            # Always-on generator (no enable bit in hardware).  The frequency
            # must come from the input's `nominal` field.
            if nominal is None:
                print(f"  WARNING: generator {gen.get('name', '?')} has no control "
                      f"and no nominal frequency on input '{output}'; emitting 0",
                      file=sys.stderr)
                nominal = 0
            return ('gen_fixed',
                    f'{{{{0, 0}}, {nominal}, clocktree::Polarity::AlwaysOn}}',
                    input_offset)

        state = ctrl.get('state')
        reg = ctrl.get('reg', '')
        field = ctrl.get('field', '')
        values = ctrl.get('values', [])
        polarity = _polarity_from_values(values)
        addr = self.citation(ctrl) if reg and field else '{0, 0}'

        if state:
            # Runtime-configurable frequency (e.g. external crystal).  An
            # accompanying enable bit is optional; without one, use AlwaysOn so
            # the runtime ignores addr.
            pol = polarity if (reg and field) else 'clocktree::Polarity::AlwaysOn'
            return ('gen_external',
                    f'{{{addr}, {self.stateSlot(state)}, {pol}}}', input_offset)

        # Fixed-frequency generator with an enable bit.  Prefer the input's
        # `nominal` field; fall back to the legacy `values`-based encoding
        # (where values=[0, freq]) for clock trees that haven't been migrated.
        if nominal is not None:
            freq = nominal
        elif len(values) == 2 and values[0] == 0 and values[1] != 0:
            freq = values[1]
        elif values:
            # Multi-state or magic-value table — pick a plausible non-zero entry.
            # This is a known approximation for cases like the H7 HSI selector.
            freq = next((v for v in reversed(values) if v != 0), 0)
        else:
            freq = 0
        return ('gen_fixed', f'{{{addr}, {freq}, {polarity}}}', input_offset)

    def buildGate(self, gate):
        """Build a gate descriptor: (type key, descriptor, input offset)."""
        input_offset = self.addInputs(gate.get('input', '_'))
        ctrl = gate.get('control')
        if ctrl is None:
            return ('passthrough', '{}', input_offset)
        return ('gate', f'{{{self.citation(ctrl)}}}', input_offset)

    def buildDivider(self, div):
        """Build a divider descriptor: (type key, descriptor, input offset)."""
        input_offset = self.addInputs(div['input'])
        factor = div.get('factor')
        if factor is None:
            # Fixed divider, or passthrough (divide by 1) without a value.
            return ('fixed_div', f'{{{div.get("value") or 1}}}', input_offset)

        addr, _ = self.citation(factor, with_width=True)
        if factor.get('values'):
            # Table-based divider
            tbl_offset, tbl_size = self.internValues(factor['values'])
            return ('table_div', f'{{{addr}, {tbl_offset}, {tbl_size}}}', input_offset)
        # Linear divider: divisor = raw + offset (offset 0 = raw field value)
        value_range = factor.get('value_range') or {}
        return ('linear_div', f'{{{addr}, {value_range.get("offset", 0)}}}',
                input_offset)

    def buildMux(self, mux):
        """Build a mux descriptor: (type key, descriptor, input offset)."""
        inputs = mux['inputs']
        # Normalize empty inputs (an "off" mux setting) to the empty signal.
        input_offset = self.addInputs(*(i if i else '_' for i in inputs))
        addr, _ = self.citation(mux['control'], with_width=True)
        return ('mux', f'{{{addr}, {len(inputs)}}}', input_offset)

    def buildPll(self, pll):
        """Build a PLL descriptor: (type key, descriptor, input offset)."""
        input_offset = self.addInputs(pll['input'])

        def field(cite, default_offset=0):
            """(initializer, value_range max, divisor offset) for one PLL field."""
            if cite is None:
                return '{0, 0, 0}', 0, default_offset
            addr, _ = self.citation(cite, with_width=True)
            vr = cite.get('value_range')
            return (addr,
                    vr.get('max', 0) if vr else 0,
                    vr.get('offset', 0) if vr else default_offset)

        fb_int, _, fb_int_offset = field(pll.get('feedback_integer'), 1)
        fb_frac, frac_max, _ = field(pll.get('feedback_fraction'))
        post_div, _, post_div_offset = field(pll.get('post_divider'), 1)

        # Determine fractional bits from max value
        frac_bits = (frac_max.bit_length()
                     if pll.get('feedback_fraction') and frac_max > 0 else 0)
        return ('pll',
                f'{{{fb_int}, {fb_int_offset}, {fb_frac}, {frac_bits}, '
                f'{post_div}, {post_div_offset}}}',
                input_offset)

    # -- assembly -----------------------------------------------------------

    def build(self):
        """Resolve all register citations and build the descriptor tables."""
        sections = [(self.content.get(key, []), builder) for key, builder in [
            ('generators', self.buildGenerator),
            ('plls',       self.buildPll),
            ('gates',      self.buildGate),
            ('dividers',   self.buildDivider),
            ('muxes',      self.buildMux),
        ]]

        # Load the peripheral models this clock tree cites, then give them
        # their base addresses — both are needed before any citation can be
        # turned into a (word offset, bit) pair.
        instances = {self.instance}
        for elements, _ in sections:
            for elem in elements:
                for key in CLOCK_CITATIONS:
                    cite = elem.get(key)
                    if cite and 'instance' in cite:
                        instances.add(cite['instance'])
        for inst in instances:
            if inst:
                self.peripheral(inst)
        self.resolveBaseAddresses()

        for elements, builder in sections:
            for elem in elements:
                self.addElement(elem['output'], *builder(elem))

    def header(self, namespace):
        """Assemble the clock-tree header text."""
        # Types with no descriptors are skipped; the remaining ones get
        # 1-based indices (0 means "undriven" in the signal table).
        active = [key for key, _, _ in CLOCK_TYPES if self.descs[key]]
        type_index = {key: i for i, key in enumerate(active, start=1)}
        cpp = {key: (cpp_type, cpp_fn) for key, cpp_type, cpp_fn in CLOCK_TYPES}

        # EXPORT discipline: clocktree.hpp is included unconditionally so its
        # types ride on whatever EXPORT setting the wrapping context has chosen.
        # In module mode the cppm has already #defined EXPORT=export, so
        # clocktree.hpp's namespace is re-exported through this module — no
        # separate #include "clocktree.hpp" needed by importers.  In include
        # mode EXPORT is undefined; clocktree.hpp's own #ifndef-EXPORT block
        # pulls in STL and defines EXPORT empty, after which the chip's
        # namespace below is just declared, not exported.
        txt = ["// generated header file, please don't edit.",
               '#pragma once',
               '',
               '#include "clocktree.hpp"',
               '',
               '#ifndef EXPORT',
               '#define EXPORT',
               '#endif',
               '',
               f'EXPORT namespace {namespace} {{',
               '']

        # Signals enum
        txt.append('enum class Signals : '
                   f'{"uint8_t" if len(self.signals) <= 256 else "uint16_t"} {{')
        txt += [f"        {s['name']},  //!< {s.get('description', '')}"
                for s in self.signals]
        txt += ['};', '']

        # Clocks struct
        txt += ['struct Clocks : clocktree::ClockTreeBase {',
                '    using S = Signals;',
                '']

        # State struct
        if self.state:
            txt.append('    struct State {')
            txt += [f'        uint32_t {name} = {default};'
                    for name, (_, default) in self.state.items()]
            txt += ['    };', '']

        # Descriptor arrays
        for key in active:
            cpp_type, _ = cpp[key]
            if cpp_type == 'uint8_t':
                # Passthrough has no real descriptor; use a single dummy byte
                txt.append(f'    static constexpr uint8_t {key}_descs[] = {{0}};')
            else:
                txt.append(f'    static constexpr {cpp_type} {key}_descs[] = {{')
                txt += [f'        {d},' for d in self.descs[key]]
                txt.append('    };')
        txt.append('')

        # Type table
        txt.append('    static constexpr clocktree::BlockType type_table[] = {')
        txt.append('        {},  // index 0 = undriven')
        for key in active:
            cpp_type, cpp_fn = cpp[key]
            desc_size = f'sizeof({cpp_type})' if cpp_type != 'uint8_t' else '1'
            txt.append(f'        {{{cpp_fn}, {key}_descs, {desc_size}}},  // {key}')
        txt += ['    };', '']

        # Input pool
        txt.append('    static constexpr uint8_t input_pool_data[] = {'
                   + ', '.join(str(v) for v in self.inputs) + '};')
        txt.append('')

        # Value tables
        txt.append('    static constexpr uint32_t value_tables_data[] = {'
                   + (', '.join(str(v) for v in self.values) if self.values else '0')
                   + '};')
        txt.append('')

        # Signal table
        txt.append('    static constexpr clocktree::Signal signal_table[] = {')
        for s in self.signals:
            tk, di, ioff = self.elements.get(s['name'], (None, 0, 0))
            ti = type_index[tk] if tk else 0
            txt.append(f'        {{{ti}, {di}, {ioff}}},  // {s["name"]}')
        txt += ['    };', '']

        # Mutable state
        txt.append(f'    uint32_t state_data[{max(len(self.state), 1)}] = {{'
                   + ', '.join(str(d) for _, d in self.state.values()) + '};')
        txt.append('')

        # Constructor wires up base class pointers
        if self.state:
            txt.append('    Clocks(State st) {')
            txt += [f'        state_data[{slot}] = st.{name};'
                    for name, (slot, _) in self.state.items()]
        else:
            txt.append('    Clocks() {')
        txt += ['        signals = signal_table;',
                '        signal_count = sizeof(signal_table) / sizeof(signal_table[0]);',
                '        types = type_table;',
                '        input_pool = input_pool_data;',
                '        value_tables = value_tables_data;',
                '        state = state_data;',
                '    }',
                '};',
                '',
                '} // namespace',
                '',
                '#undef EXPORT',
                '']
        return '\n'.join(txt)

    def module(self, mod, header):
        """`.cppm` wrapper for a clock-tree header.

        Differs from the peripheral/chip pattern: those put their support
        header (hwreg.hpp) in the global module fragment because its types
        are not meant to cross the module boundary.  Here we want
        clocktree::ClockTree<> visible to importers, so clocktree.hpp goes
        inside the EXPORT=export region — pulled in transitively via the
        chip-specific header — and only STL goes in the GMF.
        """
        return CLOCK_MODULE.substitute(mod=mod, header=header)


def _polarity_from_values(values):
    """Infer enable-bit polarity from a control's `values` list.

    The convention is values=[off, on]: the bit value that disables the
    output comes first, the value that enables it comes second.  Active-low
    enables (e.g. LPC43 XTAL_OSC_CTRL.ENABLE) appear as values=[1, 0].
    Anything else falls back to active-high.
    """
    if len(values) == 2 and values[1] == 0 and values[0] != 0:
        return 'clocktree::Polarity::ActiveLow'
    return 'clocktree::Polarity::ActiveHigh'


# ---------------------------------------------------------------------------
# Subfamily passthrough
# ---------------------------------------------------------------------------

PASS_HPP = ("// generated header file, please don't edit.\n"
            "// subfamily passthrough — no C++ content at this tier.\n"
            "#pragma once\n")

PASS_CPPM = Template("// generated module file, please don't edit.\n"
                     "// subfamily passthrough — no C++ content at this tier.\n"
                     "module;\n"
                     "export module $mod;\n")


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def main(argv):
    # Optional `--endian <native|big|little>` flag (default native), stripped
    # up front so the positional-argument convention is left intact.  Only
    # peripheral blocks consume it; chip MMIO and clock trees are always
    # native.
    endian = 'native'
    if '--endian' in argv:
        i = argv.index('--endian')
        endian = argv[i + 1] if i + 1 < len(argv) else ''
        if endian not in ('native', 'big', 'little'):
            print(f"--endian must be native/big/little, got {endian!r}",
                  file=sys.stderr)
            return 1
        del argv[i:i + 2]

    if len(argv) < 4:
        print("usage: generate_header.py <model.yaml> <model_name> <suffix>"
              " [--endian <native|big|little>]", file=sys.stderr)
        return 1
    model_path, filename = argv[1], argv[2] + argv[3]

    model = load(model_path)
    if not model:
        print(f"No model loaded: {model_path}", file=sys.stderr)
        return 1

    ns = namespace_of(model_path)
    mod = module_id(ns, filename)
    name = Path(filename).name

    if 'registers' in model:
        text = PerFormatter(endian=endian).formatPeripheral(model, ns)
        emit(filename, text + '\n', hwreg_module(mod, name) + '\n')

    elif 'cpu' in model:
        text, imports = ChipFormatter(model, model_path).createHeader(ns, argv[3])
        emit(filename, text + '\n', hwreg_module(mod, name, imports) + '\n')

    elif 'signals' in model or 'clocks' in model:
        fmt = ClockFormatter(model, model_path)
        fmt.build()
        emit(filename, fmt.header(ns), fmt.module(mod, name))

    elif 'inherits' in model or 'instances' in model or 'models' in model:
        emit(filename, PASS_HPP, PASS_CPPM.substitute(mod=mod))

    else:
        print(f"Unknown model type in {model_path} "
              f"(keys: {', '.join(model.keys())})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
