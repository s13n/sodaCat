# CMakeLists.txt for Microchip SVD-based model generation
cmake_minimum_required(VERSION 3.28)

# Microchip CMSIS Device Family Pack (DFP) archives are stored in-tree
# (downloaded from packs.download.microchip.com as `.atpack`, renamed to `.zip`).

include(${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/microchip-extraction.cmake)

# ============================================================================
# Microchip Family Registrations
# ============================================================================
microchip_add_family(ID samv71  CODE SAMV71  DISPLAY "SAM V71"
    ZIP SAMV71_DFP.4.13.257.zip)

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
