# Task: STM32G5 family

Status: **First version done (2026-11-05).  Open: timer unification with TimerV2.**

## Sources

- SVDs: ST's GitHub device family pack `STMicroelectronics/stm32g5xx-dfp`
  2.0.0 (no G5 archive on st.com yet), pinned in `svd.supplement` by tag
  and sha256.  `stm32_add_family()` accepts a family with no ZIP for this
  case; when ST publishes `stm32g5-svd.zip`, `tools/st_maintenance.py svd`
  lists it as unregistered.  Add `zip:` then, and drop chips from the
  supplement as the archive covers them (the extractor reports this).
- RM0514 Rev. 1; datasheets G534/G544 in the user's Databook folder.

## Structure

Two dies, two subfamilies: G53x_G54x (G534, G544) and G55x_G56x (G553, G554,
G563, G564).  Within a die the parts differ only in presence: HRTIM on Gxx4,
AES on G544/G563/G564, SAES/CCB/OTFDEC on G563/G564.

- Shared models are used wherever they fit (40 blocks).  G5-local blocks
  (ADC, ADC_Common, COMP, DAC, DBGMCU, EXTI, Flash, HRTIM, POSENC, PWR,
  RAMCFG, RCC, SBS, Timer) are sourced from G564 and merged with the other
  parts (mergeFrom).  G564 turned out to be a superset everywhere.
- Shared models promoted on the way (user decision): CCB, DTS, OTFDEC
  (params has_cr/has_privcfgr), PLAY, USBSRAM, TCOPAMP (C53x/C54x and G5
  op-amp; C55x/C56x now correctly use HSOPAMP).
- Shared models extended for G5, checked against RM0514: BasicTimer UIOVRF
  (SR now 32 bits), ICACHE/DCACHE ECC, GPDMA drain bits, TAMP ITAMP14 /
  RPCFG6-8 / OR_Remap3 (or_reg 5), and IWDG gen 4 (EWIF at SR[15] plus ICR;
  N6 now uses the shared IWDG as well).
- Coverage: 1148/1168 chip instances.  Deliberately left out: I3C BCR1/3/4/5
  (hardware-fixed per RM0514) and XSPI ADOFF/BERR (not in RM0514).

## Open

- [ ] Timers (user decision: G5-local first).  The G5 `Timer` block is TIM1
      with 32-bit CNT/ARR/CCR1-4, covering TIM1-5, 8-17 and 20.  G5's timers
      are a newer TimerV2 generation: they only add or widen fields, with no
      conflicts (7th channel, MMS2/SMS/OCxM/ETRSEL/OCRSEL wider, CKD2,
      TIxINV/TIxFS, UIOVRF, BKCMP9-14, MPR registers...).  Fold into
      TimerV2: switch its source if G5 TIM1 is a superset of N645's,
      otherwise patch; add params; regenerate ~14 families.  Analysis
      scripts: tools/g5_family/ (tconf.py classifies the timer fields).
- [ ] GTZC is not modelled (same as H5).
