# LPC865 Clock Model Audit

Comparison of `LPC865_clocks.yaml` against UM11607 Rev. 3.1.
Resolution notes reference the updated model in `models/NXP/LPC8/LPC86x/LPC86x_clocks.yaml`.

## Signal / topology issues

1. **`fro_div` derivation.** The model chains `fro` -> FRO_DIV (div 2) -> `fro_div`. AI audit claimed this is wrong (should be fro_oscout / 2 independent of FRO_DIRECT), but Figure 7 confirms the model's topology. **Kept as-is.**

2. **FTM SC.CLKS input 1 should be `system_clk`, not `main_clk`.** The FTM's "input clock" is the system clock (post-SYSAHBCLKDIV), not the main clock. **Fixed.**

3. **`lwpwr_clk_vulp` vs `lpwr_clk_vulp` — two distinct signals, not a typo.** `lpwr_clk_vulp` is the ULP oscillator output (~10 kHz), `lwpwr_clk_vulp` is the WKTCLKSEL mux output (fro or lp_osc). The UM has bugs around these names (Figure 8 shows two separate sources both labeled similarly). **Kept — naming is intentional, matches UM figures.**

## Mux input encoding (systematic: figure vs register description)

4. **ADCCLKSEL[1]**: model says `pll_div_clk`, register description says `sys_pll0_clk`.
5. **CLKOUTSEL[2]**: model says `pll_div_clk`, register description says `sys_pll0_clk`.
6. **FRG0CLKSEL[2]**: model says `pll_div_clk`, register description says `sys_pll0_clk`.
7. **FRG1CLKSEL[2]**: model says `pll_div_clk`, register description says `sys_pll0_clk`.

These all follow the clock diagram (Figure 7) rather than the register tables. Figures are likely correct; would need hardware to confirm. **Kept as-is.**

## I3C clock muxes

8. **I3CFCLKSEL inputs**: model has `[fro, external_clk, ...]` (from Figure 8), but Table 97 lists the standard peripheral encoding: FRO, main_clk, FRG0, FRG1, FRO_DIV, none.
9. **I3CSLOWTCCLKSEL inputs**: same conflict — model follows Figure 8, register description says standard encoding.
10. **I3CSLOWCLKSEL mux missing entirely.** Register exists at offset 0x0B0 but is not modeled; the I3CSLOWCLKDIV divider takes `lp_osc` directly.

Clear UM inconsistency; Figure 8 is likely closer to the truth. Would need hardware to confirm. **Kept as-is.**

## WKT clock chain

11/12. **Three distinct muxes, two distinct oscillators.** Resolution:
- **WKTCLKSEL** (SYSCON, 0x4004 806C): selects `fro` or `lp_osc` (~1 MHz). Figures 7, 8, 43 mislabel this as `WKT_CTRL[CLKSEL]`.
- **WKT CTRL.CLKSEL** (WKT, bit 0): selects divided clock (÷16 of WKTCLKSEL output) or ULP oscillator (~10 kHz). The "low power clock" in the CTRL description means the ULP oscillator, not lp_osc.
- **WKT CTRL.SEL_EXTCLK** (WKT, bit 3): selects internal or external WKTCLKIN.
- The "FRO 12 MHz" in Figure 43 is likely a copy-paste artifact from older LPC8xx manuals; the actual frequency depends on FRO and WKTCLKSEL settings.

The original model topology (WKTCLKSEL → WKT_DIV → WKT_CLKSEL → WKT_EXTCLK) is correct. **Added clarifying comments.**

## Register/field naming

13. **SYSAHBCLKCTRL0 I3C field**: model says `I3C0`, UM says `I3C`. **Fixed.**
14. **WKTCLKSEL field name**: model says `SEL`, UM says `CLKSEL`. **Fixed.**
15. **SPI0/SPI1 register names**: model uses `FCLKSEL2[0]`/`FCLKSEL2[1]`, UM uses `SPI0CLKSEL`/`SPI1CLKSEL`. Array notation is intentional for compactness. **Kept as-is.**
16. **UART/I2C register names**: model uses `FCLKSEL[n]`, UM uses individual names. Same rationale. **Kept as-is.**

## Missing elements

17. **EFLASHREFCLKDIV** (Figure 7, register at 0x0C0): marked "Reserved" in register overview, no documented fields. **Not added.**
18. **LPOSCEN gate register** (Table 93, offset 0x07C): WDT_CLK_EN and WKT_CLK_EN gate lp_osc to WWDT and WKT. **Fixed — added LPOSC_WDT and LPOSC_WKT gates.**

## Metadata / minor

19. **`lp_osc` nominal 1 MHz**: UM says configurable 9.3 kHz–2.3 MHz, undefined after reset. 1 MHz is a reasonable working assumption. **Kept.**
20. **Document revision**: `"3"` → `"3.1"`. **Fixed.**
21. **I3CCLKSEL vs I3CFCLKSEL**: UM internal inconsistency (overview says I3CCLKSEL, Section 8.6.26 says I3CFCLKSEL). Model uses `I3CCLKSEL` matching the register overview. **Kept.**

## Needs hardware verification

The following items remain uncertain due to UM internal contradictions (figures vs register descriptions). They require testing on actual LPC865 hardware to resolve:

- **#4-7: pll_div_clk vs sys_pll0_clk** — Do ADCCLKSEL, CLKOUTSEL, FRG0CLKSEL, and FRG1CLKSEL select the raw PLL output or the post-SYSPLLDIV divided output? Model follows figures; register tables say raw PLL.
- **#8-10: I3C clock mux inputs** — Do I3CFCLKSEL and I3CSLOWTCCLKSEL use the dedicated encoding shown in Figure 8, or the standard peripheral clock encoding from Table 97? Does I3CSLOWCLKSEL (0x0B0) actually exist and function?
- **WKT_DIV ratio** — Figure 43 states 12 MHz ÷ 16 = 750 kHz, but `fro` can be 24 or 48 MHz depending on FRO_DIRECT. Is the ÷16 ratio correct, or is it a different divisor that always yields 750 kHz? Or is the 750 kHz figure simply wrong for non-default FRO settings?
