# Feature-flag params: driver reuse via unified peripheral models

When peripherals exist across capability tiers — ST USART / LPUART, Microchip
UART / USART, ST timers (basic / general-purpose / advanced), and others —
sodaCat models the **superset** register/field surface in one block model.
Per-instance boolean parameters record which features the underlying hardware
actually wires up.  Params are packed bitfields in the integration struct so
the cost stays compact regardless of how many flags accumulate.

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

Until C++26 contracts land, the enforcement is documentation + driver-side
discipline.  Eventually the integration struct's `if (params.foo) { ... }`
guards should be expressible as preconditions on driver methods, making the
contract machine-checked instead of conventional.

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
