# Task: Restructure the STM32H5 block models (and add STM32H543/H553)

Status: **Phase A done and verified (2026-11-05); Phase B not started.**
Started 2026-11-04.

## Why

Adding STM32H543/H553 exposed that the H5 models were wrong for most
existing chips:

- No H5 block had `variants:`, so one model per block served all three
  subfamilies (H503, H52x_H57x, H5Ex_H5Fx). The non-secure alias of
  RCC/PWR/EXTI/Flash/SBS/DBGMCU/RAMCFG/... on every H52x_H57x chip got the
  **H503** register layout (RCC: 200+ fields off).
- 29 blocks had a separate `X_S` (secure alias) block. Their models were
  **empty**: in the H523 SVD each `X_S` is `derivedFrom` `X`, and the
  extractor emitted `'@derivedFrom': X` and `registers: []`.
- H562/H563/H573 name secure aliases `SEC_X`; nothing claimed them.

## Decisions (user, 2026-11-04)

1. **Keep three subfamilies.** H52x_H57x stays as one subfamily, even though
   it spans three dies (H523/533 · H562/563/573 · H543/553, all in RM0481).
   Differences inside it are handled by **superset models plus per-chip
   feature-flag params** (see docs/design/feature-flag-params.md and
   tasks/shared-block-unification.md), not by splitting the subfamily.
2. **Fold aliases.** `X`, `X_S` and `SEC_X` are instances of one block. This
   was verified on all 13 H5 chips (incl. H543/H553): the secure and
   non-secure aliases are register-identical, with 0 mismatches.
3. **Interim variant sources** (Phase A, until Phase B picks supersets):
   H573 for H52x_H57x and H5F5 for H5Ex_H5Fx; H503 stays the base.
4. **H543/H553 join H52x_H57x**, SVDs from the Open-CMSIS-Pack DFP via
   `svd.supplement` (commit e699aaa7). They are not yet listed as chips.
5. **H7P deferred** until ST publishes an SVD. RM0533 Rev. 1 (and RM0481
   Rev. 5) are in `docs/ST/` (local, gitignored); the datasheet is in the
   user's Databook folder.

## Phase A (done, WIP)

- 29 `X_S` blocks folded; `SEC_X` instances added to 47 blocks.
- Variants for ADC, COMP, DAC, DBGMCU, EXTI, Flash, PWR, RAMCFG, RCC, SBS.
- Flash/RCC: secure vectors (`FLASH_S`=7, `RCC_S`=10) declared as `INTR_S`
  (precedent: DMAMUX `OVR_S`). `RTC_S` belongs to the shared `RTC_V2` block,
  so it was left unmatched.
- chip_params: alias instances mirror their partner's instance-level params.
  This fixed TIM2_S/TIM5_S/TIM15_S, added TIM3_S/TIM4_S, and added SEC_*.
  Block-level keys already cover aliases.
- 57 stale/unreferenced H5 model files deleted.

**Verification (2026-11-05):**
- [x] Compile check: `test/h5/` builds every H5 chip, one binary dir per
      subfamily (target `soc-data-h5`, a dependency of `soc-data-test`).
      This needed `generate_header()` dedup to be scoped per binary
      directory: previously a dependency already generated in another
      directory was skipped and its module was invisible to the target.
