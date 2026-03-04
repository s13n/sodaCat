# CMake file for soc-data
cmake_minimum_required(VERSION 3.28)

project(soc-data CXX)

# SVD-based model generation
add_subdirectory(svd)

# Tests
add_subdirectory(test)

# ============================================================================
# Clock-Tree Validation (not built by default)
# ============================================================================
# Usage: cmake --build <build_dir> --target validate-clocks
find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_custom_target(validate-clocks
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_clocks.py
            --schema ${CMAKE_CURRENT_SOURCE_DIR}/schemas/clock-tree.schema.yaml
            --docs "${CMAKE_CURRENT_SOURCE_DIR}/models/**/*clocks.y*ml"
    COMMENT "Validating clock-tree models (schema + graph checks)..."
)
