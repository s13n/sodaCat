# CMake module for generating STM32G0 family models
# This module extracts functional block and chip-level models from STM32G0 SVD files
# and organizes them for use across the entire G0 family.

# Find Python3 (required for SVD parsing and model generation)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Configuration
set(STM32G0_SVD_ZIP "${CMAKE_SOURCE_DIR}/svd/stm32g0-svd.zip" CACHE PATH
    "Path to stm32g0-svd.zip containing all STM32G0 SVD files")
set(STM32G0_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/ST" CACHE PATH
    "Output directory for generated STM32G0 models (source tree - commitable to git)")
set(STM32G0_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_stm32g0_models.py" CACHE PATH
    "Path to model generation script")

# STM32G0 Family definitions
set(STM32G0_FAMILIES
    "G03x_G04x:STM32G030,STM32G031,STM32G041"
    "G05x_G06x:STM32G050,STM32G051,STM32G061"
    "G07x_G08x:STM32G070,STM32G071,STM32G081"
    "G0Bx_G0Cx:STM32G0B0,STM32G0B1,STM32G0C1"
)

# Create a CMake target for extracting all STM32G0 models
function(add_stm32g0_extraction_target target_name)
    set(extraction_marker "${CMAKE_BINARY_DIR}/stm32g0-models.stamp")

    add_custom_command(
        OUTPUT ${extraction_marker}
        COMMAND ${Python3_EXECUTABLE} ${STM32G0_GENERATOR}
                ${STM32G0_SVD_ZIP} ${STM32G0_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${extraction_marker}
        MAIN_DEPENDENCY ${STM32G0_SVD_ZIP}
        DEPENDS ${STM32G0_GENERATOR}
        COMMENT "Extracting STM32G0 family models from SVD files..."
        VERBATIM
    )

    add_custom_target(${target_name} ALL DEPENDS ${extraction_marker})

    message(STATUS "Added target '${target_name}' to extract STM32G0 models")
endfunction()

# Helper function to get block model path
function(get_stm32g0_block_path block_name family_or_common output_var)
    if(family_or_common STREQUAL "G0_common")
        set(${output_var} "${STM32G0_MODELS_DIR}/G0/${block_name}.yaml" PARENT_SCOPE)
    else()
        set(${output_var} "${STM32G0_MODELS_DIR}/G0/${family_or_common}/${block_name}.yaml" PARENT_SCOPE)
    endif()
endfunction()

# Parse family definitions and return list of chips in a family
function(get_stm32g0_family_chips family_name output_var)
    foreach(family_def ${STM32G0_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        if(current_family STREQUAL family_name)
            string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
            string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
            set(${output_var} "${chips_list}" PARENT_SCOPE)
            return()
        endif()
    endforeach()

    message(FATAL_ERROR "Unknown STM32G0 family: ${family_name}")
endfunction()

# For documentation: print out the family structure
function(print_stm32g0_family_info)
    message(STATUS "STM32G0 Family Organization:")
    message(STATUS "")

    foreach(family_def ${STM32G0_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
        string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
        list(LENGTH chips_list num_chips)

        message(STATUS "  ${current_family}: ${num_chips} variants")
    endforeach()
endfunction()
