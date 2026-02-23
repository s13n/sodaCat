# GpTimer Hardware Comparison Across STM32 Families

All 17 families source GpTimer from TIM2 (4-channel, 32-bit superset).
The core register set (CR1–CCR4, offsets 0x00–0x40) is identical across all families.
Differences are in bitfields within core registers, option/configuration registers,
and DCR/DMAR placement.

## Feature Catalog

### Core register features (bitfields in CR1/CR2/SMCR/CCMR)

| Feature | Register.Field | Description |
|---------|---------------|-------------|
| **UIFREMAP** | CR1.UIFREMAP (bit 11) | UIF status bit remapping to CNT bit 31, enables atomic overflow detection |
| **DITHEN** | CR1.DITHEN (bit 12) | Dithering enable — adds 4 fractional bits to ARR/CCRx for sub-LSB PWM resolution |
| **SMS_ext** | SMCR.SMS_3 (bit 16) | 4th bit of slave mode selection (8→16 slave modes) |
| **TS_ext** | SMCR.TS_4_3 (bits 20-21) | Extended trigger selection (3→5 bits, more trigger sources) |
| **OCM_ext** | CCMRx.OCxM_3 (bit 16/24) | 4th bit of output compare mode (8→16 modes, adds asymmetric/combined PWM) |
| **MMS_ext** | CR2.MMS_1 (bit 25) | 4th bit of master mode selection (8→16 master modes) |
| **OCCS** | SMCR.OCCS (bit 3) | OCREF clear source selection (ETRF vs comparator/other) |
| **SMSPE** | SMCR.SMSPE (bit 24) | SMS preload enable — preload slave mode bits on update/index event |
| **CNT_V2** | CNT @0x024 (alternate) | Alternate counter register view with UIFCPY at bit 31 (companion to UIFREMAP) |

### Option/configuration registers

| Register | Description |
|----------|-------------|
| **OR** | Legacy option register (ITR1 remap, TI4 remap). Gen1 families only. |
| **OR1** | Option register 1 (ETR remap, TI1 remap, OCREF_CLR source). Gen2-3 transition. |
| **OR2** | Option register 2 (ETR source select). Gen2 families. |
| **ECR** | Encoder control register (index signal: direction, position, pulse width). Gen4 only. |
| **AF1** | Alternate function register 1 (ETR source select). Gen3+ replaces OR-based ETR routing. |
| **AF2** | Alternate function register 2 (OCRSEL — OCREF clear source select). Gen4 only. |
| **TISEL** | Timer input selection (TI1SEL–TI4SEL mux). Gen3+ replaces OR-based input routing. |
| **DCR/DMAR** | DMA control/address registers for burst transfers. Present on most instances. |

### Encoder index feature group (Gen4 only, tied to ECR)

ECR, SMSPE, MMS_ext, and the following SR/DIER bits form a coherent encoder index feature:
- DIER: IDXIE, DIRIE, IERRIE, TERRIE (index/direction/error interrupts)
- SR: IDXF, DIRF, IERRF, TERRF (corresponding status flags)

## Timer IP Generation Classification

| Generation | Families | Core features | Config registers | DCR offset |
|-----------|----------|---------------|-----------------|-----------|
| Gen1 | F4, L0, L1 | (base) | OR @0x50 | 0x48 |
| Gen1.5 | F3 | +UIFREMAP, +SMS_ext, +OCM_ext | OR @0x50 (F37x only) | 0x48 |
| Gen2 | F7 | +UIFREMAP, +SMS_ext, +OCM_ext | OR @0x50 | 0x48 |
| Gen2.5 | L4, L5 | +UIFREMAP, +SMS_ext, +OCM_ext, +OCCS | OR1 @0x50, OR2 @0x60 | 0x48 |
| Gen2.75 | L4P | +TS_ext, +CNT_V2 | OR1 @0x50, OR2 @0x60 | 0x48 |
| Gen3 | C0, G0, H7 | +TS_ext (±CNT_V2, ±OCCS) | AF1 @0x60, TISEL @0x68 (±OR1) | 0x48 |
| Gen3.5 | U0 | +OCCS, +CNT_V2 | OR1 @0x50, AF1 @0x60, TISEL @0x68 | 0x48 |
| Gen4 | G4, H5, N6, U3, U5 | +DITHEN, +MMS_ext, +SMSPE, +ECR | ECR @0x58, TISEL @0x5C, AF1 @0x60, AF2 @0x64 | **0x3DC** |

