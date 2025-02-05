# CMake file for soc-data
cmake_minimum_required(VERSION 3.14)

add_custom_command(
    OUTPUT utils.lc parseSVD.lc writeYAML.lc generatePer.lc generateChip.lc
    DEPENDS utils.lua parseSVD.lua writeYAML.lua generatePer.lua generateChip.lua
    COMMENT "Compile lua utility scripts"
    COMMAND luac -o utils.lc ${CMAKE_CURRENT_SOURCE_DIR}/utils.lua
    COMMAND luac -o parseSVD.lc ${CMAKE_CURRENT_SOURCE_DIR}/parseSVD.lua
    COMMAND luac -o writeYAML.lc ${CMAKE_CURRENT_SOURCE_DIR}/writeYAML.lua
    COMMAND luac -o generatePer.lc ${CMAKE_CURRENT_SOURCE_DIR}/generatePer.lua
    COMMAND luac -o generateChip.lc ${CMAKE_CURRENT_SOURCE_DIR}/generateChip.lua
)
add_custom_target(svd2chip DEPENDS utils.lc parseSVD.lc writeYAML.lc generatePer.lc generateChip.lc)

