# Generate the header file for a peripheral
#
# This generator expects that the formatting is going to be fine tuned with clang-format or a similar tool.
# There is no point in trying to please everyone with the formatting done here, when there are much better
# tools that can be configured to conform with arbitrary formatting wishes.
#
# We use namespaces a lot here, because they help avoiding ambiguities when the naming of registers, fields
# and/or enumerators overlaps. That is frequently the case, unfortunately. The user can avoid unnecessary
# verbosity in his code by employing `using namespace <...>` directives. This is why we use namespaces
# instead of other scoping mechanisms like scoped enums, which can't be abbreviated in this way.
#
# Note that a struct or an unscoped enum can have the same name as a namespace or an enumerator or a struct
# member - the enumerator or member takes precedence and hides the struct/enum name. If you explicitly want
# to refer to the struct/enum name in such a situation, you can write `struct <name>` or `enum <name>`
# instead of using the name on its own, similar to the situation in C.

from ruamel.yaml import YAML
from pathlib import Path
from string import Template
from itertools import pairwise
import sys
import os

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

def _safe_name(name: str) -> str:
    """Return name unchanged, or with a trailing underscore if it is reserved,
    or with an 'e' prefix if it starts with a digit."""
    if name and name[0].isdigit():
        return 'e' + name
    return name + '_' if name in _RESERVED_NAMES else name


