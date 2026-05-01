// test for soc-data

#include <cstdint>
// clocktree.hpp lives in the support library, not in any module.  In include
// mode the per-chip clock-tree header pulls it in transitively; in module
// mode it sits in the .cppm's global module fragment and isn't re-exported,
// so consumers needing clocktree::ClockTree<> must include it directly.
#include "clocktree.hpp"
#if REGISTERS_MODULE
// The chip module imports peripherals but does not re-export them, so any
// peripheral namespace named below in `using namespace ...` must be imported
// explicitly here.
import stm32h7.DMA;
import stm32h7.MDMA;
import stm32h7.STM32H757_CM7;
import microchip.ATSAME70Q21B;
import microchip.SAM_Gen1_clocks;
#else
#include "stm32h7/STM32H757_CM7.hpp"
#include "microchip/ATSAME70Q21B.hpp"
#include "microchip/SAM_Gen1_clocks.hpp"
#endif

using namespace stm32h7::DMA;
using namespace stm32h7::MDMA;

int main() {
    auto &mdma = *stm32h7::i_MDMA.registers;    // MDMA register set
    auto &dma = *stm32h7::i_DMA1.registers;     // DMA register set

    stm32h7::i_MDMA.registers->GISR0.set(0);    // Using the smart pointer directly
    auto ξ = dma.S[2].CR.val();                 // read CR register as 32-bit integer
    uint32_t d = dma.S[2].CR;                   // dto.
    auto b = mdma.C[6].CR.get();                // read CR register as bitfield struct
    C_CR c = mdma.C[6].CR;                      // explicit CR register type
    auto e = mdma.C[6].CR.get().EN;             // read individual bitfield
    auto f = get(mdma.C[6].CR).EN;              // dto.
    auto ma1 = get(dma.S[1].M1AR).M1A;          // dto.
    b.EN = 1;                                   // modify field in bitfield struct
    mdma.C[6].CR = b;                           // write back entire bitfield struct to register

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
