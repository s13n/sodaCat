/**@file
 * Fixed-size hardware array with a configurable starting index.
 *
 * Many vendor reference manuals number registers from 1 (e.g. STM32 DMA
 * channels CCR1..CCR8, HSEM R1..R31) or from some other non-zero value.
 * HwArray<T, N, Base> preserves that numbering: a[Base] is the first
 * element, a[Base + size() - 1] is the last. This is in contrast to
 * std::array, where the first element is always at index 0.
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
#pragma once

#include <cstddef>

inline namespace hwreg {

template<typename T, std::size_t N, std::size_t Base = 0>
struct HwArray {
    static_assert(N > 0, "HwArray requires at least one element");

    using value_type = T;
    using size_type = std::size_t;
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

    //! Smallest valid index (== Base).
    static constexpr size_type first_index() noexcept {
        return Base;
    }
    //! Largest valid index (== Base + size() - 1).
    static constexpr size_type last_index() noexcept {
        return Base + N - 1;
    }
    //! True iff i is a valid index for this array.
    static constexpr bool contains(size_type i) noexcept {
        return i >= Base && i < Base + N;
    }

    //! Unchecked element access. Behaviour is undefined if !contains(i).
    constexpr T &operator[](size_type i) noexcept {
        return storage_[i - Base];
    }
    constexpr T const &operator[](size_type i) const noexcept {
        return storage_[i - Base];
    }
    constexpr T volatile &operator[](size_type i) volatile noexcept {
        return storage_[i - Base];
    }
    constexpr T const volatile &operator[](size_type i) const volatile noexcept {
        return storage_[i - Base];
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
