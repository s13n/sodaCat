# CMake module for generating STM32L1 family models
# This module extracts functional block and chip-level models from STM32L1 SVD files
# and organizes them for use across the entire L1 family.

# Find Python3 (required for SVD parsing and model generation)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Configuration
set(STM32L1_SVD_ZIP "${CMAKE_SOURCE_DIR}/svd/stm32l1_svd.zip" CACHE PATH
    "Path to stm32l1_svd.zip containing all STM32L1 SVD files")
set(STM32L1_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/ST" CACHE PATH
    "Output directory for generated STM32L1 models (source tree - commitable to git)")
set(STM32L1_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_stm32l1_models.py" CACHE PATH
    "Path to model generation script")

# STM32L1 Family definitions
set(STM32L1_FAMILIES
    "L10x:STM32L100"
    "L15x_L16x:STM32L151,STM32L152,STM32L162"
)

# Create a CMake target for extracting all STM32L1 models
function(add_stm32l1_extraction_target target_name)
    set(extraction_marker "${CMAKE_BINARY_DIR}/stm32l1-models.stamp")

    add_custom_command(
        OUTPUT ${extraction_marker}
        COMMAND ${Python3_EXECUTABLE} ${STM32L1_GENERATOR}
                ${STM32L1_SVD_ZIP} ${STM32L1_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${extraction_marker}
        MAIN_DEPENDENCY ${STM32L1_SVD_ZIP}
        DEPENDS ${STM32L1_GENERATOR}
        COMMENT "Extracting STM32L1 family models from SVD files..."
        VERBATIM
    )

    add_custom_target(${target_name} ALL DEPENDS ${extraction_marker})

    message(STATUS "Added target '${target_name}' to extract STM32L1 models")
endfunction()

# Helper function to get block model path
function(get_stm32l1_block_path block_name family_or_common output_var)
    if(family_or_common STREQUAL "L1_common")
        set(${output_var} "${STM32L1_MODELS_DIR}/L1_common/${block_name}.yaml" PARENT_SCOPE)
    else()
        set(${output_var} "${STM32L1_MODELS_DIR}/${family_or_common}/blocks/${block_name}.yaml" PARENT_SCOPE)
    endif()
endfunction()

# Parse family definitions and return list of chips in a family
function(get_stm32l1_family_chips family_name output_var)
    foreach(family_def ${STM32L1_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        if(current_family STREQUAL family_name)
            string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
            string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
            set(${output_var} "${chips_list}" PARENT_SCOPE)
            return()
        endif()
    endforeach()

    message(FATAL_ERROR "Unknown STM32L1 family: ${family_name}")
endfunction()

# For documentation: print out the family structure
function(print_stm32l1_family_info)
    message(STATUS "STM32L1 Family Organization:")
    message(STATUS "")

    foreach(family_def ${STM32L1_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
        string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
        list(LENGTH chips_list num_chips)

        message(STATUS "  ${current_family}: ${num_chips} variants")
    endforeach()
endfunction()