class PerFormatter:
    def __init__(self, **keywords):
        self.enumTemplate      = Template(keywords.get('enum'     , '\n\t/** $description */\n\t$name = $value,'))
        self.enumsTemplate     = Template(keywords.get('enums'    , '\ninline namespace ${name}_ {\nEXPORT enum ${name}_e : $type {$enums\n};\n} // namespace ${name}_\n'))
        self.regEnumsTemplate  = Template(keywords.get('regEnums' , '\ninline namespace ${name}_ {$enums} // namespace ${name}_\n'))
        self.bitfieldTemplate  = Template(keywords.get('bitfield' , '\n\t/** $description */\n\t$type $name:$width;'))
        self.resBitsTemplate   = Template(keywords.get('resBits'  , '\n\t$type _$res:$width;\t// reserved'))
        self.typeTemplate      = Template(keywords.get('type'     , 'HwReg<struct $name>'))
        self.resBytesTemplate  = Template(keywords.get('resBytes' , '\n\tuint8_t _$res[$bytes];\t// reserved'))
        self.fieldTemplate     = Template(keywords.get('field'    , '\n\t/** $description */\n\t$type $name;'))
        self.fieldsTemplate    = Template(keywords.get('fields'   , '\n/** $description */\nEXPORT struct $name {$fields\n};\n'))
        self.registersTemplate = Template(keywords.get('registers', '\n$types\n/** $description */\nEXPORT struct $name {$regs\n}; // size = $size\n'))
        self.addressTemplate   = Template(keywords.get('address'  , '\t$type$usage;\t// offset = $offset, size = $size\n'))
        self.interruptTemplate = Template(keywords.get('interrupt', '\tException ex$name;\t//!< $description\n'))
        self.parameterTemplate = Template(keywords.get('parameter', '\tuint16_t $name:$bits;\t//!< $description\n'))
        self.headerTemplate    = Template(keywords.get('header', """
$prefix
namespace ${name} {$enums
$types
/** $description */
EXPORT struct $name {$regs
}; // size = $size

/** Integration of peripheral in the SoC. */
EXPORT struct Intgr {
$params$ints$blocks};
} // namespace ${name}
$postfix"""))
                                                       
    def formatEnumList(self, enums:list):
        """ Generate enumerator list """
        list = []
        for enum in enums:
            value = enum.get('value', 1)
            description = enum.get('description', '')
            txt = self.enumTemplate.substitute(enum, name=_safe_name(enum.get('name', '')), type=type, value=value, description=description)
            list.append(txt)
        return ''.join(list)
        
    def formatFieldList(self, fields:list, type:str):
        """ Generate bitfield list
        Returns:
        - the formatted list of bitfields as a multiline string
        - the formatted list of enum definitions as a multiline string
        """
        list = []
        for field in fields:
            enum = ''
            if 'enumeratedValues' in field:
                txt = self.formatEnumList(field['enumeratedValues'])
                if txt:
                    enum = self.enumsTemplate.substitute(field, name=_safe_name(field.get('name', '')), enums=txt, type=type)
            width = field.get('bitWidth', 1)
            description = field.get('description', '')
            txt = self.bitfieldTemplate.substitute(field, name=_safe_name(field.get('name', '')), type=type, width=width, description=description)
            list.append([txt, field['bitOffset'], width, enum])
            
        list.sort(key=lambda f:f[1])    # sort fields according to increasing offset
        txt = ''
        enums = ''
        res = 0
        pos = 0
        for line, offset, width, enum in list:
            enums += enum
            if offset > pos:
                txt += self.resBitsTemplate.substitute(type=type, res=res, width=offset-pos)
                res += 1
                pos = offset
            txt += line
            pos += width
        return txt, enums
                
    def formatRegisterList(self, reglist:list, defaultType:str, padToSize:int, defaultSize:int, structPrefix:str=''):
        """ Generate structs and instances for a list of registers
        Returns four values (in this order):
        1. All the type definitions for the registers as a multiline string
        2. The formatted list of registers as a multiline string
        3. The size of the register list in the address space of the controller
        4. The list of enumeration definitions

        structPrefix is prepended to struct/enum type names to avoid collisions
        when multiple clusters have identically-named registers.
        """
        enums = ''
        structs = ''
        list = []
        for reg in reglist:
            addressOffset = reg['addressOffset']
            description = reg.get('description', '')
            dim = reg.get('dim', 1)
            # Support list-valued dim for multidimensional arrays (sodaCat extension)
            if isinstance(dim, int):
                dim_fmt = dim      # for % formatting
                dim_total = dim    # total element count
            else:
                dim_fmt = tuple(dim)
                dim_total = 1
                for d in dim: dim_total *= d
            if 'registers' in reg:
                dimIndex = reg.get('dimIndex', '')
                # Derive the struct type name: strip [%s] or %s, drop trailing _
                name = reg['name'].replace('[%s]', '').replace('%s', '').rstrip('_')
                padSize = reg.get('dimIncrement', 0)
                innerPrefix = structPrefix + name + '_'
                types, regs, size, enum = self.formatRegisterList(reg['registers'], 'uint32_t', padSize, 4, innerPrefix)
                enums += enum
                structs += self.registersTemplate.substitute(name=name, regs=regs, types=types, description=description, size=size)
                if dimIndex:
                    names = ','.join(reg['name'] % item for item in dimIndex.split(','))
                elif '[%s]' in reg['name']:
                    names = reg['name'] % dim_fmt
                else:
                    names = reg['name']
                line = self.fieldTemplate.substitute(name=names, type='struct ' + name, description=description)
                list.append([line, addressOffset, size*dim_total])
            else:
                dimIndex = reg.get('dimIndex', "")
                memberName = reg['name'].replace('%s', '')
                typeName = structPrefix + memberName
                names = memberName
                if dimIndex:
                    #TODO: Check if the address offset matches the size
                    names = ",".join(reg['name'] % item for item in dimIndex.split(","))
                elif dim_total > 1:
                    memberName = reg['name'].replace('[%s]', '')
                    typeName = structPrefix + memberName
                    names = reg['name'] % dim_fmt
                size = reg.get('size', defaultSize * 8)
                type = reg.get('dataType', 'uint%s_t' % size)
                if 'fields' in reg and reg['fields']:
                    fields, enum = self.formatFieldList(reg['fields'], type)
                    enums += self.regEnumsTemplate.substitute(reg, name=typeName, enums=enum) if enum else ''
                    structs += self.fieldsTemplate.substitute(reg, name=typeName, fields=fields, description=description)
                    regType = self.typeTemplate.substitute(reg, name=typeName)
                else:
                    regType = type
                line = self.fieldTemplate.substitute(reg, name=names, type=regType, description=description)
                list.append([line, addressOffset, (size>>3)*dim_total])

        list.sort(key=lambda r:r[1])
        list.append(['', 0xFFFFFFFF, 0])     # dummy
        txt = ''
        res = 0
        pos = 0
        union = False
        for this, following in pairwise(list):
            if not union and this[1] == following[1]:
                union = True
                txt += '\n\tunion {'
            if this[1] > pos:
                txt += self.resBytesTemplate.substitute(res=res, bytes=this[1]-pos)
                res += 1
                pos = this[1]
            txt += this[0]
            if union and this[1] != following[1]:
                union = False
                txt += '\n\t};'
            else:
                pos += this[2]
        if padToSize > pos:
            txt += self.resBytesTemplate.substitute(res=res, bytes=padToSize-pos)
            pos = padToSize
        return structs, txt, pos, enums

    def formatIntegrationList(self, per:dict):
        """ Generate definitions for the parameterization of a peripheral """
        blocks = ''
        for block in per.get('addressBlocks', []):
            type = (f'HwPtr<struct {per['name']} volatile> ') if block['usage'] == 'registers' else 'std::span<std::byte> '
            blocks += self.addressTemplate.substitute(block, type=type)
        ints = ''
        for int in per.get('interrupts', []):
            desc = int.get('description', '')
            ints += self.interruptTemplate.substitute(int, description=desc)
        params = ''
        for par in per.get('parameters', per.get('params', [])):
            desc = par.get('description', '')
            if par.get('type') == 'int' and 'max' in par:
                bits = par['max'].bit_length() or 1
                params += self.parameterTemplate.substitute(par, bits=bits, description=desc)
            elif par.get('type') == 'bool':
                params += self.parameterTemplate.substitute(par, bits=1, description=desc)
            elif 'bits' in par:
                params += self.parameterTemplate.substitute(par, description=desc)
            else:
                ptype = {'string': 'const char*'}.get(par.get('type', 'int'), 'uint32_t')
                params += f'\t{ptype} {par["name"]};\t//!< {desc}\n'
        return blocks, ints, params

    def formatPeripheral(self, per:dict, prefix:str, postfix:str):
        """ Generate definitions for a peripheral """
        defaultSize = per.get('size', 32) >> 3
        types, regs, size, enums = self.formatRegisterList(per['registers'], 'uint32_t', 0, defaultSize)
        blocks, ints, params = self.formatIntegrationList(per)
        description = per.get('description', '')
        return self.headerTemplate.substitute(per, blocks=blocks, ints=ints, params=params, regs=regs, enums=enums, types=types, description=description, size=size, prefix=prefix, postfix=postfix)
    
         
