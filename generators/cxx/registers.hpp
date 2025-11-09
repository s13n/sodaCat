/**@file
 * Definitions for dealing with hardware registers in C++
 */
#ifdef REGISTERS_MODULE
module;
#define EXPORT export
#else
#pragma once
#define EXPORT
#endif

#include <algorithm>
#include <bit>
#include <cstdint>
#include <cstring>
#include <type_traits>
#include <version>

#ifdef REGISTERS_MODULE
export module registers;
#endif

//! Templated unsigned integer type in the spirit of `boost::uint_t`.
template<size_t N> struct UnsignedInt {};
template<> struct UnsignedInt<1> { typedef uint8_t type; };
template<> struct UnsignedInt<2> { typedef uint16_t type; };
template<> struct UnsignedInt<4> { typedef uint32_t type; };
template<> struct UnsignedInt<8> { typedef uint64_t type; };

/** Swap bytes.
 * This is implemented depending on what's available in the standard library.
 * We can only handle big or little endian, not mixed endian.
 */
EXPORT template<typename X> constexpr X byteswap(X x) noexcept {
    X res{};
    if constexpr (sizeof(x) == 1)
        res = x;
    else {
#if defined(__cpp_lib_byteswap)         // C++23
        res = std::byteswap(x);
#elif defined(_MSC_VER)
        switch(sizeof(x)) {
        case 2: res = _byteswap_ushort(x); break;
        case 4: res = _byteswap_ulong(x); break;
        case 8: res = _byteswap_uint64(x); break;
        }
#elif defined(__GNUC__) ||  defined(__clang__)
        switch(sizeof(x)) {
        case 2: res = __builtin_bswap16(x); break;
        case 4: res = __builtin_bswap32(x); break;
        case 8: res = __builtin_bswap64(x); break;
        }
#else
        std::reverse_copy(reinterpret_cast<uint8_t const *>(&x), reinterpret_cast<uint8_t const *>(&x)+sizeof(x), reinterpret_cast<uint8_t *>(&res));
#endif
    }
    return res;
}

//! Concept for checking the bitfield type used with the Reg template.
EXPORT template<typename T> concept RegBitfield = requires(T x) {
    std::has_unique_object_representations_v<T>;
    std::is_aggregate_v<T>;
    std::is_integral_v<typename UnsignedInt<sizeof(T)>::type>;
};

/** The HwReg template is meant to represent hardware registers.
 *
 * The template encapsulates the bitfields and the endianness of the register,
 * and ensures it is accessed in the right way. This is achieved by returning
 * the content as either a bitfield or an integer when reading, and setting the
 * content from either type when writing. In-place bitfield modification is
 * deliberately not supported, because it leads to access patterns that are
 * obscure. You want to make obvious when a register is read or written, how
 * often and in what order, because reading or writing a hardware register often
 * has side effects.
 */
EXPORT template<RegBitfield R, std::endian E = std::endian::native>
struct HwReg {
    using BitField = R;
    using Native = UnsignedInt<sizeof(R)>::type;
    static constinit std::endian const endian = E;

    HwReg(HwReg &&) = delete;

    /** Read register as integer */
    constexpr Native val() volatile const noexcept {
        if constexpr (endian != std::endian::native)
            return byteswap(reg_);
        else
            return reg_;
    }

    /** Read register as integer */
    constexpr Native val() const noexcept {
        if constexpr (endian != std::endian::native)
            return byteswap(reg_);
        else
            return reg_;
    }

    /** Read register as integer */
    friend constexpr Native val(HwReg volatile const &reg) noexcept {
        return reg.val();
    }

    /** Read register as integer */
    friend constexpr Native val(HwReg const &reg) noexcept {
        return reg.val();
    }

    /** Read register as integer */
    constexpr operator Native() volatile const noexcept {
        return val();
    }

    /** Read register as integer */
    constexpr operator Native() const noexcept {
        return val();
    }

    /** Write register as integer */
    void set(Native val) volatile noexcept {
        if constexpr (endian != std::endian::native)
            reg_ = byteswap(val);
        else
            reg_ = val;
    }

    /** Write register as integer */
    void set(Native val) noexcept {
        if constexpr (endian != std::endian::native)
            reg_ = byteswap(val);
        else
            reg_ = val;
    }

    /** Write register as integer */
    void operator=(Native val) volatile noexcept {
        set(val);
    }

    /** Write register as integer */
    void operator=(Native val) noexcept {
        set(val);
    }

    /** Read register as bitfield struct */
    constexpr BitField get() volatile const noexcept {
        return std::bit_cast<BitField>(val());
    }

    /** Read register as bitfield struct */
    constexpr BitField get() const noexcept {
        return std::bit_cast<BitField>(val());
    }

    /** Read register as bitfield struct */
    friend constexpr BitField get(HwReg volatile const &reg) noexcept {
        return reg.get();
    }

    /** Read register as bitfield struct */
    friend constexpr BitField get(HwReg const &reg) noexcept {
        return reg.get();
    }

    /** Read register as bitfield struct */
    constexpr operator BitField() volatile const noexcept {
        return get();
    }

    /** Read register as bitfield struct */
    constexpr operator BitField() const noexcept {
        return get();
    }

    /** Write register as bitfield struct */
    void set(BitField val) volatile noexcept {
        set(std::bit_cast<Native>(val));
    }

    /** Write register as bitfield struct */
    void set(BitField val) noexcept {
        set(std::bit_cast<Native>(val));
    }

    /** Write register as bitfield struct */
    void operator=(BitField val) volatile noexcept {
        set(val);
    }

    /** Write register as bitfield struct */
    void operator=(BitField val) noexcept {
        set(val);
    }

    Native reg_;
};

// Bitfield mask for given bitfield
#define FIELDMASK(t, f) []() constexpr { t r{}; r.f -= 1; return std::bit_cast<HwReg<t>::Native>(r); }()

/** Pointer to a hardware register block.
 *
 * The motivation for this template is the fact that it is illegal since C++20
 * to use reinterpret_cast to initialize constexpr data. This makes it almost
 * impossible to initialize a constexpr pointer with a numeric value, as
 * required for hardware registers with a known address. The workaround used
 * here is to use reinterpret_cast when the address is used, rather than when it
 * is initialized. Note that the constructor is constexpr, while the operator*
 * isn't. The initialization is done with a plain integer, so no explicit casts
 * need to be done by the user.
 */
EXPORT template<typename T>
struct HwPtr {
    using element_type = T;
    constexpr HwPtr(std::uintptr_t addr) : addr_{addr} {}
    T &operator*() const noexcept { return *reinterpret_cast<T*>(addr_); }
    T *operator->() const noexcept { return reinterpret_cast<T*>(addr_); }
private:
    std::uintptr_t addr_;
};

//! Type for representing exceptions/interrupts.
EXPORT typedef uint16_t Exception;
