
import yaml
from pathlib import Path

def generate_header(yaml_path, output_path):
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    signals = data.get('signals', [])
    plls = data.get('plls', [])
    gates = data.get('gates', [])
    dividers = data.get('dividers', [])
    muxes = data.get('muxes', [])

    signals.insert(0, {'name': '', 'description': 'Empty signal'})
    signal_enum_map = {s['name']: ('_' if s['name'] == '' else s['name']) for s in signals}

    enum_count = len(signals)
    if enum_count <= 256:
        enum_type = 'uint8_t'
    elif enum_count <= 65536:
        enum_type = 'uint16_t'
    else:
        enum_type = 'uint32_t'

    lines = []
    lines.append('#pragma once')
    lines.append('#include <optional>')
    lines.append('#include <cstdint>')
    lines.append('#include <initializer_list>')
    lines.append('')
    lines.append('class ClockTree {')
    lines.append('  public:')

    lines.append(f'    enum class SignalName : {enum_type} {{')
    for s in signals:
        enum_name = '_' if s['name'] == '' else s['name']
        lines.append(f'        {enum_name},')
    lines.append('    };')
    lines.append('')

    lines.append('    struct Signal {')
    lines.append('        const char* name;')
    lines.append('        std::optional<uint32_t> min_freq;')
    lines.append('        std::optional<uint32_t> max_freq;')
    lines.append('        std::optional<uint32_t> nominal_freq;')
    lines.append('        const char* description;')
    lines.append('    };')
    lines.append('')

    lines.append('    struct PLL {')
    lines.append('        const char* name;')
    lines.append('        SignalName input;')
    lines.append('        SignalName output;')
    lines.append('    };')
    lines.append('')

    lines.append('    struct Gate {')
    lines.append('        const char* name;')
    lines.append('        SignalName input;')
    lines.append('        SignalName output;')
    lines.append('    };')
    lines.append('')

    lines.append('    struct Divider {')
    lines.append('        const char* name;')
    lines.append('        SignalName input;')
    lines.append('        SignalName output;')
    lines.append('        uint32_t divisor;')
    lines.append('    };')
    lines.append('')

    lines.append('    struct Mux {')
    lines.append('        const char* name;')
    lines.append('        SignalName output;')
    lines.append('        std::initializer_list<SignalName> inputs;')
    lines.append('    };')
    lines.append('')

    lines.append('    static constexpr Signal signals[] = {')
    for s in signals:
        lines.append(f'        {{ "{s["name"]}", {s.get("min", "std::nullopt")}, {s.get("max", "std::nullopt")}, {s.get("nominal", "std::nullopt")}, "{s.get("description", "")}" }},')
    lines.append('    };')
    lines.append('')

    lines.append('    static constexpr PLL plls[] = {')
    for p in plls:
        lines.append(f'        {{ "{p["name"]}", SignalName::{signal_enum_map[p["input"]]}, SignalName::{signal_enum_map[p["output"]]} }},')
    lines.append('    };')
    lines.append('')

    lines.append('    static constexpr Gate gates[] = {')
    for g in gates:
        lines.append(f'        {{ "{g["name"]}", SignalName::{signal_enum_map[g["input"]]}, SignalName::{signal_enum_map[g["output"]]} }},')
    lines.append('    };')
    lines.append('')

    lines.append('    static constexpr Divider dividers[] = {')
    for d in dividers:
        divisor = d.get("divisor", 1)
        lines.append(f'        {{ "{d["name"]}", SignalName::{signal_enum_map[d["input"]]}, SignalName::{signal_enum_map[d["output"]]}, {divisor} }},')
    lines.append('    };')
    lines.append('')

    lines.append('    static constexpr Mux muxes[] = {')
    for m in muxes:
        input_list = []
        for i in m['inputs']:
            if i in signal_enum_map:
                input_list.append(f'SignalName::{signal_enum_map[i]}')
            elif i in ['', None]:
                input_list.append('SignalName::_')
            else:
                raise KeyError(f"Unknown signal name in mux inputs: {i}")
        inputs_str = '{ ' + ', '.join(input_list) + ' }'
        lines.append(f'        {{ "{m["name"]}", SignalName::{signal_enum_map[m["output"]]}, {inputs_str} }},')
    lines.append('    };')
    lines.append('')

    lines.append('};')
    lines.append('')

    Path(output_path).write_text("\n".join(lines))

if __name__ == '__main__':
    generate_header('LPC865.yaml', 'ClockTree.hpp')
