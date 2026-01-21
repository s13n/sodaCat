# C++ header generation

The C++ header file generator is included as an example. It generates C++20
modules compatible code that can also be used with older compilers, depending on
whether macro `REGISTERS_MODULE` is defined.

See the project in the `test` folder to see how this is used.

### C++ scoping rules

Starting from the C rules, the following additions are made:

- The struct/union/enum tags are automatically visible in the surrounding scope,
  but they can be hidden by an identifier in the same scope, in which case the
  keywords `struct`/`union`/`enum` need to be used to get the hidden meaning.
- A scoped enum (`enum class`) creates a new scope for the value definitions
  rather than making them visible in the surrounding scope.
- Inside a class, struct or union, all sorts of definitions can be placed,
  including nested class, struct, union or enum. The scope resolution operator
  `::` is used to disambiguate.
- Namespaces can be defined, and nested inside each other, which are also
  disambiguated with the scope resolution operator `::`. In contrast to the
  above, a namespace can be opened multiple times, and its content can be
  aliased into the current scope with `using namespace`. This is very convenient
  for dealing with potential name clashes, while reducing clutter, which makes
  it attractive for automatically generated headers.

### Scoped enums

Since C++11, the language supports scoped enums, whose value names don't appear
in the surrounding scope. While this sound just fine for us, there is a serious
drawback that effectively makes them inconvenient for our use case: The values
of scoped enums don't automatically convert to integers. Hence they can't be
combined easily with bitwise and arithmetic operators. You would need a cast,
which adds considerable clutter to the code. Or you would need to overload the
relevant operators to accept values from the scoped enums. That's not a
"lightweight" solution.

We therefore use namespaces: We make the plain, unscoped enum definitions part
of a namespace. To bring all enum values intos scope, `using namespace x;`
suffices.

### Inline namespaces

Namespaces can be declared inline, which automatically makes their content
visible within the surrounding namespace. While this appears pointless at first,
it has an important property: Name overlap with names from the surrounding scope
isn't an error. The name in the surrounding scope will be found preferentially,
but you can use the scope resolution operator to get at the name in the inline
namespace when necessary. This is useful to reduce clutter and still allow name
overlaps. It allows you to choose between being concise or being explicit on
each instance.

We use a trailing underscore with inline namespaces to help recognizing when
they are used to disambiguate names, and to minimize the chance of them being
confused with type names.

## Example

```c++
// UART.hpp
#include "registers.hpp"  // where HwReg template is defined
namespace chipFamily {
inline namespace UART_ {
struct CR {
    uint32_t WL:2,        //!< Wordlength selection
    uint32_t PE:1,        //!< Parity enable
    //...
};

struct SR {
    uint32_t RDRF:1,      //!< Receive data register full
    uint32_t TDRE:1,      //!< Transmit data register empty
    //...
};

struct UART {
    union {
        uint32_t TDR;     //!< Transmit data register
        uint32_t RDR;     //!< Receive data register
    };
    HwReg<struct CR> CR;  //!< Control register
    HwReg<struct SR> SR;  //!< Status register
};
} // namespace UART
} // namespace chipFamily
```

With this style of definitions, there's only a namespace name in the surrounding
scope (in the example it's namespace UART). Since it is an inline namespace, the
namespace name can be omitted unless there's an ambiguity. It could be used like
this:

```c++
// UartDriver.hpp
namespace chipFamily { inline namespace UART_ {
    struct UART;       // forward declaration, no need for #include here
}}

class UartDriver : InterruptHandler {
public:
    UartDriver(chipFamily::UART volatile *hw) : hw_{hw} {}
private:
    void isr() override;                // from InterruptHandler
    chipFamily::UART volatile *hw_;     // pointer to register set of peripheral
};

// UartDriver.cpp
#include "UartDriver.hpp"
#include "UART.hpp"

void UartDriver::isr() {
    if(hw_->SR.get().RDRF)
        char data = hw_->RDR;
    //...
}
```