## Per-Instance Parameter Values

Parameter values for every GpTimer instance across all 17 families. Values in
parentheses are defaults (inherited, nothing to configure); bare values are
explicit overrides. Columns only appear when at least one instance has a
non-default value.

### C0

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst | compl |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|:-----:|
| TIM2     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM3     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM14    | (N)     | 1   | N         | (0)     | N   | N   | 0         | (N)   |
| TIM15    | (N)     | 2   | N         | (0)     | (Y) | N   | (1)       | Y     |
| TIM16    | (N)     | 1   | N         | (0)     | N   | N   | (1)       | Y     |
| TIM17    | (N)     | 1   | N         | (0)     | N   | N   | (1)       | Y     |

### F3

F3 has per-subfamily instance differences (F37x has TIM5/TIM12–14/TIM19;
F30x/F302/F303/F334 have TIM15–17).

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst | compl | Notes |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|:-----:|-------|
| TIM2     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |       |
| TIM3     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |       |
| TIM4     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |       |
| TIM5     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   | F37x  |
| TIM12    | (N)     | 2   | N         | (0)     | N   | N   | 0         | (N)   | F37x  |
| TIM13    | (N)     | 1   | N         | (0)     | N   | N   | 0         | (N)   | F37x  |
| TIM14    | (N)     | 1   | N         | (0)     | N   | N   | 0         | (N)   | F37x  |
| TIM15    | (N)     | 2   | N         | (0)     | (Y) | N   | (1)       | Y     | F30x+ |
| TIM16    | (N)     | 1   | N         | (0)     | N   | N   | (1)       | Y     | F30x+ |
| TIM17    | (N)     | 1   | N         | (0)     | N   | N   | (1)       | Y     | F30x+ |
| TIM19    | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   | F37x  |

### F4

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|
| TIM2     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       |
| TIM3     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       |
| TIM4     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       |
| TIM5     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       |
| TIM9     | (N)     | 2   | N         | (0)     | N   | N   | 0         |
| TIM10    | (N)     | 1   | N         | (0)     | N   | N   | 0         |
| TIM11    | (N)     | 1   | N         | (0)     | N   | N   | 0         |
| TIM12    | (N)     | 2   | N         | (0)     | N   | N   | 0         |
| TIM13    | (N)     | 1   | N         | (0)     | N   | N   | 0         |
| TIM14    | (N)     | 1   | N         | (0)     | N   | N   | 0         |

### F7

F7 has per-subfamily param differences: F72x_F73x has `has_uifremap` and
`has_extended_ocm` on all instances.

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst | uifremap* | ext_ocm* |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|:---------:|:--------:|
| TIM2     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | Y         | Y        |
| TIM3     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | Y         | Y        |
| TIM4     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | Y         | Y        |
| TIM5     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | Y         | Y        |
| TIM9     | (N)     | 2   | N         | (0)     | N   | N   | 0         | Y         | Y        |
| TIM10    | (N)     | 1   | N         | (0)     | N   | N   | 0         | Y         | Y        |
| TIM11    | (N)     | 1   | N         | (0)     | N   | N   | 0         | Y         | Y        |
| TIM12    | (N)     | 2   | N         | (0)     | N   | N   | 0         | Y         | Y        |
| TIM13    | (N)     | 1   | N         | (0)     | N   | N   | 0         | Y         | Y        |
| TIM14    | (N)     | 1   | N         | (0)     | N   | N   | 0         | Y         | Y        |

*F72x_F73x only; F74x_F75x and F76x_F77x use defaults (false).

### G0

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst | compl |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|:-----:|
| TIM2     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM3     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM4     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM14    | (N)     | 1   | N         | (0)     | N   | N   | 0         | (N)   |
| TIM15    | (N)     | 2   | N         | (0)     | (Y) | N   | (1)       | Y     |
| TIM16    | (N)     | 1   | N         | (0)     | N   | N   | (1)       | Y     |
| TIM17    | (N)     | 1   | N         | (0)     | N   | N   | (1)       | Y     |

