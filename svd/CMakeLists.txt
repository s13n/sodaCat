# CMakeLists.txt for SVD-based model generation
cmake_minimum_required(VERSION 3.28)

# Include the STM32H7 model extraction module
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32h7-extraction.cmake)

# ============================================================================
# STM32H7 Model Extraction Target
# ============================================================================
# This uses the comprehensive extraction system that:
# - Parses all 21 STM32H7 SVD files from the zip archive
# - Extracts functional blocks (peripherals)
# - Organizes models into a three-tier structure:
#   * H7/             - Family folder with common blocks + subfamily subdirs
#   * H7/H73x/        - H73x subfamily-specific blocks
#   * H7/H74x_H75x/   - H74x/H75x subfamily-specific blocks
#   * H7/H7A3_B/      - H7A3/B subfamily-specific blocks
# - Creates chip-level models for all 21 variants
#
# See: IMPLEMENTATION_SUMMARY.md for detailed architecture documentation
# See: README_STM32H7_EXTRACTION.md for usage examples

add_stm32h7_extraction_target(stm32h7-models)

# Also provide a manual rebuild target
add_custom_target(rebuild-stm32h7-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32h7-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32h7-models
    COMMENT "Force rebuild of STM32H7 family models"
)

# ============================================================================
# STM32H5 Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32h5-extraction.cmake)

add_stm32h5_extraction_target(stm32h5-models)

add_custom_target(rebuild-stm32h5-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32h5-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32h5-models
    COMMENT "Force rebuild of STM32H5 family models"
)

# ============================================================================
# STM32N6 Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32n6-extraction.cmake)

add_stm32n6_extraction_target(stm32n6-models)

add_custom_target(rebuild-stm32n6-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32n6-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32n6-models
    COMMENT "Force rebuild of STM32N6 family models"
)

# ============================================================================
# STM32F7 Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32f7-extraction.cmake)

add_stm32f7_extraction_target(stm32f7-models)

add_custom_target(rebuild-stm32f7-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32f7-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32f7-models
    COMMENT "Force rebuild of STM32F7 family models"
)

# ============================================================================
# STM32G4 Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32g4-extraction.cmake)

add_stm32g4_extraction_target(stm32g4-models)

add_custom_target(rebuild-stm32g4-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32g4-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32g4-models
    COMMENT "Force rebuild of STM32G4 family models"
)

# ============================================================================
# STM32U3 Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32u3-extraction.cmake)

add_stm32u3_extraction_target(stm32u3-models)

add_custom_target(rebuild-stm32u3-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32u3-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32u3-models
    COMMENT "Force rebuild of STM32U3 family models"
)

# ============================================================================
# STM32U5 Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32u5-extraction.cmake)

add_stm32u5_extraction_target(stm32u5-models)

add_custom_target(rebuild-stm32u5-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32u5-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32u5-models
    COMMENT "Force rebuild of STM32U5 family models"
)

# ============================================================================
# STM32C0 Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32c0-extraction.cmake)

add_stm32c0_extraction_target(stm32c0-models)

add_custom_target(rebuild-stm32c0-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32c0-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32c0-models
    COMMENT "Force rebuild of STM32C0 family models"
)

# ============================================================================
# STM32F3 Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32f3-extraction.cmake)

add_stm32f3_extraction_target(stm32f3-models)

add_custom_target(rebuild-stm32f3-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32f3-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32f3-models
    COMMENT "Force rebuild of STM32F3 family models"
)

# ============================================================================
# STM32F4 Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32f4-extraction.cmake)

add_stm32f4_extraction_target(stm32f4-models)

add_custom_target(rebuild-stm32f4-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32f4-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32f4-models
    COMMENT "Force rebuild of STM32F4 family models"
)

# ============================================================================
# STM32G0 Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32g0-extraction.cmake)

add_stm32g0_extraction_target(stm32g0-models)

add_custom_target(rebuild-stm32g0-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32g0-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32g0-models
    COMMENT "Force rebuild of STM32G0 family models"
)

# ============================================================================
# STM32L0 Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32l0-extraction.cmake)

add_stm32l0_extraction_target(stm32l0-models)

add_custom_target(rebuild-stm32l0-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32l0-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32l0-models
    COMMENT "Force rebuild of STM32L0 family models"
)

# ============================================================================
# STM32L1 Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32l1-extraction.cmake)

add_stm32l1_extraction_target(stm32l1-models)

add_custom_target(rebuild-stm32l1-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32l1-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32l1-models
    COMMENT "Force rebuild of STM32L1 family models"
)

# ============================================================================
# STM32L4 Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32l4-extraction.cmake)

add_stm32l4_extraction_target(stm32l4-models)

add_custom_target(rebuild-stm32l4-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32l4-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32l4-models
    COMMENT "Force rebuild of STM32L4 family models"
)

# ============================================================================
# STM32L4+ Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32l4plus-extraction.cmake)

add_stm32l4plus_extraction_target(stm32l4plus-models)

add_custom_target(rebuild-stm32l4plus-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32l4plus-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32l4plus-models
    COMMENT "Force rebuild of STM32L4+ family models"
)

# ============================================================================
# STM32L5 Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32l5-extraction.cmake)

add_stm32l5_extraction_target(stm32l5-models)

add_custom_target(rebuild-stm32l5-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32l5-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32l5-models
    COMMENT "Force rebuild of STM32L5 family models"
)

# ============================================================================
# STM32U0 Model Extraction Target
# ============================================================================
include(${CMAKE_CURRENT_SOURCE_DIR}/../cmake/stm32u0-extraction.cmake)

add_stm32u0_extraction_target(stm32u0-models)

add_custom_target(rebuild-stm32u0-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target clean-stm32u0-models
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target stm32u0-models
    COMMENT "Force rebuild of STM32U0 family models"
)

# ============================================================================
# Summary
# ============================================================================
message(STATUS "STM32 Model Generation targets:")
message(STATUS "")
message(STATUS "  stm32c0-models     -  6 STM32C0 variants")
message(STATUS "  stm32f3-models     -  6 STM32F3 variants")
message(STATUS "  stm32f4-models     - 17 STM32F4 variants")
message(STATUS "  stm32f7-models     - 16 STM32F7 variants")
message(STATUS "  stm32g0-models     - 12 STM32G0 variants")
message(STATUS "  stm32g4-models     - 10 STM32G4 variants")
message(STATUS "  stm32h5-models     -  6 STM32H5 variants")
message(STATUS "  stm32h7-models     - 21 STM32H7 variants")
message(STATUS "  stm32l0-models     -  8 STM32L0 variants")
message(STATUS "  stm32l1-models     -  4 STM32L1 variants")
message(STATUS "  stm32l4-models     - 16 STM32L4 variants")
message(STATUS "  stm32l4plus-models -  8 STM32L4+ variants")
message(STATUS "  stm32l5-models     -  2 STM32L5 variants")
message(STATUS "  stm32n6-models     -  4 STM32N6 variants")
message(STATUS "  stm32u0-models     -  3 STM32U0 variants")
message(STATUS "  stm32u3-models     -  2 STM32U3 variants")
message(STATUS "  stm32u5-models     - 10 STM32U5 variants")
