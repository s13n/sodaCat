# USART Cross-Family Comparison

## Architectural Split

STM32 USART exists in two fundamentally different register architectures:

- **v1** (F4, L1): SR/DR/BRR/CR1/CR2/CR3/GTPR — 7 registers. Cannot be unified with v2.
- **v2** (15 families): CR1/CR2/CR3/BRR/GTPR/RTOR/RQR/ISR/ICR/RDR/TDR/[PRESC]/[AUTOCR]

Only v2 is a candidate for cross-family shared model unification. F4 and L1 remain per-family.

## v2 Family Register Summary

| Family | Regs | FIFO | PRESC | SPI_slave | TCBGT | Wakeup | AUTOCR | M1 | Alternate CR1/ISR |
|--------|------|------|-------|-----------|-------|--------|--------|----|-------------------|
| F3     | 11   | -    | -     | -         | -     | Yes    | -      | -  | No                |
| F7     | 11   | -    | -     | -         | Yes   | Yes    | -      | Yes| No                |
| L0     | 11   | -    | -     | -         | -     | Yes    | -      | Yes| No                |
| L4     | 11   | -    | -     | -         | -     | Yes    | -      | Yes| No                |
| C0     | 14   | Yes  | Yes   | Yes       | Yes   | Yes    | -      | Yes| Yes               |
| G0     | 12   | Yes  | Yes   | Yes       | Yes   | Yes    | -      | Yes| No                |
| G4     | 12   | Yes  | Yes   | Yes       | Yes   | Yes    | -      | Yes| No                |
| H5     | 14   | Yes  | Yes   | Yes       | Yes   | Yes    | -      | Yes| Yes               |
| H7     | 12   | Yes  | Yes   | Yes       | Yes   | Yes    | -      | Yes| No                |
| L4P    | 14   | Yes  | Yes   | Yes       | Yes   | Yes    | -      | Yes| Yes               |
| L5     | 12   | Yes  | Yes   | Yes       | Yes   | Yes    | -      | Yes| No                |
| N6     | 14   | Yes  | Yes   | Yes       | Yes   | Yes    | -      | Yes| Yes               |
| U0     | 14   | Yes  | Yes   | Yes       | Yes   | Yes    | -      | Yes| Yes               |
| U3     | 16   | Yes  | Yes   | Yes       | Yes   | -      | Yes    | Yes| Yes               |
| U5     | 15   | Yes  | Yes   | Yes       | Yes   | -      | Yes    | Yes| Yes               |

**Observations:**
- FIFO, PRESC, and SPI slave are perfectly correlated (always appear together)
- TCBGT is independent: F7 has it without FIFO, while F3/L0/L4 lack both
- Wakeup (WUS/WUFIE/WUF/WUCF) is present everywhere except U3/U5
- AUTOCR is only on U3/U5
- M1 (7-bit data mode) is present on all except F3
- F7 uniquely has UCESM (CR3 bit 23), mutually exclusive with TXFTIE on FIFO families

## Parameter Definitions

| # | Parameter | Type | Default | Description |
|---|-----------|------|---------|-------------|
| 1 | `synchronous` | int | 3 | Synchronous/smartcard capability: 0=none, 1=synchronous only, 2=sync+smartcard, 3=sync+smartcard+TCBGT |
| 2 | `has_fifo` | bool | true | FIFO mode (FIFOEN/TXFEIE/RXFFIE in CR1; TXFTIE/RXFTCFG/RXFTIE/TXFTCFG in CR3; TXFE/RXFF/RXFT/TXFT in ISR; TXFECF in ICR). Also implies PRESC register and SPI slave fields. |
| 3 | `has_wakeup` | bool | true | Wakeup from Stop mode interrupt flag selection (WUS/WUFIE in CR3; WUF in ISR; WUCF in ICR) |
| 4 | `has_autocr` | bool | false | Autonomous mode (AUTOCR register at 0x30) |

**`synchronous` enum levels:**
- **0**: No synchronous mode, no smartcard (UART instances — lack CLKEN, CPOL, CPHA, LBCL, SCEN, NACK, SCARCNT, GTPR.GT, EOBF/EOBCF, TCBGT/TCBGTIE/TCBGTCF)
- **1**: Synchronous only (C0/U0 Basic USART instances — have CLKEN/CPOL/CPHA/LBCL but lack smartcard and TCBGT)
- **2**: Sync + smartcard, no TCBGT (F3/L0/L4 USART instances, F7 F74x_F75x USART instances, F4/L1 v1 USART instances)
- **3**: Sync + smartcard + TCBGT (default — most USART instances on most families)

**Dropped candidates:**
- `has_presc` — perfectly correlated with `has_fifo`, no need for separate param
- `has_spi_slave` — perfectly correlated with `has_fifo`, no need for separate param
- `has_m1` — only F3 lacks it; too minor for a param (one bit on one family)
- `has_ucesm` — only F7; bit 23 of CR3 is mutually exclusive with TXFTIE
- `has_synchronous` / `has_smartcard` / `has_tcbgt` — consolidated into `synchronous` enum (strict hierarchy: smartcard implies sync, TCBGT implies smartcard)

## SVD Cosmetic Differences (not parameters)

These are field naming/encoding differences that don't affect hardware behavior:

