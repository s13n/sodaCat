"""Clock tree header generator — flyweight architecture.

Generates a C++ header with compact descriptor tables for each clock tree
element type. Register access is encoded as data (byte offset + bit position
+ bit width) rather than generated lambdas.

Usage: called from generate_header.py when the model has a 'signals' key.
"""

from ruamel.yaml import YAML
from pathlib import Path
import sys


# ---------------------------------------------------------------------------
# Peripheral model cache — loads register YAML models to resolve offsets
# ---------------------------------------------------------------------------

_periph_cache = {}   # instance_name -> { 'base': int, 'regs': {reg_name: {offset, fields: {name: {bitOffset, bitWidth}}}} }

def find_model_file(name, start_dir):
    """Find a YAML model file by name, searching start_dir and ancestors."""
    d = Path(start_dir)
    while d != d.parent:
        candidate = d / f"{name}.yaml"
        if candidate.exists():
            return candidate
        d = d.parent
    raise FileNotFoundError(f"Cannot find model file {name}.yaml starting from {start_dir}")


def _collect_registers(reg_list, base_offset, regs):
    """Recursively collect registers, handling clusters (dim/dimIncrement)."""
    for reg in reg_list:
        name = reg['name']
        offset = reg['addressOffset'] + base_offset
        # Check if this is a cluster (has sub-registers)
        sub_regs = reg.get('registers')
        dim = reg.get('dim', 1)
        dim_inc = reg.get('dimIncrement', 0)
        if sub_regs:
            # This is a register cluster — expand each dimension instance
            for i in range(dim):
                cluster_name = name.replace('%s', str(i))
                cluster_offset = offset + i * dim_inc
                _collect_registers(sub_regs, cluster_offset, regs)
                # Also register sub-regs with cluster prefix
                for sr in sub_regs:
                    prefixed = f"{cluster_name}.{sr['name']}"
                    sr_offset = cluster_offset + sr['addressOffset']
                    fields = {}
                    for f in sr.get('fields', []):
                        fields[f['name']] = {
                            'bitOffset': f['bitOffset'],
                            'bitWidth': f.get('bitWidth', 1),
                        }
                    regs[prefixed] = {'addressOffset': sr_offset, 'fields': fields}
        else:
            # Plain register, possibly with dim
            fields = {}
            for f in reg.get('fields', []):
                fields[f['name']] = {
                    'bitOffset': f['bitOffset'],
                    'bitWidth': f.get('bitWidth', 1),
                }
            if dim > 1:
                for i in range(dim):
                    rname = name.replace('%s', str(i))
                    regs[rname] = {'addressOffset': offset + i * dim_inc, 'fields': fields}
            else:
                regs[name] = {'addressOffset': offset, 'fields': fields}


def load_peripheral_model(instance, model_dir):
    """Load a peripheral YAML model and extract register/field layout."""
    if instance in _periph_cache:
        return _periph_cache[instance]
    yaml = YAML(typ='safe')
    path = find_model_file(instance, model_dir)
    data = yaml.load(path)
    regs = {}
    _collect_registers(data.get('registers', []), 0, regs)
    _periph_cache[instance] = {'regs': regs, 'base': None}
    return _periph_cache[instance]


def load_chip_model(model_dir):
    """Find and load the chip model to get peripheral base addresses.
    The chip model has 'instances' key with baseAddress per peripheral."""
    # Search for a YAML file with 'instances' key in model_dir and ancestors
    d = Path(model_dir)
    while d != d.parent:
        for f in d.glob("*.yaml"):
            try:
                yaml = YAML(typ='safe')
                data = yaml.load(f)
                if data and 'instances' in data:
                    return data
            except:
                continue
        d = d.parent
    # Fallback: chip model may live in a subdirectory (e.g. LPC43xx/LPC4330.yaml).
    for f in Path(model_dir).rglob("*.yaml"):
        try:
            yaml = YAML(typ='safe')
            data = yaml.load(f)
            if data and 'instances' in data:
                return data
        except:
            continue
    return None


def resolve_base_addresses(model_dir):
    """Load chip model and populate base addresses in peripheral cache."""
    chip = load_chip_model(model_dir)
    if not chip:
        return
    instances = chip.get('instances', {})
    for name, info in instances.items():
        if name in _periph_cache and isinstance(info, dict):
            _periph_cache[name]['base'] = info.get('baseAddress', 0)


