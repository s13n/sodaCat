# cmake/lpc-extraction.cmake
# Unified CMake module for LPC family model extraction from SVD files.
#
# Provides:
#   lpc_add_family()       - Register a family and create extraction targets
#   lpc_print_families()   - Print summary of all registered families
#
# For each registered family with ID <id>, three targets are created:
#   lpc<id>-models         - Extract YAML models from SVD files
#   rebuild-lpc<id>-models - Force re-extraction (deletes stamp, then rebuilds)
#   audit-lpc<id>-models   - Detect transforms that became no-ops
#
# User-overridable cache variables:
#   NXP_SVD_DIR            - Path to the NXP SVD repository checkout
#   LPC_GENERATOR          - Path to the unified Python generator script
#   LPC_MODELS_DIR         - Shared output directory (default: models/NXP)

find_package(Python3 REQUIRED COMPONENTS Interpreter)

set(LPC_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/NXP" CACHE PATH
    "Output directory for generated LPC models")
set(LPC_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_lpc_models.py" CACHE PATH
    "Path to the unified LPC model generator script")

# Internal registry of family IDs
set(_LPC_FAMILY_IDS "" CACHE INTERNAL "")

# lpc_add_family(
#     ID <id>                    # Lowercase ID for target names (e.g. "8", "54")
#     CODE <code>                # Directory name under models/NXP/ (e.g. "LPC8", "LPC54")
#     DISPLAY <name>             # Display name for messages (e.g. "LPC8xx", "LPC54xxx")
# )
function(lpc_add_family)
    cmake_parse_arguments(FAM "" "ID;CODE;DISPLAY" "" ${ARGN})

    foreach(_arg ID CODE DISPLAY)
        if(NOT DEFINED FAM_${_arg})
            message(FATAL_ERROR "lpc_add_family: ${_arg} is required")
        endif()
    endforeach()

    if(NOT DEFINED NXP_SVD_DIR)
        message(FATAL_ERROR "lpc_add_family: NXP_SVD_DIR must be set before registering families")
    endif()

    # Store metadata (CACHE INTERNAL for cross-scope access)
    set(_LPC_${FAM_ID}_CODE "${FAM_CODE}" CACHE INTERNAL "")
    set(_LPC_${FAM_ID}_DISPLAY "${FAM_DISPLAY}" CACHE INTERNAL "")

    # Family config file (consolidated YAML with all family definitions)
    set(_family_config "${CMAKE_SOURCE_DIR}/svd/NXP/LPC.yaml")

    # Create extraction target
    set(_target "lpc${FAM_ID}-models")
    set(_marker "${CMAKE_BINARY_DIR}/${_target}.stamp")

    add_custom_command(
        OUTPUT ${_marker}
        COMMAND ${Python3_EXECUTABLE} ${LPC_GENERATOR}
                ${FAM_CODE} ${NXP_SVD_DIR} ${LPC_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${_marker}
        DEPENDS ${LPC_GENERATOR} ${_family_config}
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
        COMMAND ${Python3_EXECUTABLE} ${LPC_GENERATOR}
                ${FAM_CODE} ${NXP_SVD_DIR} ${LPC_MODELS_DIR}
                --audit
        COMMENT "Auditing ${FAM_DISPLAY} transforms for no-ops..."
        VERBATIM
    )

    # Register in global list
    set(_ids "${_LPC_FAMILY_IDS}")
    list(APPEND _ids "${FAM_ID}")
    set(_LPC_FAMILY_IDS "${_ids}" CACHE INTERNAL "")
endfunction()

# lpc_print_families()
# Prints a summary of all registered families.
function(lpc_print_families)
    message(STATUS "")
    message(STATUS "LPC Model Extraction targets:")
    foreach(_id IN LISTS _LPC_FAMILY_IDS)
        set(_label "lpc${_id}-models")
        string(LENGTH "${_label}" _len)
        math(EXPR _pad "20 - ${_len}")
        if(_pad LESS 1)
            set(_pad 1)
        endif()
        string(REPEAT " " ${_pad} _spaces)
        message(STATUS "  ${_label}${_spaces}- ${_LPC_${_id}_DISPLAY}")
    endforeach()
    message(STATUS "")
endfunction()
