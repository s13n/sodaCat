import sys
import yaml
from pathlib import Path

def generate_header(yaml_path, hpp_path):
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

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

    field_map = {}
    field_list = []

    def register_field_id(field):
        key = (field.get("reg", ""), field.get("field", ""), field.get("offset", 0))
        if key not in field_map:
            field_map[key] = len(field_list)
            field_list.append(field)
        return field_map[key]

    def emit_field_ref(field):
        if not field:
            return "{}"
        return f"{register_field_id(field)}"

    # Map signal name to generator
    signal_generators = {}

    for gen in generators:
        signal_generators[gen['output']] = (gen['name'], 'generators', gen)
    for pll in plls:
        signal_generators[pll['output']] = (pll['name'], 'plls', pll)
    for gate in gates:
        signal_generators[gate['output']] = (gate['name'], 'gates', gate)
    for div in dividers:
        signal_generators[div['output']] = (div['name'], 'dividers', div)
    for mux in muxes:
        signal_generators[mux['output']] = (mux['name'], 'muxes', mux)

    sigIndexType = 'uint8_t' if len(signals) < 255 else 'uint16_t'
    eleIndexType = 'uint8_t' if len(signal_generators) < 255 else 'uint16_t'
    fldIndexType = 'uint8_t' if len(field_list) < 255 else 'uint16_t'
    
    # Header file
    hpp_lines = [
        '#pragma once',
        '#include "clocktree.hpp"',
        '',
        'namespace clocktree {',
        'struct Indices {',
        f'    enum class Signals : {sigIndexType} {{'
    ]
    for s in signals:
        hpp_lines.append(f"        {signal_enum_map[s['name']]},  //!< {s.get('description', '')}")
    hpp_lines.append("    };")
    hpp_lines.append("")
    hpp_lines.append(f"    enum class Elements : {eleIndexType} {{")
    hpp_lines.append("        _,  //!< none")
    for e in generators:
        hpp_lines.append(f"        {e['name']},  //!< {e.get('description', '')}")
    for e in plls:
        hpp_lines.append(f"        {e['name']},  //!< {e.get('description', '')}")
    for e in gates:
        hpp_lines.append(f"        {e['name']},  //!< {e.get('description', '')}")
    for e in dividers:
        hpp_lines.append(f"        {e['name']},  //!< {e.get('description', '')}")
    for e in muxes:
        hpp_lines.append(f"        {e['name']},  //!< {e.get('description', '')}")
    hpp_lines.append("    };")
    hpp_lines.append("")
    hpp_lines.append(f"    enum class RegFields : {fldIndexType} {{")
    for f in field_list:
        hpp_lines.append(f"        {f['name']},  //!< {f.get('description', '')}")
    hpp_lines.append("    };")
    hpp_lines.append("};")
    hpp_lines.append("")
    hpp_lines.append("struct Clocks {")
    hpp_lines.append("    using Ix = Indices;")
    hpp_lines.append("    using Sig = Ix::Signals;")
    hpp_lines.append("    using Ele = Ix::Elements;")
    hpp_lines.append("    using Fld = Ix::RegFields;")
    hpp_lines.append("")
    
    hpp_lines.append(f"    static constexpr std::array<RegisterField const *, {len(field_list)+1}> register_fields = {{")
    hpp_lines.append("        {},")
    for f in field_list:
        reg = f.get("reg", "")
        field = f.get("field", "")
        offset = f.get("offset", 0)
        hpp_lines.append(f'        {{ "{reg}", "{field}", {offset} }},')
    hpp_lines.append("    };\n")

    hpp_lines.append("    static constexpr auto generators = std::to_array<Generator<Indices>>({")
    for gen in generators:
        ctrl = gen.get("control")
        values = ctrl.get("values", []) if ctrl else []
        values_str = "{ " + ", ".join(str(v) for v in values) + " }"
        hpp_lines.append(
            f'        {{ Sig::{signal_enum_map[gen["output"]]}, {emit_field_ref(ctrl)}, {values_str} }},  // {gen['name']}'
        )
    hpp_lines.append("    });\n")

    hpp_lines.append("    static constexpr auto plls = std::to_array<Pll<Indices>>({")
    for p in plls:
        hpp_lines.append(
            f'        {{ Sig::{signal_enum_map[p["input"]]}, Sig::{signal_enum_map[p["output"]]}, '
            f'{emit_field_ref(p.get("feedback_integer"))}, '
            f'{emit_field_ref(p.get("feedback_fraction"))}, '
            f'{emit_field_ref(p.get("post_divider"))} }},  // {p['name']}'
        )
    hpp_lines.append("    });\n")

    hpp_lines.append("    static constexpr auto gates = std::to_array<Gate<Indices>>({")
    for g in gates:
        hpp_lines.append(
            f'        {{ Sig::{signal_enum_map[g["input"]]}, Sig::{signal_enum_map[g["output"]]}, {emit_field_ref(g.get("control"))} }},  // {g['name']}'
        )
    hpp_lines.append("    });\n")

    hpp_lines.append("    static constexpr auto dividers = std::to_array<Divider<Indices>>({")
    for d in dividers:
        hpp_lines.append(
            f'        {{ Sig::{signal_enum_map[d["input"]]}, Sig::{signal_enum_map[d["output"]]}, {d.get("value", 0)}, '
            f'{emit_field_ref(d.get("factor"))}, {emit_field_ref(d.get("denominator"))} }},  // {d['name']}'
        )
    hpp_lines.append("    });\n")

    hpp_lines.append("    static constexpr auto muxes = std::to_array<Mux<Indices>>({")
    for m in muxes:
        input_list = []
        for i in m['inputs']:
            if i in signal_enum_map:
                input_list.append(f'Sig::{signal_enum_map[i]}')
            elif i in ['', None]:
                input_list.append('Sig::_')
            else:
                raise KeyError(f"Unknown signal name in mux inputs: {i}")
        inputs_str = "{ " + ", ".join(input_list) + " }"
        hpp_lines.append(
            f'        {{ Sig::{signal_enum_map[m["output"]]}, {inputs_str}, {emit_field_ref(m.get("control"))} }},  // {m['name']}'
        )
    hpp_lines.append("    });\n")

    hpp_lines.append("    static constexpr auto signals = std::to_array<Signal<Indices>>({")
    for s in signals:
        name = s["name"]
        gen_name, gen_type, gen_obj = signal_generators.get(name, ("_", "Source", None))
        gen_list = locals().get(gen_type, [])
        gen_ref = f"&{gen_type}[{gen_list.index(gen_obj)}]" if gen_obj else "{}"
        hpp_lines.append(
            f'        {{ Ele::{gen_name}, {s.get("min", "0")}, {s.get("max", "0")}, {s.get("nominal", "0")} }},  // {name}'
        )
    hpp_lines.append("    });")
    
    hpp_lines.append("};")
    hpp_lines.append("} // namespace\n")

    Path(hpp_path).write_text("\n".join(hpp_lines))


if __name__ == "__main__":
    generate_header(sys.argv[1], sys.argv[2])
