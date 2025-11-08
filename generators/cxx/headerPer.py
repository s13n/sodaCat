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

class PerFormatter:
    def __init__(self, **keywords):
        self.enumTemplate      = Template(keywords.get('enum'     , '\n\t/** $description */\n\t$name = $value,'))
        self.enumsTemplate     = Template(keywords.get('enums'    , '\ninline namespace ${name}_ {\nEXPORT enum $name : $type {$enums\n};\n} // namespace ${name}_\n'))
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
inline namespace $name {$enums
$types
/** $description */
EXPORT struct $name {$regs
}; // size = $size

/** Integration of peripheral in the SoC. */
EXPORT struct Integration {
$params$ints$blocks};

} // inline namespace $name
$postfix"""))
                                                       
    def formatEnumList(self, enums:list):
        """ Generate enumerator list """
        list = []
        for enum in enums:
            value = enum.get('value', 1)
            description = enum.get('description', '')
            txt = self.enumTemplate.substitute(enum, type=type, value=value, description=description)
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
                    enum = self.enumsTemplate.substitute(field, enums=txt, type='uint32_t')
            width = field.get('bitWidth', 1)
            description = field.get('description', '')
            txt = self.bitfieldTemplate.substitute(field, type=type, width=width, description=description)
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
                
    def formatRegisterList(self, reglist:list, defaultType:str, padToSize:int, defaultSize:int):
        """ Generate structs and instances for a list of registers
        Returns four values (in this order):
        1. All the type definitions for the registers as a multiline string
        2. The formatted list of registers as a multiline string
        3. The size of the register list in the address space of the controller
        4. The list of enumeration definitions
        """
        enums = ''
        structs = ''
        list = []
        for reg in reglist:
            addressOffset = reg['addressOffset']
            description = reg.get('description', '')
            dim = reg.get('dim', 1)
            if 'registers' in reg:
                name = reg['name'].replace('[%s]', '')
                padSize = reg.get('dimIncrement', 0)
                types, regs, size, enum = self.formatRegisterList(reg['registers'], 'uint32_t', padSize, 4)
                enums += enum
                structs += self.registersTemplate.substitute(name=name, regs=regs, types=types, description=description, size=size)
                names = reg['name'] % dim
                line = self.fieldTemplate.substitute(name=names, type='struct ' + name, description=description)
                list.append([line, addressOffset, size*dim])
            else:
                dimIndex = reg.get('dimIndex', "")
                name = reg['name'].replace('%s', '')
                names = name
                if dimIndex:
                    #TODO: Check if the address offset matches the size
                    names = ",".join(reg['name'] % item for item in dimIndex.split(","))
                elif dim > 1:
                    name = reg['name'].replace('[%s]', '')
                    names = reg['name'] % dim
                size = reg.get('size', defaultSize * 8)
                type = reg.get('dataType', 'uint%s_t' % size)
                if 'fields' in reg and reg['fields']:
                    fields, enum = self.formatFieldList(reg['fields'], type)
                    enums += self.regEnumsTemplate.substitute(reg, name=name, enums=enum) if enum else ''
                    structs += self.fieldsTemplate.substitute(reg, name=name, fields=fields, description=description)
                line = self.fieldTemplate.substitute(reg, name=names, type=self.typeTemplate.substitute(reg, name=name), description=description)
                list.append([line, addressOffset, (size>>3)*dim])

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
            type = ('HwPtr<struct ' + per['name'] + ' volatile> ') if block['usage'] == 'registers' else 'std::span<std::byte> '
            blocks += self.addressTemplate.substitute(block, type=type)
        ints = ''
        for int in per.get('interrupts', []):
            desc = int.get('description', '')
            ints += self.interruptTemplate.substitute(int, description=desc)
        params = ''
        for par in per.get('parameters', []):
            desc = par.get('description', '')
            params += self.parameterTemplate.substitute(par, description=desc)
        return blocks, ints, params
            
    def formatPeripheral(self, per:dict, prefix:str, postfix:str):
        """ Generate definitions for a peripheral """
        types, regs, size, enums = self.formatRegisterList(per['registers'], 'uint32_t', 0, 4)
        blocks, ints, params = self.formatIntegrationList(per)
        description = per.get('description', '')
        return self.headerTemplate.substitute(per, blocks=blocks, ints=ints, params=params, regs=regs, enums=enums, types=types, description=description, size=size, prefix=prefix, postfix=postfix)
    
         
yaml=YAML(typ='safe')
per = yaml.load(Path(sys.argv[1]))
fmt = PerFormatter()

prefixTemplate = Template("""// File was generated, do not edit!
#ifdef REGISTERS_MODULE
module;
#define EXPORT export
#else
#pragma once
#include "registers.hpp"
#undef EXPORT
#define EXPORT
#endif

#include <cstdint>

#ifdef REGISTERS_MODULE
export module $mod;
import registers;
#endif

namespace $ns {""")

postfixTemplate = Template("""} // namespace $ns

#undef EXPORT
""")

print(fmt.formatPeripheral(per, prefixTemplate.substitute(ns=sys.argv[3], mod=os.path.basename(sys.argv[2])), postfixTemplate.substitute(ns=sys.argv[3])), file=open(sys.argv[2] + '.hpp', mode = 'w'))
