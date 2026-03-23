# cmake/mcx-extraction.cmake
# Unified CMake module for MCX family model extraction from SVD files.
#
# Provides:
#   mcx_add_family()       - Register a family and create extraction targets
#   mcx_print_families()   - Print summary of all registered families
#
# For each registered family with ID <id>, three targets are created:
#   mcx<id>-models         - Extract YAML models from SVD files
#   rebuild-mcx<id>-models - Force re-extraction (deletes stamp, then rebuilds)
#   audit-mcx<id>-models   - Detect transforms that became no-ops
#
# User-overridable cache variables:
#   NXP_SVD_DIR            - Path to the NXP SVD repository checkout
#   MCX_GENERATOR          - Path to the unified Python generator script
#   MCX_MODELS_DIR         - Shared output directory (default: models/NXP)

find_package(Python3 REQUIRED COMPONENTS Interpreter)

set(MCX_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/NXP" CACHE PATH
    "Output directory for generated MCX models")
set(MCX_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_models.py" CACHE PATH
    "Path to the unified model generator script")

# Internal registry of family IDs
set(_MCX_FAMILY_IDS "" CACHE INTERNAL "")

# mcx_add_family(
#     ID <id>                    # Lowercase ID for target names (e.g. "n")
#     CODE <code>                # Directory name under models/NXP/ (e.g. "MCXN")
#     DISPLAY <name>             # Display name for messages (e.g. "MCX N")
# )
function(mcx_add_family)
    cmake_parse_arguments(FAM "" "ID;CODE;DISPLAY" "" ${ARGN})

    foreach(_arg ID CODE DISPLAY)
        if(NOT DEFINED FAM_${_arg})
            message(FATAL_ERROR "mcx_add_family: ${_arg} is required")
        endif()
    endforeach()

    if(NOT DEFINED NXP_SVD_DIR)
        message(FATAL_ERROR "mcx_add_family: NXP_SVD_DIR must be set before registering families")
    endif()

    # Store metadata (CACHE INTERNAL for cross-scope access)
    set(_MCX_${FAM_ID}_CODE "${FAM_CODE}" CACHE INTERNAL "")
    set(_MCX_${FAM_ID}_DISPLAY "${FAM_DISPLAY}" CACHE INTERNAL "")

    # Family config file (consolidated YAML with all family definitions)
    set(_family_config "${CMAKE_SOURCE_DIR}/svd/NXP/MCX.yaml")

    # Create extraction target
    set(_target "mcx${FAM_ID}-models")
    set(_marker "${CMAKE_BINARY_DIR}/${_target}.stamp")

    add_custom_command(
        OUTPUT ${_marker}
        COMMAND ${Python3_EXECUTABLE} ${MCX_GENERATOR}
                mcx ${FAM_CODE} ${NXP_SVD_DIR} ${MCX_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${_marker}
        DEPENDS ${MCX_GENERATOR} ${_family_config}
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
        COMMAND ${Python3_EXECUTABLE} ${MCX_GENERATOR}
                mcx ${FAM_CODE} ${NXP_SVD_DIR} ${MCX_MODELS_DIR}
                --audit
        COMMENT "Auditing ${FAM_DISPLAY} transforms for no-ops..."
        VERBATIM
    )

    # Register in global list
    set(_ids "${_MCX_FAMILY_IDS}")
    list(APPEND _ids "${FAM_ID}")
    set(_MCX_FAMILY_IDS "${_ids}" CACHE INTERNAL "")
endfunction()

# mcx_print_families()
# Prints a summary of all registered families.
function(mcx_print_families)
    message(STATUS "")
    message(STATUS "MCX Model Extraction targets:")
    foreach(_id IN LISTS _MCX_FAMILY_IDS)
        set(_label "mcx${_id}-models")
        string(LENGTH "${_label}" _len)
        math(EXPR _pad "20 - ${_len}")
        if(_pad LESS 1)
            set(_pad 1)
        endif()
        string(REPEAT " " ${_pad} _spaces)
        message(STATUS "  ${_label}${_spaces}- ${_MCX_${_id}_DISPLAY}")
    endforeach()
    message(STATUS "")
endfunction()
