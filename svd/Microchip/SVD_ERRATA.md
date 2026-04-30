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

### GMAC — SAMV71 RM, DS60001527J pages 742–744

| Array | RM range | Worked around with |
|------|----------|--------------------|
| `IERPQ[%s]` | `n=1..5` | `patchRegisters` → `dimIndex: 1,2,3,4,5` |
| `IDRPQ[%s]` | `n=1..5` | `patchRegisters` → `dimIndex: 1,2,3,4,5` |
| `IMRPQ[%s]` | `n=1..5` | `patchRegisters` → `dimIndex: 1,2,3,4,5` |

The PIC32CZ-CA70 RM (DS60001825E) numbers the same registers `n=0..4`,
disagreeing with the SAMV71 RM. The hardware is identical (same Cadence
GEM IP, same offsets); we follow the SAMV71/SAME70 RM convention because
it matches the existing explicit `<dimIndex>1-4</dimIndex>` on `GMAC_SA`
in the same SVD, and matches Cadence's upstream GEM TRM.

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
