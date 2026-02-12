// test for soc-data

#include <cstdint>
#if REGISTERS_MODULE
import MDMA;
import H757;
#else
#include "MDMA.hpp"
#include "H757.hpp"
#endif

using namespace stm32h7;

int main() {
    auto &mdma = *i_MDMA.registers;         // MDMA register set
    auto &dma = *i_DMA1.registers;          // DMA register set

    i_MDMA.registers->GISR0.set(0);         // Using the smart pointer directly
    auto ξ = dma.S[2].CR.val();             // read CR register as 32-bit integer
    uint32_t d = dma.S[2].CR;               // dto.
    auto b = mdma.C[6].CR.get();            // read CR register as bitfield struct
    MDMA_::CR c = mdma.C[6].CR;             // dto., must disambiguate between CR registers
    auto e = mdma.C[6].CR.get().EN;         // read individual bitfield
    auto f = get(mdma.C[6].CR).EN;          // dto.
    auto ma1 = get(dma.S[1].M1AR).M1A;      // dto.
    b.EN = 1;                               // modify field in bitfield struct 
    mdma.C[6].CR = b;                       // write back entire bitfield struct to register
}
