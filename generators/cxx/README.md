# C++ header generation

The C++ header file generator produces C++20 modules compatible code that can
also be used with older compilers, depending on whether the macro
`REGISTERS_MODULE` is defined.

Note that the Python generator scripts require `ruamel.yaml` to be installed.

## CMake integration

The `sodaCat.cmake` module provides everything needed to generate C++ headers
from YAML models in a downstream project. It can fetch both the generator
scripts and model files automatically from a remote repository.

### Setup

```cmake
cmake_minimum_required(VERSION 3.28)
project(my_firmware CXX)

set(CMAKE_CXX_STANDARD 20)

# Point to the sodaCat models — either a local checkout or a download directory
set(SODACAT_LOCAL_DIR "${CMAKE_SOURCE_DIR}/models")

# Optional: enable auto-download of models and generators from a remote repo
set(SODACAT_URL_BASE "https://raw.githubusercontent.com/<owner>/sodaCat/main")

# Include the integration module and fetch the C++ generator
list(APPEND CMAKE_MODULE_PATH "<path-to-sodacat>/cmake")
include(sodaCat)
sodacat_fetch_generator(cxx)
```

`sodacat_fetch_generator(cxx)` locates the generator scripts. When they exist
locally (e.g. in a sodaCat checkout), they are used directly. Otherwise, if
`SODACAT_URL_BASE` is set, they are downloaded from the remote repository.

### Generating headers

Use `generate_header()` to turn a YAML model into a C++ header and add it to
a target:

```cmake
generate_header(<target> <language> <namespace> <model_path> <suffix>)
```

Parameters:
- **target** — CMake target to attach the generated header to
- **language** — Generator language directory (e.g. `cxx`)
- **namespace** — C++ namespace for the generated code
- **model_path** — Path to the YAML model relative to `SODACAT_LOCAL_DIR`,
  without the `.yaml` extension
- **suffix** — File extension for the generated header (e.g. `.hpp`)

Example for an STM32H757 project:

```cmake
add_library(soc-data OBJECT)

# Chip model — automatically pulls in block model dependencies
generate_header(soc-data cxx stm32h7 ST/H7/H745_H757/STM32H757_CM7 .hpp)

# Individual block models
generate_header(soc-data cxx stm32h7 ST/H7/H745_H757/RCC .hpp)
generate_header(soc-data cxx stm32h7 ST/GPIO .hpp)
generate_header(soc-data cxx stm32h7 ST/USART .hpp)
```

The function handles deduplication — calling `generate_header` for the same
model path more than once is safe and only generates the header once.

### Model auto-download

When `SODACAT_URL_BASE` is set and a model file is not found under
`SODACAT_LOCAL_DIR`, it is downloaded automatically. Chip models contain a
`models:` section listing their block model dependencies, and these are fetched
transitively — so generating a chip header downloads all referenced block
models as well.

### Minimal downstream example

```cmake
cmake_minimum_required(VERSION 3.28)
project(my_firmware CXX)
set(CMAKE_CXX_STANDARD 20)

set(SODACAT_LOCAL_DIR "${CMAKE_SOURCE_DIR}/models")
list(APPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/third_party/sodaCat/cmake")
include(sodaCat)
sodacat_fetch_generator(cxx)

add_library(hw-registers OBJECT)
generate_header(hw-registers cxx myns ST/H7/H745_H757/STM32H757_CM7 .hpp)
generate_header(hw-registers cxx myns ST/USART .hpp)
generate_header(hw-registers cxx myns ST/GPIO .hpp)

add_executable(firmware main.cpp)
target_link_libraries(firmware PRIVATE hw-registers)
```

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
namespace UART {
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
scope (in the example it's namespace UART). One would usually have a `using
namespace chipFamily::UART` declaration in the driver source. It could be used
like this:

```c++
// UartDriver.hpp
namespace chipFamily { namespace UART {
    struct UART;       // forward declaration, no need for #include here
}}

class UartDriver : InterruptHandler {
public:
    UartDriver(chipFamily::UART::UART volatile *hw) : hw_{hw} {}
private:
    void isr() override;                // from InterruptHandler
    chipFamily::UART::UART volatile *hw_;     // pointer to register set of peripheral
};

// UartDriver.cpp
#include "UartDriver.hpp"
#include "UART.hpp"

using namespace chipFamily::UART;

void UartDriver::isr() {
    if(hw_->SR.get().RDRF)
        char data = hw_->RDR;
    //...
}
```
