# CMakeLists.txt for NXP LPC SVD-based model generation
cmake_minimum_required(VERSION 3.28)

include(FetchContent)

# ============================================================================
# NXP SVD Repository (fetched at configure time)
# ============================================================================
FetchContent_Declare(nxp_svd
    GIT_REPOSITORY https://github.com/nxp-mcuxpresso/mcux-soc-svd.git
    GIT_TAG        MCUX_2.16.100
    GIT_SHALLOW    TRUE
)
FetchContent_MakeAvailable(nxp_svd)

set(NXP_SVD_DIR "${nxp_svd_SOURCE_DIR}" CACHE PATH
    "Path to NXP SVD repository checkout")

include(${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/lpc-extraction.cmake)

# ============================================================================
# LPC Family Registrations
# ============================================================================
# Each call creates targets: lpc<id>-models, rebuild-lpc<id>-models,
# audit-lpc<id>-models.

lpc_add_family(ID 8   CODE LPC8   DISPLAY "LPC8xx")
lpc_add_family(ID 54  CODE LPC54  DISPLAY "LPC54xxx")

# ============================================================================
# Summary
# ============================================================================
lpc_print_families()

# ============================================================================
# Transform Audit (not built by default)
# ============================================================================
# Usage: cmake --build <build_dir> --target audit-lpc-models
#        cmake --build <build_dir> --target audit-lpc8-models  (single family)
# Detects transforms that became no-ops due to SVD fixes.
add_custom_target(audit-lpc-models
    COMMENT "Auditing all LPC transforms for no-ops..."
)
foreach(_id IN LISTS _LPC_FAMILY_IDS)
    add_dependencies(audit-lpc-models audit-lpc${_id}-models)
endforeach()

# ============================================================================
# Reference Manual Check (not built by default)
# ============================================================================
# Usage: cmake --build <build_dir> --target check-lpc-manuals
# Compares local PDFs in docs/NXP/ against revisions tracked in LPC.yaml.
# NXP blocks automated downloads, so there is no update/download target.
set(_lpc_config "${CMAKE_CURRENT_SOURCE_DIR}/LPC.yaml")
set(_nxp_docs "${CMAKE_CURRENT_SOURCE_DIR}/../../docs/NXP")
add_custom_target(check-lpc-manuals
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/../../tools/check_nxp_manuals.py
            --config ${_lpc_config} --docs-dir ${_nxp_docs}
    COMMENT "Checking NXP LPC reference manuals against tracked revisions..."
)
