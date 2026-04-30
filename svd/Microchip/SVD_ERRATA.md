# Microchip Vendor Errata

Known SVD bugs *and* reference-manual oversights, both verified by cross-
referencing the SVD, the family RM, and (where available) sibling RMs from
the same IP family. SVD-side bugs are worked around with transforms in
`svd/Microchip/Microchip.yaml`; RM-side oversights are documented here for
context (no extraction-side fix is required when the SVD is already correct).

When Microchip fixes an SVD bug in a new DFP release, the corresponding
transform becomes a no-op and can be detected with
`cmake --build <dir> --target audit-microchip-models`.


## Vendor-wide: missing `<dimIndex>` on register arrays

Microchip's CMSIS-SVD generator emits `<dim>` and `<dimIncrement>` on
register arrays but almost never emits `<dimIndex>`, so per the SVD spec
every array defaults to `0..(dim-1)` regardless of the RM's actual
numbering. Across all ten DFP archives in the repo (SAME70, SAMS70,
SAMV70, SAMV71, PIC32CZ-CA70, PIC32CZ-MC70, PIC32CZ-CA80, PIC32CZ-CA90),
`<dim>` appears 81–109 times per chip and `<dimIndex>` appears at most
once — the lone exception being the `GMAC_SA[1-4]` cluster in the
GMAC-bearing chips, which Microchip presumably annotated explicitly because
the slot-0 register set lives elsewhere and a 0-based array would be
unambiguously wrong.

For most arrays the 0-based default happens to match the RM (`ISRPQ`,
`ST1RPQ`, `ST2RPQ`, etc.). For the rest the model was wrong until
patched. The two affected blocks identified to date are GMAC and ETH:

### GMAC — SAMV71 RM, DS60001527J pages 732–748

All six priority-queue array registers cover the same logical queues
1..5. The SAMV71 RM is internally inconsistent about the indexing:

| Array | RM offset formula | RM register names |
|------|-------------------|-------------------|
| `ISRPQ`, `TBQBAPQ`, `RBQBAPQ`, `RBSRPQ`, `ST1RPQ`, `ST2RPQ`, `ST2ER` | `x*0x04 [x=0..N]` | 0-based |
| `IERPQ`, `IDRPQ`, `IMRPQ` | `(x-1)*0x04 [x=1..5]` | 1-based |

The free-text descriptions on every PQ array nevertheless say *"Priority
Queue (1..5)"* — confirming the registers all conceptually represent
queues 1..5 regardless of the formula. We therefore force a uniform
1-based numbering across the four ISRPQ/TBQBAPQ/RBQBAPQ/RBSRPQ arrays
in addition to the three IERPQ/IDRPQ/IMRPQ arrays, so the array index
always equals the queue number throughout the GMAC block:

| Array | Worked around with |
|------|--------------------|
| `ISRPQ[%s]`   | `dimIndex: 1,2,3,4,5` |
| `TBQBAPQ[%s]` | `dimIndex: 1,2,3,4,5` |
| `RBQBAPQ[%s]` | `dimIndex: 1,2,3,4,5` |
| `RBSRPQ[%s]`  | `dimIndex: 1,2,3,4,5` |
| `IERPQ[%s]`   | `dimIndex: 1,2,3,4,5` |
| `IDRPQ[%s]`   | `dimIndex: 1,2,3,4,5` |
| `IMRPQ[%s]`   | `dimIndex: 1,2,3,4,5` |

This deviates from the SAMV71 RM register *names* for the ISRPQ-group
(which are `GMAC_ISRPQ0..GMAC_ISRPQ4`) but matches both the description
text and the SAMV71 RM names for the IERPQ-group (`GMAC_IERPQ1..
GMAC_IERPQ5`) and the explicit `<dimIndex>1-4</dimIndex>` on the sibling
`GMAC_SA` cluster. The PIC32CZ-CA70 RM (DS60001825E) numbers all PQ
registers as `n=0..4` — internally consistent, but the underlying
hardware and queue-number convention is identical, so the same dimIndex
choice applies.

