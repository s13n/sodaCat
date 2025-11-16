import sys
import yaml
from pathlib import Path


field_map = {}
field_list = []
states = {}
elements = {}

def register_field_id(field, instance):
    key = (field.get("instance", instance), field.get("reg", ""), field.get("field", field.get("state", "")))
    if key not in field_map:
        field_map[key] = len(field_list)+1
        field_list.append(field)
    return field_map[key]

def emit_field_ref(field, instance):
    if not field:
        return "{}"
    return f"R({register_field_id(field, instance)})"

def collectElements(array, kind):
    for elem in array:
        last = elem['name']
        elements[elem['output']] = (last, kind, elem)
    return last

def formatSignalsEnum(signals, enum_map):
    typ = 'uint8_t' if len(signals) < 255 else 'uint16_t'
    txt = [f'    enum class Signals : {typ} {{']
    for s in signals:
        txt.append(f"        {enum_map[s['name']]},  //!< {s.get('description', '')}")
    txt.append("    };")
    return "\n".join(txt)
    
def formatEnumEntries(entries):
    txt = []
    for e in entries:
        txt.append(f"        {e['name']},  //!< {e.get('description', '')}")
    return "\n".join(txt)

def formatElementsEnum(generators, plls, gates, dividers, muxes):
    typ = 'uint8_t' if len(elements) < 255 else 'uint16_t'
    txt = [f"    enum class Elements : {typ} {{"]
    txt.append("        _,  //!< none")
    txt.append(formatEnumEntries(generators))
    txt.append(formatEnumEntries(plls))
    txt.append(formatEnumEntries(gates))
    txt.append(formatEnumEntries(dividers))
    txt.append(formatEnumEntries(muxes))
    txt.append("    };")
    return "\n".join(txt)

def formatRegfieldEnum(entries):
    typ = 'uint8_t' if len(entries) < 255 else 'uint16_t'
    txt = [f"    enum class RegFields : {typ} {{"]
    for f in entries:
        txt.append(f"        {f['name']},  //!< {f.get('description', '')}")
    txt.append("    };")
    return "\n".join(txt)

def formatStructIndices(signals, signal_enum_map, generators, plls, gates, dividers, muxes, field_list):
    # Map signal name to generating element
    last_gen = collectElements(generators, 'generators')
    last_pll = collectElements(plls, 'plls')
    last_gate = collectElements(gates, 'gates')
    last_div = collectElements(dividers, 'dividers')
    last_mux = collectElements(muxes, 'muxes')
    signalsEnum = formatSignalsEnum(signals, signal_enum_map)
    elementsEnum = formatElementsEnum(generators, plls, gates, dividers, muxes)
    regEnums = formatRegfieldEnum(field_list)
    
    txt = ['struct Indices {',
        f'{signalsEnum}',
        '',
        f'{elementsEnum}',
        '',
        f'{regEnums}',
        '',
        f'    static constexpr auto last_gen = Elements::{last_gen};',
        f'    static constexpr auto last_pll = Elements::{last_pll};',
        f'    static constexpr auto last_gate= Elements::{last_gate};',
        f'    static constexpr auto last_div = Elements::{last_div};',
        f'    static constexpr auto last_mux = Elements::{last_mux};'
        '};'
    ]
    return "\n".join(txt)

def formatGenerators(generators, instance, signal_enum_map):
    txt = ["    static constexpr std::array generators = {"]
    for gen in generators:
        ctrl = gen.get("control")
        values = ctrl.get("values", []) if ctrl else []
        values_str = "{ " + ", ".join(str(v) for v in values) + " }"
        sig = signal_enum_map[gen["output"]]
        reg = emit_field_ref(ctrl, instance)
        txt.append(f'        Ge{{ S::{sig}, {reg}, {values_str} }},  // {gen['name']}')
    txt.append("    };")
    return "\n".join(txt)

def formatPlls(plls, instance, signal_enum_map):
    txt = ["    static constexpr std::array plls = {"]
    for p in plls:
        inp = signal_enum_map[p["input"]]
        outp = signal_enum_map[p["output"]]
        fbi = emit_field_ref(p.get("feedback_integer"), instance)
        fbf = emit_field_ref(p.get("feedback_fraction"), instance)
        pdiv = emit_field_ref(p.get("post_divider"), instance)
        txt.append(f'        Pl{{ S::{inp}, S::{outp}, {fbi}, {fbf}, {pdiv} }},  // {p['name']}')
    txt.append("    };")
    return "\n".join(txt)

def formatGates(gates, instance, signal_enum_map):
    txt = ["    static constexpr std::array gates = {"]
    for g in gates:
        inp = signal_enum_map[g["input"]]
        outp = signal_enum_map[g["output"]]
        reg = emit_field_ref(g.get("control"), instance)
        txt.append(f'        Ga{{ S::{inp}, S::{outp}, {reg} }},  // {g['name']}')
    txt.append("    };")
    return "\n".join(txt)

def formatDividers(dividers, instance, signal_enum_map):
    txt = ["    static constexpr std::array dividers = {"]
    for d in dividers:
        inp = signal_enum_map[d["input"]]
        outp = signal_enum_map[d["output"]]
        fac = emit_field_ref(d.get("factor"), instance)
        den = emit_field_ref(d.get("denominator"), instance)
        txt.append(f'        Di{{ S::{inp}, S::{outp}, {d.get("value", 0)}, {fac}, {den} }},  // {d['name']}')
    txt.append("    };")
    return "\n".join(txt)

