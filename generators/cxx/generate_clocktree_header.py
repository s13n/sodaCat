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
            return "nullptr"
        return f"register_fields[{register_field_id(field)}]"

    # Map signal name to generator
    signal_generators = {}

    for gen in generators:
        signal_generators[gen['output']] = ('generators', gen)
    for pll in plls:
        signal_generators[pll['output']] = ('plls', pll)
    for gate in gates:
        signal_generators[gate['output']] = ('gates', gate)
    for div in dividers:
        signal_generators[div['output']] = ('dividers', div)
    for mux in muxes:
        signal_generators[mux['output']] = ('muxes', mux)

    # Header file
    hpp_lines = [
        '#pragma once',
        '#include "clocktree.hpp"',
        '',
        'enum class Signals {'
    ]
    for s in signals:
        hpp_lines.append(f"    {signal_enum_map[s['name']]},")
    hpp_lines.append("};")
    hpp_lines.append("")
    
    hpp_lines.append("template<> constexpr auto ClockTree<Signals>::register_fields = std::to_array<RegisterField const *>({")
    for f in field_list:
        reg = f.get("reg", "")
        field = f.get("field", "")
        offset = f.get("offset", 0)
        hpp_lines.append(f'  {{ "{reg}", "{field}", {offset} }},')
    hpp_lines.append("});\n")

    hpp_lines.append("template<> constexpr auto ClockTree<Signals>::generators = std::to_array<Generator>({")
    for gen in generators:
        ctrl = gen.get("control")
        values = ctrl.get("values", []) if ctrl else []
        values_str = "{ " + ", ".join(str(v) for v in values) + " }"
        hpp_lines.append(
            f'  {{ "{gen["name"]}", Signals::{signal_enum_map[gen["output"]]}, {emit_field_ref(ctrl)}, {values_str}, "{gen.get("description", "")}" }},'
        )
    hpp_lines.append("});\n")

    hpp_lines.append("template<> constexpr auto ClockTree<Signals>::plls = std::to_array<Pll>({")
    for p in plls:
        hpp_lines.append(
            f'  {{ "{p["name"]}", Signals::{signal_enum_map[p["input"]]}, Signals::{signal_enum_map[p["output"]]}, '
            f'{emit_field_ref(p.get("feedback_integer"))}, '
            f'{emit_field_ref(p.get("feedback_fraction"))}, '
            f'{emit_field_ref(p.get("post_divider"))} }},'
        )
    hpp_lines.append("});\n")

    hpp_lines.append("template<> constexpr auto ClockTree<Signals>::gates = std::to_array<Gate>({")
    for g in gates:
        hpp_lines.append(
            f'  {{ "{g["name"]}", Signals::{signal_enum_map[g["input"]]}, Signals::{signal_enum_map[g["output"]]}, {emit_field_ref(g.get("control"))} }},'
        )
    hpp_lines.append("};\n")

    hpp_lines.append("template<> constexpr auto ClockTree<Signals>::dividers = std::to_array<Divider>({")
    for d in dividers:
        hpp_lines.append(
            f'  {{ "{d["name"]}", Signals::{signal_enum_map[d["input"]]}, Signals::{signal_enum_map[d["output"]]}, {d.get("value", 0)}, '
            f'{emit_field_ref(d.get("factor"))}, {emit_field_ref(d.get("denominator"))} }},'
        )
    hpp_lines.append("};\n")

    hpp_lines.append("template<> constexpr auto ClockTree<Signals>::muxes = std::to_array<Mux>({")
    for m in muxes:
        input_list = []
        for i in m['inputs']:
            if i in signal_enum_map:
                input_list.append(f'Signals::{signal_enum_map[i]}')
            elif i in ['', None]:
                input_list.append('Signals::_')
            else:
                raise KeyError(f"Unknown signal name in mux inputs: {i}")
        inputs_str = "{ " + ", ".join(input_list) + " }"
        hpp_lines.append(
            f'  {{ "{m["name"]}", Signals::{signal_enum_map[m["output"]]}, {inputs_str}, {emit_field_ref(m.get("control"))} }},'
        )
    hpp_lines.append("};\n")

    hpp_lines.append("template<> constexpr auto ClockTree<Signals>::signals = std::to_array<Signal>({")
    for s in signals:
        name = s["name"]
        gen_type, gen_obj = signal_generators.get(name, ("Source", None))
        gen_list = locals().get(gen_type, [])
        gen_ref = f"&{gen_type}[{gen_list.index(gen_obj)}]" if gen_obj else "{}"
        hpp_lines.append(
            f'  {{ "{name}", {s.get("min", "std::nullopt")}, {s.get("max", "std::nullopt")}, {s.get("nominal", "std::nullopt")}, "{s.get("description", "")}", {gen_ref} }},'
        )
    hpp_lines.append("});\n")

    Path(hpp_path).write_text("\n".join(hpp_lines))


if __name__ == "__main__":
    generate_header("models/NXP/LPC8/LPC865_clocks.yaml", "LPC865_clocks.hpp")