In addition, four flat scalars `TIDM1..TIDM4` (Type ID Match registers,
offsets 168/172/176/180) were collapsed into a `TIDM%s` array indexed
1..4, following the same 1-based convention. This required normalizing
the per-register field names `ENID1`/`ENID2`/`ENID3`/`ENID4` to plain
`ENID` first.

### ETH — PIC32CZ-CA80 RM, DS60001749G pages 899–994

| Array | RM range | SVD `dim` | Worked around with |
|------|----------|-----------|--------------------|
| `SA[%s]` | `x=1..4` (SAB cluster) | 4 | `dimIndex: 1,2,3,4` |
| `STDM[%s]` | `x=1..4` (RM: TIDM) | 4 | `dimIndex: 1,2,3,4` |
| `ISRQ[%s]` | `n=1..5` | 15 | `dimIndex: 1..15` (SVD over-declares) |
| `TBPQB[%s]` | `n=1..5` | 15 | `dimIndex: 1..15` |
| `RBPQB[%s]` | `n=1..5` | 7 | `dimIndex: 1..7` |
| `RBQSZ[%s]` | `n=1..5` | 7 | `dimIndex: 1..7` |
| `IERQ[%s]` | `n=1..5` | 7 | `dimIndex: 1..7` |
| `IDRQ[%s]` | `n=1..5` | 7 | `dimIndex: 1..7` |
| `IMRQ[%s]` | `n=1..5` | 7 | `dimIndex: 1..7` |
| `IERQU[%s]` | not in RM | 8 | `dimIndex: 1..8` (paired with `IERQ`) |
| `IDRQU[%s]` | not in RM | 8 | `dimIndex: 1..8` (paired with `IDRQ`) |
| `IMRQU[%s]` | not in RM | 8 | `dimIndex: 1..8` (paired with `IMRQ`) |

The SVD `dim` exceeds what the RM documents because the underlying Cadence
GEM IP physically supports up to 16 priority queues; the PIC32CZ-CA80
implementation only enables 5, but the register address window is reserved
for the full set. The over-declared upper slots keep the same 1-based
shift so `IERQ[1..5]` matches the documented queue-1..5 enable bits.

The `IERQU`/`IDRQU`/`IMRQU` "(upper)" registers are paired bit-extensions
of the corresponding non-`U` siblings; the RM does not document them
separately, but they get the same 1-based shift for consistency.


## Vendor-wide: under-utilised SVD register summary tables

Aside from the missing `<dimIndex>` discussed above, no other SVD-side
bugs have been identified in either GMAC or ETH so far. Other peripherals
likely have similar 1-based array oversights waiting to be discovered;
the systematic pattern is "any array whose RM offset formula contains
`(n-1)*incr` or `[n=1..N]` is currently 0-indexed in the model."


## MCLK CLKMSK: dim over-declared, MASK field not bit-decomposed

References: DS60001749G §21.6.5–.7 (CLKMSK0/1/2).

Two minor observations on the CA80/CA90 `MCLK.CLKMSK[%s]` array; both
are noted for completeness but neither requires a transform.

- The SVD declares `CLKMSK` with `<dim>9</dim>` at offset `0x3C`, but
  only `CLKMSK0/1/2` (offsets 0x3C/0x40/0x44) are documented in the RM.
  The next six register slots (0x48..0x5C) are unused address space;
  the next documented register (`ODOFF`) resumes at 0x60.  This is most
  likely a deliberate forward-compatibility allocation by Microchip —
  the CA80/CA90 only populates the first three CLKMSK words but the IP
  reserves 9× 32-bit slots for future expansion as more peripherals are
  added.  Harmless.
