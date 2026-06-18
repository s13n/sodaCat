// Cirrus WM8994 endianness compile test.
//
// The WM8994 is generated with ENDIAN big (see test/CMakeLists.txt): the
// CODEC transmits MSB-first, so over an I2C byte stream onto a little-endian
// host its 16-bit register words land big-endian in memory.  Like the other
// TUs here this is a compile-only exercise — building it validates that the
// build-time `--endian big` flag threaded through into the HwReg<R, E>
// endianness slot and that the byte-swapping access paths instantiate.

#include <bit>
#include <cstdint>
#include <utility>
#if REGISTERS_MODULE
import cirrus.WM8994;
#else
#include "cirrus/WM8994.hpp"
#endif

// The endianness argument reached the generated register types.
static_assert(decltype(std::declval<cirrus::WM8994::WM8994>().Power_Management_1)::endian
              == std::endian::big,
              "WM8994 must be generated big-endian for the I2C use case");

void test_cirrus() {
    // HwReg models MMIO and is never value-constructed; it is accessed over
    // existing storage (here an I2C register shadow rather than a bus
    // address).  Lay the register block over a byte buffer and exercise the
    // big-endian read/write paths so they get instantiated.
    alignas(cirrus::WM8994::WM8994)
        static unsigned char buf[sizeof(cirrus::WM8994::WM8994)]{};
    auto &dev = *reinterpret_cast<cirrus::WM8994::WM8994 *>(buf);

    dev.Power_Management_1 = std::uint16_t{0x1234};   // write via integer (byteswapped)
    auto raw = dev.Power_Management_1.reg_;            // raw big-endian storage word
    auto v = dev.Power_Management_1.val();             // read back as host-order integer
    auto bf = dev.Power_Management_1.get().SPKOUTR_ENA;// read an individual bitfield
    dev.WSEQ[0].WSEQ_CTRL_A = std::uint16_t{0};        // cluster-array element, also big-endian

    (void)raw; (void)v; (void)bf;
}
