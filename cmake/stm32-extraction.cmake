# cmake/stm32-extraction.cmake
# Unified CMake module for STM32 family model extraction from SVD files.
#
# Provides:
#   stm32_add_family()       - Register a family and create extraction targets
#   stm32_print_families()   - Print summary of all registered families
#
# For each registered family with ID <id>, three targets are created:
#   stm32<id>-models         - Extract YAML models from the SVD archive
#   rebuild-stm32<id>-models - Force re-extraction (deletes stamp, then rebuilds)
#   audit-stm32<id>-models   - Detect transforms that became no-ops
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
# )
function(stm32_add_family)
    cmake_parse_arguments(FAM "" "ID;CODE;DISPLAY;ZIP" "" ${ARGN})

    foreach(_arg ID CODE DISPLAY ZIP)
        if(NOT DEFINED FAM_${_arg})
            message(FATAL_ERROR "stm32_add_family: ${_arg} is required")
        endif()
    endforeach()

    # Store metadata (CACHE INTERNAL for cross-scope access)
    set(_STM32_${FAM_ID}_CODE "${FAM_CODE}" CACHE INTERNAL "")
    set(_STM32_${FAM_ID}_DISPLAY "${FAM_DISPLAY}" CACHE INTERNAL "")

    # User-overridable SVD zip path
    set(STM32${FAM_CODE}_SVD_ZIP "${CMAKE_SOURCE_DIR}/svd/ST/${FAM_ZIP}" CACHE PATH
        "Path to ${FAM_DISPLAY} SVD archive")

    # Family config file (consolidated YAML with all family definitions)
    set(_family_config "${CMAKE_SOURCE_DIR}/svd/ST/STM32.yaml")

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

# stm32_print_families()
# Prints a summary of all registered families.
function(stm32_print_families)
    message(STATUS "")
    message(STATUS "STM32 Model Extraction targets:")
    foreach(_id IN LISTS _STM32_FAMILY_IDS)
        set(_label "stm32${_id}-models")
        string(LENGTH "${_label}" _len)
        math(EXPR _pad "20 - ${_len}")
        if(_pad LESS 1)
            set(_pad 1)
        endif()
        string(REPEAT " " ${_pad} _spaces)
        message(STATUS "  ${_label}${_spaces}- ${_STM32_${_id}_DISPLAY}")
    endforeach()
    message(STATUS "")
endfunction()
