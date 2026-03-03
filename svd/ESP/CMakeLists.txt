# CMakeLists.txt for ESP32 SVD-based model generation
cmake_minimum_required(VERSION 3.28)

# ESP SVD files are stored in-tree (no external download needed)
set(ESP32_SVD_DIR "${CMAKE_CURRENT_SOURCE_DIR}" CACHE PATH
    "Path to directory containing ESP SVD files")

include(${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/esp32-extraction.cmake)

# ============================================================================
# ESP32 Family Registrations
# ============================================================================
esp32_add_family(ID p4  CODE P4  DISPLAY "ESP32-P4")

# ============================================================================
# Summary
# ============================================================================
esp32_print_families()

# ============================================================================
# Transform Audit (not built by default)
# ============================================================================
add_custom_target(audit-esp32-models
    COMMENT "Auditing all ESP32 transforms for no-ops..."
)
foreach(_id IN LISTS _ESP32_FAMILY_IDS)
    add_dependencies(audit-esp32-models audit-esp32${_id}-models)
endforeach()
