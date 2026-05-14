/**@file
 * Definitions for dealing with hardware registers in C++
 */
#pragma once

#include <algorithm>
#include <bit>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iterator>
#include <type_traits>
#include <version>

inline namespace hwreg {

//! Templated unsigned integer type in the spirit of `boost::uint_t`.
template<size_t N> using uint =
    std::conditional_t<N == 1, std::uint8_t,
    std::conditional_t<N == 2, std::uint16_t,
    std::conditional_t<N == 4, std::uint32_t,
    std::conditional_t<N == 8, std::uint64_t,
    void>>>>;

/** Swap bytes.
 * This is implemented depending on what's available in the standard library.
 * We can only handle big or little endian, not mixed endian.
 */
template<typename X> constexpr X byteswap(X x) noexcept {
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
template<typename T> concept RegBitfield = requires(T x) {
    std::has_unique_object_representations_v<T>;
    std::is_aggregate_v<T>;
    std::is_integral_v<uint<sizeof(T)>>;
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
template<RegBitfield R, std::endian E = std::endian::native>
struct HwReg {
    using BitField = R;
    using Native = uint<sizeof(R)>;
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

    /** Return a reference to the register's bitfield representation.
     * Keep in mind that this may need to be byteswapped on access.
     */
    constexpr BitField &ref() noexcept {
        return *std::bit_cast<BitField*>(&reg_);
    }

    /** Return a reference to the register's bitfield representation.
     * Keep in mind that this may need to be byteswapped on access.
     */
    constexpr BitField &ref() volatile noexcept {
        return *std::bit_cast<BitField*>(&reg_);
    }

    /** Cast to a user-typed reference.
     * This is for cases when the register needs to be accessed
     * as a different type. You need to use this responsibly,
     * because it is easy to abuse it.
     */
    template<typename T> T &cast() noexcept {
        return *std::bit_cast<T*>(&reg_);
    }

    /** Cast to a user-typed reference.
     * This is for cases when the register needs to be accessed
     * as a different type. You need to use this responsibly,
     * because it is easy to abuse it.
     */
    template<typename T> T &cast() volatile noexcept {
        return *std::bit_cast<T*>(&reg_);
    }

    Native reg_;
};

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
template<typename T>
struct HwPtr {
    using element_type = T;
    constexpr HwPtr(std::uintptr_t addr) : addr_{addr} {}
    T &operator*() const noexcept { return *reinterpret_cast<T*>(addr_); }
    T *operator->() const noexcept { return reinterpret_cast<T*>(addr_); }
private:
    std::uintptr_t addr_;
};

//! Type for representing exceptions/interrupts.
typedef uint16_t Exception;

/** Opaque, chip-scoped identity for one (instance, output) wiring pair.
 *
 * Forward-declared here so peripheral headers (`USART.hpp`, `SPI.hpp`,
 * ...) can name the type in their Intgr structs without acquiring a
 * chip-namespace dependency.  The chip header re-opens `namespace hwreg`
 * to define the enum with chip-specific enumerators.
 *
 * See docs/design/connection-routing.md for the full design.
 */
enum class Connection : uint16_t;

/** Port-value type for routing-table lookups.
 *
 * Single point of customisation for a future typed-per-target-port
 * upgrade: `resolve()` returns `port_t`, call sites that write `auto`
 * stay correct when this becomes deduced from the table.
 */
using port_t = uint16_t;

/** One row of a pair-list routing table.
 *
 * Used by OR-able targets (NVIC vectors) where multiple Connections
 * can land on the same `port`.  Tables of this type are generator-sorted
 * by `conn` so `resolve()` can binary-search.
 */
struct RouteEntry {
    Connection conn;
    port_t     port;
};

/** Look up the port that the given Connection lands on, given a routing
 *  table emitted by the chip header.
 *
 *  Two table shapes are dispatched via the element type:
 *  - `RouteEntry[]` (pair list, OR-able targets) — binary search.
 *  - `Connection[]` (direct array, exclusive targets) — linear scan,
 *    returns the array index.
 *
 *  Returns 0 when the Connection isn't in the table; callers passing a
 *  Connection guaranteed to be in their target's table (the constexpr
 *  Intgr-field path) never observe that case.
 */
constexpr port_t resolve(const auto& table, Connection c) {
    using Elem = std::remove_cvref_t<decltype(table[0])>;
    if constexpr (std::is_same_v<Elem, Connection>) {
        auto it = std::find(std::begin(table), std::end(table), c);
        return it != std::end(table)
            ? static_cast<port_t>(it - std::begin(table))
            : 0;
    } else {
        auto it = std::lower_bound(std::begin(table), std::end(table), c,
            [](const RouteEntry& e, Connection v) { return e.conn < v; });
        return (it != std::end(table) && it->conn == c) ? it->port : 0;
    }
}

/** Fixed-size hardware array with a configurable starting index and
 * optional typed index.
 *
 * Many vendor reference manuals number registers from 1 (e.g. STM32 DMA
 * channels CCR1..CCR8, HSEM R1..R31) or from some other non-zero value.
 * HwArray<T, N, Base> preserves that numbering: a[Base] is the first
 * element, a[Base + size() - 1] is the last. This is in contrast to
 * std::array, where the first element is always at index 0.
 *
 * The optional fourth template parameter Idx selects the index type.
 * When Idx is left at its std::size_t default, the array indexes by
 * plain integer as before. When Idx is a scoped enum (the typical use
 * once a register array carries a schema-level enumeratedIndices), the
 * compiler rejects raw-integer subscripts and only accepts values of
 * that enum -- the type system enforces that you index a Branch[]-style
 * array with a Branch value rather than an arbitrary integer. Idx and
 * Base are independent: the storage offset is always
 * static_cast<size_type>(i) - Base, regardless of whether i is an
 * integer or a scoped enum.
 *
 * size() always returns the number of elements N, irrespective of Base.
 * Use first_index(), last_index() or contains() when looping by index.
 *
 * The interface is intentionally a small subset of std::array's: fill(),
 * swap(), at() and the comparison operators are omitted because they are
 * either meaningless or unsafe when the elements are HwReg instances over
 * volatile MMIO memory. Element-access members are provided in const,
 * non-const, volatile and const-volatile overloads so that
 * volatile-qualified peripheral structs index naturally.
 *
 * Storage is a raw T[N] rather than a wrapped std::array because
 * std::array has no volatile-qualified operator[]/data(), and reaching
 * through it via reinterpret_cast would only be well-defined on
 * implementations where std::array happens to have the same layout as
 * T[N] -- a property that holds in practice but is not guaranteed.
 */
template<typename T, std::size_t N, std::size_t Base = 0, typename Idx = std::size_t>
struct HwArray {
    static_assert(N > 0, "HwArray requires at least one element");

    using value_type = T;
    using size_type = std::size_t;
    using index_type = Idx;
    using reference = T &;
    using const_reference = T const &;
    using pointer = T *;
    using const_pointer = T const *;
    using iterator = T *;
    using const_iterator = T const *;

    HwArray(HwArray &&) = delete;

    //! Number of elements; independent of Base.
    static constexpr size_type size() noexcept {
        return N;
    }
    static constexpr bool empty() noexcept {
        return false;
    }

    //! Smallest valid index (== Base, in the index type).
    static constexpr index_type first_index() noexcept {
        return static_cast<index_type>(Base);
    }
    //! Largest valid index (== Base + size() - 1, in the index type).
    static constexpr index_type last_index() noexcept {
        return static_cast<index_type>(Base + N - 1);
    }
    //! True iff i is a valid index for this array.
    static constexpr bool contains(index_type i) noexcept {
        auto v = static_cast<size_type>(i);
        return v >= Base && v < Base + N;
    }

    //! Unchecked element access. Behaviour is undefined if !contains(i).
    constexpr T &operator[](index_type i) noexcept {
        return storage_[static_cast<size_type>(i) - Base];
    }
    constexpr T const &operator[](index_type i) const noexcept {
        return storage_[static_cast<size_type>(i) - Base];
    }
    constexpr T volatile &operator[](index_type i) volatile noexcept {
        return storage_[static_cast<size_type>(i) - Base];
    }
    constexpr T const volatile &operator[](index_type i) const volatile noexcept {
        return storage_[static_cast<size_type>(i) - Base];
    }

    constexpr T &front() noexcept {
        return storage_[0];
    }
    constexpr T const &front() const noexcept {
        return storage_[0];
    }
    constexpr T volatile &front() volatile noexcept {
        return storage_[0];
    }
    constexpr T const volatile &front() const volatile noexcept {
        return storage_[0];
    }

    constexpr T &back() noexcept {
        return storage_[N - 1];
    }
    constexpr T const &back() const noexcept {
        return storage_[N - 1];
    }
    constexpr T volatile &back() volatile noexcept {
        return storage_[N - 1];
    }
    constexpr T const volatile &back() const volatile noexcept {
        return storage_[N - 1];
    }

    constexpr T *data() noexcept {
        return storage_;
    }
    constexpr T const *data() const noexcept {
        return storage_;
    }
    constexpr T volatile *data() volatile noexcept {
        return storage_;
    }
    constexpr T const volatile *data() const volatile noexcept {
        return storage_;
    }

    /* Iterators traverse the underlying storage in declaration order; the
     * dereferenced value at position k corresponds to logical index Base+k.
     */
    constexpr iterator begin() noexcept {
        return storage_;
    }
    constexpr iterator end() noexcept {
        return storage_ + N;
    }
    constexpr const_iterator begin() const noexcept {
        return storage_;
    }
    constexpr const_iterator end() const noexcept {
        return storage_ + N;
    }
    constexpr const_iterator cbegin() const noexcept {
        return storage_;
    }
    constexpr const_iterator cend() const noexcept {
        return storage_ + N;
    }
    constexpr T volatile *begin() volatile noexcept {
        return storage_;
    }
    constexpr T volatile *end() volatile noexcept {
        return storage_ + N;
    }
    constexpr T const volatile *begin() const volatile noexcept {
        return storage_;
    }
    constexpr T const volatile *end() const volatile noexcept {
        return storage_ + N;
    }

    T storage_[N];
};

} // inline namespace hwreg
