import yaml
from pathlib import Path

def generate_header(yaml_path, hpp_path, cpp_path):
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    signals = data.get('signals', [])
    sources = data.get('sources', [])
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

    def emit_field_ref(field, mandatory=False):
        if not field:
            return "nullptr" if not mandatory else "/* missing mandatory field */"
        return f"{'*' if mandatory else '&'}register_fields[{register_field_id(field)}]"

    # Map signal name to generator
    signal_generators = {}

    for src in sources:
        signal_generators[src['output']] = ('sources', src)
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
        "#pragma once",
        "#include <cstdint>",
        "#include <initializer_list>",
        "#include <optional>",
        "#include <variant>",
        "",
        "class ClockTree {",
        " public:",
        f"  enum class Signal : {enum_type} {{"
    ]
    for s in signals:
        hpp_lines.append(f"    {signal_enum_map[s['name']]},")
    hpp_lines.append("  };")
    hpp_lines.append("")
    hpp_lines.extend([
        "  struct RegisterField {",
        "    const char* reg;",
        "    const char* field;",
        "    int32_t offset;",
        "    virtual uint32_t read() const = 0;",
        "  };",
        "",
        "  struct Source {",
        "    const char* name;",
        "    Signal output;",
        "    const RegisterField* control;",
        "    std::initializer_list<uint32_t> values;",
        "    const char* description;",
        "  };",
        "",
        "  struct PLL {",
        "    const char* name;",
        "    Signal input;",
        "    Signal output;",
        "    const RegisterField* feedback_integer;",
        "    const RegisterField* feedback_fraction;",
        "    const RegisterField* post_divider;",
        "  };",
        "",
        "  struct Gate {",
        "    const char* name;",
        "    Signal input;",
        "    Signal output;",
        "    const RegisterField* control;",
        "  };",
        "",
        "  struct Divider {",
        "    const char* name;",
        "    Signal input;",
        "    Signal output;",
        "    uint16_t value;",
        "    const RegisterField* factor;",
        "    const RegisterField* denominator;",
        "  };",
        "",
        "  struct Mux {",
        "    const char* name;",
        "    Signal output;",
        "    std::initializer_list<Signal> inputs;",
        "    const RegisterField* control;",
        "  };",
        "",
        "  using Generator = std::variant<",
        "    const Source*,",
        "    const PLL*,",
        "    const Gate*,",
        "    const Divider*,",
        "    const Mux*",
        "  >;",
        "",
        "  struct SignalInfo {",
        "    const char* name;",
        "    std::optional<uint32_t> min_freq;",
        "    std::optional<uint32_t> max_freq;",
        "    std::optional<uint32_t> nominal_freq;",
        "    const char* description;",
        "    Generator generator;",
        "  };",
        "",
        "  double getFrequency(Signal s) const;",
        "",
        "  static constexpr RegisterField *register_fields[];",
        "  static constexpr SignalInfo signals[];",
        "  static constexpr Source sources[];",
        "  static constexpr PLL plls[];",
        "  static constexpr Gate gates[];",
        "  static constexpr Divider dividers[];",
        "  static constexpr Mux muxes[];",
        "",
        "private:",
        "  double get_frequency(const Source *src) const;",
        "  double get_frequency(const PLL *pll) const;",
        "  double get_frequency(const Gate *gate) const;",
        "  double get_frequency(const Divider *div) const;",
        "  double get_frequency(const Mux *mux) const;",
        "};"
    ])
    Path(hpp_path).write_text("\n".join(hpp_lines))

    # Source file
    cpp_lines = [f'#include "{Path(hpp_path).name}"', "#include <algorithm>", ""]

    cpp_lines.append("constexpr ClockTree::RegisterField *ClockTree::register_fields[] = {")
    for f in field_list:
        reg = f.get("reg", "")
        field = f.get("field", "")
        offset = f.get("offset", 0)
        cpp_lines.append(f'  {{ "{reg}", "{field}", {offset} }},')
    cpp_lines.append("};\n")

    cpp_lines.append("constexpr ClockTree::SignalInfo ClockTree::signals[] = {")
    for s in signals:
        name = s["name"]
        gen_type, gen_obj = signal_generators.get(name, ("Source", None))
        gen_list = locals().get(gen_type, [])
        gen_ref = f"&ClockTree::{gen_type}[{gen_list.index(gen_obj)}]" if gen_obj else "nullptr"
        cpp_lines.append(
            f'  {{ "{name}", {s.get("min", "std::nullopt")}, {s.get("max", "std::nullopt")}, {s.get("nominal", "std::nullopt")}, "{s.get("description", "")}", {gen_ref} }},'
        )
    cpp_lines.append("};\n")

    cpp_lines.append("constexpr ClockTree::Source ClockTree::sources[] = {")
    for src in sources:
        ctrl = src.get("control")
        values = ctrl.get("values", []) if ctrl else []
        values_str = "{ " + ", ".join(str(v) for v in values) + " }"
        cpp_lines.append(
            f'  {{ "{src["name"]}", Signal::{signal_enum_map[src["output"]]}, {emit_field_ref(ctrl)}, {values_str}, "{src.get("description", "")}" }},'
        )
    cpp_lines.append("};\n")

    cpp_lines.append("constexpr ClockTree::PLL ClockTree::plls[] = {")
    for p in plls:
        cpp_lines.append(
            f'  {{ "{p["name"]}", Signal::{signal_enum_map[p["input"]]}, Signal::{signal_enum_map[p["output"]]}, '
            f'{emit_field_ref(p.get("feedback_integer"), mandatory=True)}, '
            f'{emit_field_ref(p.get("feedback_fraction"))}, '
            f'{emit_field_ref(p.get("post_divider"))} }},'
        )
    cpp_lines.append("};\n")

    cpp_lines.append("constexpr ClockTree::Gate ClockTree::gates[] = {")
    for g in gates:
        cpp_lines.append(
            f'  {{ "{g["name"]}", Signal::{signal_enum_map[g["input"]]}, Signal::{signal_enum_map[g["output"]]}, {emit_field_ref(g.get("control"))} }},'
        )
    cpp_lines.append("};\n")

    cpp_lines.append("constexpr ClockTree::Divider ClockTree::dividers[] = {")
    for d in dividers:
        cpp_lines.append(
            f'  {{ "{d["name"]}", Signal::{signal_enum_map[d["input"]]}, Signal::{signal_enum_map[d["output"]]}, {d.get("value", 0)}, '
            f'{emit_field_ref(d.get("factor"))}, {emit_field_ref(d.get("denominator"))} }},'
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
        cpp_lines.append(
            f'  {{ "{m["name"]}", Signal::{signal_enum_map[m["output"]]}, {inputs_str}, {emit_field_ref(m.get("control"))} }},'
        )
    cpp_lines.append("};\n")

    cpp_lines.append('''
inline double ClockTree::get_frequency(const Source *src) const {
    if (!src->control) {
        return src->values.size() > 0 ? src->values.begin()[0] : 0.0;
    }
    return src->control->read(); // or map value to frequency
}

inline double ClockTree::get_frequency(const PLL *pll) const {
    double input_freq = getFrequency(pll->input);
    uint32_t fb_int = pll->feedback_integer ? pll->feedback_integer->read() : 1;
    uint32_t fb_frac = pll->feedback_fraction ? pll->feedback_fraction->read() : 0;
    uint32_t post_div = pll->post_divider ? pll->post_divider->read() : 1;
    double fb = fb_int + fb_frac / 65536.0;
    return (input_freq * fb) / post_div;
}

inline double ClockTree::get_frequency(const Gate *gate) const {
    return getFrequency(gate->input);
}

inline double ClockTree::get_frequency(const Divider *div) const {
    double input_freq = getFrequency(div->input);
    uint32_t factor = div->factor ? div->factor->read() : div->value;
    uint32_t denom = div->denominator ? div->denominator->read() : 1;
    return input_freq * denom / factor;
}

inline double ClockTree::get_frequency(const Mux *mux) const {
    size_t index = mux->control ? mux->control->read() : 0;
    auto it = mux->inputs.begin();
    std::advance(it, std::min(index, mux->inputs.size() - 1));
    return getFrequency(*it);
}

double ClockTree::getFrequency(Signal s) const {
    const SignalInfo& info = signals[static_cast<size_t>(s)];
    return std::visit([this](auto* gen) { return get_frequency(gen); }, info.generator);
}''')

    Path(cpp_path).write_text("\n".join(cpp_lines))

if __name__ == "__main__":
    generate_header("LPC865.yaml", "ClockTree.hpp", "ClockTree.cpp")