### G4

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst | compl | dither | sms_pre |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|:-----:|:------:|:-------:|
| TIM2     | Y       | (4) | (Y)       | 2       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM3     | (N)     | (4) | (Y)       | 2       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM4     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM5     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM15    | (N)     | 2   | N         | (0)     | (Y) | N   | 2         | Y     | Y      | (0)     |
| TIM16    | (N)     | 1   | N         | (0)     | N   | N   | 2         | Y     | Y      | (0)     |
| TIM17    | (N)     | 1   | N         | (0)     | N   | N   | 2         | Y     | Y      | (0)     |

### H5

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst | compl | dither | sms_pre |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|:-----:|:------:|:-------:|
| TIM2     | Y       | (4) | (Y)       | 3       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM3     | (N)     | (4) | (Y)       | 3       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM4     | (N)     | (4) | (Y)       | 3       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM5     | Y       | (4) | (Y)       | 3       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM12    | (N)     | 2   | N         | 3       | Y   | N   | 0         | (N)   | Y      | (0)     |
| TIM13    | (N)     | 1   | N         | (0)     | N   | N   | 0         | (N)   | Y      | (0)     |
| TIM14    | (N)     | 1   | N         | (0)     | N   | N   | 0         | (N)   | Y      | (0)     |
| TIM15    | (N)     | 2   | N         | (0)     | (Y) | N   | 2         | Y     | Y      | 1       |
| TIM16    | (N)     | 1   | N         | (0)     | N   | N   | 2         | Y     | Y      | (0)     |
| TIM17    | (N)     | 1   | N         | (0)     | N   | N   | 2         | Y     | Y      | (0)     |

### H7

H7 has per-subfamily instance differences: TIM23/TIM24 only exist on H73x
(RM0468). The other three subfamilies (H742_H753, H745_H757, H7A3_B) have
TIM2–TIM5 and TIM12–TIM17 only.

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst | compl | Notes |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|:-----:|-------|
| TIM2     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |       |
| TIM3     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |       |
| TIM4     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |       |
| TIM5     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |       |
| TIM12    | (N)     | 2   | N         | (0)     | N   | N   | 0         | (N)   |       |
| TIM13    | (N)     | 1   | N         | (0)     | N   | N   | 0         | (N)   |       |
| TIM14    | (N)     | 1   | N         | (0)     | N   | N   | 0         | (N)   |       |
| TIM15    | (N)     | 2   | N         | (0)     | (Y) | N   | (1)       | Y     |       |
| TIM16    | (N)     | 1   | N         | (0)     | N   | N   | (1)       | Y     |       |
| TIM17    | (N)     | 1   | N         | (0)     | N   | N   | (1)       | Y     |       |
| TIM23    | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   | H73x  |
| TIM24    | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   | H73x  |

### L0

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|
| TIM2     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       |
| TIM3     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       |
| TIM21    | (N)     | 2   | (Y)       | (0)     | N   | (Y) | 0         |
| TIM22    | (N)     | 2   | (Y)       | (0)     | N   | (Y) | 0         |

### L1

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|
| TIM2     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       |
| TIM3     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       |
| TIM4     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       |
| TIM5     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       |
| TIM9     | (N)     | 2   | N         | (0)     | N   | N   | 0         |
| TIM10    | (N)     | 1   | N         | (0)     | N   | N   | 0         |
| TIM11    | (N)     | 1   | N         | (0)     | N   | N   | 0         |

### L4

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst | compl |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|:-----:|
| TIM2     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM3     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM4     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM5     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM15    | (N)     | 2   | N         | (0)     | (Y) | N   | (1)       | Y     |
| TIM16    | (N)     | 1   | N         | (0)     | N   | N   | (1)       | Y     |
| TIM17    | (N)     | 1   | N         | (0)     | N   | N   | (1)       | Y     |

### L4P

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst | compl |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|:-----:|
| TIM2     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM3     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM4     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM5     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM15    | (N)     | 2   | N         | (0)     | (Y) | N   | (1)       | Y     |
| TIM16    | (N)     | 1   | N         | (0)     | N   | N   | (1)       | Y     |
| TIM17    | (N)     | 1   | N         | (0)     | N   | N   | (1)       | Y     |

### L5

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst | compl |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|:-----:|
| TIM2     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM3     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM4     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM5     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM15    | (N)     | 2   | N         | (0)     | (Y) | N   | (1)       | Y     |
| TIM16    | (N)     | 1   | N         | (0)     | N   | N   | (1)       | Y     |
| TIM17    | (N)     | 1   | N         | (0)     | N   | N   | (1)       | Y     |

