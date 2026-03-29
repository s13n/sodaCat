# cmake/raspberry-extraction.cmake
# Unified CMake module for Raspberry Pi family model extraction from SVD files.
#
# Provides:
#   raspberry_add_family()       - Register a family and create extraction targets
#   raspberry_print_families()   - Print summary of all registered families
#
# For each registered family with ID <id>, three targets are created:
#   rp<id>-models         - Extract YAML models from SVD files
#   rebuild-rp<id>-models - Force re-extraction (deletes stamp, then rebuilds)
#   audit-rp<id>-models   - Detect transforms that became no-ops
#
# User-overridable cache variables:
#   RASPBERRY_SVD_DIR            - Path to directory containing Raspberry Pi SVD files
#   RASPBERRY_GENERATOR          - Path to the unified Python generator script
#   RASPBERRY_MODELS_DIR         - Output directory (default: models/Raspberry)

find_package(Python3 REQUIRED COMPONENTS Interpreter)

set(RASPBERRY_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/Raspberry" CACHE PATH
    "Output directory for generated Raspberry Pi models")
set(RASPBERRY_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_models.py" CACHE PATH
    "Path to the unified model generator script")

# Internal registry of family IDs
set(_RASPBERRY_FAMILY_IDS "" CACHE INTERNAL "")

# raspberry_add_family(
#     ID <id>                    # Lowercase ID for target names (e.g. "rp")
#     CODE <code>                # Directory name under models/Raspberry/ (e.g. "RP")
#     DISPLAY <name>             # Display name for messages (e.g. "RP2040/RP2350")
# )
function(raspberry_add_family)
    cmake_parse_arguments(FAM "" "ID;CODE;DISPLAY" "" ${ARGN})

    foreach(_arg ID CODE DISPLAY)
        if(NOT DEFINED FAM_${_arg})
            message(FATAL_ERROR "raspberry_add_family: ${_arg} is required")
        endif()
    endforeach()

    if(NOT DEFINED RASPBERRY_SVD_DIR)
        message(FATAL_ERROR "raspberry_add_family: RASPBERRY_SVD_DIR must be set before registering families")
    endif()

    # Store metadata (CACHE INTERNAL for cross-scope access)
    set(_RASPBERRY_${FAM_ID}_CODE "${FAM_CODE}" CACHE INTERNAL "")
    set(_RASPBERRY_${FAM_ID}_DISPLAY "${FAM_DISPLAY}" CACHE INTERNAL "")

    # Family config file (consolidated YAML with all family definitions)
    set(_family_config "${CMAKE_SOURCE_DIR}/svd/Raspberry/Raspberry.yaml")

    # Create extraction target
    set(_target "rp${FAM_ID}-models")
    set(_marker "${CMAKE_BINARY_DIR}/${_target}.stamp")

    add_custom_command(
        OUTPUT ${_marker}
        COMMAND ${Python3_EXECUTABLE} ${RASPBERRY_GENERATOR}
                raspberry ${FAM_CODE} ${RASPBERRY_SVD_DIR} ${RASPBERRY_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${_marker}
        DEPENDS ${RASPBERRY_GENERATOR} ${_family_config}
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
        COMMAND ${Python3_EXECUTABLE} ${RASPBERRY_GENERATOR}
                raspberry ${FAM_CODE} ${RASPBERRY_SVD_DIR} ${RASPBERRY_MODELS_DIR}
                --audit
        COMMENT "Auditing ${FAM_DISPLAY} transforms for no-ops..."
        VERBATIM
    )

    # Register in global list
    set(_ids "${_RASPBERRY_FAMILY_IDS}")
    list(APPEND _ids "${FAM_ID}")
    set(_RASPBERRY_FAMILY_IDS "${_ids}" CACHE INTERNAL "")
endfunction()

# raspberry_print_families()
# Prints a summary of all registered families.
function(raspberry_print_families)
    message(STATUS "")
    message(STATUS "Raspberry Pi Model Extraction targets:")
    foreach(_id IN LISTS _RASPBERRY_FAMILY_IDS)
        set(_label "rp${_id}-models")
        string(LENGTH "${_label}" _len)
        math(EXPR _pad "20 - ${_len}")
        if(_pad LESS 1)
            set(_pad 1)
        endif()
        string(REPEAT " " ${_pad} _spaces)
        message(STATUS "  ${_label}${_spaces}- ${_RASPBERRY_${_id}_DISPLAY}")
    endforeach()
    message(STATUS "")
endfunction()
