// soc-data compile test.
//
// The actual exercise lives in per-chip TUs because each chip's
// `hwreg::Connection` enum has chip-specific enumerators that can't
// coexist in a single TU.  See docs/design/connection-routing.md.

void test_stm32h7();
void test_microchip();

int main() {
    test_stm32h7();
    test_microchip();
}