### N6

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst | compl | dither | sms_pre |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|:-----:|:------:|:-------:|
| TIM2     | Y       | (4) | (Y)       | 3       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM3     | Y       | (4) | (Y)       | 3       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM4     | Y       | (4) | (Y)       | 3       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM5     | Y       | (4) | (Y)       | 3       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM9     | (N)     | 2   | N         | (0)     | Y   | N   | 0         | (N)   | Y      | (0)     |
| TIM10    | (N)     | 1   | N         | (0)     | N   | N   | 0         | (N)   | Y      | (0)     |
| TIM11    | (N)     | 1   | N         | (0)     | N   | N   | 0         | (N)   | Y      | (0)     |
| TIM12    | (N)     | 2   | N         | (0)     | Y   | N   | 0         | (N)   | Y      | (0)     |
| TIM13    | (N)     | 1   | N         | (0)     | N   | N   | 0         | (N)   | Y      | (0)     |
| TIM14    | (N)     | 1   | N         | (0)     | N   | N   | 0         | (N)   | Y      | (0)     |
| TIM15    | (N)     | 2   | N         | (0)     | (Y) | N   | 2         | Y     | Y      | 1       |
| TIM16    | (N)     | 1   | N         | (0)     | N   | N   | 2         | Y     | Y      | (0)     |
| TIM17    | (N)     | 1   | N         | (0)     | N   | N   | 2         | Y     | Y      | (0)     |

### U0

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst | compl |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|:-----:|
| TIM2     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM3     | (N)     | (4) | (Y)       | 1       | (Y) | (Y) | (1)       | (N)   |
| TIM15    | (N)     | 2   | N         | (0)     | (Y) | N   | (1)       | Y     |
| TIM16    | (N)     | 1   | N         | (0)     | N   | N   | (1)       | Y     |

### U3

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst | compl | dither | sms_pre |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|:-----:|:------:|:-------:|
| TIM2     | Y       | (4) | (Y)       | 3       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM3     | Y       | (4) | (Y)       | 3       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM4     | Y       | (4) | (Y)       | 3       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM15    | (N)     | 2   | N         | (0)     | (Y) | N   | 2         | Y     | Y      | 1       |
| TIM16    | (N)     | 1   | N         | (0)     | N   | N   | 2         | Y     | Y      | (0)     |
| TIM17    | (N)     | 1   | N         | (0)     | N   | N   | 2         | Y     | Y      | (0)     |

### U5

| Instance | width32 | ch  | centerPWM | encoder | xor | etr | dma_burst | compl | dither | sms_pre |
|----------|:-------:|:---:|:---------:|:-------:|:---:|:---:|:---------:|:-----:|:------:|:-------:|
| TIM2     | Y       | (4) | (Y)       | 2       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM3     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM4     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM5     | Y       | (4) | (Y)       | 1       | (Y) | (Y) | 2         | (N)   | Y      | 2       |
| TIM15    | (N)     | 2   | N         | (0)     | (Y) | N   | 2         | Y     | Y      | (0)     |
| TIM16    | (N)     | 1   | N         | (0)     | N   | N   | 2         | Y     | Y      | (0)     |
| TIM17    | (N)     | 1   | N         | (0)     | N   | N   | 2         | Y     | Y      | (0)     |

### Parameter legend

| Abbreviation | Parameter | Default |
|--------------|-----------|---------|
| width32 | `width32` | false |
| ch | `channels` | 4 |
| centerPWM | `has_centerPWM` | true |
| encoder | `encoder` | 0 |
| xor | `has_xor_input` | true |
| etr | `has_etr` | true |
| dma_burst | `dma_burst` | 1 |
| compl | `has_complementary` | false |
| dither | `has_dither` | false |
| sms_pre | `sms_preload` | 0 |
| uifremap | `has_uifremap` | false |
| ext_ocm | `has_extended_ocm` | false |

Bare values = explicit overrides. `(parenthesized)` = default (no config needed).
`Y`/`N` = true/false, numbers = enum values.

## Parameters

Parameters control conditional compilation of registers and fields that vary
between timer instances. Each parameter is listed with the register/field
additions it gates.

### `width32` — 32-bit counter

| | |
|---|---|
| **Type** | bool |
| **Default** | false |
| **Families** | All 17 |

Controls the width of the counter and auto-reload registers.