def get_bit_addr(instance, reg_name, field_name, model_dir):
    """Return (word_addr, bit, width) for a register field."""
    periph = load_peripheral_model(instance, model_dir)
    reg = periph['regs'].get(reg_name)
    if reg is None:
        raise KeyError(f"Register {reg_name} not found in {instance}")
    field = reg['fields'].get(field_name)
    if field is None:
        raise KeyError(f"Field {field_name} not found in {instance}.{reg_name}")
    base = periph.get('base')
    if base is None:
        raise ValueError(f"Base address not found for {instance}")
    byte_addr = base + reg['addressOffset']
    # Word offset relative to Cortex-M peripheral base 0x40000000
    word_offset = (byte_addr - 0x40000000) >> 2
    return word_offset, field['bitOffset'], field['bitWidth']


# ---------------------------------------------------------------------------
# Signal/element tracking
# ---------------------------------------------------------------------------

elements = {}  # signal_name -> (elem_name, elem_type, elem_obj)
signal_enum_map = {}
signal_index = {}  # signal_name -> integer index


def sig_id(name):
    """Return the integer signal index for a signal name."""
    return signal_index.get(name, 0)


# ---------------------------------------------------------------------------
# Value table pool — shared across all dividers
# ---------------------------------------------------------------------------

value_table_pool = []      # flat list of uint32_t values
value_table_map = {}       # tuple(values) -> (offset, size)


def intern_value_table(values):
    """Add a value table to the pool (deduplicating) and return (offset, size)."""
    key = tuple(values)
    if key in value_table_map:
        return value_table_map[key]
    offset = len(value_table_pool)
    value_table_pool.extend(values)
    value_table_map[key] = (offset, len(values))
    return (offset, len(values))


# ---------------------------------------------------------------------------
# Input pool — flat array of signal IDs for element inputs
# ---------------------------------------------------------------------------

input_pool = []  # flat list of uint8_t signal IDs


def add_inputs(*signal_names):
    """Add input signal IDs to the pool, return the start offset."""
    offset = len(input_pool)
    for name in signal_names:
        input_pool.append(sig_id(name))
    return offset


# ---------------------------------------------------------------------------
# State slots
# ---------------------------------------------------------------------------

state_slots = {}  # state_name -> slot index
state_defaults = {}


def get_state_slot(name, default=0):
    if name not in state_slots:
        state_slots[name] = len(state_slots)
        state_defaults[name] = default
    return state_slots[name]


# ---------------------------------------------------------------------------
# Descriptor builders — return (type_name, descriptor_string)
# ---------------------------------------------------------------------------

def make_bit_addr(instance, reg, field, model_dir):
    """Format a BitAddr initializer."""
    w, b, _ = get_bit_addr(instance, reg, field, model_dir)
    return f"{{{w}, {b}}}"


def make_field_addr(instance, reg, field, model_dir):
    """Format a FieldAddr initializer and return (string, width)."""
    w, b, width = get_bit_addr(instance, reg, field, model_dir)
    return f"{{{w}, {b}, {width}}}", width


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


def build_generator(gen, instance, model_dir, inputs_map):
    """Build a generator descriptor. Returns (type_key, descriptor_string, input_offset).

    inputs_map maps signal name -> input metadata dict (with optional 'nominal').
    """
    ctrl = gen.get('control')
    output = gen.get('output', '')
    nominal = inputs_map.get(output, {}).get('nominal')
    input_offset = add_inputs()  # generators have no inputs

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
    inst = ctrl.get('instance', instance)
    values = ctrl.get('values', [])
    polarity = _polarity_from_values(values)
    addr = (make_bit_addr(inst, reg, field, model_dir)
            if reg and field else '{0, 0}')

    if state:
        # Runtime-configurable frequency (e.g. external crystal).  An
        # accompanying enable bit is optional; without one, use AlwaysOn so
        # the runtime ignores addr.
        slot = get_state_slot(state)
        pol = polarity if (reg and field) else 'clocktree::Polarity::AlwaysOn'
        return ('gen_external', f'{{{addr}, {slot}, {pol}}}', input_offset)

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


