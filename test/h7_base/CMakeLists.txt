# H7 family-base blocks whose header path collides with a subfamily variant
# that the STM32H757 chip in the parent directory pulls in (both are in
# namespace stm32h7).  Generated into this binary directory instead; the
# target compiles the header through its .cppm wrapper.

add_library(soc-data-h7-base OBJECT)
set_target_properties(soc-data-h7-base PROPERTIES
    CXX_SCAN_FOR_MODULES ${FOR_MODULES}
    LINKER_LANGUAGE "CXX"
)
generate_header(soc-data-h7-base cxx ST/H7/SYSCFG .hpp)
