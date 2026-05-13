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
        # Destination strings in chip YAML's per-instance `connections:` map
        # carry the absolute vector index (NVIC's own input numbering), so
        # the emit no longer applies `interruptOffset` — that offset is purely
        # descriptive of NVIC's relationship to the Cortex-M exception space.
        self.instanceIntTemplate  = Template(keywords.get('instanceInt',  '\n\t.ex$name = ${value}u,'))
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
        """Return (param_names, output_names, param_defaults) declared
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
                [i['name'] for i in block.get('outputs', [])],
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
        """Emit ex<NAME> designated initialisers for this instance's NVIC-bound
        outputs.

        Reads `instance['connections']` — a {signal_name: [destination_string]}
        map.  Only destinations of the form 'NVIC.<vector>' produce an
        initialiser; non-NVIC destinations (DMAMUX, EXTI, ...) are silently
        ignored at this Phase-1 stage and will get their own emit paths as
        the C++ side grows field-type dispatch.
        """
        connections = instance.get('connections') or {}
        if int_order is None:
            names = list(connections.keys())
        else:
            unknown = set(connections.keys()) - set(int_order)
            if unknown:
                raise ValueError(
                    f"chip instance '{instance_name}' (model '{instance['model']}'): "
                    f"output(s) {sorted(unknown)!r} not declared by block model"
                )
            names = [n for n in int_order if n in connections]
        out = ''
        for name in names:
            for dest in connections[name]:
                inst_pfx, dot, port = dest.partition('.')
                if not dot or inst_pfx != 'NVIC':
                    continue
                try:
                    vec = int(port)
                except ValueError:
                    continue
                out += self.instanceIntTemplate.substitute(name=name, value=vec)
        return out

    def createIntegration(self, chip, chip_path, namespace, incl_suffix):
        """ create list of integration structs.

        Returns (decl, includes, model_to_ns) where model_to_ns maps each
        referenced peripheral model name to its C++ namespace — read from
        the referenced block YAML's own `namespace:` key (with directory-
        based fallback via _namespace.resolve).
        """
        from _namespace import resolve as _resolve_ns
        # Walk the `inherits:` chain so instances and models declared at the
        # subfamily/shared-spec tier feed into the per-chip integration view.
        # Chip-level entries override ancestor entries by key (instance name
        # / block name).
        instances, models_map = self._collectInstances(chip, chip_path)
        chip_dir = Path(chip_path).parent
        model_to_ns = {}
        decl = ''
        for k, i in instances.items():
            m = i['model']
            if m not in model_to_ns:
                block_path = self._resolve_block_path(
                    chip_dir, models_map.get(m, m))
                model_to_ns[m] = _resolve_ns(block_path) if block_path else namespace
            ns = model_to_ns[m]
            param_order, int_order, param_defaults = self._loadBlockOrder(
                chip_dir, models_map, m)
            params = self.createParameters(k, i, param_order, param_defaults)
            ints = self.createInterrupts(k, i, int_order)
            init = '\n\t.registers = %#Xu\n' % i['baseAddress']
            decl += self.instanceDeclTemplate.substitute(i, name=k, ns=ns, params=params, ints=ints, init=init)
        includes = [
            self.instanceInclTemplate.substitute(model=m, ns=ns, incl_suffix=incl_suffix)
            for m, ns in model_to_ns.items()
        ]
        return decl, ''.join(includes), model_to_ns

    def createHeader(self, chip, chip_path, namespace, incl_suffix, prefix, postfix):
        decl, incl, model_to_ns = self.createIntegration(chip, chip_path, namespace, incl_suffix)
        imports = [f'{ns}.{m}' for m, ns in model_to_ns.items()]
        # Vector table is the union of the chip's `interrupts:` and every
        # ancestor reachable via `inherits:`.  This lets a subfamily own the
        # common entries while each chip carries only its per-chip deltas.
        interrupts = self._collectInterrupts(chip, chip_path)
        interruptCount = max(interrupts.keys(), default=chip.get('interruptOffset', 0) - 1) + 1
        header = prefix.substitute(chip, ns=namespace, incl=incl, interruptCount=interruptCount) + decl + postfix.substitute(ns=namespace)
        return header, imports

    def _walkInheritsChain(self, chip, chip_path):
        """Return [(node, node_path), ...] from chip up to the root of the
        `inherits:` chain.  Used by the collect-merge helpers below.
        """
        chain = []
        node, node_path = chip, chip_path
        while node is not None:
            chain.append((node, node_path))
            parent_ref = node.get('inherits')
            if not parent_ref:
                break
            parent_path = self._resolve_block_path(Path(node_path).parent, parent_ref)
            if parent_path is None:
                break
            node = YAML(typ='safe').load(parent_path)
            node_path = str(parent_path)
        return chain

    def _collectInterrupts(self, chip, chip_path):
        """Derive the NVIC vector table by walking each instance's per-output
        destinations across the chip + every ancestor reached via `inherits:`.

        Returns {vec: ["inst.signal", ...]}.  Only destinations of the form
        `NVIC.<vector>` contribute; vectors are absolute (NVIC's own input
        numbering).  Used by createHeader to size `interruptCount`.
        """
        instances, _ = self._collectInstances(chip, chip_path)
        table = {}
        for inst_name, inst in instances.items():
            for sig, dests in (inst.get('connections') or {}).items():
                for dest in dests:
                    inst_pfx, dot, port = dest.partition('.')
                    if not dot or inst_pfx != 'NVIC':
                        continue
                    try:
                        vec = int(port)
                    except ValueError:
                        continue
                    entry = f"{inst_name}.{sig}"
                    bucket = table.setdefault(vec, [])
                    if entry not in bucket:
                        bucket.append(entry)
        return dict(sorted(table.items()))

    def _collectInstances(self, chip, chip_path):
        """Merge the chip's `instances:` and `models:` maps with each
        ancestor reached via `inherits:`.  Chip-level entries override
        ancestor entries by key (instance name / block name).

        Returns (instances_dict, models_dict).
        """
        instances = {}
        models = {}
        # Walk root-first so chip entries are applied last and win.
        for node, _ in reversed(self._walkInheritsChain(chip, chip_path)):
            for name, entry in (node.get('instances') or {}).items():
                instances[name] = entry
            for name, path in (node.get('models') or {}).items():
                models[name] = path
        # Sort by key so the emitted integration struct order stays stable
        # regardless of where each instance is materialised in the chain.
        instances = dict(sorted(instances.items()))
        models = dict(sorted(models.items()))
        return instances, models
                
prefixTemplate = Template("""// File was generated, do not edit!
#pragma once

