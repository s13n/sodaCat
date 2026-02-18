# CMake module for generating STM32H5 family models
# This module extracts functional block and chip-level models from STM32H5 SVD files
# and organizes them for use across the entire H5 family.

# Find Python3 (required for SVD parsing and model generation)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Configuration
set(STM32H5_SVD_ZIP "${CMAKE_SOURCE_DIR}/svd/stm32h5-svd.zip" CACHE PATH
    "Path to stm32h5-svd.zip containing all STM32H5 SVD files")
set(STM32H5_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/ST" CACHE PATH
    "Output directory for generated STM32H5 models (source tree - commitable to git)")
set(STM32H5_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_stm32h5_models.py" CACHE PATH
    "Path to model generation script")

# STM32H5 Family definitions
set(STM32H5_FAMILIES
    "H503:STM32H503"
    "H52x_H53x:STM32H523,STM32H533"
    "H56x_H57x:STM32H562,STM32H563,STM32H573"
)

# Create a CMake target for extracting all STM32H5 models
function(add_stm32h5_extraction_target target_name)
    set(extraction_marker "${CMAKE_BINARY_DIR}/stm32h5-models.stamp")

    add_custom_command(
        OUTPUT ${extraction_marker}
        COMMAND ${Python3_EXECUTABLE} ${STM32H5_GENERATOR}
                ${STM32H5_SVD_ZIP} ${STM32H5_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${extraction_marker}
        MAIN_DEPENDENCY ${STM32H5_SVD_ZIP}
        DEPENDS ${STM32H5_GENERATOR}
        COMMENT "Extracting STM32H5 family models from SVD files..."
        VERBATIM
    )

    add_custom_target(${target_name} ALL DEPENDS ${extraction_marker})

    message(STATUS "Added target '${target_name}' to extract STM32H5 models")
endfunction()

# Helper function to get block model path
function(get_stm32h5_block_path block_name family_or_common output_var)
    if(family_or_common STREQUAL "H5_common")
        set(${output_var} "${STM32H5_MODELS_DIR}/H5_common/${block_name}.yaml" PARENT_SCOPE)
    else()
        set(${output_var} "${STM32H5_MODELS_DIR}/${family_or_common}/blocks/${block_name}.yaml" PARENT_SCOPE)
    endif()
endfunction()

# Parse family definitions and return list of chips in a family
function(get_stm32h5_family_chips family_name output_var)
    foreach(family_def ${STM32H5_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        if(current_family STREQUAL family_name)
            string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
            string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
            set(${output_var} "${chips_list}" PARENT_SCOPE)
            return()
        endif()
    endforeach()

    message(FATAL_ERROR "Unknown STM32H5 family: ${family_name}")
endfunction()

# For documentation: print out the family structure
function(print_stm32h5_family_info)
    message(STATUS "STM32H5 Family Organization:")
    message(STATUS "")

    foreach(family_def ${STM32H5_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
        string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
        list(LENGTH chips_list num_chips)

        message(STATUS "  ${current_family}: ${num_chips} variants")
    endforeach()
endfunction()