prefixTemplate = Template("""// File was generated, do not edit!
#pragma once

#ifndef EXPORT
#include "hwreg.hpp"
#include <cstdint>
#define EXPORT
#endif

namespace $ns {""")

postfixTemplate = Template("""} // namespace $ns

#undef EXPORT""")

moduleTemplate = Template("""// File was generated, do not edit!
module;

#include <cstdint>

export module $mod;
import hwreg;

#define EXPORT export
#include "$header"
#undef EXPORT
""")

def generate_module(mod, header):
    """Generate a .cppm module wrapper for a peripheral header."""
    return moduleTemplate.substitute(mod=mod, header=header)

if __name__ == "__main__":
    yaml= YAML(typ='safe')
    per = yaml.load(Path(sys.argv[1]))
    if per:
        fmt = PerFormatter()
        prefix = prefixTemplate.substitute(ns=sys.argv[2])
        postfix = postfixTemplate.substitute(ns=sys.argv[2])
        txt = fmt.formatPeripheral(per, prefix, postfix)
        filename = sys.argv[3]+sys.argv[4]
        print(txt, file=open(filename, mode = 'w'))
        modid = Path(filename).stem
        cppm = Path(filename).with_suffix('.cppm')
        print(generate_module(modid, Path(filename).name), file=open(cppm, mode='w'))
    else:
        print(f"No model loaded: {sys.argv[1]}")
