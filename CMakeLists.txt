# CMake file for soc-data
cmake_minimum_required(VERSION 3.28)

project(soc-data CXX)

# SVD-based model generation
add_subdirectory(svd)

# Tests
add_subdirectory(test)