def formatMuxes(muxes, instance, signal_enum_map):
    txt = ["    static constexpr std::array muxes = {"]
    for m in muxes:
        input_list = []
        for i in m['inputs']:
            if i in signal_enum_map:
                input_list.append(f'S::{signal_enum_map[i]}')
            elif i in ['', None]:
                input_list.append('S::_')
            else:
                raise KeyError(f"Unknown signal name in mux inputs: {i}")
        inputs_str = "{ " + ", ".join(input_list) + " }"
        outp = signal_enum_map[m["output"]]
        reg = emit_field_ref(m.get("control"), instance)
        txt.append(f'        Mu{{ S::{outp}, {inputs_str}, {reg} }},  // {m['name']}')
    txt.append("    };")
    return "\n".join(txt)

def formatFields(field_list, instance):
    txt = ["    static constexpr std::array register_fields = {"]
    txt.append("        Rf{},")
    for f in field_list:
        inst = f.get("instance", instance)
        reg = f.get("reg", "")
        field = f.get("field", "")
        state = f.get("state", "")
        if state:
            states[state] = f.get("default", 0)
            f_get = f'''[](void const *ctx) -> uint32_t {{
                return static_cast<Clocks const*>(ctx)->{state};
            }}'''
            f_set = f'''[](void *ctx, uint32_t val){{
                {f.get("set", "")}
                static_cast<Clocks*>(ctx)->{state} = val;
            }}'''
        else:
            f_get = f'''[](void const *ctx) -> uint32_t {{
                return i_{inst}.registers->{reg}.get().{field};
            }}'''
            f_set = f'''[](void *ctx, uint32_t val){{
                auto reg = i_{inst}.registers->{reg}.get();
                reg.{field} = val;
                i_{inst}.registers->{reg}.set(reg);
            }}'''
        txt.append(f'        Rf{{ {f_get}, {f_set} }},')
    txt.append("    };")
    return "\n".join(txt)
    
def formatSignals(signals):
    txt = ["    static constexpr std::array signals = {"]
    for s in signals:
        name = s["name"]
        gen_name, gen_type, gen_obj = elements.get(name, ("_", "Source", None))
        min = s.get("min", "0")
        max = s.get("max", "0")
        nom = s.get("nominal", "0")
        txt.append(f'        Si{{ E::{gen_name}, {min}, {max}, {nom} }},  // {name}')
    txt.append("    };")
    return "\n".join(txt)
    
def formatStates():
    txt = []
    for state,default in states.items():
        txt.append(f'    uint32_t {state} = {default};')
    return "\n".join(txt)
    
def formatClassClocks(signals, signal_enum_map, generators, plls, gates, dividers, muxes, instance):
    ge = formatGenerators(generators, instance, signal_enum_map)
    pl = formatPlls(plls, instance, signal_enum_map)
    ga = formatGates(gates, instance, signal_enum_map)
    di = formatDividers(dividers, instance, signal_enum_map)
    mu = formatMuxes(muxes, instance, signal_enum_map)
    fi = formatFields(field_list, instance)
    si = formatSignals(signals)
    st = formatStates()
    
    txt = ['class Clocks {',
        f'{st}',
        "",
        "public:",
        "    using Ix = Indices;",
        "    using S = Ix::Signals;",
        "    using E = Ix::Elements;",
        "    using R = Ix::RegFields;",
        "    using Rf = clocktree::RegisterField;",
        "    using Ge = clocktree::Generator<Ix>;",
        "    using Pl = clocktree::Pll<Ix>;",
        "    using Ga = clocktree::Gate<Ix>;",
        "    using Di = clocktree::Divider<Ix>;",
        "    using Mu = clocktree::Mux<Ix>;",
        "    using Si = clocktree::Signal<Ix>;",
        "",
        f'{ge}',
        "",
        f'{pl}',
        "",
        f'{ga}',
        "",
        f'{di}',
        "",
        f'{mu}',
        "",
        f'{fi}',
        "",
        f'{si}',
        "};"
    ]
    return "\n".join(txt)
    
def generate_header(yaml_path, hpp_path, namespace):
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    instance = data.get('instance', '')
    signals = data.get('signals', [])
    generators = data.get('generators', [])
    plls = data.get('plls', [])
    gates = data.get('gates', [])
    dividers = data.get('dividers', [])
    muxes = data.get('muxes', [])

    signals.insert(0, {'name': '', 'description': 'Empty signal'})
    signal_enum_map = {s['name']: ('_' if s['name'] == '' else s['name']) for s in signals}
    enum_count = len(signals)
    enum_type = 'uint8_t' if enum_count <= 256 else 'uint16_t' if enum_count <= 65536 else 'uint32_t'
    
    structIndices = formatStructIndices(signals, signal_enum_map, generators, plls, gates, dividers, muxes, field_list)
    classClocks = formatClassClocks(signals, signal_enum_map, generators, plls, gates, dividers, muxes, instance)
    
    header = [
        '#pragma once',
        '#include "clocktree.hpp"',
        '#include "chip.hpp"',
        '',
        f'namespace {namespace} {{',
        '',
        f'{structIndices}',
        '',
        f'{classClocks}',
        '',
        '} // namespace',
        ''
    ]

    Path(hpp_path).write_text("\n".join(header))


if __name__ == "__main__":
    generate_header(sys.argv[1], sys.argv[2] + '.hpp', sys.argv[3])
