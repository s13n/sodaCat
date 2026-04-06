module;

#include <algorithm>
#include <bit>
#include <cstdint>
#include <cstring>
#include <type_traits>
#include <version>

export module hwreg;

#define EXPORT export
#include "hwreg.hpp"
#undef EXPORT
