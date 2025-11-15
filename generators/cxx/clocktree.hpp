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

namespace clocktree {
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
    template<typename Indices> struct Generator {
        Indices::Signals output;
        Indices::RegFields control;
        std::initializer_list<uint32_t> const values;
    };

    /** PLL functional element.
     * 
     * A PLL is a functional element that produces a clock signal from an input clock by
     * multiplying the frequency with an integer, or potentially fractional factor.
     */
    template<typename Indices> struct Pll {
        Indices::Signals input;
        Indices::Signals output;
        Indices::RegFields feedback_integer;
        Indices::RegFields feedback_fraction;
        Indices::RegFields post_divider;
    };

    /** Gate functional element.
     * 
     * A Gate is a controlled element that can switch a clock signal on or off.
     */
    template<typename Indices> struct Gate {
        Indices::Signals input;
        Indices::Signals output;
        Indices::RegFields control;
    };

    /** Divider functional element.
     * 
     * A Divider divides an input clock signal by an integer, or potentially fractional factor.
     */
    template<typename Indices> struct Divider {
        Indices::Signals input;
        Indices::Signals output;
        uint16_t value;
        Indices::RegFields factor;
        Indices::RegFields denominator;
    };

    /** Multiplexer functional element.
     * 
     * A multiplexer selects between multiple input clocks.
     */
    template<typename Indices> struct Mux {
        Indices::Signals output;
        std::initializer_list<typename Indices::Signals> const inputs;
        Indices::RegFields control;
    };

    /** Clock signal.
     * 
     * A clock signal is what flows between functional elements. It has one source,
     * and potentially many consumers. This struct holds the properties of a signal.
     * There is a one to one correspondence between the clock signal number in
     * `enum class Signals` and an instance of struct Signal.
     */
    template<typename Indices> struct Signal {
        Indices::Elements source;
        uint32_t min_freq;
        uint32_t max_freq;
        uint32_t nominal_freq;
    };

/** ClockTree class template, parameterized with Signals enum. */
EXPORT template<typename Base> class ClockTree : public Base {
public:
    /** Get frequency of given signal in Hz. */
    uint32_t getFrequency(typename Base::Sig s) const {
        size_t index = static_cast<size_t>(s);
        if (index >= Base::signals.size()) [[unlikely]]
            return 0;
        return std::visit([this](auto* gen) { return get_frequency(gen); }, Base::signals[index].source);
    }

private:
    uint32_t get_frequency(typename Base::Ele src) const {
        return 0;
    }

    uint32_t get_frequency(Pll<typename Base::Ix> const *pll) const {
        uint32_t input_freq = getFrequency(pll->input);
        uint32_t fb_int = pll->feedback_integer ? pll->feedback_integer->read() : 1;
        uint32_t fb_frac = pll->feedback_fraction ? pll->feedback_fraction->read() : 0;
        uint32_t post_div = pll->post_divider ? pll->post_divider->read() : 1;
        double fb = fb_int + fb_frac / 65536.0;
        return uint32_t(input_freq * fb / post_div);
    }

    uint32_t get_frequency(Gate<typename Base::Ix> const *gate) const {
        return getFrequency(gate->input);
    }

    uint32_t get_frequency(Divider<typename Base::Ix> const *div) const {
        uint64_t input_freq = getFrequency(div->input);
        uint32_t factor = div->factor ? div->factor->read() : div->value;
        uint32_t denom = div->denominator ? div->denominator->read() : 1; 
        return uint32_t(input_freq * denom / factor);
    }

    uint32_t get_frequency(Mux<typename Base::Ix> const *mux) const {
        size_t index = mux->control ? mux->control->read() : 0;
        if (index >= mux->inputs.size()) [[unlikely]]
            return 0;
        return getFrequency(*std::next(mux->inputs.begin(), index));
    }
};
} // namespace