- Each CLKMSK register is emitted with a single 32-bit `MASK` field,
  even though the RM names individual mask bits `MSK0..MSK31`.  The
  clock-tree model in
  [PIC32CZ_Gen2_clocks.yaml](../../models/Microchip/PIC32CZ_Gen2_clocks.yaml)
  references the per-bit names (`MSK0`, `MSK1`, …) anyway since the
  clock-tree validator does not cross-check field names against the
  peripheral model; eventual C++ generation would benefit from a
  `patchFields` transform that splits each CLKMSK into 32 single-bit
  fields, but that's a presentation tweak rather than a correctness
  fix.


## PIC32CZ-CA80/CA90 RM: I2S0 mislabeled as "I2S2" in CLKMSK1

Reference: DS60001749G p.319 (CLKMSK1 mask-bit table).

The CLKMSK1 bit-22 mask-bit row in the CA80/CA90 RM is labeled
*"I2S2"*, but the chip has only two I2S instances — `I2S0` and `I2S1` —
per the Chapter 47 (Inter-IC Sound Controller) pinout table on page 41
and the GCLK PCHCTRL channel mapping on page 288 (which lists
`GCLK_I2S0` at index 44 and `GCLK_I2S1` at index 45).  The
"I2S2" label is consistent with neither, so it is taken to be a typo
for `I2S0`.  Bit 23 in the same register is correctly labeled
`I2S1`, which is consistent with the bit-22 / bit-23 pair gating the
two-instance I2S block.

The clock-tree model assumes bit 22 is `clk_i2s0_apb`.  No SVD-side
fix is required; flagged here purely so a future reader who consults
the RM doesn't mis-route the bit to a non-existent third I2S.


## PIC32CZ-CA80/CA90 RM: missing SAT registers (RM erratum)

Reference: PIC32CZ-CA80/CA9x Family Data Sheet DS60001749G

The CA80/CA90 RM documents `SABx` (Specific Address Bottom 1..4) at
offsets `0x1088 + (x-1)*0x08` but treats the four interleaved `SATx`
(Specific Address Top) registers at `0x108C, 0x1094, 0x109C, 0x10A4`
as reserved space — as if the MAC address space were 32-bit-only.

This is an RM erratum, not an SVD or model bug:

- The SVD correctly declares `SA[%s]` as a cluster with `SAB` at offset 0
  and `SAT` at offset 4, so the model emits both halves of every MAC
  address slot.
- The SAMV71 RM (DS60001527, page 600) documents both halves explicitly:
  *"Specific Address register 1 bottom bits 31:0 (0x98)"* and *"Specific
  Address register 1 top bits 31:0 (0x9C)"*.
- The PIC32CZ-CA70 RM (DS60001825E) documents both halves under a single
  cluster.

No transform required; the model is already correct. Documented here so a
future reader who spots the RM "reserved" entries doesn't try to "fix" the
SVD or the model.


## PIC32CZ-CA80/CA90: missing I2S peripheral block

