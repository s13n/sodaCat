# Feature-flag params: driver reuse via unified peripheral models

When peripherals exist across capability tiers — ST USART / LPUART, Microchip
UART / USART, ST timers (basic / general-purpose / advanced), and others —
sodaCat models the **superset** register/field surface in one block model.
Per-instance parameters record which features the underlying hardware actually
wires up.  Params are packed bitfields in the integration struct so the cost
stays compact regardless of how many flags accumulate.

The pattern comes in two complementary forms:

- **Presence flags** — boolean (or `int, max: 1`) params that say whether a
  feature exists on this instance.  E.g. `has_secure_ovr` on DMAMUX: false
  almost everywhere, true on L5.  See "Presence flags" below.
- **Extent params** — `int` params that give a silicon-valid range within a
  uniformly-shaped block.  E.g. `highest_channel` on DMAMUX: 15 on G4 (16
  channels), 4 on C0 (5 channels).  The block model declares the block-wide
  maximum; the param tells drivers where the valid range actually ends on
  this instance.  See "Extent params" below.

Both forms share the same enforcement contract — touching a register or field
outside the parameterised extent is a bug, not a soft fallback.

## Why unify

The driving goal is **driver reuse**, not model neatness.  A single driver
should cover as many hardware variants as practical — the construction-time
params tell it which variant it has.  Splitting the peripheral model means
splitting the driver, which is the cost being avoided.  So when faced with
"unify or split?", weigh how much driver code can stay shared, not just
whether the model files look tidy.

## The contract

A driver touching a register or field for a feature whose flag is `false` on
its instance is a **bug** — same status as a buffer overflow.  The flags are
not advisory.

The same goes for extent params: accessing `CCR[i]` for `i > highest_channel`
is a bug, not a soft no-op.  The C++ struct slot exists (the block declares
the array at block-wide max), but the silicon memory behind it isn't there;
reads return reserved values, writes have undefined effect.

Until C++26 contracts land, the enforcement is documentation + driver-side
discipline.  Eventually the integration struct's `if (params.foo) { ... }`
guards (and `i <= params.highest_x` bounds checks) should be expressible as
preconditions on driver methods, making the contract machine-checked instead
of conventional.

## Presence flags

The boolean form. Used when a register-or-field exists on some instances
and is silicon-reserved on others. Two encodings see use:

- `type: bool` with `default: true`/`false`
- `type: int` with `max: 1` and `default: 0`/`1` — equivalent semantically;
  this form makes the "1-bit field" intent explicit and pairs visually with
  the int extent params below.

Examples:
- DMAMUX `has_secure_ovr` — TrustZone-aware silicon exposes a second NVIC
  vector (OVR_S) for the secure world. True on L5, false elsewhere.
- DMAMUX `has_sync_overrun` — silicon has CSR/CFR per-channel sync-overrun
  registers. False on G0 (silicon-missing), true elsewhere.
- GpTimer `has_dma`, `has_break`, etc. — feature gates within the timer
  superset.

## Extent params

The int form. Used when a *uniformly-shaped* feature (an array of
identically-structured slots, or a field width that varies smoothly) is
present on every consumer but with different silicon-valid extents.

The block declaration carries the block-wide-maximum shape (the largest
array dim, the widest field) — extending it via `createArray` +
`patchRegisters` for arrays, or `patchFields` with a `bitWidth` bump for
fields. Per-instance extent params then tell each instance's driver where
the valid range ends.

Two sub-patterns:

### Highest-index params for arrays

When channel-like registers form an array, name the param
`highest_<thing>` and constrain it to the array dim's index range:

```yaml
- {name: highest_channel, type: int, default: 15, max: 31, ...}
```

The block holds `CCR[%s]` with `dim: 32`; the param caps the silicon-valid
subscript at 15 (G4) or 4 (C0) or 7 (H7 DMAMUX2). The "highest valid
index" semantic is preferred over a count (`channels: 16`) because the
direct bound check is `i <= highest_channel` — fewer off-by-one risks
than `i < channels`.

Pick `max` so the value fits in the next-smaller binary range (e.g.
`max: 31` → 5 bits, `max: 15` → 4 bits). This makes the storage cost
explicit and gives a hint about the silicon's address-space capacity.

### Field-width params for selectors

When a bitfield within a control register has different widths on
different instances (e.g. DMAREQ_ID is 7-bit on DMAMUX1, 5-bit on
DMAMUX2, 6-bit on C0's DMAMUX), the block declares the widest form
(8 bits — the register-layout maximum) and the param value IS the
silicon-valid width:

```yaml
- {name: request_inputs, type: int, default: 7, max: 8, ...}
```

Drivers convert to the addressable range with `1u << request_inputs`.
The bit-width encoding fits in 3 bits (1..8 → max=8), versus 9 bits
for the count encoding (2..256), making the storage cost explicit.

The naming follows the *meaning of the value the bit width determines*
("how many request inputs are there?") rather than the encoding shape
("how many bits is DMAREQ_ID?"). DMAMUX's three selector params —
`request_inputs`, `sync_inputs`, `request_triggers` — read as a coherent
trio describing the silicon, not a register-layout trivia listing.

## When to stop unifying

The natural break point is when the register maps no longer form a clean
superset — when the "larger" variant has registers at offsets the smaller
variant uses for something different, or when the basic register layout
itself diverges.  Past that point feature flags can't hide the asymmetry and
you're better off with separate models (and separate drivers).

## How to apply

- Prefer the unified-with-flags shape; bias toward unifying until the
  register-map argument breaks down.
- Don't try to enforce the contract with runtime guards or partial template
  specialisation in driver code — wait for C++26 contracts.  Until then,
  the flag is documentation that a code reviewer can check against the
  driver's actual register accesses.
- New flags should describe **hardware presence**, not driver behaviour —
  "has DMA support", not "use DMA for writes".  Behaviour belongs in the
  driver's own API.

## See also

- [tasks/shared-block-unification.md](../../tasks/shared-block-unification.md) —
  procedural guide for actually unifying a specific block.
- `svd/ST/STM32.yaml` `shared_blocks:` — cross-family shared blocks; most
  carry feature-flag params.
