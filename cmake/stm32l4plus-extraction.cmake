# CMake module for generating STM32L4+ family models
# This module extracts functional block and chip-level models from STM32L4+ SVD files
# and organizes them for use across the entire L4+ family.

# Find Python3 (required for SVD parsing and model generation)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Configuration
set(STM32L4P_SVD_ZIP "${CMAKE_SOURCE_DIR}/svd/stm32l4plus-svd.zip" CACHE PATH
    "Path to stm32l4plus-svd.zip containing all STM32L4+ SVD files")
set(STM32L4P_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/ST" CACHE PATH
    "Output directory for generated STM32L4+ models (source tree - commitable to git)")
set(STM32L4P_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_stm32l4plus_models.py" CACHE PATH
    "Path to model generation script")

# STM32L4+ Family definitions
set(STM32L4P_FAMILIES
    "L4Px_L4Qx:STM32L4P5,STM32L4Q5"
    "L4Rx_L4Sx:STM32L4R5,STM32L4R7,STM32L4R9,STM32L4S5,STM32L4S7,STM32L4S9"
)

# Create a CMake target for extracting all STM32L4+ models
function(add_stm32l4plus_extraction_target target_name)
    set(extraction_marker "${CMAKE_BINARY_DIR}/stm32l4plus-models.stamp")

    add_custom_command(
        OUTPUT ${extraction_marker}
        COMMAND ${Python3_EXECUTABLE} ${STM32L4P_GENERATOR}
                ${STM32L4P_SVD_ZIP} ${STM32L4P_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${extraction_marker}
        MAIN_DEPENDENCY ${STM32L4P_SVD_ZIP}
        DEPENDS ${STM32L4P_GENERATOR}
        COMMENT "Extracting STM32L4+ family models from SVD files..."
        VERBATIM
    )

    add_custom_target(${target_name} ALL DEPENDS ${extraction_marker})

    message(STATUS "Added target '${target_name}' to extract STM32L4+ models")
endfunction()

# Helper function to get block model path
function(get_stm32l4plus_block_path block_name family_or_common output_var)
    if(family_or_common STREQUAL "L4P_common")
        set(${output_var} "${STM32L4P_MODELS_DIR}/L4P_common/${block_name}.yaml" PARENT_SCOPE)
    else()
        set(${output_var} "${STM32L4P_MODELS_DIR}/${family_or_common}/blocks/${block_name}.yaml" PARENT_SCOPE)
    endif()
endfunction()

# Parse family definitions and return list of chips in a family
function(get_stm32l4plus_family_chips family_name output_var)
    foreach(family_def ${STM32L4P_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        if(current_family STREQUAL family_name)
            string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
            string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
            set(${output_var} "${chips_list}" PARENT_SCOPE)
            return()
        endif()
    endforeach()

    message(FATAL_ERROR "Unknown STM32L4+ family: ${family_name}")
endfunction()

# For documentation: print out the family structure
function(print_stm32l4plus_family_info)
    message(STATUS "STM32L4+ Family Organization:")
    message(STATUS "")

    foreach(family_def ${STM32L4P_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
        string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
        list(LENGTH chips_list num_chips)

        message(STATUS "  ${current_family}: ${num_chips} variants")
    endforeach()
endfunction()
