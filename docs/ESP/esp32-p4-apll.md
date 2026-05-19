# ESP32-P4 APLL (Audio PLL): what it is and how runtime-tunable it actually is

Notes compiled from the ESP32-P4 TRM (Pre-release), the ESP32-P4 datasheet, and
the ESP32-P4-specific code paths in ESP-IDF master.

## TL;DR

- The APLL on the ESP32-P4 is a **fractional-N PLL with an internal
  sigma-delta-modulated divider**, structurally the same family as the APLL on
  the original ESP32 / S2 / S3.
- Static frequency resolution is **excellent** for audio: ~610 Hz at the VCO,
  ~15 Hz at a typical 12.288 MHz I2S MCLK.
- It is **not** a clean fit for *live* small-step retuning. Every coefficient
  change goes over an internal analog-I²C bus, and the documented flow runs a
  calibration sweep after each change. There is no documented glitch-free
  fractional-update path comparable to the STM32H7's FRACN1.
- The actual SDM order / topology / noise floor is **not publicly
  documented**.

## Architecture

Source clock: `XTAL_CLK = 40 MHz`.

Frequency formula (from ESP-IDF `rtc_clk_apll_coeff_calc`):

```
f_VCO  = xtal · (4 + sdm2 + sdm1/256 + sdm0/65536)
f_apll = f_VCO / ((o_div + 2) · 2)
```

Coefficients and widths:

| Field   | Bits | Range  | Role                                   |
| ------- | ---- | ------ | -------------------------------------- |
| `sdm2`  | 6    | 0–63   | Integer part of the multiplier         |
| `sdm1`  | 8    | 0–255  | High byte of fractional part (1/256)   |
| `sdm0`  | 8    | 0–255  | Low  byte of fractional part (1/65536) |
| `o_div` | 5    | 0–31   | Post-divider; output divisor = 2(o_div+2) |

Effective fractional word: 24 bits (`sdm2.sdm1.sdm0`).

Limits enforced by ESP-IDF on the P4:

| Constant                         | Value         |
| -------------------------------- | ------------- |
| `CLK_LL_APLL_MULTIPLIER_MIN_HZ`  | 350 MHz       |
| `CLK_LL_APLL_MULTIPLIER_MAX_HZ`  | 500 MHz       |
| `CLK_LL_APLL_MIN_HZ`             | 5,303,031 Hz  |
| `CLK_LL_APLL_MAX_HZ`             | 125 MHz       |

The TRM §46 says "configurable APLL clock with frequencies up to 240 MHz", but
that refers to the I2S master-clock source mux ceiling, not a number the IDF
will program the APLL to. The datasheet text matches the IDF: **6–125 MHz**.

## Where the registers live

The APLL is treated as an **analog block** by the digital register map.
Coefficients are not memory-mapped peripheral registers — they are written
through the internal Analog I²C master (TRM §45.1), addressed as slave `0x6f`
("PLLA"):

- `I2C_APLL_OR_OUTPUT_DIV`  — `o_div`
- `I2C_APLL_DSDM0`          — `sdm0`
- `I2C_APLL_DSDM1`          — `sdm1`
- `I2C_APLL_DSDM2`          — `sdm2`
- `I2C_APLL_IR_CAL_DELAY`   — calibration sweep
- `I2C_APLL_OR_CAL_END`     — calibration-done flag

A single coefficient update therefore costs 4–5 internal I²C transactions
(microseconds each) followed by a calibration poll, not a single APB store.

## Is it sigma-delta noise-shaped?

Probably yes — the marketing/datasheet wording is "low-noise fractional-N
audio PLL", the field naming (`sdm0/1/2`) literally calls it a sigma-delta
modulator, and the chip-level use case (audio MCLK at 12.288/22.5792 MHz)
would be unusable with a 1st-order accumulator's spurs. But:

- **Order, dither, and topology are not publicly documented.**
- **Phase-noise / spur specs are absent** from both TRM and datasheet.
- There is no user-visible knob to choose modulator order, dither amplitude,
  or shaping characteristic.
- A `sdm_stop` magic value changes between silicon revisions (`0x69` on rev0,
  `0x49` on rev1), implying the Espressif analog team tunes the modulator
  per-revision without exposing what's behind it.

The 24-bit fractional word is the *target ratio*; the actual sigma-delta
switching of the integer divider happens inside the analog macro and is not
under software control.

## Static resolution

