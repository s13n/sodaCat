# cmake/stm32-extraction.cmake
# Unified CMake module for STM32 family model extraction from SVD files.
#
# Provides:
#   stm32_add_family()       - Register a family and create extraction targets
#   stm32_block_path()       - Resolve path to a block YAML model
#   stm32_chip_path()        - Resolve path to a chip-level YAML model
#   stm32_subfamily_chips()  - Get the list of chips in a subfamily
#   stm32_print_families()   - Print summary of all registered families
#
# For each registered family with ID <id>, two targets are created:
#   stm32<id>-models         - Extract YAML models from the SVD archive
#   rebuild-stm32<id>-models - Force re-extraction (deletes stamp, then rebuilds)
#
# User-overridable cache variables:
#   STM32<CODE>_SVD_ZIP      - Path to the SVD zip archive (per family)
#   STM32_GENERATOR          - Path to the unified Python generator script
#   STM32_MODELS_DIR         - Shared output directory (default: models/ST)

find_package(Python3 REQUIRED COMPONENTS Interpreter)

set(STM32_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/ST" CACHE PATH
    "Output directory for generated STM32 models")
set(STM32_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_stm32_models.py" CACHE PATH
    "Path to the unified STM32 model generator script")

# Internal registry of family IDs
set(_STM32_FAMILY_IDS "" CACHE INTERNAL "")

