# CMake module for generating STM32G4 family models
# This module extracts functional block and chip-level models from STM32G4 SVD files
# and organizes them for use across the entire G4 family.

# Find Python3 (required for SVD parsing and model generation)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Configuration
set(STM32G4_SVD_ZIP "${CMAKE_SOURCE_DIR}/svd/stm32g4_svd.zip" CACHE PATH
    "Path to stm32g4_svd.zip containing all STM32G4 SVD files")
set(STM32G4_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/ST" CACHE PATH
    "Output directory for generated STM32G4 models (source tree - commitable to git)")
set(STM32G4_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_stm32g4_models.py" CACHE PATH
    "Path to model generation script")

# STM32G4 Family definitions
set(STM32G4_FAMILIES
    "G43x_G44x:STM32G431,STM32G441,STM32GBK1CBT6"
    "G47x_G48x:STM32G471,STM32G473,STM32G474,STM32G483,STM32G484"
    "G49x_G4Ax:STM32G491,STM32G4A1"
)

# Create a CMake target for extracting all STM32G4 models
function(add_stm32g4_extraction_target target_name)
    set(extraction_marker "${CMAKE_BINARY_DIR}/stm32g4-models.stamp")

    add_custom_command(
        OUTPUT ${extraction_marker}
        COMMAND ${Python3_EXECUTABLE} ${STM32G4_GENERATOR}
                ${STM32G4_SVD_ZIP} ${STM32G4_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${extraction_marker}
        MAIN_DEPENDENCY ${STM32G4_SVD_ZIP}
        DEPENDS ${STM32G4_GENERATOR}
        COMMENT "Extracting STM32G4 family models from SVD files..."
        VERBATIM
    )

    add_custom_target(${target_name} ALL DEPENDS ${extraction_marker})

    message(STATUS "Added target '${target_name}' to extract STM32G4 models")
endfunction()

# Helper function to get block model path
function(get_stm32g4_block_path block_name family_or_common output_var)
    if(family_or_common STREQUAL "G4_common")
        set(${output_var} "${STM32G4_MODELS_DIR}/G4/${block_name}.yaml" PARENT_SCOPE)
    else()
        set(${output_var} "${STM32G4_MODELS_DIR}/G4/${family_or_common}/${block_name}.yaml" PARENT_SCOPE)
    endif()
endfunction()

# Parse family definitions and return list of chips in a family
function(get_stm32g4_family_chips family_name output_var)
    foreach(family_def ${STM32G4_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        if(current_family STREQUAL family_name)
            string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
            string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
            set(${output_var} "${chips_list}" PARENT_SCOPE)
            return()
        endif()
    endforeach()

    message(FATAL_ERROR "Unknown STM32G4 family: ${family_name}")
endfunction()

# For documentation: print out the family structure
function(print_stm32g4_family_info)
    message(STATUS "STM32G4 Family Organization:")
    message(STATUS "")

    foreach(family_def ${STM32G4_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")

        string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
        string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
        list(LENGTH chips_list num_chips)

        message(STATUS "  ${current_family}: ${num_chips} variants")
    endforeach()
endfunction()
