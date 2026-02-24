# CMakeLists.txt for STM32 SVD-based model generation
cmake_minimum_required(VERSION 3.28)

include(${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/stm32-extraction.cmake)

# ============================================================================
# STM32 Family Registrations
# ============================================================================
# Each call creates targets: stm32<id>-models, rebuild-stm32<id>-models,
# audit-stm32<id>-models.  ZIP filenames must match svd.zip in ./STM32.yaml.

stm32_add_family(ID c0     CODE C0  DISPLAY "STM32C0"  ZIP stm32c0-svd.zip)
stm32_add_family(ID f3     CODE F3  DISPLAY "STM32F3"  ZIP stm32f3-svd.zip)
stm32_add_family(ID f4     CODE F4  DISPLAY "STM32F4"  ZIP stm32f4-svd.zip)
stm32_add_family(ID f7     CODE F7  DISPLAY "STM32F7"  ZIP stm32f7-svd.zip)
stm32_add_family(ID g0     CODE G0  DISPLAY "STM32G0"  ZIP stm32g0-svd.zip)
stm32_add_family(ID g4     CODE G4  DISPLAY "STM32G4"  ZIP stm32g4_svd.zip)
stm32_add_family(ID h5     CODE H5  DISPLAY "STM32H5"  ZIP stm32h5-svd.zip)
stm32_add_family(ID h7     CODE H7  DISPLAY "STM32H7"  ZIP stm32h7-svd.zip)
stm32_add_family(ID l0     CODE L0  DISPLAY "STM32L0"  ZIP stm32l0-svd.zip)
stm32_add_family(ID l1     CODE L1  DISPLAY "STM32L1"  ZIP stm32l1_svd.zip)
stm32_add_family(ID l4     CODE L4  DISPLAY "STM32L4"  ZIP stm32l4_svd.zip)
stm32_add_family(ID l4plus CODE L4P DISPLAY "STM32L4+" ZIP stm32l4plus-svd.zip)
stm32_add_family(ID l5     CODE L5  DISPLAY "STM32L5"  ZIP stm32l5-svd.zip)
stm32_add_family(ID n6     CODE N6  DISPLAY "STM32N6"  ZIP stm32n6-svd.zip)
stm32_add_family(ID u0     CODE U0  DISPLAY "STM32U0"  ZIP stm32u0-svd.zip)
stm32_add_family(ID u3     CODE U3  DISPLAY "STM32U3"  ZIP stm32u3-svd.zip)
stm32_add_family(ID u5     CODE U5  DISPLAY "STM32U5"  ZIP stm32u5_svd.zip)

# ============================================================================
# Summary
# ============================================================================
stm32_print_families()

# ============================================================================
# Transform Audit (not built by default)
# ============================================================================
# Usage: cmake --build <build_dir> --target audit-stm32-models
#        cmake --build <build_dir> --target audit-stm32h7-models  (single family)
# Detects transforms that became no-ops due to SVD fixes.
add_custom_target(audit-stm32-models
    COMMENT "Auditing all STM32 transforms for no-ops..."
)
foreach(_id IN LISTS _STM32_FAMILY_IDS)
    add_dependencies(audit-stm32-models audit-stm32${_id}-models)
endforeach()

# ============================================================================
# SVD Update Check (not built by default)
# ============================================================================
# Usage: cmake --build <build_dir> --target check-stm32-svds  (read-only check)
#        cmake --build <build_dir> --target update-stm32-svds  (download updates)
set(_stm32_config "${CMAKE_CURRENT_SOURCE_DIR}/STM32.yaml")
add_custom_target(check-stm32-svds
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/../../tools/download_stm32_svds.py
            ${CMAKE_CURRENT_SOURCE_DIR} ${_stm32_config} --dry-run
    COMMENT "Checking ST website for SVD updates (no downloads)..."
)
add_custom_target(update-stm32-svds
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/../../tools/download_stm32_svds.py
            ${CMAKE_CURRENT_SOURCE_DIR} ${_stm32_config}
    COMMENT "Downloading SVD updates from ST website..."
)