| Aspect | Older SVDs | Newer SVDs | Families affected |
|--------|-----------|------------|-------------------|
| BRR fields | DIV_Fraction + DIV_Mantissa | BRR (single 16-bit) or BRR_0_3 + BRR_4_15 | F3, L0, L4, G4 (old) vs C0, H5, L4P, L5, N6, U0, U3, U5 (new) vs G0, H7 (split) |
| DEDT/DEAT | DEDT0-DEDT4 (5 individual bits) | DEDT (5-bit field) | F7, G4, H7, L0, L4, L5 (individual) vs C0, F3, G0, H5, L4P, N6, U0, U3, U5 (single) |
| ABRMOD | ABRMOD0 + ABRMOD1 | ABRMOD (2-bit field) | F7, G4, H7, L0, L4, L5, G0 (split) vs C0, F3, H5, L4P, N6, U0, U3, U5 (single) |
| ADD | ADD0_3 + ADD4_7 or ADD0 + ADD4 | ADD (8-bit field) | See individual models |
| DATAINV vs TAINV | TAINV | DATAINV | F7, G0, G4, H7, L0, L4 (TAINV) vs C0, F3, H5, L4P, L5, N6, U0, U3, U5 (DATAINV) |
| NF vs NE | NF | NE | F3, F7, G0, G4, H7, L0, L4, L5 (NF) vs C0, H5, L4P, N6, U0, U3, U5 (NE) |
| NCF vs NECF | NCF | NECF | Same split as NF/NE |
| WUS encoding | WUS (2-bit) | WUS0 + WUS1 | Most (WUS) vs C0, H5, N6, U0 (split) |
| CR1/ISR alternates | Single register with all fields | Separate FIFO_ENABLED/FIFO_DISABLED | G0, G4, H7, L5 (single) vs C0, H5, L4P, N6, U0, U3, U5 (alternates) |
| Mixed case (U3) | RXINV, TXINV | RxINV, TxINV | Only U3 uses mixed case |
| H7 ICR typo | TCBGTCF | TCBGTC | Only H7 has truncated name |

## Source Selection

**Recommended: STM32N645.USART1** (N6 family)

Rationale:
- Newest-generation SVD (v1.0, likely from clean IP-XACT)
- Has FIFO + PRESC + SPI slave + TCBGT + Wakeup — all features except AUTOCR
- Clean field naming (single-field DEDT/DEAT/ABRMOD/ADD, NE/NECF naming)
- Has proper alternate CR1/ISR registers for FIFO modes
- AUTOCR (U3/U5 only) can be added via patchRegisters transform

**AUTOCR register to add via transform:**
- Offset: 0x30, size: 32, resetValue: 0
- Fields: TDN (bits 0-15), TRIGPOL (bit 16), TRIGEN (bits 17-19), IDLEDIS (bit 20), TRIGSEL (bits 21-24)
- U5 variant adds TECLREN (bit 25)

## Per-Family chip_params

### Instance-level overrides
UART instances need: `{synchronous:0}`
C0/U0 Basic USART instances need: `{synchronous:1, has_fifo: false, has_wakeup: false}`

### Family-level overrides (non-default values)

| Family | synchronous| has_fifo | has_wakeup | has_autocr | Notes |
|--------|-----------|----------|------------|------------|-------|
| F3     | 2         | false    | (true)     | (false)    | No TCBGT, no FIFO |
| F7     | (3)       | false    | (true)     | (false)    | F74x_F75x: synchronous=2 |
| L0     | 2         | false    | (true)     | (false)    | No TCBGT, no FIFO |
| L4     | 2         | false    | (true)     | (false)    | No TCBGT, no FIFO |
| C0     | (3)       | (true)   | (true)     | (false)    | Basic instances: synchronous=1 |
| G0     | (3)       | (true)   | (true)     | (false)    | All defaults |
| G4     | (3)       | (true)   | (true)     | (false)    | All defaults |
| H5     | (3)       | (true)   | (true)     | (false)    | All defaults |
| H7     | (3)       | (true)   | (true)     | (false)    | All defaults |
| L4P    | (3)       | (true)   | (true)     | (false)    | All defaults |
| L5     | (3)       | (true)   | (true)     | (false)    | All defaults |
| N6     | (3)       | (true)   | (true)     | (false)    | Source family |
| U0     | (3)       | (true)   | (true)     | (false)    | Basic instances: synchronous=1 |
| U3     | (3)       | (true)   | false      | true       | No wakeup, has AUTOCR |
| U5     | (3)       | (true)   | false      | true       | No wakeup, has AUTOCR |

`(parenthesized)` = default value (no chip_params entry needed)

Only non-default block-level entries needed:
- F3, L0, L4: `USART: {has_fifo: false, synchronous: 2}`
- F7 _all: `USART: {has_fifo: false}` + F74x_F75x: `USART: {synchronous:2}`
- U3, U5: `USART: {has_wakeup: false, has_autocr: true}`

Instance-level entries:
- All UART instances (all families): `{synchronous:0}`
- C0 USART2/3/4 (Basic): `{synchronous:1, has_fifo: false, has_wakeup: false}`
- U0 USART3/4 (Basic): `{synchronous:1, has_fifo: false, has_wakeup: false}`
