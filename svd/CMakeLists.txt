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
# Summary
# ============================================================================
message(STATUS "STM32H7 Model Generation:")
message(STATUS "  Target: stm32h7-models")
message(STATUS "  Extracts all 21 STM32H7 variants into three-tier structure")
message(STATUS "  Output: ${STM32H7_MODELS_DIR}/")
message(STATUS "           ├── H7_common/        (shared blocks)")
message(STATUS "           ├── H73x/blocks/      (H73x-specific)")
message(STATUS "           ├── H74x_H75x/blocks/ (H74x/H75x-specific)")
message(STATUS "           └── H7A3_B/blocks/    (H7A3/B-specific)")
message(STATUS "")
message(STATUS "STM32H5 Model Generation:")
message(STATUS "  Target: stm32h5-models")
message(STATUS "  Extracts all 6 STM32H5 variants into three-tier structure")
message(STATUS "  Output: ${STM32H5_MODELS_DIR}/")
message(STATUS "           ├── H5_common/        (shared blocks)")
message(STATUS "           ├── H503/blocks/      (H503-specific)")
message(STATUS "           ├── H52x_H53x/blocks/ (H52x/H53x-specific)")
message(STATUS "           └── H56x_H57x/blocks/ (H56x/H57x-specific)")
message(STATUS "")
message(STATUS "STM32N6 Model Generation:")
message(STATUS "  Target: stm32n6-models")
message(STATUS "  Extracts all 4 STM32N6 variants into three-tier structure")
message(STATUS "  Output: ${STM32N6_MODELS_DIR}/")
message(STATUS "           ├── N6_common/        (shared blocks)")
message(STATUS "           ├── N64x/blocks/      (N64x-specific)")
message(STATUS "           └── N65x/blocks/      (N65x-specific)")
