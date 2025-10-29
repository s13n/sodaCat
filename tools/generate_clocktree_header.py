
import yaml
from pathlib import Path

def generate_header(yaml_path, output_path):
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    signals = data.get('signals', [])
    plls = data.get('plls', [])
    gates = data.get('gates', [])
    dividers = data.get('dividers', [])

    lines = []
    lines.append('#pragma once')
    lines.append('#include <optional>')
    lines.append('#include <cstdint>')
    lines.append('')
    lines.append('class ClockTree {')

    # Enum for signal names
    lines.append('  public:')
    lines.append('    enum class SignalName {')
    for s in signals:
        lines.append(f'        {s["name"]},')
    lines.append('    };\n')

    # Signal struct
    lines.append('    struct Signal {')
    lines.append('        const char* name;')
    lines.append('        std::optional<uint32_t> min_freq;')
    lines.append('        std::optional<uint32_t> max_freq;')
    lines.append('        std::optional<uint32_t> nominal_freq;')
    lines.append('        const char* description;')
    lines.append('    };\n')

    # PLL struct
    lines.append('    struct PLL {')
    lines.append('        const char* name;')
    lines.append('        const char* input;')
    lines.append('        const char* output;')
    lines.append('    };\n')

    # Gate struct
    lines.append('    struct Gate {')
    lines.append('        const char* name;')
    lines.append('        const char* input;')
    lines.append('        const char* output;')
    lines.append('    };\n')

    # Divider struct
    lines.append('    struct Divider {')
    lines.append('        const char* name;')
    lines.append('        const char* input;')
    lines.append('        const char* output;')
    lines.append('        uint32_t divisor;')
    lines.append('    };\n')

    # Signals array
    lines.append('    static constexpr Signal signals[] = {')
    for s in signals:
        lines.append(f'        {{ "{s["name"]}", {s.get("min", "std::nullopt")}, {s.get("max", "std::nullopt")}, {s.get("nominal", "std::nullopt")}, "{s.get("description", "")}" }},')
    lines.append('    };\n')

    # PLLs array
    lines.append('    static constexpr PLL plls[] = {')
    for p in plls:
        lines.append(f'        {{ "{p["name"]}", "{p["input"]}", "{p["output"]}" }},')
    lines.append('    };\n')

    # Gates array
    lines.append('    static constexpr Gate gates[] = {')
    for g in gates:
        lines.append(f'        {{ "{g["name"]}", "{g["input"]}", "{g["output"]}" }},')
    lines.append('    };\n')

    # Dividers array
    lines.append('    static constexpr Divider dividers[] = {')
    for d in dividers:
        divisor = d.get("divisor", 1)
        lines.append(f'        {{ "{d["name"]}", "{d["input"]}", "{d["output"]}", {divisor} }},')
    lines.append('    };\n')

    lines.append('};\n')

    # Write to output file
    Path(output_path).write_text("\n".join(lines))

if __name__ == '__main__':
    generate_header('LPC865.yaml', 'ClockTree.hpp')
