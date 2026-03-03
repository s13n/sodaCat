// test for soc-data

#include <cstdint>
#if REGISTERS_MODULE
import MDMA;
import STM32H757_CM7;
#else
#include "STM32H757_CM7.hpp"
#endif

using namespace stm32h7::DMA;
using namespace stm32h7::MDMA;

int main() {
    auto &mdma = *stm32h7::i_MDMA.registers;         // MDMA register set
    auto &dma = *stm32h7::i_DMA1.registers;          // DMA register set

    stm32h7::i_MDMA.registers->GISR0.set(0);         // Using the smart pointer directly
    auto ξ = dma.S2CR.val();                // read CR register as 32-bit integer
    uint32_t d = dma.S2CR;                  // dto.
    auto b = mdma.C6CR.get();               // read CR register as bitfield struct
    C6CR c = mdma.C6CR;              // must disambiguate between CR registers
    auto e = mdma.C6CR.get().EN;            // read individual bitfield
    auto f = get(mdma.C6CR).EN;             // dto.
    auto ma1 = get(dma.S1M1AR).M1A;        // dto.
    b.EN = 1;                               // modify field in bitfield struct
    mdma.C6CR = b;                          // write back entire bitfield struct to register
}
