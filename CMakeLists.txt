# CMake file for soc-data
cmake_minimum_required(VERSION 3.28)

project(soc-data CXX)

# Family extractors share output paths (cross-family shared blocks like
# models/ST/MDMA.yaml or models/ARM/PL08x.yaml are produced by more than
# one family) but each only declares its stamp file as OUTPUT.  Without
# serialisation, ninja schedules them in parallel and concurrent writes
# corrupt the YAML.  Run extractors in a depth-1 pool to serialise them
# while leaving the rest of the build (compilation, validation, etc.)
# free to parallelise.
set_property(GLOBAL APPEND PROPERTY JOB_POOLS extract_models=1)

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