With `xtal = 40 MHz`, the VCO-side step is `40 MHz / 65536 ≈ 610.35 Hz`.
After the post-divider:

| f_out                          | (o_div+2)·2 | Step at output |
| ------------------------------ | ----------- | -------------- |
| 12.288 MHz (48 kHz × 256)      | 40          | ≈ 15.3 Hz      |
| 11.2896 MHz (44.1 kHz × 256)   | 44          | ≈ 13.9 Hz      |
| 22.5792 MHz (44.1 kHz × 512)   | 22          | ≈ 27.7 Hz      |
| 24.576 MHz (96 kHz × 256)      | 20          | ≈ 30.5 Hz      |

Roughly 1 ppm steady-state tuning resolution at standard audio MCLKs.

## Runtime retuning — the catch

The ESP-IDF flow for *any* coefficient change is:

1. Disable consumers of APLL_CLK.
2. Compute new `(o_div, sdm0, sdm1, sdm2)`.
3. Write each of the four fields over the analog-I²C bus.
4. Run `clk_ll_apll_set_calibration()` — writes `I2C_APLL_IR_CAL_DELAY` with
   the sequence `0x0f, 0x3f, 0x1f`.
5. Poll `I2C_APLL_OR_CAL_END` until set (`clk_ll_apll_calibration_is_done`).
6. Re-enable consumers.

Total wall-clock latency per change is on the order of tens of microseconds,
and during steps 3–5 the output is **not specified glitch-free**.

There is **no documented "live" path** that updates only the fractional bytes
(`sdm0`, `sdm1`) without recalibration — the way Si5351's NUM/DEN can be
nudged on-the-fly, or the way STM32H7's FRACN1 takes runtime updates without
a relock.

Empirically (ESP32 forum reports), some users *have* updated only the
fractional bytes and skipped calibration with acceptable audible results, but:

- That is outside the supported flow.
- Espressif gives no spec for behavior under such updates.
- There's no guarantee the analog loop filter accommodates it cleanly across
  process/voltage/temperature.

## When the APLL is a good fit

- Setting a fixed, non-stock audio MCLK once at boot (48 kHz family or
  44.1 kHz family) — ~15 Hz of trim is plenty.
- Periodic, infrequent retuning where a sub-millisecond drop-out is OK.

## When it isn't

- Adaptive sample-rate tracking that needs continuous, sub-Hz live updates
  (USB-audio sync, recovered word-clock without ASRC, network audio with
  PLL-on-PLL). On STM32H7 the FRACN1 is structurally better here; the P4's
  APLL is not designed for that pattern.
- Anything that needs a published phase-noise mask or jitter spec — there
  isn't one.

## Code pointers

- ESP-IDF P4 LL header: `components/hal/esp32p4/include/hal/clk_tree_ll.h`
  (`clk_ll_apll_set_config`, `clk_ll_apll_set_calibration`,
  `clk_ll_apll_calibration_is_done`).
- ESP-IDF P4 RTC clock: `components/esp_hw_support/port/esp32p4/rtc_clk.c`
  (`rtc_clk_apll_coeff_calc`, `rtc_clk_apll_coeff_set`).
- TRM §10 (Reset and Clock), §45 (Analog I2C Controller), §46 (I2S).

## Open questions / experiments worth running on real silicon

- Does writing only `sdm0`/`sdm1` and skipping `clk_ll_apll_set_calibration`
  produce a phase-continuous output? Measure with a fast scope on the I2S
  MCLK pin while sweeping `sdm0` in unit steps.
- What is the actual settling time of `clk_ll_apll_calibration_is_done`
  across the supported output range?
- Phase-noise floor at, say, 12.288 MHz output vs. the same output sourced
  from `PLL_F160M_CLK` divided down — to see whether the APLL is actually a
  cleaner source for audio.

## Sources

- ESP32-P4 Technical Reference Manual (Pre-release):
  <https://documentation.espressif.com/esp32-p4_technical_reference_manual_en.pdf>
- ESP32-P4 Series Datasheet:
  <https://www.espressif.com/sites/default/files/documentation/esp32-p4_datasheet_en.pdf>
- ESP-IDF Clock Tree (P4):
  <https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/api-reference/peripherals/clk_tree.html>
- ESP-IDF I2S (P4):
  <https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/api-reference/peripherals/i2s.html>
- ESP-IDF source (master):
  <https://github.com/espressif/esp-idf>
