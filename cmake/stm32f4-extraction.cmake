# CMake module for generating STM32F4 family models
# This module extracts functional block and chip-level models from STM32F4 SVD files
# and organizes them for use across the entire F4 family.

# Find Python3 (required for SVD parsing and model generation)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Configuration
set(STM32F4_SVD_ZIP "${CMAKE_SOURCE_DIR}/svd/stm32f4-svd.zip" CACHE PATH
    "Path to stm32f4-svd.zip containing all STM32F4 SVD files")
set(STM32F4_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/ST" CACHE PATH
    "Output directory for generated STM32F4 models (source tree - commitable to git)")
set(STM32F4_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_stm32f4_models.py" CACHE PATH
    "Path to model generation script")

# STM32F4 Family definitions
set(STM32F4_FAMILIES
    "F401_F410_F411:STM32F401,STM32F410,STM32F411"
    "F405_F407:STM32F405,STM32F407,STM32F415,STM32F417"
    "F412_F413_F423:STM32F412,STM32F413,STM32F423"
    "F42x_F43x:STM32F427,STM32F429,STM32F437,STM32F439"
    "F446_F469_F479:STM32F446,STM32F469,STM32F479"
)

# Create a CMake target for extracting all STM32F4 models
function(add_stm32f4_extraction_target target_name)
    set(extraction_marker "${CMAKE_BINARY_DIR}/stm32f4-models.stamp")

    add_custom_command(
        OUTPUT ${extraction_marker}
        COMMAND ${Python3_EXECUTABLE} ${STM32F4_GENERATOR}
                ${STM32F4_SVD_ZIP} ${STM32F4_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${extraction_marker}
        MAIN_DEPENDENCY ${STM32F4_SVD_ZIP}
        DEPENDS ${STM32F4_GENERATOR}
        COMMENT "Extracting STM32F4 family models from SVD files..."
        VERBATIM
    )

    add_custom_target(${target_name} ALL DEPENDS ${extraction_marker})

    message(STATUS "Added target '${target_name}' to extract STM32F4 models")
endfunction()

# Helper function to get block model path
function(get_stm32f4_block_path block_name family_or_common output_var)
    if(family_or_common STREQUAL "F4_common")
        set(${output_var} "${STM32F4_MODELS_DIR}/F4/${block_name}.yaml" PARENT_SCOPE)
    else()
        set(${output_var} "${STM32F4_MODELS_DIR}/F4/${family_or_common}/${block_name}.yaml" PARENT_SCOPE)
    endif()
endfunction()

# Parse family definitions and return list of chips in a family
function(get_stm32f4_family_chips family_name output_var)
    foreach(family_def ${STM32F4_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        if(current_family STREQUAL family_name)
            string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
            string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
            set(${output_var} "${chips_list}" PARENT_SCOPE)
            return()
        endif()
    endforeach()

    message(FATAL_ERROR "Unknown STM32F4 family: ${family_name}")
endfunction()

# For documentation: print out the family structure
function(print_stm32f4_family_info)
    message(STATUS "STM32F4 Family Organization:")
    message(STATUS "")

    foreach(family_def ${STM32F4_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
        string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
        list(LENGTH chips_list num_chips)

        message(STATUS "  ${current_family}: ${num_chips} variants")
    endforeach()
endfunction()
