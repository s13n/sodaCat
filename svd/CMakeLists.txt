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
#   * H7_common/      - Blocks shared across all variants (58 blocks)
#   * H73x/           - H73x subfamily-specific blocks
#   * H74x_H75x/      - H74x/H75x subfamily-specific blocks
#   * H7A3_B/         - H7A3/B subfamily-specific blocks
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
# Summary
# ============================================================================
message(STATUS "STM32 Model Generation targets:")
message(STATUS "")
message(STATUS "  stm32h7-models  - 21 STM32H7 variants")
message(STATUS "  stm32h5-models  -  6 STM32H5 variants")
message(STATUS "  stm32n6-models  -  4 STM32N6 variants")
message(STATUS "  stm32f7-models  - 16 STM32F7 variants")
message(STATUS "  stm32g4-models  - 10 STM32G4 variants")
message(STATUS "  stm32u3-models  -  2 STM32U3 variants")
message(STATUS "  stm32u5-models  - 10 STM32U5 variants")
