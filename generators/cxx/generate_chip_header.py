# Generate the header file for a System on Chip
#
# Script arguments:
#   argv[1] - Model (Name of yaml file)
#   argv[2] - Namespace name, or path of namespace file (yaml format)
#   argv[3] - Model name (used for type names)
#   argv[4] - Output file suffix (appended to model name)
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
        self.instanceInclTemplate = Template(keywords.get('instanceIncl', '\n#   include "$model$incl_suffix"'))
        self.instanceDeclTemplate = Template(keywords.get('instanceDecl', """
/** Integration parameters for $name */
EXPORT constexpr struct $ns::integration::${model} i_$name = {$params$ints$init};
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
        
    def createIntegration(self, instances, namespace, namespaces):
        """ create list of integration structs """
        types = {}
        decl = ''
        for k, i in instances.items():            
            types[i['model']] = None
            ns = namespaces.get(i['model'], namespace)
            params = self.createParameters(i)
            ints = self.createInterrupts(i)
            init = '\n\t.registers = %#Xu\n' % i['baseAddress']
            decl += self.instanceDeclTemplate.substitute(i, name=k, ns=ns, params=params, ints=ints, init=init)
        includes = [self.instanceInclTemplate.substitute(model=t, incl_suffix=sys.argv[4]) for t in types]
        return decl, ''.join(includes)
        
    def createHeader(self, chip, namespaces, name, prefix, postfix):
        namespace = namespaces
        inverse = {}
        if isinstance(namespaces, dict):
            namespace = namespaces.pop("", None)
            for k, vals in namespaces.items():
                for v in vals:
                    if inverse.setdefault(v, k) != k:
                        raise ValueError(f"Duplicate value {v!r}")
        decl, incl = self.createIntegration(chip['instances'], namespace, inverse)
        imports = [re.search(r'"(\w+)\.hpp"', l).group(1) for l in incl.splitlines() if '#   include ' in l]
        return prefix.substitute(chip, ns=namespace, name=name, incl=incl, imp=';\nimport '.join(imports)) + decl + postfix.substitute(ns=namespace)
                
prefixTemplate = Template("""// File was generated, do not edit!
#ifdef REGISTERS_MODULE
module;
#define EXPORT export
#else
#pragma once
$incl
#undef EXPORT
#define EXPORT
#endif
#ifdef REGISTERS_MODULE
export module $name;
import hwreg;
import $imp;
#endif

namespace $ns {

EXPORT constexpr Exception interruptOffset = $interruptOffset;\t//!< Exception number of first interrupt
""")

postfixTemplate = Template("""
                           
} // namespace $ns

#undef EXPORT
""")

yaml = YAML(typ='safe')
chip = yaml.load(Path(sys.argv[1]))
fmt  = ChipFormatter()
nsfile = Path(sys.argv[2])
namespaces = yaml.load(nsfile) if nsfile.exists() else sys.argv[2]

header = fmt.createHeader(chip, namespaces, sys.argv[3], prefixTemplate, postfixTemplate)
print(header, file=open(sys.argv[3]+sys.argv[4], mode = 'w'))
