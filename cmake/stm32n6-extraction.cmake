# CMake module for generating STM32N6 family models
# This module extracts functional block and chip-level models from STM32N6 SVD files
# and organizes them for use across the entire N6 family.

# Find Python3 (required for SVD parsing and model generation)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Configuration
set(STM32N6_SVD_ZIP "${CMAKE_SOURCE_DIR}/svd/stm32n6-svd.zip" CACHE PATH
    "Path to stm32n6-svd.zip containing all STM32N6 SVD files")
set(STM32N6_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/ST" CACHE PATH
    "Output directory for generated STM32N6 models (source tree - commitable to git)")
set(STM32N6_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_stm32n6_models.py" CACHE PATH
    "Path to model generation script")

# STM32N6 Family definitions
set(STM32N6_FAMILIES
    "N64x:STM32N645,STM32N647"
    "N65x:STM32N655,STM32N657"
)

# Create a CMake target for extracting all STM32N6 models
function(add_stm32n6_extraction_target target_name)
    set(extraction_marker "${CMAKE_BINARY_DIR}/stm32n6-models.stamp")

    add_custom_command(
        OUTPUT ${extraction_marker}
        COMMAND ${Python3_EXECUTABLE} ${STM32N6_GENERATOR}
                ${STM32N6_SVD_ZIP} ${STM32N6_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${extraction_marker}
        MAIN_DEPENDENCY ${STM32N6_SVD_ZIP}
        DEPENDS ${STM32N6_GENERATOR}
        COMMENT "Extracting STM32N6 family models from SVD files..."
        VERBATIM
    )

    add_custom_target(${target_name} ALL DEPENDS ${extraction_marker})

    message(STATUS "Added target '${target_name}' to extract STM32N6 models")
endfunction()

# Helper function to get block model path
function(get_stm32n6_block_path block_name family_or_common output_var)
    if(family_or_common STREQUAL "N6_common")
        set(${output_var} "${STM32N6_MODELS_DIR}/N6/${block_name}.yaml" PARENT_SCOPE)
    else()
        set(${output_var} "${STM32N6_MODELS_DIR}/N6/${family_or_common}/${block_name}.yaml" PARENT_SCOPE)
    endif()
endfunction()

# Parse family definitions and return list of chips in a family
function(get_stm32n6_family_chips family_name output_var)
    foreach(family_def ${STM32N6_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        if(current_family STREQUAL family_name)
            string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
            string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
            set(${output_var} "${chips_list}" PARENT_SCOPE)
            return()
        endif()
    endforeach()

    message(FATAL_ERROR "Unknown STM32N6 family: ${family_name}")
endfunction()

# For documentation: print out the family structure
function(print_stm32n6_family_info)
    message(STATUS "STM32N6 Family Organization:")
    message(STATUS "")

    foreach(family_def ${STM32N6_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
        string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
        list(LENGTH chips_list num_chips)

        message(STATUS "  ${current_family}: ${num_chips} variants")
    endforeach()
endfunction()
