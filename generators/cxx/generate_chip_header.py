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
        self.instanceInclTemplate = Template(keywords.get('instanceIncl', '\n#   include "$ns/$model$incl_suffix"'))
        self.instanceDeclTemplate = Template(keywords.get('instanceDecl', """
/** Integration parameters for $name */
EXPORT constexpr struct $ns::${model}::Intgr i_$name = {$params$ints$init};
"""))
        # Block-name → (param_names, interrupt_names) cache, populated lazily.
        # The block model is the authoritative source for designated-initializer
        # order; chip-side lists are sorted to match before emission.
        self._block_orders = {}

    @staticmethod
    def _resolve_block_path(chip_dir, model_relpath):
        """Walk up from chip_dir until <parent>/<model_relpath>.yaml exists."""
        target = Path(model_relpath + '.yaml')
        p = Path(chip_dir).resolve()
        while True:
            candidate = p / target
            if candidate.is_file():
                return candidate
            if p.parent == p:
                return None
            p = p.parent

    def _loadBlockOrder(self, chip_dir, models_map, model_name):
        """Return (param_names, interrupt_names, param_defaults) declared
        by the block model.

        param_defaults is a {name: value} map for params that declare a
        default; chip instances that don't override such a param fall
        back to the default at integration-emission time.

        Returns (None, None, {}) when the block YAML can't be located,
        in which case callers preserve chip-side order with no default
        fallback — that's the ad-hoc-runs case outside the standard
        models tree.  Under CMake the file is always present (ensure_model()
        downloads it ahead of header generation).
        """
        if model_name in self._block_orders:
            return self._block_orders[model_name]
        relpath = models_map.get(model_name, model_name)
        block_path = self._resolve_block_path(chip_dir, relpath)
        if block_path is None:
            result = (None, None, {})
        else:
            block = YAML(typ='safe').load(block_path)
            params_decl = block.get('params', [])
            result = (
                [p['name'] for p in params_decl],
                [i['name'] for i in block.get('interrupts', [])],
                {p['name']: p['default']
                 for p in params_decl if 'default' in p},
            )
        self._block_orders[model_name] = result
        return result

    def createParameters(self, instance_name, instance, param_order,
                         param_defaults):
        """Emit designated initialisers for an instance's params.

        Chip-yaml `parameters:` overrides take precedence; any param
        declared by the block model with a default that the chip yaml
        didn't override falls back to the default.  Params with neither
        a chip override nor a block default are silently skipped (the
        struct member is then default-initialised by C++ — caller's
        responsibility to ensure that's acceptable).
        """
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
                params += self.instanceParamTemplate.substitute(
                    name=name, value=v)
        return params

    def createInterrupts(self, instance_name, instance, int_order):
        by_name = {}
        for i in instance.get('interrupts', []):
            by_name.setdefault(i['name'], i)  # dedup, first occurrence wins
        if int_order is None:
            ordered = list(by_name.values())
        else:
            unknown = set(by_name) - set(int_order)
            if unknown:
                raise ValueError(
                    f"chip instance '{instance_name}' (model '{instance['model']}'): "
                    f"interrupt(s) {sorted(unknown)!r} not declared by block model"
                )
            ordered = [by_name[n] for n in int_order if n in by_name]
        return ''.join(self.instanceIntTemplate.substitute(i) for i in ordered)

    def createIntegration(self, chip, chip_path, namespace, namespaces):
        """ create list of integration structs.

        Returns (decl, includes, model_to_ns) where model_to_ns maps each
        referenced peripheral model name to its C++ namespace — needed both
        for namespace-qualified `#include`s and for module import names.
        """
        instances = chip['instances']
        models_map = chip.get('models', {})
        chip_dir = Path(chip_path).parent
        model_to_ns = {}
        decl = ''
        for k, i in instances.items():
            m = i['model']
            ns = namespaces.get(m, namespace)
            model_to_ns[m] = ns
            param_order, int_order, param_defaults = self._loadBlockOrder(
                chip_dir, models_map, m)
            params = self.createParameters(k, i, param_order, param_defaults)
            ints = self.createInterrupts(k, i, int_order)
            init = '\n\t.registers = %#Xu\n' % i['baseAddress']
            decl += self.instanceDeclTemplate.substitute(i, name=k, ns=ns, params=params, ints=ints, init=init)
        includes = [
            self.instanceInclTemplate.substitute(model=m, ns=ns, incl_suffix=sys.argv[4])
            for m, ns in model_to_ns.items()
        ]
        return decl, ''.join(includes), model_to_ns

    def createHeader(self, chip, chip_path, namespaces, prefix, postfix):
        namespace = namespaces
        inverse = {}
        if isinstance(namespaces, dict):
            namespace = namespaces.pop("", None)
            for k, vals in namespaces.items():
                for v in vals:
                    if inverse.setdefault(v, k) != k:
                        raise ValueError(f"Duplicate value {v!r}")
        decl, incl, model_to_ns = self.createIntegration(chip, chip_path, namespace, inverse)
        imports = [f'{ns}.{m}' for m, ns in model_to_ns.items()]
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
        # need the hyphen replaced.  Prefix with the namespace when it's a
        # plain identifier, so module names stay unique across vendors.
        stem = Path(model_name + out_suffix).stem.replace('-', '_')
        module_name = (f'{namespace}.{stem}'
                       if isinstance(namespace, str)
                       and re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', namespace)
                       else stem)
    header, imports = fmt.createHeader(chip, model_file, namespaces, prefixTemplate, postfixTemplate)
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
