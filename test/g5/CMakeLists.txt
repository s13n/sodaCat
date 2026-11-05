# STM32G5: compile every chip.  All G5 blocks are family-level (no
# subfamily variants), so both subfamilies fit in one binary directory.

add_library(soc-data-g5 OBJECT)
set_target_properties(soc-data-g5 PROPERTIES
    CXX_SCAN_FOR_MODULES ${FOR_MODULES}
    LINKER_LANGUAGE "CXX"
)
generate_header(soc-data-g5 cxx ST/G5/G53x_G54x/STM32G534 .hpp)
generate_header(soc-data-g5 cxx ST/G5/G53x_G54x/STM32G544 .hpp)
generate_header(soc-data-g5 cxx ST/G5/G55x_G56x/STM32G553 .hpp)
generate_header(soc-data-g5 cxx ST/G5/G55x_G56x/STM32G554 .hpp)
generate_header(soc-data-g5 cxx ST/G5/G55x_G56x/STM32G563 .hpp)
generate_header(soc-data-g5 cxx ST/G5/G55x_G56x/STM32G564 .hpp)
