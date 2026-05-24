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
        self.instanceInclTemplate = Template(keywords.get('instanceIncl', '\n#   include "$ns/$model$incl_suffix"'))
        self.instanceDeclTemplate = Template(keywords.get('instanceDecl', """
/** Integration parameters for $name */
EXPORT constexpr struct $ns::${model}::Intgr i_$name = {$params$init};
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
        """Return (param_names, param_defaults, input_names) declared by
        the block model.

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
        if model_name in self._block_orders:
            return self._block_orders[model_name]
        relpath = models_map.get(model_name, model_name)
        block_path = self._resolve_block_path(chip_dir, relpath)
        if block_path is None:
            result = (None, {}, None)
        else:
            block = YAML(typ='safe').load(block_path)
            params_decl = block.get('params', [])
            inputs_decl = block.get('inputs')
            result = (
                [p['name'] for p in params_decl],
                {p['name']: p['default']
                 for p in params_decl if 'default' in p},
                ([i['name'] for i in inputs_decl]
                 if inputs_decl is not None else None),
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

    def _collectConnections(self, chip, chip_path):
        """Walk the merged instance set (chip + inherits chain) and collect:

        - `enumerators` — ordered list of (instance, signal) pairs naming
          every Connection enumerator the chip needs.  Instance-major,
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
          The chip generator uses this to size the per-target array to
          match the block's full Input enum length rather than max(port)+1
          (so the C++ table is safely indexable by any Input enumerator
          the block declares — slots the chip doesn't wire become NONE),
          and to annotate each slot's initializer with the matching
          Input enum value name as a line-end comment.

        Malformed destinations (no dot, unresolved name) are silently
        skipped; the validator in tools/validate_chip_connections.py is the
        place that flags those.
        """
        instances, models_map = self._collectInstances(chip, chip_path)
        chip_dir = Path(chip_path).parent
        enumerators = []
        seen = set()
        target_routes = {}
        target_input_names = {}
        for inst_name, inst in instances.items():
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
                        target_routes.setdefault(prefix, []).append(
                            (enum_name, port))
                        continue
                    except ValueError:
                        pass
                    # Non-integer tail: must be a named input on a block
                    # that declares `inputs:`.  Only the 2-part form
                    # (instance.input_name) qualifies — 3-part forms
                    # (instance.subport.<tail>) require integer tails.
                    if '.' in prefix:
                        continue
                    target_inst = prefix
                    inst_entry = instances.get(target_inst)
                    if inst_entry is None:
                        continue
                    target_model = inst_entry.get('model')
                    if not target_model:
                        continue
                    _, _, input_names = self._loadBlockOrder(
                        chip_dir, models_map, target_model)
                    if input_names is None:
                        continue
                    try:
                        port = input_names.index(port_str)
                    except ValueError:
                        continue
                    target_routes.setdefault(prefix, []).append(
                        (enum_name, port))
                    target_input_names[prefix] = input_names
        return enumerators, target_routes, target_input_names

    @staticmethod
    def _tableName(prefix):
        """Map target_prefix → emitted table identifier.

        `c_NVIC`, `c_TIM2_ITR` (once Phase 2 dotted destinations land).
        Case is preserved to match the manufacturer's naming; dots in
        dotted prefixes collapse to underscores.
        """
        return 'c_' + prefix.replace('.', '_')

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
        """
        if not enumerators:
            # Even a chip with zero wired outputs still needs a complete
            # Connection type so its Intgr fields can default-initialise.
            body = '\n\tNONE = 0,\n'
        else:
            lines = ['\tNONE = 0,']
            for i, name in enumerate(enumerators, start=1):
                lines.append(f'\t{name} = {i},')
            body = '\n' + '\n'.join(lines) + '\n'
        # `inline` matches hwreg.hpp's opening declaration; without it, GCC/Clang
        # warn about reopening an inline namespace as non-inline.
        return (
            'extern "C++" {\n'
            'inline namespace hwreg {\n'
            'enum class Connection : uint16_t {'
            f'{body}'
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
        which is what `resolve()`'s binary search expects.
        """
        if not target_routes:
            return ''
        enum_index = {name: i for i, name in enumerate(enumerators)}
        chunks = []
        # Stable target ordering by prefix for reproducible output.
        for prefix in sorted(target_routes):
            routes = target_routes[prefix]
            ports = [p for _, p in routes]
            shape = ('pair_list'
                     if len(ports) != len(set(ports))
                     else 'array')
            table_id = self._tableName(prefix)
            if shape == 'pair_list':
                # Deduplicate identical (conn, port) rows, then sort.
                rows = sorted(set(routes), key=lambda r: enum_index[r[0]])
                body = ''.join(
                    f'\n\t{{Connection::{n}, {p}}},'
                    for n, p in rows)
                chunks.append(
                    f'\nEXPORT constexpr RouteEntry {table_id}[] = {{{body}\n}};\n'
                )
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
                    conn = n if n else 'NONE'
                    if input_names is not None and i < len(input_names):
                        body_lines.append(
                            f'\tConnection::{conn},\t// {input_names[i]}')
                    else:
                        body_lines.append(f'\tConnection::{conn},')
                body = '\n' + '\n'.join(body_lines)
                chunks.append(
                    f'\nEXPORT constexpr Connection {table_id}[{size}] = {{{body}\n}};\n'
                )
        return ''.join(chunks)

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
            param_order, param_defaults, _ = self._loadBlockOrder(
                chip_dir, models_map, m)
            params = self.createParameters(k, i, param_order, param_defaults)
            init = '\n\t.registers = %#Xu\n' % i['baseAddress']
            decl += self.instanceDeclTemplate.substitute(i, name=k, ns=ns, params=params, init=init)
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
        enumerators, target_routes, target_input_names = self._collectConnections(chip, chip_path)
        conn_enum = self.emitConnectionEnum(enumerators)
        target_tables = self.emitTargetTables(enumerators, target_routes, target_input_names)
        header = (prefix.substitute(chip, ns=namespace, incl=incl,
                                    interruptCount=interruptCount,
                                    conn_enum=conn_enum)
                  + target_tables
                  + decl
                  + postfix.substitute(ns=namespace))
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

$conn_enum

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
    """Generate a .cppm module wrapper for a chip header.

    The chip header itself emits the Connection enum inside an
    `extern "C++"` block, which pins its attachment to the global
    module even when the .hpp is included inside the module's purview.
    That keeps the chip module's Connection identical to the type the
    peripheral headers reference, without needing a duplicate emission
    in the global module fragment here.
    """
    imp_lines = ''.join(f'import {i};\n' for i in imports)
    return moduleTemplate.substitute(
        mod=mod, header=header, imports=imp_lines)

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
    header, imports = fmt.createHeader(
        chip, model_file, namespace, out_suffix, prefixTemplate, postfixTemplate)
    filename = model_name + out_suffix
    print(header, file=open(filename, mode='w'))
    cppm = Path(filename).with_suffix('.cppm')
    print(generate_module(module_name, Path(filename).name, imports),
          file=open(cppm, mode='w'))

# Script arguments:
#   argv[1] - Model (Name of yaml file)
#   argv[2] - Model name (used for type names)
#   argv[3] - Output file suffix (appended to model name)
#
if __name__ == "__main__":
    generate_header(sys.argv[1], sys.argv[2], sys.argv[3])