def build_gate(gate, instance, model_dir):
    """Build a gate descriptor. Returns (type_key, descriptor_string, input_offset)."""
    inp = gate.get('input', '_')
    input_offset = add_inputs(inp)
    ctrl = gate.get('control')
    if ctrl is None:
        return ('passthrough', '{}', input_offset)
    inst = ctrl.get('instance', instance)
    addr = make_bit_addr(inst, ctrl['reg'], ctrl['field'], model_dir)
    return ('gate', f'{{{addr}}}', input_offset)


def build_divider(div, instance, model_dir):
    """Build a divider descriptor. Returns (type_key, descriptor_string, input_offset)."""
    inp = div['input']
    input_offset = add_inputs(inp)

    factor = div.get('factor')
    fixed_value = div.get('value')

    if factor is None and fixed_value:
        # Fixed divider
        return ('fixed_div', f'{{{fixed_value}}}', input_offset)

    if factor is None:
        # No factor, no fixed value — passthrough (divide by 1)
        return ('fixed_div', '{1}', input_offset)

    inst = factor.get('instance', instance)
    reg = factor['reg']
    field = factor['field']
    values = factor.get('values')
    value_range = factor.get('value_range')

    if values:
        # Table-based divider
        tbl_offset, tbl_size = intern_value_table(values)
        fa, width = make_field_addr(inst, reg, field, model_dir)
        return ('table_div', f'{{{fa}, {tbl_offset}, {tbl_size}}}', input_offset)
    elif value_range:
        # Linear divider: divisor = raw + offset
        offset = value_range.get('offset', 0)
        fa, width = make_field_addr(inst, reg, field, model_dir)
        return ('linear_div', f'{{{fa}, {offset}}}', input_offset)
    else:
        # Raw field value as divisor (offset=0)
        fa, width = make_field_addr(inst, reg, field, model_dir)
        return ('linear_div', f'{{{fa}, 0}}', input_offset)


def build_mux(mux, instance, model_dir):
    """Build a mux descriptor. Returns (type_key, descriptor_string, input_offset)."""
    inputs = mux['inputs']
    # Normalize empty inputs to '_'
    normalized = [i if i else '_' for i in inputs]
    input_offset = add_inputs(*normalized)

    ctrl = mux.get('control')
    inst = ctrl.get('instance', instance)
    fa, width = make_field_addr(inst, ctrl['reg'], ctrl['field'], model_dir)
    return ('mux', f'{{{fa}, {len(inputs)}}}', input_offset)


def build_pll(pll, instance, model_dir):
    """Build a PLL descriptor. Returns (type_key, descriptor_string, input_offset)."""
    inp = pll['input']
    input_offset = add_inputs(inp)

    def make_pll_field(field_data, default_offset=0):
        if field_data is None:
            return '{0, 0, 0}', 0, default_offset
        inst = field_data.get('instance', instance)
        fa_str, width = make_field_addr(inst, field_data['reg'], field_data['field'], model_dir)
        vr = field_data.get('value_range')
        offset = vr.get('offset', 0) if vr else default_offset
        frac_max = vr.get('max', 0) if vr else 0
        return fa_str, frac_max, offset

    fb_int_str, _, fb_int_offset = make_pll_field(pll.get('feedback_integer'), 1)
    fb_frac_str, frac_max, _ = make_pll_field(pll.get('feedback_fraction'), 0)
    post_div_str, _, post_div_offset = make_pll_field(pll.get('post_divider'), 1)

    # Determine fractional bits from max value
    frac_bits = 0
    if pll.get('feedback_fraction'):
        frac_max_val = frac_max
        if frac_max_val > 0:
            frac_bits = frac_max_val.bit_length()

    return ('pll', f'{{{fb_int_str}, {fb_int_offset}, {fb_frac_str}, {frac_bits}, {post_div_str}, {post_div_offset}}}', input_offset)


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

# Type registry: type_key -> (cpp_desc_type, cpp_freq_fn, list_of_descriptors)
type_registry = {}
# signal_entries: list of (type_key, desc_index, input_offset) indexed by signal index
signal_entries = []


def register_type(key, cpp_type, cpp_fn):
    if key not in type_registry:
        type_registry[key] = (cpp_type, cpp_fn, [])


def add_element(output_signal, type_key, desc_str, input_offset):
    """Add an element: appends to type's descriptor list, records signal mapping."""
    descs = type_registry[type_key][2]
    desc_index = len(descs)
    descs.append(desc_str)
    elements[output_signal] = (type_key, desc_index, input_offset)


