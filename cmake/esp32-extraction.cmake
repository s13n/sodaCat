# cmake/esp32-extraction.cmake
# Unified CMake module for ESP32 family model extraction from SVD files.
#
# Provides:
#   esp32_add_family()       - Register a family and create extraction targets
#   esp32_print_families()   - Print summary of all registered families
#
# For each registered family with ID <id>, three targets are created:
#   esp32<id>-models         - Extract YAML models from SVD files
#   rebuild-esp32<id>-models - Force re-extraction (deletes stamp, then rebuilds)
#   audit-esp32<id>-models   - Detect transforms that became no-ops
#
# User-overridable cache variables:
#   ESP32_SVD_DIR            - Path to directory containing ESP SVD files
#   ESP32_GENERATOR          - Path to the unified Python generator script
#   ESP32_MODELS_DIR         - Output directory (default: models/ESP)

find_package(Python3 REQUIRED COMPONENTS Interpreter)

set(ESP32_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/ESP" CACHE PATH
    "Output directory for generated ESP32 models")
set(ESP32_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_models.py" CACHE PATH
    "Path to the unified model generator script")

# Internal registry of family IDs
set(_ESP32_FAMILY_IDS "" CACHE INTERNAL "")

# esp32_add_family(
#     ID <id>                    # Lowercase ID for target names (e.g. "p4")
#     CODE <code>                # Directory name under models/ESP/ (e.g. "P4")
#     DISPLAY <name>             # Display name for messages (e.g. "ESP32-P4")
# )
function(esp32_add_family)
    cmake_parse_arguments(FAM "" "ID;CODE;DISPLAY" "" ${ARGN})

    foreach(_arg ID CODE DISPLAY)
        if(NOT DEFINED FAM_${_arg})
            message(FATAL_ERROR "esp32_add_family: ${_arg} is required")
        endif()
    endforeach()

    if(NOT DEFINED ESP32_SVD_DIR)
        message(FATAL_ERROR "esp32_add_family: ESP32_SVD_DIR must be set before registering families")
    endif()

    # Store metadata (CACHE INTERNAL for cross-scope access)
    set(_ESP32_${FAM_ID}_CODE "${FAM_CODE}" CACHE INTERNAL "")
    set(_ESP32_${FAM_ID}_DISPLAY "${FAM_DISPLAY}" CACHE INTERNAL "")

    # Family config file (consolidated YAML with all family definitions)
    set(_family_config "${CMAKE_SOURCE_DIR}/svd/ESP/ESP32.yaml")

    # Create extraction target
    set(_target "esp32${FAM_ID}-models")
    set(_marker "${CMAKE_BINARY_DIR}/${_target}.stamp")

    add_custom_command(
        OUTPUT ${_marker}
        COMMAND ${Python3_EXECUTABLE} ${ESP32_GENERATOR}
                esp ${FAM_CODE} ${ESP32_SVD_DIR} ${ESP32_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${_marker}
        DEPENDS ${ESP32_GENERATOR} ${_family_config}
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
        COMMAND ${Python3_EXECUTABLE} ${ESP32_GENERATOR}
                esp ${FAM_CODE} ${ESP32_SVD_DIR} ${ESP32_MODELS_DIR}
                --audit
        COMMENT "Auditing ${FAM_DISPLAY} transforms for no-ops..."
        VERBATIM
    )

    # Register in global list
    set(_ids "${_ESP32_FAMILY_IDS}")
    list(APPEND _ids "${FAM_ID}")
    set(_ESP32_FAMILY_IDS "${_ids}" CACHE INTERNAL "")
endfunction()

# esp32_print_families()
# Prints a summary of all registered families.
function(esp32_print_families)
    message(STATUS "")
    message(STATUS "ESP32 Model Extraction targets:")
    foreach(_id IN LISTS _ESP32_FAMILY_IDS)
        set(_label "esp32${_id}-models")
        string(LENGTH "${_label}" _len)
        math(EXPR _pad "20 - ${_len}")
        if(_pad LESS 1)
            set(_pad 1)
        endif()
        string(REPEAT " " ${_pad} _spaces)
        message(STATUS "  ${_label}${_spaces}- ${_ESP32_${_id}_DISPLAY}")
    endforeach()
    message(STATUS "")
endfunction()