| Condition | Register/field effect |
|-----------|---------------------|
| true | CNT, ARR, CCR1–CCR4 are 32-bit (full register width) |
| false | CNT, ARR, CCR1–CCR4 use only bits [15:0] (upper bits reserved) |

32-bit instances: TIM2 (all families), TIM5 (F3/F4/F7/G4/H5/L1/L4/L4P/L5/N6/U5),
TIM3/TIM4 (N6/U3/U5 only — upgraded in newer Gen4 silicon),
TIM23/TIM24 (H7 H73x only).

### `channels` — Number of capture/compare channels

| | |
|---|---|
| **Type** | int |
| **Default** | 4 |
| **Values** | 1, 2, 4 |
| **Families** | All 17 |

Controls which capture/compare channels and associated mode registers are present.

| Condition | Register/field effect |
|-----------|---------------------|
| channels=4 | CCR1–CCR4, CCMR1 (ch1+2), CCMR2 (ch3+4), CCER ch1–4 fields |
| channels=2 | CCR1–CCR2, CCMR1 only, CCER ch1–2 fields; no CCMR2/CCR3/CCR4 |
| channels=1 | CCR1 only, CCMR1 ch1 fields only; no CCMR2/CCR2–4 |

Also affects SMCR presence: instances with channels ≤ 1 typically lack SMCR
(no slave mode, no trigger input selection, no ETR).

### `has_uifremap` — UIF status bit remapping

| | |
|---|---|
| **Type** | bool |
| **Default** | false |
| **Families** | F7 only (currently); feature exists in all Gen1.5+ families |

Enables the UIF copy mechanism for atomic overflow detection in OS tick handlers.

| Condition | Register/field effect |
|-----------|---------------------|
| true | CR1: UIFREMAP (bit 11) present |
| true | CNT: bit 31 reads as UIFCPY (copy of UIF flag) when UIFREMAP=1 |

**Note:** This param currently only exists on F7 because F7 has a per-subfamily
split (F72x_F73x has it, F74x_F75x and F76x_F77x do not in the SVD — though
this may be an SVD omission since all F7 RMs document it). On all other families
with the feature, it's a family-level constant (always present or always absent).

### `has_extended_ocm` — Extended output compare mode bits

| | |
|---|---|
| **Type** | bool |
| **Default** | false |
| **Families** | F7 only (currently); feature exists in all Gen1.5+ families |

Adds the 4th bit to the output compare mode field, enabling 16 OC modes (including
asymmetric PWM, combined PWM mode, retriggerable OPM).

| Condition | Register/field effect |
|-----------|---------------------|
| true | CCMR1_Output: OC1M_3 (bit 16), OC2M_3 (bit 24) present |
| true | CCMR2_Output: OC3M_3 (bit 16), OC4M_3 (bit 24) present |

**Note:** Same situation as `has_uifremap` — only parameterized on F7, constant
on all other families.

### `has_dither` — Dithering (sub-LSB PWM resolution)

| | |
|---|---|
| **Type** | bool |
| **Default** | false |
| **Families** | Gen4 (G4, H5, N6, U3, U5) |

Enables sigma-delta dithering that adds 4 fractional bits to ARR and CCRx,
allowing finer PWM frequency/duty-cycle control than the integer counter permits.

| Condition | Register/field effect |
|-----------|---------------------|
| true | CR1: DITHEN (bit 12) present |
| true | ARR: field width becomes 20 bits (16 integer + 4 fractional) for 16-bit timers |
| true | CCR1–CCR4: field width becomes 20 bits for 16-bit timers |

All Gen4 families have this feature on all GP timer instances (it's a family-level
constant, not per-instance). The dithering bits are ignored when DITHEN=0.

### `has_centerPWM` — Center-aligned PWM mode

| | |
|---|---|
| **Type** | bool |
| **Default** | true |
| **Families** | All 17 |

Enables center-aligned (up/down) counting modes and explicit direction control.
This is an independent parameter from `channels` — most 4-channel timers have it,
but 2-channel timers may or may not (L0 TIM21/TIM22 have it; TIM9/TIM12 do not).

| Condition | Register/field effect |
|-----------|---------------------|
| true | CR1: CMS (bits 6:5, 2-bit) — center-aligned mode selection |
| true | CR1: DIR (bit 4, 1-bit) — counting direction |

No other register/field implications. Center-aligned mode changes update event
behavior (two per period instead of one) but does not add or remove any bits
beyond CMS and DIR.

