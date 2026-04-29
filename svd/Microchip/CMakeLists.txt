# CMakeLists.txt for Microchip SVD-based model generation
cmake_minimum_required(VERSION 3.28)

# Microchip SVD files are stored in-tree
set(MICROCHIP_SVD_DIR "${CMAKE_CURRENT_SOURCE_DIR}" CACHE PATH
    "Path to directory containing Microchip SVD files")

include(${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/microchip-extraction.cmake)

# ============================================================================
# Microchip Family Registrations
# ============================================================================
microchip_add_family(ID samv71  CODE SAMV71  DISPLAY "SAM V71")

# ============================================================================
# Summary
# ============================================================================
microchip_print_families()

# ============================================================================
# Transform Audit (not built by default)
# ============================================================================
add_custom_target(audit-microchip-models
    COMMENT "Auditing all Microchip transforms for no-ops..."
)
foreach(_id IN LISTS _MICROCHIP_FAMILY_IDS)
    add_dependencies(audit-microchip-models audit-microchip${_id}-models)
endforeach()
