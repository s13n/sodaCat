#ifdef REGISTERS_MODULE
module;
#define EXPORT export
#else
#pragma once
#define EXPORT
#endif

#include <algorithm>
#include <array>
#include <cstdint>
#include <initializer_list>
#include <span>
#include <variant>

#ifdef REGISTERS_MODULE
export module clocktree;
#endif

/** ClockTree class template, parameterized with Signals enum. */
EXPORT template<typename Signals> class ClockTree {
public:
    /** Representation of a register field used to control a functional element. */
    struct RegisterField {
        char const *reg;
        char const *field;
        int32_t offset;
        virtual uint32_t read() const = 0;
    };

    /** Generator functional element.
     * 
     * A Generator is a source of a clock signal that isn't derived from another clock signal.
     */
    struct Generator {
        char const *name;
        Signals output;
        RegisterField const *control;
        std::initializer_list<uint32_t> values;
        char const *description;
    };

    /** PLL functional element.
     * 
     * A PLL is a functional element that produces a clock signal from an input clock by
     * multiplying the frequency with an integer, or potentially fractional factor.
     */
    struct Pll {
        char const *name;
        Signals input;
        Signals output;
        RegisterField const *feedback_integer;
        RegisterField const *feedback_fraction;
        RegisterField const *post_divider;
    };

    /** Gate functional element.
     * 
     * A Gate is a controlled element that can switch a clock signal on or off.
     */
    struct Gate {
        char const *name;
        Signals input;
        Signals output;
        RegisterField const *control;
    };

    /** Divider functional element.
     * 
     * A Divider divides an input clock signal by an integer, or potentially fractional factor.
     */
    struct Divider {
        char const *name;
        Signals input;
        Signals output;
        uint16_t value;
        RegisterField const *factor;
        RegisterField const *denominator;
    };

    /** Multiplexer functional element.
     * 
     * A multiplexer selects between multiple input clocks.
     */
    struct Mux {
        char const *name;
        Signals output;
        std::initializer_list<Signals> inputs;
        RegisterField const *control;
    };

    /** Source signal reference.
     *
     * A Source is a functional element that produces an output clock signal.
     * It can be one of a set of different functional elements.
     */
    using Source = std::variant<
        const Generator*,
        const Pll*,
        const Gate*,
        const Divider*,
        const Mux*
    >;

    /** Clock signal.
     * 
     * A clock signal is what flows between functional elements. It has one source,
     * and potentially many consumers. This struct holds the properties of a signal.
     * There is a one to one correspondence between the clock signal number in
     * `enum class Signals` and an instance of struct Signal.
     */
    struct Signal {
        const char* name;
        Source source;
        uint32_t min_freq;
        uint32_t max_freq;
        uint32_t nominal_freq;
        const char* description;
    };

    /** Get frequency of given signal in Hz. */
    uint32_t getFrequency(Signals s) const {
        size_t index = static_cast<size_t>(s);
        if (index >= signals.size()) [[unlikely]]
            return 0;
        return std::visit([this](auto* gen) { return get_frequency(gen); }, signals[index].source);
    }

private:
    uint32_t get_frequency(Source const *src) const {
        if (!src->control) [[unlikely]]
            return src->values.size() > 0 ? src->values.begin()[0] : 0;
        return src->control->read(); // or map value to frequency
    }

    uint32_t get_frequency(Pll const *pll) const {
        uint32_t input_freq = getFrequency(pll->input);
        uint32_t fb_int = pll->feedback_integer ? pll->feedback_integer->read() : 1;
        uint32_t fb_frac = pll->feedback_fraction ? pll->feedback_fraction->read() : 0;
        uint32_t post_div = pll->post_divider ? pll->post_divider->read() : 1;
        double fb = fb_int + fb_frac / 65536.0;
        return uint32_t(input_freq * fb / post_div);
    }

    uint32_t get_frequency(Gate const *gate) const {
        return getFrequency(gate->input);
    }

    uint32_t get_frequency(Divider const *div) const {
        uint64_t input_freq = getFrequency(div->input);
        uint32_t factor = div->factor ? div->factor->read() : div->value;
        uint32_t denom = div->denominator ? div->denominator->read() : 1; 
        return uint32_t(input_freq * denom / factor);
    }

    uint32_t get_frequency(Mux const *mux) const {
        size_t index = mux->control ? mux->control->read() : 0;
        if (index >= mux->inputs.size()) [[unlikely]]
            return 0;
        return getFrequency(*std::next(mux->inputs.begin(), index));
    }

    static Signal const signals[];
    static Generator const generators[];
    static Pll const plls[];
    static Gate const gates[];
    static Divider const dividers[];
    static Mux const muxes[];
    static RegisterField const * const register_fields[];
};
