# cmake/microchip-extraction.cmake
# Unified CMake module for Microchip ATSAM family model extraction from SVD files.
#
# Provides:
#   microchip_add_family()       - Register a family and create extraction targets
#   microchip_print_families()   - Print summary of all registered families
#
# For each registered family with ID <id>, three targets are created:
#   microchip<id>-models         - Extract YAML models from SVD files
#   rebuild-microchip<id>-models - Force re-extraction (deletes stamp, then rebuilds)
#   audit-microchip<id>-models   - Detect transforms that became no-ops
#
# User-overridable cache variables:
#   MICROCHIP<CODE>_SVD_ZIP      - Path to the DFP zip archive (per family)
#   MICROCHIP_GENERATOR          - Path to the unified Python generator script
#   MICROCHIP_MODELS_DIR         - Output directory (default: models/Microchip)

find_package(Python3 REQUIRED COMPONENTS Interpreter)

set(MICROCHIP_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/Microchip" CACHE PATH
    "Output directory for generated Microchip models")
set(MICROCHIP_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_models.py" CACHE PATH
    "Path to the unified model generator script")

# Internal registry of family IDs
set(_MICROCHIP_FAMILY_IDS "" CACHE INTERNAL "")

# microchip_add_family(
#     ID <id>                    # Lowercase ID for target names (e.g. "samv71")
#     CODE <code>                # Family code under models/Microchip/ (e.g. "SAMV71")
#     DISPLAY <name>             # Display name for messages (e.g. "SAM V71")
#     ZIP <filename>             # DFP zip filename in svd/Microchip/ directory
# )
function(microchip_add_family)
    cmake_parse_arguments(FAM "" "ID;CODE;DISPLAY;ZIP" "" ${ARGN})

    foreach(_arg ID CODE DISPLAY ZIP)
        if(NOT DEFINED FAM_${_arg})
            message(FATAL_ERROR "microchip_add_family: ${_arg} is required")
        endif()
    endforeach()

    # Store metadata (CACHE INTERNAL for cross-scope access)
    set(_MICROCHIP_${FAM_ID}_CODE "${FAM_CODE}" CACHE INTERNAL "")
    set(_MICROCHIP_${FAM_ID}_DISPLAY "${FAM_DISPLAY}" CACHE INTERNAL "")

    # User-overridable DFP zip path
    set(MICROCHIP${FAM_CODE}_SVD_ZIP "${CMAKE_SOURCE_DIR}/svd/Microchip/${FAM_ZIP}" CACHE PATH
        "Path to ${FAM_DISPLAY} DFP zip archive")

    # Family config file (consolidated YAML with all family definitions)
    set(_family_config "${CMAKE_SOURCE_DIR}/svd/Microchip/Microchip.yaml")

    # Create extraction target
    set(_target "microchip${FAM_ID}-models")
    set(_marker "${CMAKE_BINARY_DIR}/${_target}.stamp")

    add_custom_command(
        OUTPUT ${_marker}
        COMMAND ${Python3_EXECUTABLE} ${MICROCHIP_GENERATOR}
                microchip ${FAM_CODE} ${MICROCHIP${FAM_CODE}_SVD_ZIP} ${MICROCHIP_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${_marker}
        MAIN_DEPENDENCY ${MICROCHIP${FAM_CODE}_SVD_ZIP}
        DEPENDS ${MICROCHIP_GENERATOR} ${_family_config}
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
        COMMAND ${Python3_EXECUTABLE} ${MICROCHIP_GENERATOR}
                microchip ${FAM_CODE} ${MICROCHIP${FAM_CODE}_SVD_ZIP} ${MICROCHIP_MODELS_DIR}
                --audit
        COMMENT "Auditing ${FAM_DISPLAY} transforms for no-ops..."
        VERBATIM
    )

    # Register in global list
    set(_ids "${_MICROCHIP_FAMILY_IDS}")
    list(APPEND _ids "${FAM_ID}")
    set(_MICROCHIP_FAMILY_IDS "${_ids}" CACHE INTERNAL "")
endfunction()

# microchip_print_families()
# Prints a summary of all registered families.
function(microchip_print_families)
    message(STATUS "")
    message(STATUS "Microchip Model Extraction targets:")
    foreach(_id IN LISTS _MICROCHIP_FAMILY_IDS)
        set(_label "microchip${_id}-models")
        string(LENGTH "${_label}" _len)
        math(EXPR _pad "26 - ${_len}")
        if(_pad LESS 1)
            set(_pad 1)
        endif()
        string(REPEAT " " ${_pad} _spaces)
        message(STATUS "  ${_label}${_spaces}- ${_MICROCHIP_${_id}_DISPLAY}")
    endforeach()
    message(STATUS "")
endfunction()
