# RM0399 chapter 14 — block interconnect

Extracted routing tables from STM32H745/H747/H755/H757 reference manual
[RM0399 Rev. 4](https://www.st.com/resource/en/reference_manual/rm0399-stm32h745755-and-stm32h747757-advanced-armbased-32bit-mcus-stmicroelectronics.pdf),
chapter 14 "Block interconnect" (pp. 614-648).

The tables describe every fixed (non-runtime-configurable) wire between
peripheral blocks on this family of chips: timer trigger crossbars, DMA
request multiplexer inputs, EXTI wakeup lines, MDMA trigger sources.
Their content drives the `connections:` entries on the chip-level YAML
models and the `outputs:` declarations on the block-level YAML models.

## Files

| File             | Source PDF table         | Routes |
|------------------|--------------------------|--------|
| `table-102.csv`  | Peripherals interconnect matrix details (p. 617-632) | 317 |
| `table-103.csv`  | EXTI wakeup inputs (p. 634-636)                      | 86  |
| `table-104.csv`  | EXTI pending requests clear inputs (p. 637)          | 4   |
| `table-105.csv`  | MDMA (p. 639-640)                                    | 32  |
| `table-106.csv`  | DMAMUX1, DMA1 and DMA2 connections (p. 641-645)      | 138 |
| `table-107.csv`  | DMAMUX2 and BDMA connections (p. 646-648)            | 63  |

RM0399's Tables 100 and 101 (D2/D3-domain overview matrices on pp. 615-616)
are intentionally skipped — their headers are typeset vertically, so
pdfplumber returns garbled text, and their content is fully redundant with
the row-based Table 102.

## Schema

Every CSV has the same four columns:

| Column          | Meaning                                                |
|-----------------|--------------------------------------------------------|
| `src_instance`  | Source block instance (e.g. `TIM1`, `USART2`, `ADC1`). |
| `src_signal`    | Source-side signal name as it appears in the RM.       |
| `dst_signal`    | Destination-side signal name as it appears in the RM.  |
| `dst_instance`  | Destination block instance (e.g. `DMAMUX1`, `EXTI`).   |

The Source Domain / Bus and Destination Bus / Domain columns from the
original PDF are dropped — they describe APB/AHB/AXI placement, which is
already captured by the chip-level YAML. The Type column (Table 102: A=async
/ S=sync / I=immediate / B=break) and Target column (Table 103: CPU /
CPU1 / CPU2 / ANY) are also dropped: see [Deferred
decisions](../../design/connection-routing.md#deferred-decisions).

The RM uses inconsistent signal naming. Some signals appear as
`<instance_lowercase>_<canonical>` (Table 106: `adc1_dma`,
`tim1_ch1_dma`), others as `<canonical>_<instance_lowercase>` (Table 107:
`dma_rx_lpuart`, `dma_tx_spi6`), and Table 102 mixes uppercase
canonicals (`TRGO`, `CC2`) with lowercase ones (`comp1_out`). All names
are preserved verbatim; the per-block-output canonical-name decision
happens during Phase B wiring.

## Cleanups applied

`tools/extract_rm0399_chapter14.py` runs `pdf_table_extractor.py` per
table with `--forward-fill 2,4,5` and `--drop-columns 0,1,6..`, then
applies three transformations:

1. **NC rows dropped.** Entries where `src_instance`, `src_signal`, or
   `dst_signal` is `NC` describe unwired destination ports — they're
   noise for our purposes. Rows with the DMAMUX-internal
   `dmamux<N> internal (Request generator)` pseudo-source are dropped on
   the same grounds: those describe DMAMUX's runtime-configurable
   request-generator inputs to itself, not chip-fixed wiring.
2. **"X or Y" compound sources split.** When the RM lists two sources
   sharing one destination input (e.g. `COMP1 or COMP2(2) / comp1_out or
   comp2_out → TI4_3 / TIM2`), the row is expanded to one row per
   alternative with the same destination. Semantically identical to two
   peripherals sharing an NVIC vector; our `chip_connections` schema
   already handles this case naturally.
3. **Whitespace collapsed in signal columns.** pdfplumber occasionally
   splits a cell's word at the line-wrap boundary, producing artifacts
   like `lptim2_ext_trg 0` (for `lptim2_ext_trg0`) or `mu x3` (for
   `mux3`). The fix is safe because signal names in this chapter are
   SVD-style identifiers with no legitimate internal whitespace.

The first two transformations apply to the destination signal too: a
merged-cell destination signal (visible in the PDF as a tall cell spanning
several rows) is treated as the same signal feeding all the rows of the
merge — the boundary-aware `--forward-fill` handles it automatically.

## Things this format does not capture

- Multi-destination peripherals expressed as `ADC1 / ADC2` or `DAC
  channel 1/channel 2` in the `dst_instance` column. The RM uses the
  slash to indicate that several instances share the same trigger
  input. Phase B will expand these per-instance.
- The bare `RCC CSS_LSE` row in Table 103, which lists no destination
  signal in the PDF. Preserved as a row with empty `dst_signal` for
  visibility.
- Footnote text. Footnote markers like `(1)` and `(2)` are stripped from
  the source instance column during OR-row splitting; their content (typical
  contents: clock-domain notes, RM cross-references) is not captured.

## Regenerating

After a RM revision bump, place the new PDF at
`docs/ST/RM0399 - STM32H745 STM32H755 STM32H747 STM32H757 (Rev. N).pdf`,
update the `PDF_PATH` constant in `tools/extract_rm0399_chapter14.py`,
update the per-table `TABLES` page ranges (they shift between revisions —
PDF page numbers, not RM-printed page numbers), and run:

```sh
python3 tools/extract_rm0399_chapter14.py
```

Diff the output against the previous version to spot moved/added/removed
routes.
