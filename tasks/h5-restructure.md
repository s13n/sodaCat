# Task: Restructure the STM32H5 block models (and add STM32H543/H553)

Status: **Phase A done (2026-11-05).  Phase B: family blocks, H543/H553, per-part presence and ETH done; other shared blocks open.**
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

## Phase A (done)

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

## Phase B (in progress): supersets inside H52x_H57x

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

### Phase B findings: bits that genuinely differ (2026-11-05)

User guidance: bits present only on some chips need no union. They go
into the superset, and their description names the chips that have them;
drivers must not touch them elsewhere.  Only bits/registers whose meaning
or position differs between chips need a union.  Field names follow RM0481.

`h5_conflicts.py` compares all die groups (incl. H543/H553) bit by bit.
Outcome:

- **Genuine, needs a union:**
  - PWR PMCR bits 23–27: H56x has SRAM2_16SO@24, SRAM2_48SO@25 and
    SRAM1SO@26.  H52x/H54x have SRAM2_16LSO@24, SRAM2_16HSO@25,
    SRAM2_48SO@26 and SRAM1SO@27.  RM0481 has PWR_PMCR plus two
    "[alternate] PWR_PMCR" sections (pp. 460/462/464), and the H523 SVD
    already encodes PMCR + PMCR_ALTERNATE1 (alternateRegister).
  - ETH (shared) DMACMFCR: 0x116C on the RM0481 ch. 63 IP (H563/H573,
    and H7), 0x1164 on the ch. 64 IP (H543/H553; also H5Ex, which is the
    shared model's source).  The shared model is therefore wrong for
    H7/H563/H573 today.  The offsets don't overlap, so this needs two
    names, not overlaid views.
- **SVD bugs (no union):**
  - RCC AHB2ENR SRAM2EN/SRAM3EN are swapped in the H56x SVDs; RM0481 has
    a single description (SRAM3EN=31, SRAM2EN=30).  The current
    H52x_H57x RCC model has the bug.
  - EXTI: the H523/H533 SVDs place EXTICR4 at 0x060; the H543/H553 SVDs
    omit EXTICR1–4, which RM0481 documents for all dies.
- **Widenings (superset = wider field):** RCC CFGR1.SW/SWS, CRC REV_OUT,
  HASH NBWE/NBWP, I3C SDA_HD, SBS ETH_SEL_PHY, TAMP ATCKSEL, ETH
  ACTPHYSEL.
- **Naming only:** RCC (ADC12/ADC, FDCAN12/FDCAN, USBFS/USB, DIVMx/PLLxM,
  VREF/VREFBUF, UCPD/UCPD1, USART12SEL/UART12SEL), Flash SECWM2,
  DAC HFSEL, ADC EXTSEL split, SBS FMP/FMPLUS, OTFDEC REGx_, TAMP
  POM/NOER and RPCFGR/ERCFGR (RM: POM, RPCFGR), I3C SMODE/RMODE (RM:
  SMODE), OCTOSPI MSEL/FSEL (RM: MSEL), and the per-die SVD spellings
  of the existing USART/LPUART/LPTIM/Timer/I3C alternate-register views.

### Phase B progress (2026-11-05)

Mechanism: new `mergeFrom` transform (see CLAUDE.md, Transformation
framework).  Each H52x_H57x variant takes a source chip and merges the
other dies.  Bits that differ only in presence stay in the model with an
"Only on <chips>." note.

Done:
- [x] RCC (source H533, merge H573+H553; SW/SWS restored to 2 bits), PWR
      (source H533 with PMCR + PMCR_ALT1, param `pmcr_alt1`), EXTI (H573 +
      H553, EXTICR presence override), DBGMCU, SBS, Flash, RAMCFG, ADC,
      COMP (new H52x_H57x variant from H553: dual comparator, identical to
      H5F5).  Source chips were chosen so field names match RM0481.
- [x] H543/H553 added to H52x_H57x and to test/h5.  New blocks: CCB
      (H553), PLAY (both vectors on the base instance), CEC (shared ST/CEC,
      which also gives H5Ex its CEC).  ADC3 joins ADC and ADCC12/ADCC3 join
      ADC_Common.  The `_S` aliases of numbered instances (ADC1_S, SPI1_S,
      ...) are added, with mirrored chip_params.  ICACHE vector `ICACHE1`
      is mapped.  Phantom TIM13/TIM14 are excluded.
- [x] SVD_ERRATA.md entries for all of the above.

Open:
- [x] Presence notes per part (2026-11-05): the datasheets are in
      C:\Databook\ST\Processor (WSL: /mnt/c/Databook/ST/Processor), and
      ST's CMSIS device headers are on GitHub (STMicroelectronics/
      cmsis-device-h5).  The chip instance lists were checked against both.
      CEC was added (5 parts), PKA added (H523/H562/H563), TIM12 added
      (H523), and FDCAN2/DLYBSD2 excluded on H562.  RCC/DBGMCU notes for
      peripheral bits follow the instance lists (`presence: {instance}`);
      bits without an instance keep their SVD-derived notes.  Remaining
      differences against the headers are naming only.
- [x] Instance names numbered within H52x_H57x (`rename_instances`; user
      decision: H52x_H57x only, H503/H5Ex keep their SVD names for now).
- [x] Fixed: SPI4-6 had has_i2s=true through the block-level `SPI` key.
- [x] ETH (shared, 2026-11-05): DMACMFCR_V1 @0x116C + int param `gen`
      (1: RM0481 ch. 63 IP - H563/H573, H7, H7RS; 2: ch. 64 IP - H543/H553,
      H5Ex, C5).  The address block is extended to 0x1170, ACTPHYSEL is
      widened to 4 bits (SVD bug), and H543/H553 get the missing
      has_mdio_intr.  H7/H7RS/C5/H5 regenerated.  ETH now covers every SVD
      field on H563/H573/H553/H5F5/H7RS.
- [x] ETH on C5: MAC10BT1SCR (10BASE-T1S PMD transceiver control, 0x220)
      is deliberately not modelled until RM0522 documents it (user
      decision 2026-11-05; see SVD_ERRATA.md, C5).
- [ ] Shared-block presence gaps (ICACHE CRR, SDMMC, TAMP, HASH, RNG,
      ...): mergeFrom with `annotate: false`, cross-family regen.
- [ ] Cosmetic: the H52x_H57x RCC lists output INTR_S before INTR,
      because outputs follow the source SVD's interrupt order.

## H543/H553 (done 2026-11-05; original plan)

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
- `h5_diff.py <PERIPH> [ref chip]`: field-level diff of one block across
  the H52x_H57x die groups.
- `h5_conflicts.py`: classifies every per-die difference (regmove, moved,
  clash, regname, widen, split, rename); only the first three can need a
  union.
- `model_vs_svd.py WORK|<git-rev> [--covers]`: whether chip instance models
  match their own SVD (exact field positions), or with `--covers` whether
  they cover every SVD field bit.  Takes ~3 min.
