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

    # Header file content
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
        "    struct PLL { const char* name; Signal input; Signal output; };",
        "    struct Gate { const char* name; Signal input; Signal output; };",
        "    struct Divider { const char* name; Signal input; Signal output; uint32_t divisor; };",
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

    # Source file content
    cpp_lines = [f'#include "{Path(hpp_path).name}"', ""]
    cpp_lines.append("constexpr ClockTree::SignalInfo ClockTree::signals[] = {")
    for s in signals:
        cpp_lines.append(f'    {{ "{s["name"]}", {s.get("min", "std::nullopt")}, {s.get("max", "std::nullopt")}, {s.get("nominal", "std::nullopt")}, "{s.get("description", "")}" }},')
    cpp_lines.append("};\n")

    cpp_lines.append("constexpr ClockTree::PLL ClockTree::plls[] = {")
    for p in plls:
        cpp_lines.append(f'    {{ "{p["name"]}", ClockTree::Signal::{signal_enum_map[p["input"]]}, ClockTree::Signal::{signal_enum_map[p["output"]]} }},')
    cpp_lines.append("};\n")

    cpp_lines.append("constexpr ClockTree::Gate ClockTree::gates[] = {")
    for g in gates:
        cpp_lines.append(f'    {{ "{g["name"]}", ClockTree::Signal::{signal_enum_map[g["input"]]}, ClockTree::Signal::{signal_enum_map[g["output"]]} }},')
    cpp_lines.append("};\n")

    cpp_lines.append("constexpr ClockTree::Divider ClockTree::dividers[] = {")
    for d in dividers:
        divisor = d.get("divisor", 1)
        cpp_lines.append(f'    {{ "{d["name"]}", ClockTree::Signal::{signal_enum_map[d["input"]]}, ClockTree::Signal::{signal_enum_map[d["output"]]}, {divisor} }},')
    cpp_lines.append("};\n")

    cpp_lines.append("constexpr ClockTree::Mux ClockTree::muxes[] = {")
    for m in muxes:
        input_list = []
        for i in m['inputs']:
            if i in signal_enum_map:
                input_list.append(f'ClockTree::Signal::{signal_enum_map[i]}')
            elif i in ['', None]:
                input_list.append('ClockTree::Signal::_')
            else:
                raise KeyError(f"Unknown signal name in mux inputs: {i}")
        inputs_str = "{ " + ", ".join(input_list) + " }"
        cpp_lines.append(f'    {{ "{m["name"]}", ClockTree::Signal::{signal_enum_map[m["output"]]}, {inputs_str} }},')
    cpp_lines.append("};\n")

    Path(cpp_path).write_text("\n".join(cpp_lines))

if __name__ == "__main__":
    generate_header("LPC865.yaml", "ClockTree.hpp", "ClockTree.cpp")
