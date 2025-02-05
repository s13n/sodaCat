# Considerations for header generation

Generating a header from a YAML file requires some considerations which are to
be discussed here. The requirements can be summarized as follows:

- There should be a direct relationship between the names in the YAML file and
  the identifiers defined in the header, so that the relationship between the
  code and the chip data sheet or reference manual is obvious. Ideally, the
  names should be the same.
- The names should not be unnecessarily verbose, yet the risk of name clashes or
  ambiguities should be as low as possible.
- The definitions in the header should be easy to use, and hard to accidentally
  misuse, so good use should be made of the compiler's type checking abilities.
  But the programmer must be allowed to do what needs to be done, even in odd
  cases, so nothing should be made excessively difficult.
- Accesses to registers should be clearly visible in the source code, especially
  for multiple accesses. Read-modify-write accesses should be obvious, and not
  hidden behind a compound assignment.
- Special access methods should be supported, i.e. register sets that are not
  directly mapped into the address space. This covers registers accessible via
  I2C or SPI busses, or processors with specialized instructions or instruction
  sequences for access to special registers. 

## C header style

**Note:** A C header generator might be added in the future, for now we just
explain the ramifications.

When generating C headers, one is restricted by the limitations of the language.
Most prominently there is a lack of support for identifier scopes or namespaces,
which is generally addressed with name prefixes. The downside is that it leads
to long and verbose names.

C has the following distinct name spaces or scopes:

- The global (external) scope. Identifiers must be unique throughout all source
  files of a project, because they are visible by the linker.
- The file scope. Identifiers must be unique within the source file, including
  all headers it includes.
- The tag namespace. Identifiers must be unique within struct, union and enum
  tags.
- The block scope. Identifiers must be unique within a struct block or a code
  block, i.e. within a pair of curly braces.
- Preprocessor namespace. Identifiers must be unique at file scope.

A name declared at block scope hides the same name in outer scopes, including
file and global scopes. A tag name can be the same as a name at other scopes,
because it is always associated with the keywords `struct`, `union` or `enum`.
Names defined by the preprocessor hide all identical names defined elsewhere,
regardless of scope.

Avoiding preprocessor symbols as much as possible is desirable because of their
invasive nature and their lack of visibility for a debugger. This leaves the
struct/union/enum scopes for use by headers. Starting with C23 a fixed
underlying type can be given for an enum (supported in gcc >= 13).

Enum value names are in file scope and must be unique between different enums,
so prefixes will usually need to be used. Using the enum tag as the prefix is
the most straightforward solution.

### Reserved names

C mandates that valid identifier names begin with a letter or underscore,
followed by letters, underscores or digits in any mixture. Sticking to ASCII
characters is advisable, but since C99 Unicode escape sequences are also
supported within an identifier name. C23 rules that the first character must be
of Unicode class XID_Start, the remaining characters of class XID_Continue.
Lower and upper case characters are considered different.

There are the following exceptions:

- Language keywords may not be used as identifier names.
- Identifiers starting with two underscores are reserved.
- Identifiers starting with one underscore followed by an uppercase letter are
  reserved.
- Identifiers starting with one underscore and not followed by an uppercase
  letter may only be used at block scope.

Furthermore, other headers may define additional identifiers that populate the
global, file and/or tag namespaces. There's no fixed rule for those, so avoiding
a name clash is not always possible. Reducing the likelihood of such clashes
typically involves using name prefixes. It also helps to minimize the number of
headers that a source file includes.

Macro names are best restricted to use only uppercase letters to make them stand
out and reduce name clashes with other identifiers. We are trying to avoid them
altogether, however.

## C++ header style

**Note:** A C++ header file generator is included as an example. It generates
C++20 modules compatible code that can't be used with older compilers.

C style headers can easily be used with C++, so for uniformity you may want to
generate the C style headers even when using C++, but there are some important
advantages when using C++ that can make the generated headers more concise and
less prone of name clashes, since the more elaborate scoping rules of C++ can be
employed.

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

## Peripheral header

A certain peripheral is usually reused a lot by a manufacturer. It may appear in
multiple instances on the same chip, and sometimes the instances have a
different feature set. It may also appear in different chips of a series, or
even across different series of chips. In some cases the peripheral is licensed
to chip designers, so that the same peripheral may even appear in chips of
different manufacturers. In all cases you want to be able to write common driver
code for all.

