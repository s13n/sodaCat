/**@file
 * C++20 module version of registers.hpp
 */

// GCC doesn't support standard header units yet, so we have to
// use includes in the global module fragment.
// Once standard library modules are supported, those can be replaced
// with a simple `import std;`

module;

#include <algorithm>
#include <bit>
#include <cstdint>
#include <cstring>
#include <type_traits>
#include <version>

export module registers;

#define REGISTERS_MODULE

#include "registers.hpp"
