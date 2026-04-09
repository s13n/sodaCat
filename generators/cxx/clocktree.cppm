module;

#include <algorithm>
#include <array>
#include <cstdint>
#include <initializer_list>
#include <span>
#include <variant>

export module clocktree;

#define EXPORT export
#include "clocktree.hpp"

#ifdef EXPORT
#error "Header leaks EXPORT!"
#endif
