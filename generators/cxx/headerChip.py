# Generate the header file for a System on Chip
#
# This generator expects that the formatting is going to be fine tuned with clang-format or a similar tool.
# There is no point in trying to please everyone with the formatting done here, when there are much better
# tools that can be configured to conform with arbitrary formatting wishes.
#
from ruamel.yaml import YAML
from pathlib import Path
from string import Template
import sys
import os
import re

class ChipFormatter:
    def __init__(self, **keywords):
        self.instanceParamTemplate= Template(keywords.get('instanceParam',  '\n\t.$name = ${value}u,'))
        self.instanceIntTemplate  = Template(keywords.get('instanceInt',  '\n\t.ex$name = ${value}u + interruptOffset,'))
        self.instanceInclTemplate = Template(keywords.get('instanceIncl', '\n#   include "$model.hpp"'))
        self.instanceDeclTemplate = Template(keywords.get('instanceDecl', """\n/** Integration parameters for $name */
EXPORT constexpr struct $model::Integration i_$name = {$params$ints$init};
"""))
    
    def createParameters(self, instance):
        params = ''
        for i in instance.get('parameters', []):
            params += self.instanceParamTemplate.substitute(i)
        return params
        
    def createInterrupts(self, instance):
        ints = ''
        for i in instance.get('interrupts', []):
            ints += self.instanceIntTemplate.substitute(i)
        return ints
        
    def createIntegration(self, instances):
        """ create list of integration structs """
        types = set()
        decl = ''
        for k, i in instances.items():            
            types.add(i['model'])
            params = self.createParameters(i)
            ints = self.createInterrupts(i)
            init = '\n\t.registers = %#Xu\n' % i['baseAddress']
            decl += self.instanceDeclTemplate.substitute(i, name=k, params=params, ints=ints, init=init)
        includes = [self.instanceInclTemplate.substitute(model=t) for t in sorted(types)]
        return decl, ''.join(includes)
        
    def createHeader(self, chip, namespace, name, prefix, postfix):
        decl, incl = self.createIntegration(chip['instances'])
        return prefix.substitute(chip, ns=namespace, name=name, incl=incl) + decl + postfix.substitute(ns=namespace)
                
yaml = YAML(typ='safe')
chip = yaml.load(Path(sys.argv[1]))
fmt = ChipFormatter()

prefixTemplate = Template("""// File was generated, do not edit!
#pragma once

#ifdef MODULE_CHIP
#   define EXPORT export
#else $incl
#   define EXPORT
#endif

namespace $ns {

EXPORT constexpr Exception interruptOffset = $interruptOffset;\t//!< Exception number of first interrupt
""")

postfixTemplate = Template("""
                           
} // namespace $ns

#undef EXPORT
""")

header = fmt.createHeader(chip, sys.argv[3], os.path.basename(sys.argv[2]), prefixTemplate, postfixTemplate)
print(header, file=open(sys.argv[2] + '.hpp', mode = 'w'))

#TODO: Find a better way to extract the import list
imports = [re.search(r'"(\w+)\.hpp"', l).group(1) for l in header.splitlines() if '#   include ' in l]

cppTemplate = Template("""// File was generated, do not edit!
export module $mod;
#define MODULE_CHIP
import $incl;
import registers;
#include "$mod.hpp"
""")
print(cppTemplate.substitute(mod=os.path.basename(sys.argv[2]), incl=';\nimport '.join(imports)), file=open(sys.argv[2] + '.cpp', mode = 'w'))