Reference: PIC32CZ-CA80/CA9x Family Data Sheet DS60001749G, Chapter 47
("Inter-IC Sound Controller (I2S)") and Table 6-13 ("I2S Pinout I/O
Descriptions").

The CA80/CA90 chips carry **two** instances of the Inter-IC Sound
Controller — `I2S0` and `I2S1` — confirmed both by the dedicated RM
chapter (page 1930ff) and by the pinout, which lists ten dedicated I2S
signals (`I2S_FSYNC0/1`, `I2S_MCK0/1`, `I2S_SCK0/1`, `I2S_SDI0/1`,
`I2S_SDO0/1`). The SVD defines no peripheral for either instance.

The Gen2 I2S is not just a renamed SAM-Gen1 `I2SC`; it is materially
more capable:

| | SAM-Gen1 `I2SC` | Gen2 `I2S` (CA80/CA90) |
|---|---|---|
| Native channels | 2 (stereo) | up to 8 |
| TDM | not supported | up to 32 slots per FSYNC |
| FIFOs | small holding regs | 2 × 64-byte (TX, RX) |
| Audio formats | I²S, mono/stereo, compact stereo | I²S + left/right justified + 32-bit FP audio + AM824 raw + multiple TDM variants + PCM + I2STPD |

So the CA80/CA90 *upgraded* the audio block from the SAM-Gen1 line; it
is only the SVD that has dropped it.

No transform can compensate for a wholly-absent peripheral; a hand-
written model would need to be added to `models/Microchip/I2S.yaml` once
the register layout is transcribed from the RM (or once Microchip
publishes a fixed DFP). The block name `I2S` (no trailing `C`) suggests
it should *not* re-use the SAM-Gen1 `models/Microchip/I2SC.yaml`; the
register layout is materially different.


## MLB: incomplete `MLBCLK` enum values

Reference: SAMV71 RM DS60001527J p.1396 (and equivalent CA70/CA80/CA90
RM pages).

The `MLBC0.MLBCLK[2:0]` field selects the MediaLB clock speed as a
multiplier of Fs. The field is 3 bits wide and the RM documents seven
values:

| Value | Multiplier |
|---|---|
| 0 | 256×Fs |
| 1 | 512×Fs |
| 2 | 1024×Fs (max in 3-pin mode at Fs=48 kHz: 49.152 MHz) |
| 3 | 2048×Fs |
| 4 | 3072×Fs |
| 5 | 4096×Fs |
| 6 | 6144×Fs |

All four MLB-bearing SVDs (SAMV71, PIC32CZ-CA70/CA80/CA90) declare
only the first three (256/512/1024 ×Fs). Setting `MLBCLK = 3..6` is
RM-legal and selects higher multipliers but generates no compile-time
enum constant in the C++ headers, forcing users to fall back on raw
integer literals.

This is a minor SVD bug — easy to fix via a `patchFields` transform
that adds the missing enum values when we get round to it. No transform
is applied yet.

Note that running at Fs=48 kHz with multiplier > 1024× exceeds the
49.152 MHz documented 3-pin signaling limit; multipliers 2048..6144
are intended for the 6-pin MediaLB variant (which the SAMV71/PIC32CZ
silicon does not implement) or for lower Fs values.


## PIC32CZ-CA80/CA90 ETH: misleading peripheral description

Reference: PIC32CZ-CA80/CA9x Family Data Sheet DS60001749G

The PIC32CZ-CA80/CA90 SVDs label the Ethernet peripheral
*"Ethernet MAC (Synopsys EQOS)"* in the `<description>` field, and the
chapter header in the RM also says *"Gigabit Ethernet Media Access
Controller (GMAC)"* — but inspection of the register set
(`NCR`, `NCFGR`, `NSR`, `DCFGR`, `RBQB`, `TBQB`, `USRIO`, `MAN`, the
`SABx`/`SATx` clusters, the `STxRPQ` screening Type-1/2 set, the priority-
queue interrupt-enable family, etc.) shows it is unambiguously the
**Cadence GEM** IP family — the same lineage as the SAMV71 GMAC peripheral
(95 of 110 GMAC register names are shared with ETH). Synopsys EQOS uses
a completely different register layout (`MAC_Configuration`, `MAC_Address0`,
DMA channel descriptors at `DMA_CH%s_*`, etc.), none of which appear here.

The CA80/CA90 implementation extends the older Cadence GEM with PIC32CZ-
specific wrapper registers (`CTRLA`, `CTRLB`, `SYNCB`, `EVCTRL`, `REVREG`)
and additional GEM features (queue priority, AXI master config, expanded
screening) — but the underlying IP family is GEM, not EQOS.

No transform is currently applied; the description survives unchanged in
[ETH.yaml](../../models/Microchip/ETH.yaml). Future work could either
correct the description via a `patchRegisters`-style block-level override
(the transform engine would need a small extension) or simply rename the
block to `GMAC` so it can share the existing `models/Microchip/GMAC.yaml`
once the two are unified.
