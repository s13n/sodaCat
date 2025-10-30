import yaml
from pathlib import Path

def generate_header(yaml_path, hpp_path, cpp_path):
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
    enum_type = 'uint8_t' if enum_count <= 256 else 'uint16_t' if enum_count <= 65536 else 'uint32_t'

    # Header file
    hpp_lines = [
        "#pragma once",
        "#include <optional>",
        "#include <cstdint>",
        "#include <initializer_list>",
        "",
        "class ClockTree {",
        "  public:",
        f"    enum class Signal : {enum_type} {{"
    ]
    for s in signals:
        hpp_lines.append(f"        {signal_enum_map[s['name']]},")
    hpp_lines.append("    };")
    hpp_lines.append("")

    hpp_lines.extend([
        "    struct SignalInfo {",
        "        const char* name;",
        "        std::optional<uint32_t> min_freq;",
        "        std::optional<uint32_t> max_freq;",
        "        std::optional<uint32_t> nominal_freq;",
        "        const char* description;",
        "    };",
        "",
        "    struct RegisterField {",
        "        const char* reg;",
        "        const char* field;",
        "        std::optional<int32_t> offset;",
        "    };",
        "",
        "    struct PLL { const char* name; Signal input; Signal output; };",
        "    struct Gate { const char* name; Signal input; Signal output; };",
        "    struct Divider {",
        "        const char* name;",
        "        Signal input;",
        "        Signal output;",
        "        std::optional<uint32_t> value;",
        "        std::optional<RegisterField> factor;",
        "        std::optional<RegisterField> denominator;",
        "    };",
        "    struct Mux { const char* name; Signal output; std::initializer_list<Signal> inputs; };",
        "",
        "    static constexpr SignalInfo signals[];",
        "    static constexpr PLL plls[];",
        "    static constexpr Gate gates[];",
        "    static constexpr Divider dividers[];",
        "    static constexpr Mux muxes[];",
        "};"
    ])
    Path(hpp_path).write_text("\n".join(hpp_lines))

    # Source file
    cpp_lines = [f'#include "{Path(hpp_path).name}"', ""]
    cpp_lines.append("constexpr ClockTree::SignalInfo ClockTree::signals[] = {")
    for s in signals:
        cpp_lines.append(f'    {{ "{s["name"]}", {s.get("min", "std::nullopt")}, {s.get("max", "std::nullopt")}, {s.get("nominal", "std::nullopt")}, "{s.get("description", "")}" }},')
    cpp_lines.append("};\n")

    cpp_lines.append("constexpr ClockTree::PLL ClockTree::plls[] = {")
    for p in plls:
        cpp_lines.append(f'    {{ "{p["name"]}", Signal::{signal_enum_map[p["input"]]}, Signal::{signal_enum_map[p["output"]]} }},')
    cpp_lines.append("};\n")

    cpp_lines.append("constexpr ClockTree::Gate ClockTree::gates[] = {")
    for g in gates:
        cpp_lines.append(f'    {{ "{g["name"]}", Signal::{signal_enum_map[g["input"]]}, Signal::{signal_enum_map[g["output"]]} }},')
    cpp_lines.append("};\n")

    cpp_lines.append("constexpr ClockTree::Divider ClockTree::dividers[] = {")
    for d in dividers:
        value = d.get("value")
        factor = d.get("factor")
        denom = d.get("denominator")

        def emit_field(f):
            if not f:
                return "std::nullopt"
            reg = f.get("reg", "")
            field = f.get("field", "")
            offset = f.get("offset", 0)
            return f'RegisterField{{"{reg}", "{field}", {offset}}}'

        cpp_lines.append(
            f'    {{ "{d["name"]}", '
            f'Signal::{signal_enum_map[d["input"]]}, '
            f'Signal::{signal_enum_map[d["output"]]}, '
            f'{value if value is not None else "std::nullopt"}, '
            f'{emit_field(factor)}, '
            f'{emit_field(denom)}'
            f' }},'
        )
    cpp_lines.append("};\n")

    cpp_lines.append("constexpr ClockTree::Mux ClockTree::muxes[] = {")
    for m in muxes:
        input_list = []
        for i in m['inputs']:
            if i in signal_enum_map:
                input_list.append(f'Signal::{signal_enum_map[i]}')
            elif i in ['', None]:
                input_list.append('Signal::_')
            else:
                raise KeyError(f"Unknown signal name in mux inputs: {i}")
        inputs_str = "{ " + ", ".join(input_list) + " }"
        cpp_lines.append(f'    {{ "{m["name"]}", Signal::{signal_enum_map[m["output"]]}, {inputs_str} }},')
    cpp_lines.append("};\n")

    Path(cpp_path).write_text("\n".join(cpp_lines))

if __name__ == "__main__":
    generate_header("LPC865.yaml", "ClockTree.hpp", "ClockTree.cpp")