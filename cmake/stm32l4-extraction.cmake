# CMake module for generating STM32L4 family models
# This module extracts functional block and chip-level models from STM32L4 SVD files
# and organizes them for use across the entire L4 family.

# Find Python3 (required for SVD parsing and model generation)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Configuration
set(STM32L4_SVD_ZIP "${CMAKE_SOURCE_DIR}/svd/stm32l4_svd.zip" CACHE PATH
    "Path to stm32l4_svd.zip containing all STM32L4 SVD files")
set(STM32L4_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/ST" CACHE PATH
    "Output directory for generated STM32L4 models (source tree - commitable to git)")
set(STM32L4_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_stm32l4_models.py" CACHE PATH
    "Path to model generation script")

# STM32L4 Family definitions
set(STM32L4_FAMILIES
    "L41x_L42x:STM32L412,STM32L422"
    "L43x_L44x:STM32L431,STM32L432,STM32L433,STM32L442,STM32L443"
    "L45x_L46x:STM32L451,STM32L452,STM32L462"
    "L47x_L48x:STM32L471,STM32L475,STM32L476,STM32L486"
    "L49x_L4Ax:STM32L496,STM32L4A6"
)

# Create a CMake target for extracting all STM32L4 models
function(add_stm32l4_extraction_target target_name)
    set(extraction_marker "${CMAKE_BINARY_DIR}/stm32l4-models.stamp")

    add_custom_command(
        OUTPUT ${extraction_marker}
        COMMAND ${Python3_EXECUTABLE} ${STM32L4_GENERATOR}
                ${STM32L4_SVD_ZIP} ${STM32L4_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${extraction_marker}
        MAIN_DEPENDENCY ${STM32L4_SVD_ZIP}
        DEPENDS ${STM32L4_GENERATOR}
        COMMENT "Extracting STM32L4 family models from SVD files..."
        VERBATIM
    )

    add_custom_target(${target_name} ALL DEPENDS ${extraction_marker})

    message(STATUS "Added target '${target_name}' to extract STM32L4 models")
endfunction()

# Helper function to get block model path
function(get_stm32l4_block_path block_name family_or_common output_var)
    if(family_or_common STREQUAL "L4_common")
        set(${output_var} "${STM32L4_MODELS_DIR}/L4_common/${block_name}.yaml" PARENT_SCOPE)
    else()
        set(${output_var} "${STM32L4_MODELS_DIR}/${family_or_common}/blocks/${block_name}.yaml" PARENT_SCOPE)
    endif()
endfunction()

# Parse family definitions and return list of chips in a family
function(get_stm32l4_family_chips family_name output_var)
    foreach(family_def ${STM32L4_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        if(current_family STREQUAL family_name)
            string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
            string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
            set(${output_var} "${chips_list}" PARENT_SCOPE)
            return()
        endif()
    endforeach()

    message(FATAL_ERROR "Unknown STM32L4 family: ${family_name}")
endfunction()

# For documentation: print out the family structure
function(print_stm32l4_family_info)
    message(STATUS "STM32L4 Family Organization:")
    message(STATUS "")

    foreach(family_def ${STM32L4_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
        string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
        list(LENGTH chips_list num_chips)

        message(STATUS "  ${current_family}: ${num_chips} variants")
    endforeach()
endfunction()
