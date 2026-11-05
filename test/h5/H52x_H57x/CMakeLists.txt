add_library(soc-data-h5-H52x_H57x OBJECT)
set_target_properties(soc-data-h5-H52x_H57x PROPERTIES
    CXX_SCAN_FOR_MODULES ${FOR_MODULES}
    LINKER_LANGUAGE "CXX"
)
generate_header(soc-data-h5-H52x_H57x cxx ST/H5/H52x_H57x/STM32H523 .hpp)
generate_header(soc-data-h5-H52x_H57x cxx ST/H5/H52x_H57x/STM32H533 .hpp)
generate_header(soc-data-h5-H52x_H57x cxx ST/H5/H52x_H57x/STM32H562 .hpp)
generate_header(soc-data-h5-H52x_H57x cxx ST/H5/H52x_H57x/STM32H563 .hpp)
generate_header(soc-data-h5-H52x_H57x cxx ST/H5/H52x_H57x/STM32H573 .hpp)
