# CMake module for generating STM32U5 family models
# This module extracts functional block and chip-level models from STM32U5 SVD files
# and organizes them for use across the entire U5 family.

# Find Python3 (required for SVD parsing and model generation)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Configuration
set(STM32U5_SVD_ZIP "${CMAKE_SOURCE_DIR}/svd/stm32u5_svd.zip" CACHE PATH
    "Path to stm32u5_svd.zip containing all STM32U5 SVD files")
set(STM32U5_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/ST" CACHE PATH
    "Output directory for generated STM32U5 models (source tree - commitable to git)")
set(STM32U5_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_stm32u5_models.py" CACHE PATH
    "Path to model generation script")

# STM32U5 Family definitions
set(STM32U5_FAMILIES
    "U53x_U54x:STM32U535,STM32U545"
    "U57x_U58x:STM32U575,STM32U585"
    "U59x_U5Ax:STM32U595,STM32U599,STM32U5A5,STM32U5A9"
    "U5Fx_U5Gx:STM32U5Fx,STM32U5Gx"
)

# Create a CMake target for extracting all STM32U5 models
function(add_stm32u5_extraction_target target_name)
    set(extraction_marker "${CMAKE_BINARY_DIR}/stm32u5-models.stamp")

    add_custom_command(
        OUTPUT ${extraction_marker}
        COMMAND ${Python3_EXECUTABLE} ${STM32U5_GENERATOR}
                ${STM32U5_SVD_ZIP} ${STM32U5_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${extraction_marker}
        MAIN_DEPENDENCY ${STM32U5_SVD_ZIP}
        DEPENDS ${STM32U5_GENERATOR}
        COMMENT "Extracting STM32U5 family models from SVD files..."
        VERBATIM
    )

    add_custom_target(${target_name} ALL DEPENDS ${extraction_marker})

    message(STATUS "Added target '${target_name}' to extract STM32U5 models")
endfunction()

# Helper function to get block model path
function(get_stm32u5_block_path block_name family_or_common output_var)
    if(family_or_common STREQUAL "U5_common")
        set(${output_var} "${STM32U5_MODELS_DIR}/U5_common/${block_name}.yaml" PARENT_SCOPE)
    else()
        set(${output_var} "${STM32U5_MODELS_DIR}/${family_or_common}/blocks/${block_name}.yaml" PARENT_SCOPE)
    endif()
endfunction()

# Parse family definitions and return list of chips in a family
function(get_stm32u5_family_chips family_name output_var)
    foreach(family_def ${STM32U5_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        if(current_family STREQUAL family_name)
            string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
            string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
            set(${output_var} "${chips_list}" PARENT_SCOPE)
            return()
        endif()
    endforeach()

    message(FATAL_ERROR "Unknown STM32U5 family: ${family_name}")
endfunction()

# For documentation: print out the family structure
function(print_stm32u5_family_info)
    message(STATUS "STM32U5 Family Organization:")
    message(STATUS "")

    foreach(family_def ${STM32U5_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
        string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
        list(LENGTH chips_list num_chips)

        message(STATUS "  ${current_family}: ${num_chips} variants")
    endforeach()
endfunction()
