## Code generator change: peripheral-level namespace

### Problem

When all generated peripheral headers are included together (via the SoC-level header), `inline namespace` declarations at the peripheral level collide with identically-named inline namespaces inside SYSCON. For example, `inline namespace WKT_` from `WKT.hpp` is ambiguous with `inline namespace WKT_` inside `SYSCON.hpp`'s `SYSAHBCLKCTRL0_` and `STARTERP1_` registers, because the inline chain promotes all of them to the `lpc865` scope.

### Change

For the **outermost (peripheral-level) namespace** in each generated peripheral header, change from:

```cpp
inline namespace WKT_ {
```

to:

```cpp
namespace WKT {
```

Two things change at this level only:

1. Remove `inline` — prevents the namespace from merging into the parent SoC namespace, avoiding collisions with SYSCON bitfield namespaces that reuse peripheral names.
2. Remove the trailing underscore — since this namespace is non-inline, its name never collides with the `struct` of the same name inside it (they live in different scopes). The trailing underscore convention is only needed for inline namespaces where the namespace name and its contained type would otherwise conflict via promotion.

### Scope

- Applies only to the peripheral-level namespace (the outermost one inside the SoC namespace, e.g. `WKT_`, `WWDT_`, `SYSCON_`, `SPI_`, etc.).
- All inner namespaces (register-level, field-level) remain `inline` with trailing underscore, unchanged.
- The `integration` struct references (e.g. `HwPtr<struct WKT_::WKT volatile>`) must be updated to use the new name (e.g. `WKT::WKT`).

### Example

Before:

```cpp
namespace lpc865 {
inline namespace WKT_ {
inline namespace CTRL_ {
// ...
} // namespace CTRL_
struct WKT { ... };
} // namespace WKT_

namespace integration {
struct WKT {
    HwPtr<struct WKT_::WKT volatile> registers;
};
} // namespace integration
} // namespace lpc865
```

After:

```cpp
namespace lpc865 {
namespace WKT {
inline namespace CTRL_ {
// ...
} // namespace CTRL_
struct WKT { ... };
} // namespace WKT

namespace integration {
struct WKT {
    HwPtr<struct WKT::WKT volatile> registers;
};
} // namespace integration
} // namespace lpc865
```

### Impact on user code

Driver files that previously relied on peripheral types being visible directly in the SoC namespace need an explicit `using namespace`:

```cpp
// wkt_drv.cpp
#include "WKT.hpp"
using namespace lpc865::WKT;
```
