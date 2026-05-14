// Microchip clocktree compile test.
//
// Lives in its own translation unit so its `hwreg::Connection` definition
// (specific to ATSAME70Q21B) doesn't collide with other chips' Connection
// definitions in the same TU.  See docs/design/connection-routing.md.

#include <cstdint>
#if REGISTERS_MODULE
import microchip.ATSAME70Q21B;
import microchip.SAM_Gen1;
#else
#include "microchip/ATSAME70Q21B.hpp"
#include "microchip/SAM_Gen1.hpp"
#endif

void test_microchip() {
    // Exercise the clock-tree code path: instantiate the SAM_Gen1 tree and
    // query a frequency, with the external crystal frequencies supplied via
    // the State slots.
    clocktree::ClockTree<microchip::Clocks> ct{microchip::Clocks::State{
        .stateXTAL32K = 32768,
        .stateMAIN_XTAL = 12'000'000,
    }};
    volatile uint32_t mck = ct.getFrequency(microchip::Signals::mck);
    (void)mck;
}
