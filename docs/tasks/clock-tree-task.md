# Task: MCU Clock-Tree Specification (YAML) for sodaCat

**Goal**  
Produce a machine-checkable, vendor-agnostic YAML description of an MCU’s clock tree
that sodaCat can use to generate headers and frequency resolvers.

**Output format**  
- YAML document conforming to `schemas/clock-tree.schema.json`
- Place new families under `spec/clock-tree/<vendor-or-series>/<family>.yaml`  
  (e.g., `spec/clock-tree/st/stm32h7.yaml`)

---

## Required content

### Frequency Specification Guidelines
- All frequency values must be expressed in **Hz**.
- If source material provides values in kHz or MHz, convert them:
  - `1 kHz = 1,000 Hz`
  - `1 MHz = 1,000,000 Hz`

1. **Distinct signals**  
   Model any clock that can be *gated*, *muxed*, or *divided* as its own `signals[]` entry:
   - Oscillators (HSI/CSI/HSE/HSI48/LSE/LSI, etc.)
   - PLL inputs (after DIVM), VCO, and P/Q/R outputs
   - SYSCLK and bus clocks (D1CPRE/HPRE/APB prescalers)
   - Representative kernel clocks per peripheral
   - MCO outputs (optional but recommended)

2. **Sources**  
   List each top-level oscillator under `sources[]` with its output signal names.

3. **Muxes, dividers, gates**  
   - **Muxes:** `muxes[]` with `reg`, `field`, and an `inputs` array.
     Each mux must declare a single output signal name using the output field.
     The inputs array length must be a power of two, determined by the bitfield width.
     Each index corresponds to a bit pattern:
     * Valid signal names select that input.
     * Use "" for off states.
     * Use "-reserved-" for reserved bit patterns.  
   - **Dividers:** `dividers[]` with `reg/field` and `factors` or `range`.  
   - **Gates:** `gates[]` with `reg/bit` to map bus/peripheral clock enables.

4. **Frequency limits**  
   Attach constraints to the **producing nodes**:
   - Oscillator ranges (e.g., HSE 4–48 MHz)
   - PLL ref window (e.g., 1–16 MHz after DIVM)
   - VCO ranges (e.g., 192–960 MHz or device-specific alt ranges)
   - Domain maxima (e.g., bus matrix ≤ 200 MHz)
   - Any per-peripheral kernel clock minima/maxima

5. **Descriptions**  
   Provide a concise `description` per signal/block summarizing the manual’s intent.  
   Use `notes` for device- or package-specific caveats.

6. **Device dependencies**  
   If a limit varies across SKUs, say so in `notes` and link to the datasheet section.

---


4. **Frequency limits**
Attach constraints to the **producing nodes**:
- Oscillator ranges (e.g., HSE: `min_hz: 4_000_000`, `max_hz: 48_000_000`)
- PLL reference window (e.g., `min_hz: 1_000_000`, `max_hz: 16_000_000` after DIVM)
- VCO ranges (e.g., `min_hz: 192_000_000`, `max_hz: 960_000_000`; use `ranges_hz` for conditional ranges)
- Domain maxima (e.g., bus matrix `max_hz: 200_000_000`)
- Any per-peripheral kernel clock minima/maxima


- Signals: `lower_snake_case` (e.g., `hse_ck`, `pll1_p_ck`, `sys_ck`).
- Register names: exact RM names (e.g., `RCC_CFGR`, `RCC_PLLCKSELR`).
- Fields/bits: exact RM names (e.g., `SW`, `PLLSRC`, `DIVM1`, `HSION`).
- Keep **inputs** and **outputs** consistent with the RM block diagrams.

---

## Acceptance criteria

- YAML validates against `schemas/clock-tree.schema.json`.
- No missing `reg/field/bit` for muxes/dividers/gates.
- All producing nodes with limits include `frequency`/`frequency_limit`.
- A minimal set of kernel examples (at least one timer/serial/storage/USB or ETH).

---

## Example workflow (for a new family)

1. Duplicate template `spec/clock-tree/templates/clock-tree.template.yaml`.
2. Fill in oscillators, PLLs (ref, VCO, P/Q/R), SYSCLK, prescalers.
3. Add 2–5 representative kernel muxes (USART/I2C/SAI/SDMMC/USB/ETH).
4. Run validation:  
   ```bash
   python tools/validate_clock_specs.py \
     --schema schemas/clock-tree.schema.json \
     --docs "spec/clock-tree/**/*.y*ml"
5. Open PR with a short note: RM ID, sections used, and known device caveats.