Instances with `has_centerPWM`:
TIM2, TIM3, TIM4, TIM5 (all families), TIM19 (F3 only), TIM21/TIM22 (L0 only),
TIM23/TIM24 (H7 H73x only).

Instances without: TIM9, TIM10, TIM11, TIM12, TIM13, TIM14, TIM15, TIM16, TIM17.

### `has_complementary` — Complementary outputs with dead-time

| | |
|---|---|
| **Type** | bool |
| **Default** | false |
| **Families** | 13 of 17 (C0, F3, G0, G4, H5, H7, L4, L4P, L5, N6, U0, U3, U5) |

Enables complementary (inverted) output on CH1 with programmable dead-time insertion,
break input protection, and repetition counter. Fully orthogonal with all other
parameters — the gated registers and fields do not overlap with any other param.

| Condition | Register/field effect |
|-----------|---------------------|
| true | **BDTR** register: DTG (dead-time), LOCK, OSSI, OSSR, BKE, BKP, AOE, MOE, BKF |
| true | **RCR** register: repetition counter |
| true | **DTR2** register (Gen4 only): DTGF, DTAE, DTPE (asymmetric dead-time) |
| true | CCER: CC1NE (complementary output enable for CH1) |
| true | CR2: CCPC, CCUS (preloaded control), OIS1, OIS1N (idle states) |
| true | DIER: COMIE, BIE (commutation/break interrupt enable), COMDE (commutation DMA) |
| true | SR: COMIF, BIF (commutation/break flags) |
| true | EGR: COMG, BG (commutation/break event generation) |
| true | AF1: break input config (BKINE, BKCMPxE, BKINP, BKCMPxP) instead of just ETRSEL |

Instances with `has_complementary`: TIM15, TIM16, TIM17.
Instances without: TIM2, TIM3, TIM4, TIM5, TIM9–TIM14, TIM19, TIM21/22, TIM23/24.

Families without TIM15/16/17 in GpTimer (F4, F7, L0, L1) have no complementary
instances — the parameter is unused in those families.

### `dma_burst` — DMA burst transfer support

| | |
|---|---|
| **Type** | int (enum) |
| **Default** | 1 |
| **Values** | 0, 1, 2 |
| **Families** | All 17 |

Enables DMA burst mode and selects the register variant. DMA burst allows a
single DMA request to transfer a contiguous block of timer registers in one
burst. Also gates the per-channel and trigger DMA request enable fields in DIER.

| Value | Name | Register/field effect |
|-------|------|---------------------|
| 0 | none | No DCR/DMAR registers; no UDE, CCxDE, TDE fields in DIER |
| 1 | v1 | **DCR_V1** @0x48, **DMAR_V1** @0x4C (Gen1–3 layout). DIER: UDE, CC1DE–CC4DE, TDE. |
| 2 | v2 | **DCR** @0x3DC, **DMAR** @0x3E0 (Gen4 layout, adds DCR.DBSS field). DIER: UDE, CC1DE–CC4DE, TDE. |

Family-level assignment: Gen1–3 (C0, F3, F4, F7, G0, H7, L0, L1, L4, L4P, L5, U0)
use v1 (default); Gen4 (G4, H5, N6, U3, U5) use v2.

Instances with DMA burst: TIM2, TIM3, TIM4, TIM5, TIM15, TIM16, TIM17,
TIM19 (F3), TIM23/TIM24 (H7 H73x).
Instances without: TIM9, TIM10, TIM11, TIM12, TIM13, TIM14, TIM21/TIM22 (L0).

### `encoder` — Quadrature encoder capability level

| | |
|---|---|
| **Type** | int (enum) |
| **Default** | 0 |
| **Values** | 0, 1, 2, 3 |
| **Families** | All 17 |

Encodes a strict hierarchy of encoder capabilities. Each level is a proper
superset of the previous.

| Value | Name | Register/field effect |
|-------|------|---------------------|
| 0 | none | No encoder mode support |
| 1 | basic | SMCR.SMS values 001, 010, 011 (encoder modes 1/2/3) are valid. No structural register/field change — constraint on valid SMS values only. |
| 2 | index | **ECR** register: IE, IDIR, FIDX, IPOS, PW, PWPRSC (no IBLK). DIER: IDXIE, DIRIE, IERRIE, TERRIE (bits 20–23). SR: IDXF, DIRF, IERRF, TERRF (bits 20–23). |
| 3 | index_blanking | Same as level 2, plus ECR.IBLK (bits 4:3, index blanking). |

