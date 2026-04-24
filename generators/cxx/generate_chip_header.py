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
        self.instanceInclTemplate = Template(keywords.get('instanceIncl', '\n#   include "$model$incl_suffix"'))
        self.instanceDeclTemplate = Template(keywords.get('instanceDecl', """
/** Integration parameters for $name */
EXPORT constexpr struct $ns::${model}::Intgr i_$name = {$params$ints$init};
"""))
    
    def createParameters(self, instance):
        params = ''
        for i in instance.get('parameters', []):
            v = i['value']
            if isinstance(v, bool):
                params += f"\n\t.{i['name']} = {'true' if v else 'false'},"
            elif isinstance(v, str):
                params += f'\n\t.{i["name"]} = "{v}",'
            else:
                params += self.instanceParamTemplate.substitute(i)
        return params
        
    def createInterrupts(self, instance):
        ints = ''
        seen = set()
        for i in instance.get('interrupts', []):
            if i['name'] not in seen:
                seen.add(i['name'])
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
        
    def createHeader(self, chip, namespaces, prefix, postfix):
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
        interrupts = chip.get('interrupts', {})
        interruptCount = max(interrupts.keys(), default=chip.get('interruptOffset', 0) - 1) + 1
        header = prefix.substitute(chip, ns=namespace, incl=incl, interruptCount=interruptCount) + decl + postfix.substitute(ns=namespace)
        return header, imports
                
prefixTemplate = Template("""// File was generated, do not edit!
#pragma once

#ifndef EXPORT
$incl
#include "hwreg.hpp"
#include <cstdint>
#define EXPORT
#endif

namespace $ns {

EXPORT constexpr Exception interruptOffset = $interruptOffset;\t//!< Exception number of first interrupt
EXPORT constexpr Exception interruptCount = $interruptCount;\t//!< Total number of exceptions (interrupts + system exceptions)
""")

postfixTemplate = Template("""
                           
} // namespace $ns

#undef EXPORT
""")

moduleTemplate = Template("""// File was generated, do not edit!
module;

#include <cstdint>
#include "hwreg.hpp"

export module $mod;
$imports
#define EXPORT export
#include "$header"
#undef EXPORT
""")

def generate_module(mod, header, imports):
    """Generate a .cppm module wrapper for a chip header."""
    imp_lines = ''.join(f'import {i};\n' for i in imports)
    return moduleTemplate.substitute(mod=mod, header=header, imports=imp_lines)

def generate_header(model_file, namespace, model_name, out_suffix, module_name=None):
    yaml = YAML(typ='safe')
    chip = yaml.load(Path(model_file))
    fmt  = ChipFormatter()
    nsfile = Path(namespace)
    namespaces = yaml.load(nsfile) if nsfile.exists() else namespace
    if module_name is None:
        # Module names must be valid C++ identifiers; stems like "ESP32-P4"
        # need the hyphen replaced.
        module_name = Path(model_name + out_suffix).stem.replace('-', '_')
    header, imports = fmt.createHeader(chip, namespaces, prefixTemplate, postfixTemplate)
    filename = model_name + out_suffix
    print(header, file=open(filename, mode='w'))
    cppm = Path(filename).with_suffix('.cppm')
    print(generate_module(module_name, Path(filename).name, imports), file=open(cppm, mode='w'))

# Script arguments:
#   argv[1] - Model (Name of yaml file)
#   argv[2] - Namespace name, or path of namespace file (yaml format)
#   argv[3] - Model name (used for type names)
#   argv[4] - Output file suffix (appended to model name)
#
if __name__ == "__main__":
    generate_header(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
