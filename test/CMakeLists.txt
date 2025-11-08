# CMake file for sodaCat test project
cmake_minimum_required(VERSION 3.28)

option(FOR_MODULES "Build with C++20 modules support" OFF)
if(FOR_MODULES)
    set(FILE_SET_TYPE CXX_MODULES)
    message(STATUS "Building with C++20 modules support")
else()
    set(FILE_SET_TYPE HEADERS)
    message(STATUS "Building without C++20 modules support")
endif()

set(CMAKE_CXX_STANDARD 20)

add_library(soc-data-modules OBJECT)
target_include_directories(soc-data-modules PUBLIC ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR})
target_compile_definitions(soc-data-modules PUBLIC $<$<BOOL:${FOR_MODULES}>:REGISTERS_MODULE>)
set_target_properties(soc-data-modules PROPERTIES
    CXX_SCAN_FOR_MODULES ${FOR_MODULES}
    LINKER_LANGUAGE "CXX"
)

macro(generate_peripheral model)
    add_custom_command(OUTPUT ${model}.cpp ${model}.hpp
        COMMAND python3 ${CMAKE_SOURCE_DIR}/generators/cxx/generate_peripheral_header.py ${CMAKE_SOURCE_DIR}/models/ST/H757/${model}.yaml ${CMAKE_CURRENT_BINARY_DIR}/${model} stm32h7
        MAIN_DEPENDENCY ${CMAKE_SOURCE_DIR}/models/ST/H757/${model}.yaml
        DEPENDS ${CMAKE_SOURCE_DIR}/generators/cxx/generate_peripheral_header.py
        COMMENT "Generating ${model}.hpp for STM32H7"
    )
    target_sources(soc-data-modules PUBLIC
        FILE_SET ${FILE_SET_TYPE}
            BASE_DIRS ${CMAKE_CURRENT_BINARY_DIR}
            FILES ${CMAKE_CURRENT_BINARY_DIR}/${model}.hpp
    )
    if(FOR_MODULES)
        set_source_files_properties(${CMAKE_CURRENT_BINARY_DIR}/${model}.hpp PROPERTIES
            LANGUAGE CXX
            HEADER_FILE_ONLY FALSE
        )
    endif()
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
generate_peripheral(FMC)

add_custom_command(OUTPUT H757.cpp H757.hpp
    COMMAND python3 ${CMAKE_SOURCE_DIR}/generators/cxx/generate_chip_header.py ${CMAKE_SOURCE_DIR}/models/ST/H757/H757.yaml ${CMAKE_CURRENT_BINARY_DIR}/H757 stm32h7
    MAIN_DEPENDENCY ${CMAKE_SOURCE_DIR}/models/ST/H757/H757.yaml
    DEPENDS ${CMAKE_SOURCE_DIR}/generators/cxx/generate_chip_header.py
    COMMENT "Generating H757.hpp for STM32H7"
)
target_sources(soc-data-modules PUBLIC
    FILE_SET ${FILE_SET_TYPE}
        BASE_DIRS ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR} ${CMAKE_SOURCE_DIR}/generators/cxx
        FILES ${CMAKE_SOURCE_DIR}/generators/cxx/registers.hpp ${CMAKE_CURRENT_BINARY_DIR}/H757.hpp
)
if(FOR_MODULES)
    set_source_files_properties(${CMAKE_SOURCE_DIR}/generators/cxx/registers.hpp ${CMAKE_CURRENT_BINARY_DIR}/H757.hpp
        PROPERTIES LANGUAGE CXX HEADER_FILE_ONLY FALSE
    )
endif()

add_executable(soc-data-test main.cpp)
target_link_libraries(soc-data-test PRIVATE soc-data-modules)
target_compile_options(soc-data-test PUBLIC $<$<BOOL:${FOR_MODULES}>:-fmodules-ts>)
