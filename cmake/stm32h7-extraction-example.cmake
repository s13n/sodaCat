# Example usage of STM32H7 model extraction in CMake
# This demonstrates how to use the new stm32h7-extraction.cmake module

cmake_minimum_required(VERSION 3.20)

# Include the extraction module
include(cmake/stm32h7-extraction.cmake)

# Add the main extraction target
# This will automatically extract all STM32H7 models from the SVD zip file
add_stm32h7_extraction_target(extract_stm32h7_models)

# Optional: Print family information
print_stm32h7_family_info()

# Example: Get path to a specific chip model
get_stm32h7_chip_path(STM32H757_CM4 H74x_H75x H757_CM4_MODEL_PATH)
message(STATUS "H757 CM4 model path: ${H757_CM4_MODEL_PATH}")

# Example: Get path to a functional block (handles both shared and family-specific)
get_stm32h7_block_path(GPIO H74x_H75x GPIO_BLOCK_PATH)
message(STATUS "GPIO block path: ${GPIO_BLOCK_PATH}")

get_stm32h7_block_path(ADC H74x_H75x ADC_BLOCK_PATH)
message(STATUS "ADC block path (family-specific): ${ADC_BLOCK_PATH}")

# Example: Get all chips in a family
get_stm32h7_family_chips(H73x H73x_CHIPS)
message(STATUS "H73x family chips: ${H73x_CHIPS}")

# Create a custom target that depends on extraction
# (all chip/block processing depends on extract_stm32h7_models)
add_custom_target(process_stm32h7_headers ALL
    DEPENDS extract_stm32h7_models
    COMMENT "Processing STM32H7 headers (depends on model extraction)"
)

# === PROPOSED CMakeLists.txt MODIFICATIONS FOR MAIN PROJECT ===
# 
# To integrate this into your existing build:
#
# 1. In your main CMakeLists.txt, add:
#    include(cmake/stm32h7-extraction.cmake)
#    add_stm32h7_extraction_target(extract_stm32h7_models)
#
# 2. For each test target that uses H7 models, depend on it:
#    add_dependencies(your_test_target extract_stm32h7_models)
#
# 3. Set the output directory:
#    set(STM32H7_MODELS_DIR "${CMAKE_BINARY_DIR}/models/ST")
#
# 4. To regenerate from scratch:
#    rm -rf ${CMAKE_BINARY_DIR}/models/ST/.extracted
#    cmake --build . --target extract_stm32h7_models
