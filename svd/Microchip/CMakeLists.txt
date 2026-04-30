# CMakeLists.txt for Microchip SVD-based model generation
cmake_minimum_required(VERSION 3.28)

# Microchip CMSIS Device Family Pack (DFP) archives are stored in-tree
# (downloaded from packs.download.microchip.com as `.atpack`, renamed to `.zip`).

include(${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/microchip-extraction.cmake)

# ============================================================================
# Microchip Family Registrations
# ============================================================================
microchip_add_family(ID same70  CODE SAME70  DISPLAY "SAM E70"
    ZIP SAME70_DFP.4.13.292.zip)
microchip_add_family(ID sams70  CODE SAMS70  DISPLAY "SAM S70"
    ZIP SAMS70_DFP.4.12.234.zip)
microchip_add_family(ID samv70  CODE SAMV70  DISPLAY "SAM V70"
    ZIP SAMV70_DFP.4.12.233.zip)
microchip_add_family(ID samv71  CODE SAMV71  DISPLAY "SAM V71"
    ZIP SAMV71_DFP.4.13.257.zip)
microchip_add_family(ID pic32czca70 CODE PIC32CZ-CA70 DISPLAY "PIC32CZ-CA70"
    ZIP PIC32CZ-CA70_DFP.1.3.62.zip)
microchip_add_family(ID pic32czmc70 CODE PIC32CZ-MC70 DISPLAY "PIC32CZ-MC70"
    ZIP PIC32CZ-MC70_DFP.1.3.57.zip)
microchip_add_family(ID pic32czca80 CODE PIC32CZ-CA80 DISPLAY "PIC32CZ-CA80"
    ZIP PIC32CZ-CA80_DFP.1.2.150.zip)
microchip_add_family(ID pic32czca90 CODE PIC32CZ-CA90 DISPLAY "PIC32CZ-CA90"
    ZIP PIC32CZ-CA90_DFP.1.4.160.zip)

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