- [x] Coverage, `model_vs_svd.py <rev> --covers` (bit-level: every SVD
      field's bits must be covered by model fields at the same offset):
      family blocks 55/285 before Phase A → 206/222; shared blocks
      811/974 → 1096/1324, with the same failing set as before once alias
      instances are folded (Phase A touched no shared model).
- [x] `RTC_S`: the H5 RTC entry now declares `S` (shared RTC_V2 canonical,
      as on L5/U5).  The H562/H563/H573 SVDs carry no RTC interrupts at
      all; wired via `chip_connections` (see SVD_ERRATA.md).

**Remaining coverage gaps** (input for Phase B, `--covers` output):
- Family, H523/H533 only (interim H573 source): RCC I3C2RST/EN/LPEN and
  CCIPR4.I3C2SEL; RAMCFG M2WPR3; EXTI line 58 (IMR2/EMR2); PWR
  PMCR.SRAM1SO.
- Shared, pre-existing: ICACHE CRR0–3 (all chips), SDMMC (−15, all),
  TAMP (−4), LPTIM (−1), RTC_V2 (−1), TimerV2 TIM17 (−1), HASH HR16–31
  and RNG (H5Ex_H5Fx), ModernSPI (−1, H5Ex_H5Fx), ETH (−2, H563/H573),
  AES_V3/SAES (−1, H573).

## Phase B (todo): supersets inside H52x_H57x

There are 31 blocks with more than one layout inside H52x_H57x, 19 of them
cross-family shared blocks. A change to a shared block requires regenerating
and auditing every consuming STM32 family (see memory
"shared-block-cross-family-regen"). Classify each difference against
RM0481 first: SVD bug, generation difference or cosmetic. Some differences
look editorial, e.g. HFSEL0/1 vs HFSEL and REG_ vs REGx_.

Layout groups inside H52x_H57x (chip suffixes; `|` separates layouts):

| Block | Kind | Groups |
|---|---|---|
| RCC | family | 23+33 \| 43+53 \| 62 \| 63 \| 73 |
| PWR, SBS | family | 23+33 \| 43+53 \| 62 \| 63+73 |
| DBGMCU, EXTI | family | 23+33 \| 43+53 \| 62+63+73 |
| ADC | family | 23+33+62+63+73 \| 43+53 |
| DAC, Flash, RAMCFG | family | 23+33+43+53 \| 62+63+73 |
| OTFDEC | family | 33 \| 53+73 |
| CRC, HASH, I3C, UCPD | shared | 23+33 \| 43+53 \| 62+63+73 |
| SAES | shared | 33 \| 53 \| 73 |
| AES (AES_V3) | shared | 33+53 \| 73 |
| ETH | shared | 43+53 \| 63+73 |
| ICACHE, RNG, SPI (ModernSPI) | shared | 23+33+62+63+73 \| 43+53 |
| PKA | shared | 33+73 \| 43+53 |
| FDCAN, Timer (TimerV2), IWDG, LPTIM, LPUART/USART, OCTOSPI (XSPI), SDMMC, TAMP | shared | 23+33+43+53 \| 62+63+73 |

H543/H553 carry newer IP than H523/H533:
- CRC: RTYPE_IN/OUT, and REV_OUT widens.
- HASH: HR16–31.
- PKA: CMF/CCEN/....
- ICACHE: HWCFGR.
- RNG: HTCR0–3.
- RCC: no FMAC/DCMI/GPIOI/PLL3; adds ADC3/CCB/ETH enables.
- PWR, SBS (ETH bits), EXTI (no EXTICR).
- SAES: fewer key fields.

## H543/H553 (after Phase B)

- Add both chips to H52x_H57x `chips:` (the supplement is already configured).
- Peripherals with no block yet: **ADC3**, **ADCC12/ADCC3** (H533/H563 call
  the common block `ADCC`), **CEC** (shared `ST/CEC` exists), **PLAY** and
  **CCB** (H553). GTZC1_* is unmodelled on all H5 chips, so it isn't new.

## Separate bug: empty derivedFrom models

When a block's `from:` peripheral is `derivedFrom` another, the extractor
writes `registers: []`. Besides the old H5 `_S` models, this affects
real chips:
- `ST/L4/USB`: 7 L41x/L43x chips.
- `ST/H7/FDCAN3`: H73x.
- `Microchip/PORT_AHB`: PIC32CZ CA80/CA90.

Fix this in the extractor (resolve `derivedFrom` to the base's registers),
not per family. Find affected models with `grep -rl "^'@derivedFrom'" models`.

## Tools

`tools/h5_restructure/` holds the analysis scripts from this session. Run
them from the repo root with a Python that has ruamel.yaml; they need the
supplement checkout in `build/_deps/stm32h5_svd_supplement-src`.

- `h5_layouts.py`: SVD loading and layout normalisation (alias folding,
  register-prefix stripping). The other scripts reuse it.
- `h5_plan.py`: the per-block, per-subfamily layout table above.
- `cmp_blocks.py`: new chips versus each block's `from:` source.
- `h5_phaseA_plan.py` / `h5_phaseA_apply.py`: the Phase A config edit
  (fold, SEC_ instances, variants). They are kept for reference, already
  applied, and not idempotent.
- `model_vs_svd.py WORK|<git-rev> [--covers]`: whether chip instance models
  match their own SVD (exact field positions), or with `--covers` whether
  they cover every SVD field bit.  Takes ~3 min.
