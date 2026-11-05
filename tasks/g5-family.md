# Task: STM32G5 family

Status: **Done (2026-11-05): family, shared-model extensions, timers in TimerV2.**

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

- [x] Timers folded into TimerV2 (2026-11-05).  TimerV2 is now sourced
      from G564 TIM1 (a superset of N645's), and the new param `gen` (1 = G5)
      together with the existing flags describes the additions;
      `max_channel` goes up to 6 for the 7th channel.  Split fields are named
      `<field>_1` project-wide (SMS_1, OCxM_1, MMS_1, TS_1; was `_3`) in
      TimerV1, TimerV2 and the F3 AdvCtrlTimer (user decision).  G5's timer
      params are derived by tools/g5_family/timer_params.py.  Other families'
      chips are unchanged apart from the order of the timer connections.
      Pre-existing gap noted: G4 TIM16/17 OR1.HSE32EN is not in TimerV2.
- [ ] GTZC is not modelled (same as H5).