# stm32_add_family(
#     ID <id>                    # Lowercase ID for target names (e.g. "c0", "l4plus")
#     CODE <code>                # Directory name under models/ST/ (e.g. "C0", "L4P")
#     DISPLAY <name>             # Display name for messages (e.g. "STM32C0", "STM32L4+")
#     ZIP <filename>             # SVD zip filename in svd/ST/ directory
#     SUBFAMILIES <def>...       # Subfamily defs, each "Name:Chip1,Chip2,..."
# )
function(stm32_add_family)
    cmake_parse_arguments(FAM "" "ID;CODE;DISPLAY;ZIP" "SUBFAMILIES" ${ARGN})

    foreach(_arg ID CODE DISPLAY ZIP)
        if(NOT DEFINED FAM_${_arg})
            message(FATAL_ERROR "stm32_add_family: ${_arg} is required")
        endif()
    endforeach()

    # Store metadata (CACHE INTERNAL for cross-scope access by helper functions)
    set(_STM32_${FAM_ID}_CODE "${FAM_CODE}" CACHE INTERNAL "")
    set(_STM32_${FAM_ID}_DISPLAY "${FAM_DISPLAY}" CACHE INTERNAL "")
    set(_STM32_${FAM_ID}_SUBFAMILIES "${FAM_SUBFAMILIES}" CACHE INTERNAL "")

    # User-overridable SVD zip path
    set(STM32${FAM_CODE}_SVD_ZIP "${CMAKE_SOURCE_DIR}/svd/ST/${FAM_ZIP}" CACHE PATH
        "Path to ${FAM_DISPLAY} SVD archive")

    # Family config file (consolidated YAML with all family definitions)
    set(_family_config "${CMAKE_SOURCE_DIR}/extractors/STM32.yaml")

    # Create extraction target
    set(_target "stm32${FAM_ID}-models")
    set(_marker "${CMAKE_BINARY_DIR}/${_target}.stamp")

    add_custom_command(
        OUTPUT ${_marker}
        COMMAND ${Python3_EXECUTABLE} ${STM32_GENERATOR}
                ${FAM_CODE} ${STM32${FAM_CODE}_SVD_ZIP} ${STM32_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${_marker}
        MAIN_DEPENDENCY ${STM32${FAM_CODE}_SVD_ZIP}
        DEPENDS ${STM32_GENERATOR} ${_family_config}
        COMMENT "Extracting ${FAM_DISPLAY} family models from SVD files..."
        VERBATIM
    )

    add_custom_target(${_target} ALL DEPENDS ${_marker})

    # Rebuild target: remove stamp then re-run extraction
    add_custom_target(rebuild-${_target}
        COMMAND ${CMAKE_COMMAND} -E remove -f ${_marker}
        COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target ${_target}
        COMMENT "Force rebuild of ${FAM_DISPLAY} family models"
    )

    # Audit target: check transforms for no-ops (SVD bugs potentially fixed)
    add_custom_target(audit-${_target}
        COMMAND ${Python3_EXECUTABLE} ${STM32_GENERATOR}
                ${FAM_CODE} ${STM32${FAM_CODE}_SVD_ZIP} ${STM32_MODELS_DIR}
                --audit
        COMMENT "Auditing ${FAM_DISPLAY} transforms for no-ops..."
        VERBATIM
    )

    # Register in global list
    set(_ids "${_STM32_FAMILY_IDS}")
    list(APPEND _ids "${FAM_ID}")
    set(_STM32_FAMILY_IDS "${_ids}" CACHE INTERNAL "")
endfunction()

# stm32_block_path(<family_id> <block_name> <subfamily|"common"> <output_var>)
# Sets output_var to the filesystem path of a block YAML model.
function(stm32_block_path family_id block_name subfamily output_var)
    set(_code "${_STM32_${family_id}_CODE}")
    if(subfamily STREQUAL "common")
        set(${output_var} "${STM32_MODELS_DIR}/${_code}/${block_name}.yaml" PARENT_SCOPE)
    else()
        set(${output_var} "${STM32_MODELS_DIR}/${_code}/${subfamily}/${block_name}.yaml" PARENT_SCOPE)
    endif()
endfunction()

# stm32_chip_path(<family_id> <chip_name> <subfamily> <output_var>)
# Sets output_var to the filesystem path of a chip-level YAML model.
function(stm32_chip_path family_id chip_name subfamily output_var)
    set(_code "${_STM32_${family_id}_CODE}")
    set(${output_var} "${STM32_MODELS_DIR}/${_code}/${subfamily}/${chip_name}.yaml" PARENT_SCOPE)
endfunction()

# stm32_subfamily_chips(<family_id> <subfamily_name> <output_var>)
# Sets output_var to a CMake list of chip names in the given subfamily.
function(stm32_subfamily_chips family_id subfamily output_var)
    foreach(_def IN LISTS _STM32_${family_id}_SUBFAMILIES)
        string(REGEX MATCH "^([^:]+):" _m "${_def}")
        if(CMAKE_MATCH_1 STREQUAL subfamily)
            string(REGEX MATCH ":(.+)$" _m "${_def}")
            string(REPLACE "," ";" _chips "${CMAKE_MATCH_1}")
            set(${output_var} "${_chips}" PARENT_SCOPE)
            return()
        endif()
    endforeach()
    message(FATAL_ERROR "Unknown ${_STM32_${family_id}_DISPLAY} subfamily: ${subfamily}")
endfunction()

# stm32_print_families()
# Prints a summary table of all registered families and their variant counts.
function(stm32_print_families)
    message(STATUS "")
    message(STATUS "STM32 Model Extraction targets:")
    foreach(_id IN LISTS _STM32_FAMILY_IDS)
        set(_total 0)
        foreach(_def IN LISTS _STM32_${_id}_SUBFAMILIES)
            string(REGEX MATCH ":(.+)$" _m "${_def}")
            string(REPLACE "," ";" _chips "${CMAKE_MATCH_1}")
            list(LENGTH _chips _n)
            math(EXPR _total "${_total} + ${_n}")
        endforeach()
        set(_label "stm32${_id}-models")
        string(LENGTH "${_label}" _len)
        math(EXPR _pad "20 - ${_len}")
        if(_pad LESS 1)
            set(_pad 1)
        endif()
        string(REPEAT " " ${_pad} _spaces)
        message(STATUS "  ${_label}${_spaces}- ${_STM32_${_id}_DISPLAY} (${_total} variants)")
    endforeach()
    message(STATUS "")
endfunction()