It should be possible to write a driver for the peripheral that is oblivious to
the chip into which it is integrated. Such a driver would get the base address
and the interrupt number from the outside at the time of instantiation, i.e. as
constructor arguments. The driver code shouldn't need to include the chip-level
header at all.

In the ideal case you have a YAML file for the superset of all variants,
describing all possible features. The driver will then need to be parameterized
with information about the features that are actually implemented. In our case,
those parameters are provided via a reference to a constexpr struct with the
parameters for a single instance of the peripheral.

The peripheral header contains definitions for the register set of the
peripheral, and a definition of the parameter struct (here called "integration
struct"). As a minimum, the integration struct contains a pointer to the
register set of the peripheral. But often this is augmented by feature presence
bits, interrupt/exception numbers and more. As the information in the
integration struct is constant, it can reside in read-only memory.

An example makes this clearer (TODO: Bring this up to date):

```c++
// UART.hpp
struct UART {
    union {
        uint32_t TDR;  //!< Transmit data register
        uint32_t RDR;  //!< Receive data register
    };
    uint32_t CR;       //!< Control register
    uint32_t SR;       //!< Status register
};

namespace uart {
enum CR : uint32_t {
    WL = 0x3<<0,   //!< Wordlength selection
    WL_5 = 0,      //!< 5 data bits
    WL_6 = 1,      //!< 6 data bits
    WL_7 = 2,      //!< 7 data bits
    WL_8 = 3,      //!< 8 data bits
    PE = 0x1<<2,   //!< Parity enable
    //...
};

enum SR : uint32_t {
    RDRF = 0x1<<0, //!< Receive data register full
    TDRE = 0x1<<1, //!< Transmit data register empty
    //...
};
} // namespace
```

With this style of definitions, there's only one struct name and a namespace
name in the surrounding scope. A driver can bring all enum values into scope
with a using directive. It could look like this:

```c++
// UartDriver.hpp
struct UART;       // forward declaration, no need for #include here

class UartDriver : InterruptHandler {
public:
    UartDriver(UART volatile *hw) : hw_{hw} {}
private:
    void isr() override;   // from InterruptHandler
    UART volatile *hw_;    // pointer to register set of peripheral
};

// UartDriver.cpp
#include "UartDriver.hpp"
#include "UART.hpp"

using namespace uart;      // this could also be put into each function rather than at file scope

void UartDriver::isr() {
    if(hw_->SR & RDRF)     // bitfield mask name brought into scope by using directive
        char data = hw_->RDR;
    //...
}
```

## Chip-level header

A chip consists of a CPU connected to memory blocks and a number of peripherals.
The peripherals are defined in their own headers, to facilitate reuse. All
information that is specific to their integration onto a particular chip is
defined in the chip-level header. Information that belongs there are:

- Base address of each peripheral

Optionally:

- Interrupt numbers / interrupt vectors
- DMA request interconnects
- Clock signals feeding the peripheral
- Other signaling between functional blocks, such as event or wakeup
  interconnects
- Feature implementation details

The aim of this kind of separation into distinct headers is to define the
peripherals in a way that is not tied to a particular instantiation. The
function block itself should be decribed, not the way it is integrated into a
chip. Hence the base address has no business being specified in a peripheral
header, and neither has the interrupt number and all the other parameters,
because they typically vary between different chips using the peripheral block.

The chip-level header should only be needed by code that is specific to the chip
as a whole. Typically this information is needed at initialization time, when
the various driver objects get instantiated.

Note that peripheral base addresses are usually declared as a pointer to the
`volatile` register struct of the peripheral. Making the pointer point to a
volatile struct ensures that for accesses to all registers the compiler refrains
from optimizing register accesses, so that the code doesn't show surprising
behavior.

In some cases, i.e. some registers, there would be no harm in omitting the
volatile and allowing the optimization, but this is fairly uncommon with
hardware registers, so the overall `volatile` on the pointer is actually the
most convenient declaration style. Otherwise the `volatile` would have to be
applied selectively to individual register declarations, which is much more
verbose. Furthermore, by appplying the `volatile` to the pointer, it is easy to
choose non-volatile accesses by merely using a different pointer type.
