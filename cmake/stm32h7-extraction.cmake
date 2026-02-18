# CMake module for generating STM32H7 family models
# This module extracts functional block and chip-level models from STM32H7 SVD files
# and organizes them for use across the entire H7 family.

# Find Python3 (required for SVD parsing and model generation)
find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Configuration
set(STM32H7_SVD_ZIP "${CMAKE_SOURCE_DIR}/svd/stm32h7-svd.zip" CACHE PATH 
    "Path to stm32h7-svd.zip containing all STM32H7 SVD files")
set(STM32H7_MODELS_DIR "${CMAKE_SOURCE_DIR}/models/ST" CACHE PATH 
    "Output directory for generated STM32H7 models (source tree - commitable to git)")
set(STM32H7_GENERATOR "${CMAKE_SOURCE_DIR}/extractors/generate_stm32h7_models.py" CACHE PATH
    "Path to model generation script")

# STM32H7 Family definitions
set(STM32H7_FAMILIES 
    "H73x:STM32H723,STM32H725,STM32H730,STM32H733,STM32H735,STM32H73x"
    "H74x_H75x:STM32H742,STM32H743,STM32H745_CM4,STM32H745_CM7,STM32H747_CM4,STM32H747_CM7,STM32H750,STM32H753,STM32H755_CM4,STM32H755_CM7,STM32H757_CM4,STM32H757_CM7"
    "H7A3_B:STM32H7A3,STM32H7B0,STM32H7B3"
)

# Incompatible blocks that require variant-specific models
set(STM32H7_INCOMPATIBLE_BLOCKS
    ADC ADC_Common AdvCtrlTimer BDMA DMA DBGMCU DFSDM
    FMC Flash GpTimer LPTIM MDMA PWR QUADSPI RCC RTC SPDIFRX SYSCFG OPAMP
)

# Compatible blocks that can be shared across all variants
set(STM32H7_COMPATIBLE_BLOCKS
    AXI BasicTimer DCMI EXTI GPIO I2C LPUART LTDC OTG1_HS_DEVICE
    OTG1_HS_HOST OTG1_HS_PWRCLK OTG2_HS_DEVICE OTG2_HS_HOST OTG2_HS_PWRCLK
    SDMMC2 SPI SWPMI USART DAC1 DAC2 FMAC HRTIM_Common HRTIM_Master
    HRTIM_TIMA HRTIM_TIMB HRTIM_TIMC HRTIM_TIMD HRTIM_TIME
    Delay_Block_OCTOSPI1 Delay_Block_OCTOSPI2 Delay_Block_SDMMC1 Delay_Block_SDMMC2
    DELAY_Block_QUADSPI FDCAN1 FDCAN2 FDCAN3 ART SAI DSIHOST
)

# Create a CMake target for extracting all STM32H7 models
function(add_stm32h7_extraction_target target_name)
    # Use a stamp file in the build directory (not committed to git)
    # The actual models go to the source tree and are committed
    set(extraction_marker "${CMAKE_BINARY_DIR}/stm32h7-models.stamp")
    
    add_custom_command(
        OUTPUT ${extraction_marker}
        COMMAND ${Python3_EXECUTABLE} ${STM32H7_GENERATOR}
                ${STM32H7_SVD_ZIP} ${STM32H7_MODELS_DIR}
        COMMAND ${CMAKE_COMMAND} -E touch ${extraction_marker}
        MAIN_DEPENDENCY ${STM32H7_SVD_ZIP}
        DEPENDS ${STM32H7_GENERATOR}
        COMMENT "Extracting STM32H7 family models from SVD files..."
        VERBATIM
    )
    
    add_custom_target(${target_name} ALL DEPENDS ${extraction_marker})
    
    message(STATUS "Added target '${target_name}' to extract STM32H7 models")
endfunction()

# Helper function to get compatible block model path
function(get_stm32h7_block_path block_name family_or_common output_var)
    list(FIND STM32H7_COMPATIBLE_BLOCKS "${block_name}" is_compatible)
    
    if(is_compatible GREATER -1)
        # Compatible block - can be shared
        set(${output_var} "${STM32H7_MODELS_DIR}/H7_common/${block_name}.yaml" PARENT_SCOPE)
    else()
        # Family-specific block
        set(${output_var} "${STM32H7_MODELS_DIR}/${family_or_common}/blocks/${block_name}.yaml" PARENT_SCOPE)
    endif()
endfunction()

# Helper to get chip model path
function(get_stm32h7_chip_path chip_name family_name output_var)
    set(${output_var} "${STM32H7_MODELS_DIR}/${family_name}/${chip_name}.yaml" PARENT_SCOPE)
endfunction()

# Parse family definitions and return list of chips in a family
function(get_stm32h7_family_chips family_name output_var)
    foreach(family_def ${STM32H7_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")
        
        if(current_family STREQUAL family_name)
            string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
            string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
            set(${output_var} "${chips_list}" PARENT_SCOPE)
            return()
        endif()
    endforeach()
    
    message(FATAL_ERROR "Unknown STM32H7 family: ${family_name}")
endfunction()

# For documentation: print out the family structure
function(print_stm32h7_family_info)
    message(STATUS "STM32H7 Family Organization:")
    message(STATUS "  Compatible blocks: ${STM32H7_COMPATIBLE_BLOCKS}")
    message(STATUS "  Incompatible blocks: ${STM32H7_INCOMPATIBLE_BLOCKS}")
    message(STATUS "")
    
    foreach(family_def ${STM32H7_FAMILIES})
        string(REGEX MATCH "^([^:]+):" family_match "${family_def}")
        set(current_family "${CMAKE_MATCH_1}")
        
        string(REGEX MATCH ":(.+)$" chips_match "${family_def}")
        string(REPLACE "," ";" chips_list "${CMAKE_MATCH_1}")
        list(LENGTH chips_list num_chips)
        
        message(STATUS "  ${current_family}: ${num_chips} variants")
    endforeach()
endfunction()
