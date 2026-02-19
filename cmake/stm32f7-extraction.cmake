# CMake module for generating STM32F7 family models
# This module extracts functional block and chip-level models from STM32F7 SVD files
# and organizes them for use across the entire F7 family.

# Find Python3 (required for SVD parsing and model generation)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Configuration
set(STM32F7_SVD_ZIP "${CMAKE_SOURCE_DIR}/svd/stm32f7-svd.zip" CACHE PATH
    "Path to stm32f7-svd.zip containing all STM32F7 SVD files")
set(STM32F7_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/ST" CACHE PATH
    "Output directory for generated STM32F7 models (source tree - commitable to git)")
set(STM32F7_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_stm32f7_models.py" CACHE PATH
    "Path to model generation script")

# STM32F7 Family definitions
set(STM32F7_FAMILIES
    "F72x_F73x:STM32F722,STM32F723,STM32F730,STM32F732,STM32F733"
    "F74x_F75x:STM32F745,STM32F746,STM32F750,STM32F756,STM32F765"
    "F76x_F77x:STM32F767,STM32F768,STM32F769,STM32F777,STM32F778,STM32F779"
)

# Create a CMake target for extracting all STM32F7 models
function(add_stm32f7_extraction_target target_name)
    set(extraction_marker "${CMAKE_BINARY_DIR}/stm32f7-models.stamp")

    add_custom_command(
        OUTPUT ${extraction_marker}
        COMMAND ${Python3_EXECUTABLE} ${STM32F7_GENERATOR}
                ${STM32F7_SVD_ZIP} ${STM32F7_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${extraction_marker}
        MAIN_DEPENDENCY ${STM32F7_SVD_ZIP}
        DEPENDS ${STM32F7_GENERATOR}
        COMMENT "Extracting STM32F7 family models from SVD files..."
        VERBATIM
    )

    add_custom_target(${target_name} ALL DEPENDS ${extraction_marker})

    message(STATUS "Added target '${target_name}' to extract STM32F7 models")
endfunction()

# Helper function to get block model path
function(get_stm32f7_block_path block_name family_or_common output_var)
    if(family_or_common STREQUAL "F7_common")
        set(${output_var} "${STM32F7_MODELS_DIR}/F7_common/${block_name}.yaml" PARENT_SCOPE)
    else()
        set(${output_var} "${STM32F7_MODELS_DIR}/${family_or_common}/blocks/${block_name}.yaml" PARENT_SCOPE)
    endif()
endfunction()

# Parse family definitions and return list of chips in a family
function(get_stm32f7_family_chips family_name output_var)
    foreach(family_def ${STM32F7_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        if(current_family STREQUAL family_name)
            string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
            string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
            set(${output_var} "${chips_list}" PARENT_SCOPE)
            return()
        endif()
    endforeach()

    message(FATAL_ERROR "Unknown STM32F7 family: ${family_name}")
endfunction()

# For documentation: print out the family structure
function(print_stm32f7_family_info)
    message(STATUS "STM32F7 Family Organization:")
    message(STATUS "")

    foreach(family_def ${STM32F7_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
        string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
        list(LENGTH chips_list num_chips)

        message(STATUS "  ${current_family}: ${num_chips} variants")
    endforeach()
endfunction()