#ifndef EXPORT
$incl
#include "hwreg.hpp"
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

def generate_header(model_file, model_name, out_suffix, module_name=None):
    from _namespace import resolve as _resolve_ns
    yaml = YAML(typ='safe')
    chip = yaml.load(Path(model_file))
    fmt  = ChipFormatter()
    namespace = _resolve_ns(model_file)
    if module_name is None:
        # Module names must be valid C++ identifiers; stems like "ESP32-P4"
        # need the hyphen replaced.  Prefix with the namespace when it's a
        # plain identifier, so module names stay unique across vendors.
        stem = Path(model_name + out_suffix).stem.replace('-', '_')
        module_name = (f'{namespace}.{stem}'
                       if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', namespace)
                       else stem)
    header, imports = fmt.createHeader(chip, model_file, namespace, out_suffix, prefixTemplate, postfixTemplate)
    filename = model_name + out_suffix
    print(header, file=open(filename, mode='w'))
    cppm = Path(filename).with_suffix('.cppm')
    print(generate_module(module_name, Path(filename).name, imports), file=open(cppm, mode='w'))

# Script arguments:
#   argv[1] - Model (Name of yaml file)
#   argv[2] - Model name (used for type names)
#   argv[3] - Output file suffix (appended to model name)
#
if __name__ == "__main__":
    generate_header(sys.argv[1], sys.argv[2], sys.argv[3])
