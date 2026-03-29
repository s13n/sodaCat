# CMakeLists.txt for Raspberry Pi SVD-based model generation
cmake_minimum_required(VERSION 3.28)

# Raspberry Pi SVD files are stored in-tree
set(RASPBERRY_SVD_DIR "${CMAKE_CURRENT_SOURCE_DIR}" CACHE PATH
    "Path to directory containing Raspberry Pi SVD files")

include(${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/raspberry-extraction.cmake)

# ============================================================================
# Raspberry Pi Family Registrations
# ============================================================================
raspberry_add_family(ID rp  CODE RP  DISPLAY "RP2040/RP2350")

# ============================================================================
# Summary
# ============================================================================
raspberry_print_families()

# ============================================================================
# Transform Audit (not built by default)
# ============================================================================
add_custom_target(audit-rp-models
    COMMENT "Auditing all Raspberry Pi transforms for no-ops..."
)
foreach(_id IN LISTS _RASPBERRY_FAMILY_IDS)
    add_dependencies(audit-rp-models audit-rp${_id}-models)
endforeach()