# Register all standard types
def init_types():
    register_type('gate',         'clocktree::GateDesc',        'clocktree::gate_freq')
    register_type('gate_inv',     'clocktree::GateInvDesc',     'clocktree::gate_inv_freq')
    register_type('passthrough',  'uint8_t',                    'clocktree::passthrough_freq')
    register_type('gen_fixed',    'clocktree::GenFixedDesc',    'clocktree::gen_fixed_freq')
    register_type('gen_external', 'clocktree::GenExternalDesc', 'clocktree::gen_external_freq')
    register_type('table_div',    'clocktree::TableDivDesc',    'clocktree::table_div_freq')
    register_type('linear_div',   'clocktree::LinearDivDesc',   'clocktree::linear_div_freq')
    register_type('fixed_div',    'clocktree::FixedDivDesc',    'clocktree::fixed_div_freq')
    register_type('mux',          'clocktree::MuxDesc',         'clocktree::mux_freq')
    register_type('pll',          'clocktree::PllDesc',         'clocktree::pll_freq')


def generate_header(yaml_path, namespace, hpp_path):
    yaml = YAML(typ='safe')
    data = yaml.load(Path(yaml_path))
    model_dir = str(Path(yaml_path).parent)

    instance = data.get('instance', '')
    signals = data.get('signals', [])
    generators = data.get('generators', [])
    plls = data.get('plls', [])
    gates = data.get('gates', [])
    dividers = data.get('dividers', [])
    muxes = data.get('muxes', [])

    # Insert empty signal at index 0
    signals.insert(0, {'name': '_', 'description': 'Empty signal'})

    # Build signal index map
    global signal_enum_map, signal_index
    for i, s in enumerate(signals):
        name = s['name']
        signal_index[name] = i
        signal_enum_map[name] = '_' if name == '_' else name

    # Load peripheral models referenced by the clock tree
    instances_used = {instance}
    for section in [generators, plls, gates, dividers, muxes]:
        for elem in section:
            for key in ['control', 'factor', 'denominator', 'feedback_integer', 'feedback_fraction', 'post_divider']:
                field = elem.get(key)
                if field and 'instance' in field:
                    instances_used.add(field['instance'])
    for inst in instances_used:
        if inst:
            load_peripheral_model(inst, model_dir)
    resolve_base_addresses(model_dir)

    # Initialize type registry
    init_types()

    # Build all elements
    inputs_map = {s['name']: s for s in signals}
    for gen in generators:
        tk, desc, ioff = build_generator(gen, instance, model_dir, inputs_map)
        add_element(gen['output'], tk, desc, ioff)

    for pll in plls:
        tk, desc, ioff = build_pll(pll, instance, model_dir)
        add_element(pll['output'], tk, desc, ioff)

    for gate in gates:
        tk, desc, ioff = build_gate(gate, instance, model_dir)
        add_element(gate['output'], tk, desc, ioff)

    for div in dividers:
        tk, desc, ioff = build_divider(div, instance, model_dir)
        add_element(div['output'], tk, desc, ioff)

    for mux in muxes:
        tk, desc, ioff = build_mux(mux, instance, model_dir)
        add_element(mux['output'], tk, desc, ioff)

    # --- Assign type indices (skip types with no descriptors) ---
    type_index = {}  # type_key -> 1-based index
    active_types = []
    idx = 1
    for key, (cpp_type, cpp_fn, descs) in type_registry.items():
        if descs:
            type_index[key] = idx
            active_types.append(key)
            idx += 1

    # --- Build signal table ---
    signal_lines = []
    for i, s in enumerate(signals):
        name = s['name']
        if name in elements:
            tk, di, ioff = elements[name]
            ti = type_index[tk]
            signal_lines.append(f'        {{{ti}, {di}, {ioff}}},  // {name}')
        else:
            signal_lines.append(f'        {{0, 0, 0}},  // {name}')

    # --- Format Signals enum ---
    sig_typ = 'uint8_t' if len(signals) <= 256 else 'uint16_t'
    enum_lines = []
    for s in signals:
        name = signal_enum_map[s['name']]
        enum_lines.append(f"        {name},  //!< {s.get('description', '')}")

    # --- Format descriptor arrays ---
    desc_array_lines = []
    desc_array_names = {}
    for key in active_types:
        cpp_type, cpp_fn, descs = type_registry[key]
        arr_name = f'{key}_descs'
        desc_array_names[key] = arr_name
        if cpp_type == 'uint8_t':
            # Passthrough has no real descriptor; use a single dummy byte
            desc_array_lines.append(f'    static constexpr uint8_t {arr_name}[] = {{0}};')
        else:
            desc_array_lines.append(f'    static constexpr {cpp_type} {arr_name}[] = {{')
            for d in descs:
                desc_array_lines.append(f'        {d},')
            desc_array_lines.append('    };')

    # --- Format type table ---
    type_table_lines = ['    static constexpr clocktree::BlockType type_table[] = {']
    type_table_lines.append('        {},  // index 0 = undriven')
    for key in active_types:
        cpp_type, cpp_fn, descs = type_registry[key]
        arr_name = desc_array_names[key]
        desc_size = f'sizeof({cpp_type})' if cpp_type != 'uint8_t' else '1'
        type_table_lines.append(f'        {{{cpp_fn}, {arr_name}, {desc_size}}},  // {key}')
    type_table_lines.append('    };')

    # --- Format input pool ---
    input_pool_str = ', '.join(str(v) for v in input_pool)

    # --- Format value tables ---
    value_tables_str = ', '.join(str(v) for v in value_table_pool)

    # --- Format state ---
    state_names = list(state_slots.keys())
    state_count = len(state_names)
    state_defaults_str = ', '.join(str(state_defaults[n]) for n in state_names)

    # --- Assemble the header ---
    txt = []
    txt.append("// generated header file, please don't edit.")
    txt.append('#pragma once')
    txt.append('#include "clocktree.hpp"')
    txt.append('')
    txt.append(f'namespace {namespace} {{')
    txt.append('')

    # Signals enum
    txt.append(f'enum class Signals : {sig_typ} {{')
    txt.extend(enum_lines)
    txt.append('};')
    txt.append('')

    # Clocks struct
    txt.append('struct Clocks : clocktree::ClockTreeBase {')
    txt.append(f'    using S = Signals;')
    txt.append('')

    # State struct
    if state_names:
        txt.append('    struct State {')
        for name in state_names:
            txt.append(f'        uint32_t {name} = {state_defaults[name]};')
        txt.append('    };')
        txt.append('')

    # Descriptor arrays
    txt.extend(desc_array_lines)
    txt.append('')

    # Type table
    txt.extend(type_table_lines)
    txt.append('')

    # Input pool
    txt.append(f'    static constexpr uint8_t input_pool_data[] = {{{input_pool_str}}};')
    txt.append('')

    # Value tables
    if value_table_pool:
        txt.append(f'    static constexpr uint32_t value_tables_data[] = {{{value_tables_str}}};')
    else:
        txt.append(f'    static constexpr uint32_t value_tables_data[] = {{0}};')
    txt.append('')

    # Signal table
    txt.append(f'    static constexpr clocktree::Signal signal_table[] = {{')
    txt.extend(signal_lines)
    txt.append('    };')
    txt.append('')

    # Mutable state
    txt.append(f'    uint32_t state_data[{max(state_count, 1)}] = {{{state_defaults_str}}};')
    txt.append('')

    # Constructor wires up base class pointers
    if state_names:
        txt.append('    Clocks(State st) {')
        for i, name in enumerate(state_names):
            txt.append(f'        state_data[{i}] = st.{name};')
    else:
        txt.append('    Clocks() {')
    txt.append('        signals = signal_table;')
    txt.append(f'        signal_count = sizeof(signal_table) / sizeof(signal_table[0]);')
    txt.append('        types = type_table;')
    txt.append('        input_pool = input_pool_data;')
    txt.append('        value_tables = value_tables_data;')
    txt.append('        state = state_data;')
    txt.append('    }')

    txt.append('};')
    txt.append('')
    txt.append('} // namespace')
    txt.append('')

    Path(hpp_path).write_text('\n'.join(txt))

    # Generate .cppm module wrapper
    stem = Path(hpp_path).stem
    cppm_path = Path(hpp_path).with_suffix('.cppm')
    cppm = [
        f'module;',
        f'#include "{Path(hpp_path).name}"',
        f'export module {stem};',
    ]
    cppm_path.write_text('\n'.join(cppm))


if __name__ == "__main__":
    generate_header(sys.argv[1], sys.argv[2], sys.argv[3]+sys.argv[4])
