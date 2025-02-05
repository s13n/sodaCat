# CMake file for soc-data
cmake_minimum_required(VERSION 3.28)

set(CMAKE_CXX_STANDARD 20)

add_library(soc-data-testlib)

macro(generate_peripheral model)
    add_custom_command(OUTPUT ${model}.cpp
        COMMAND python3 ${CMAKE_SOURCE_DIR}/tools/headerPer.py ${CMAKE_SOURCE_DIR}/data/ST/H757/${model}.yaml ${CMAKE_CURRENT_BINARY_DIR}/${model}.cpp stm32h7
        MAIN_DEPENDENCY ${CMAKE_SOURCE_DIR}/data/ST/H757/${model}.yaml
        DEPENDS ${CMAKE_SOURCE_DIR}/tools/headerPer.py
        COMMENT Generating ${model}.cpp for STM32H7
    )
    target_sources(soc-data-testlib PUBLIC
        FILE_SET CXX_MODULES BASE_DIRS ${CMAKE_CURRENT_BINARY_DIR} FILES
            ${CMAKE_CURRENT_BINARY_DIR}/${model}.cpp
    )
endmacro()

generate_peripheral(ADC)
generate_peripheral(ADC_Common)
generate_peripheral(DAC)
generate_peripheral(DMA)
generate_peripheral(DMAMUX1)
generate_peripheral(DMAMUX2)
generate_peripheral(MDMA)
generate_peripheral(BDMA)
generate_peripheral(GPIO)
generate_peripheral(I2C)
generate_peripheral(SAI)
generate_peripheral(SPDIFRX)
generate_peripheral(SYSCFG)
generate_peripheral(EXTI)
generate_peripheral(BasicTimer)
generate_peripheral(GpTimer)
generate_peripheral(AdvCtrlTimer)
generate_peripheral(USART)
generate_peripheral(LPTIM)
generate_peripheral(LPTIMenc)
generate_peripheral(RCC)
generate_peripheral(QUADSPI)
generate_peripheral(OPAMP)
generate_peripheral(DFSDM)
generate_peripheral(SPI)
generate_peripheral(RTC)

add_custom_command(OUTPUT H757.cpp
    COMMAND python3 ${CMAKE_SOURCE_DIR}/tools/headerChip.py ${CMAKE_SOURCE_DIR}/data/ST/H757/H757.yaml ${CMAKE_CURRENT_BINARY_DIR}/H757.cpp stm32h7
    MAIN_DEPENDENCY ${CMAKE_SOURCE_DIR}/data/ST/H757/H757.yaml
    DEPENDS ${CMAKE_SOURCE_DIR}/tools/headerChip.py
    COMMENT Generating H757.cpp for STM32H7
)

target_include_directories(soc-data-testlib PUBLIC ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR})
target_compile_options(soc-data-testlib PUBLIC -fmodules-ts)
set_target_properties(soc-data-testlib PROPERTIES CXX_SCAN_FOR_MODULES On)

target_sources(soc-data-testlib PUBLIC
    FILE_SET CXX_MODULES BASE_DIRS ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR} FILES
        registers.cpp    
        ${CMAKE_CURRENT_BINARY_DIR}/H757.cpp
)

add_executable(soc-data-test main.cpp)
target_link_libraries(soc-data-test PUBLIC soc-data-testlib)
