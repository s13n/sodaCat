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
        uint32_t(*get)(void const *);   //!< Read register field
        void(*set)(void *, uint32_t);   //!< Write register field
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
    uint32_t getFrequency(typename Base::S s) const {
        size_t index = static_cast<size_t>(s);
        if (index >= Base::signals.size()) [[unlikely]]
            return 0;
        auto elem = Base::signals[index].source;
        if (size_t(elem) == 0)
            return 0;
        if (size_t(elem) <= size_t(Base::Ix::last_gen))
            return get_frequency(Base::generators[size_t(elem) - 1]);
        if (size_t(elem) <= size_t(Base::Ix::last_pll))
            return get_frequency(Base::plls[size_t(elem) - size_t(Base::Ix::last_gen)]);
        if (size_t(elem) <= size_t(Base::Ix::last_gate))
            return get_frequency(Base::gates[size_t(elem) - size_t(Base::Ix::last_pll)]);
        if (size_t(elem) <= size_t(Base::Ix::last_div))
            return get_frequency(Base::dividers[size_t(elem) - size_t(Base::Ix::last_gate)]);
        if (size_t(elem) <= size_t(Base::Ix::last_mux))
            return get_frequency(Base::muxes[size_t(elem) - size_t(Base::Ix::last_div)]);
        return 0;
    }

private:
    uint32_t get_frequency(typename Base::Ge const &gen) const {
        auto *get_sel = Base::register_fields[size_t(gen.control)].get;
        size_t index = get_sel ? get_sel(static_cast<Base const*>(this)) : 0;
        if (index >= gen.values.size()) [[unlikely]]
            return 0;
        return *std::next(gen.values.begin(), index);
    }

    uint32_t get_frequency(typename Base::Pl const &pll) const {
        uint32_t input_freq = getFrequency(pll.input);
        auto *get_int = Base::register_fields[size_t(pll.feedback_integer)].get;
        uint32_t fb_int = get_int ? get_int(static_cast<Base const*>(this)) : 1;
        auto *get_frac = Base::register_fields[size_t(pll.feedback_fraction)].get;
        uint32_t fb_frac = get_frac ? get_frac(static_cast<Base const*>(this)) : 0;
        auto *get_div = Base::register_fields[size_t(pll.post_divider)].get;
        uint32_t post_div = get_div ? get_div(static_cast<Base const*>(this)) : 1;
        double fb = fb_int + fb_frac / 65536.0;
        return uint32_t(input_freq * fb / post_div);
    }

    uint32_t get_frequency(typename Base::Ga const &gate) const {
        auto *get = Base::register_fields[size_t(gate.control)].get;
        return get && get(static_cast<Base const*>(this)) ? getFrequency(gate.input) : 0;
    }

    uint32_t get_frequency(typename Base::Di const &div) const {
        uint64_t input_freq = getFrequency(div.input);
        auto *get_factor = Base::register_fields[size_t(div.factor)].get;
        uint32_t factor = get_factor ? get_factor(static_cast<Base const*>(this)) : div.value;
        auto *get_denom = Base::register_fields[size_t(div.denominator)].get;
        uint32_t denom = get_denom ? get_denom(static_cast<Base const*>(this)) : 1; 
        return uint32_t(input_freq * denom / factor);
    }

    uint32_t get_frequency(typename Base::Mu const &mux) const {
        auto *get_sel = Base::register_fields[size_t(mux.control)].get;
        size_t index = get_sel ? get_sel(static_cast<Base const*>(this)) : 0;
        if (index >= mux.inputs.size()) [[unlikely]]
            return 0;
        return getFrequency(*std::next(mux.inputs.begin(), index));
    }
};
} // namespace