All encoder index fields (ECR, DIER/SR bits 20–23) are at bit positions that
don't overlap with any other parameter's gated set. Fully orthogonal.

**Note:** SMCR.SMSPE/SMSPS (slave mode preload) are associated with encoder
index in hardware, but SMSPE also appears independently on some instances
(e.g., TIM15 on H5/N6/U3). These fields belong to the slave mode feature set
rather than the encoder hierarchy.

Instances by level:
- **encoder=1**: TIM2, TIM3, TIM4, TIM5 (all families), TIM19 (F3),
  TIM12 (H5 only — upgraded IP), TIM23/TIM24 (H7 H73x).
- **encoder=2**: TIM2, TIM3 (G4); TIM2 (U5). Same instances as encoder=1
  within these families.
- **encoder=3**: TIM2–TIM5 (H5, N6, U3), plus H5 TIM12. Same instances
  as encoder=1 within these families.
- **encoder=0**: TIM9, TIM12 (F4/F7/N6), TIM15, TIM21/TIM22 (L0),
  TIM10–TIM14, TIM16/TIM17 (no SMCR at all).

**SVD note:** U3 has casing anomalies in ECR/DIER/SR (`FIDx`, `IDxIE`, `IDxF`
with lowercase x) — requires `renameFields` transforms to normalize.

### `has_xor_input` — TI1 input XOR (Hall sensor interface)

| | |
|---|---|
| **Type** | bool |
| **Default** | true |
| **Families** | All 17 |

Enables XOR combination of TI1, TI2, TI3 inputs onto the TI1 input channel,
used for Hall sensor interface (3-phase commutation detection via a single
timer input). Orthogonal with all other parameters — gates a single field in
CR2 that doesn't overlap with any other param's gated set.

| Condition | Register/field effect |
|-----------|---------------------|
| true | CR2: TI1S (bit 7, 1-bit) — TI1 input XOR enable |

Instances with `has_xor_input`: TIM2, TIM3, TIM4, TIM5 (all families),
TIM15 (all families that have it), TIM19 (F3), TIM23/TIM24 (H7 H73x),
TIM9/TIM12 (H5, N6 — newer IP revisions).
Instances without: TIM10, TIM11, TIM13, TIM14, TIM16, TIM17 (1-channel),
TIM9/TIM12 (F4, F7, L1 — older IP), TIM21/TIM22 (L0).

Not correlated with `channels` (TIM15 is 2-channel with TI1S; TIM21/22 are
2-channel without) or `has_complementary` (TIM15 has both; TIM16/17 have
complementary but not TI1S).

### `has_etr` — External trigger input

| | |
|---|---|
| **Type** | bool |
| **Default** | true |
| **Families** | All 17 |

Enables the external trigger (ETR) input with its filter, prescaler, polarity,
and external clock mode 2. Gates four fields in SMCR bits 8–15 that are always
present or absent as a group. Fully orthogonal — these bits don't overlap with
any other parameter's gated set.

| Condition | Register/field effect |
|-----------|---------------------|
| true | SMCR: ETF (bits 11:8, 4-bit) — external trigger filter |
| true | SMCR: ETPS (bits 13:12, 2-bit) — external trigger prescaler |
| true | SMCR: ECE (bit 14, 1-bit) — external clock mode 2 enable |
| true | SMCR: ETP (bit 15, 1-bit) — external trigger polarity |

AF1.ETRSEL (ETR source mux) is family-level, not per-instance — present on
families with AF1 register (C0, G0, G4, H5, H7, N6, U0, U3, U5).

Instances with `has_etr`: TIM2, TIM3, TIM4, TIM5 (all families), TIM19 (F3),
TIM23/TIM24 (H7 H73x), TIM21/TIM22 (L0).
Instances without: TIM9, TIM12, TIM15 (have SMCR but no ETR fields),
TIM10, TIM11, TIM13, TIM14, TIM16, TIM17 (no SMCR at all).

Not correlated with `channels` (TIM21/22 are 2-channel with ETR; TIM9/12/15
are 2-channel without), `has_encoder` (TIM21/22 have ETR but no encoder), or
`has_centerPWM` (TIM21/22 have both; TIM15 has neither).

### `sms_preload` — Slave mode selection preload

