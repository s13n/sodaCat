add_library(soc-data-h5-H503 OBJECT)
set_target_properties(soc-data-h5-H503 PROPERTIES
    CXX_SCAN_FOR_MODULES ${FOR_MODULES}
    LINKER_LANGUAGE "CXX"
)
generate_header(soc-data-h5-H503 cxx ST/H5/H503/STM32H503 .hpp)
