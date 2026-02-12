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
# Summary
# ============================================================================
message(STATUS "STM32H7 Model Generation:")
message(STATUS "  Target: stm32h7-models")
message(STATUS "  Extracts all 21 STM32H7 variants into three-tier structure")
message(STATUS "  Output: ${STM32H7_MODELS_DIR}/")
message(STATUS "           ├── H7_common/      (58 shared blocks)")
message(STATUS "           ├── H73x/blocks/    (H73x-specific blocks)")
message(STATUS "           ├── H74x_H75x/blocks/ (H74x/H75x-specific blocks)")
message(STATUS "           └── H7A3_B/blocks/  (H7A3/B-specific blocks)")