| | |
|---|---|
| **Type** | int (enum) |
| **Default** | 0 |
| **Values** | 0, 1, 2 |
| **Families** | 5 of 17 (G4, H5, N6, U3, U5) |

Enables preloading the SMS (slave mode selection) field, so slave mode switching
takes effect atomically on a trigger event rather than immediately on write.
Strict hierarchy: each level is a superset of the previous.

| Value | Name | Register/field effect |
|-------|------|---------------------|
| 0 | none | No SMS preload capability |
| 1 | smspe | SMCR: SMSPE (bit 24, SMS preload enable). Preload source is implicitly the update event. |
| 2 | smspe_smsps | SMCR: SMSPE (bit 24) + SMSPS (bit 25, SMS preload source selector). Source can be update event or encoder index. |

Fully orthogonal — SMSPE (bit 24) and SMSPS (bit 25) are at positions that
don't overlap with any other parameter's gated set. The ETR fields occupy
bits 8–15, encoder fields are in ECR/DIER/SR, and SMS/TS occupy bits 0–6 + 16–21.

Instances by level:
- **sms_preload=2**: TIM2, TIM3, TIM4, TIM5 on G4/H5/N6/U3/U5. All 4-channel
  timers within these families.
- **sms_preload=1**: TIM15 on H5, N6, U3 only. SMSPE without SMSPS — preload
  triggered by update event (no source selection needed).
- **sms_preload=0**: All instances on the other 12 families; TIM9, TIM12,
  TIM16, TIM17 within Gen4 families.

## Family-level observations (not per-instance parameters)

### Extended slave mode selection (SMS_3, TS_4_3)

SMS_3 (bit 16) extends SMS from 3 to 4 bits, enabling combined reset+trigger
and other advanced slave modes. TS_4_3 (bits 21:20) extends TS from 3 to 5 bits,
enabling ITR4–ITR11 trigger sources. Both are family-level constants on 15 of 17
families:

Present: C0, F3 (F30x only), F7, G0, G4, H5, H7, L4, L4P, L5, N6, U0, U3, U5.
Absent: F3 (F37x), F4, L0, L1.

**F7 per-instance anomaly:** TIM2–TIM5 have SMS_3; TIM9/TIM12 do not (older
timer IP in the same SVD). This is the only family where SMS_3 varies per-instance.
Not worth a dedicated parameter — the affected instances (TIM9/TIM12) are already
heavily parameterized with reduced capabilities.

### OCREF clear source selection

OCREF clear allows forcing the output compare reference signal low via an external
event. Three components exist, all family-level constants (not per-instance):

1. **OCxCE fields** (OC1CE–OC4CE in CCMR1/CCMR2_Output): per-channel clear enable.
   Nearly universal — present on all TIM2 source models across all 17 families.
   Not a parameter candidate (always present when the channel exists).

2. **SMCR.OCCS** (bit 3): selects internal `ocref_clr` vs ETRF as the clear source.
   Present: C0, F3, G0, G4, H5, L1, L4, N6, U0, U3, U5.
   Absent: F4, F7, H7, L0, L4P, L5.

3. **AF2.OCRSEL** (bits 18:16, 3-bit mux): selects among 8 `tim_ocref_clr` sources.
   Only Gen4: G4, H5, N6, U3, U5. Field lives in AF2 which is already family-determined.

Additionally G0 has `OR1.IOCREF_CLR` (1-bit) and U0 has `OR1.OCREF_CLR` (2-bit
COMP1/COMP2 mux) for family-specific internal source selection.

## Caveats

- **SVD derivedFrom:** Many small timer instances (TIM9-14) are defined as derivedFrom
  TIM2/TIM3 in SVD files. This means their register definitions are copies of the parent,
  NOT their actual register set. Per-instance tables above use directly-defined SVD data
  where available and note derivedFrom cases.

- **Channels and width:** These are physical hardware properties not reflected in the
  register map (all registers exist at the same offsets regardless of channel count).
  Values come from the existing STM32.yaml config, not SVD extraction.

- **arr_width=20 in Gen4:** SVDs for Gen4 families (G4, H5, N6, U3, U5) show 20-bit
  ARR fields. This reflects the 4-bit dithering extension (16+4=20 for 16-bit timers,
  32+4=36 theoretical but SVD shows 32 for TIM2/TIM5). The extra 4 bits are the
  dithering fractional part, only active when DITHEN=1.
