add_library(soc-data-h5-H5Ex_H5Fx OBJECT)
set_target_properties(soc-data-h5-H5Ex_H5Fx PROPERTIES
    CXX_SCAN_FOR_MODULES ${FOR_MODULES}
    LINKER_LANGUAGE "CXX"
)
generate_header(soc-data-h5-H5Ex_H5Fx cxx ST/H5/H5Ex_H5Fx/STM32H5E4 .hpp)
generate_header(soc-data-h5-H5Ex_H5Fx cxx ST/H5/H5Ex_H5Fx/STM32H5E5 .hpp)
generate_header(soc-data-h5-H5Ex_H5Fx cxx ST/H5/H5Ex_H5Fx/STM32H5F4 .hpp)
generate_header(soc-data-h5-H5Ex_H5Fx cxx ST/H5/H5Ex_H5Fx/STM32H5F5 .hpp)
