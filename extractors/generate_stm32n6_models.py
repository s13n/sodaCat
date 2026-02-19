#!/usr/bin/env python3
"""
Extract and generate YAML models for all STM32N6 family members.
Creates functional block models and chip-level models automatically.
"""

import sys
import os
import tempfile
from pathlib import Path
from collections import defaultdict

# Add sodaCat tools to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))
import svd

# Define STM32N6 family information
STM32N6_FAMILIES = {
    'N64x': {
        'chips': ['STM32N645', 'STM32N647'],
        'cores': {'': None},  # Single core
    },
    'N65x': {
        'chips': ['STM32N655', 'STM32N657'],
        'cores': {'': None},
    },
}


# Map SVD peripheral instance names to canonical block type names.
# Entries where canonical == instance name are omitted (handled by .get() default).
# None means the peripheral is skipped (ARM core internals, security shadows, etc.).
NAME_MAP = {
    'ADC12_S': None,
    'ADC1_S': None,
    'ADC2_S': None,
    'ADF_S': None,
    'BSEC': None,
    'BSEC_S': None,
    'CACHEAXI': None,
    'CACHEAXI_S': None,
    'CRC_S': None,
    'CRYP_S': None,
    'CSI_S': None,
    'DBGMCU_S': None,
    'DCMIPP_S': None,
    'DCMI_S': None,
    'DLYBSD': None,
    'DLYBSD2': None,
    'DLYBSD2_S': None,
    'DLYBSD_S': None,
    'DMA2D_S': None,
    'DTS_S': None,
    'ETH_S': None,
    'EXTI_S': None,
    'FDCAN1_S': None,
    'FDCAN2_S': None,
    'FDCAN3_S': None,
    'FMC1_S': None,
    'GFXMMU_S': None,
    'GFXTIM_S': None,
    'GPDMA_S': None,
    'GPIOA_S': None,
    'GPIOB_S': None,
    'GPIOC_S': None,
    'GPIOD_S': None,
    'GPIOE_S': None,
    'GPIOF_S': None,
    'GPIOG_S': None,
    'GPIOH_S': None,
    'GPION_S': None,
    'GPIOO_S': None,
    'GPIOP_S': None,
    'GPIOQ_S': None,
    'HASH_S': None,
    'HDP': None,
    'HDP_S': None,
    'HPDMA_S': None,
    'I2C1_S': None,
    'I2C2_S': None,
    'I2C3_S': None,
    'I2C4_S': None,
    'I3C1_S': None,
    'I3C2_S': None,
    'IAC': None,
    'IAC_S': None,
    'ICACHE': None,
    'ICACHE_S': None,
    'IWDG_S': None,
    'JPEG_S': None,
    'LPTIM1_S': None,
    'LPTIM2_S': None,
    'LPTIM3_S': None,
    'LPTIM4_S': None,
    'LPTIM5_S': None,
    'LPUART1_S': None,
    'LTDC_S': None,
    'MCE1': None,
    'MCE1_S': None,
    'MCE2': None,
    'MCE2_S': None,
    'MCE3': None,
    'MCE3_S': None,
    'MCE4': None,
    'MCE4_S': None,
    'MDF1_S': None,
    'MDIOS_S': None,
    'OTG1_S': None,
    'OTG2_S': None,
    'PKA_S': None,
    'PSSI_S': None,
    'PWR_S': None,
    'RAMCFG_S': None,
    'RCC_S': None,
    'RIFSC': None,
    'RIFSC_S': None,
    'RISAF': None,
    'RISAF_S': None,
    'RNG_S': None,
    'RTC_S': None,
    'SAES_S': None,
    'SAI1_S': None,
    'SAI2_S': None,
    'SDMMC1_S': None,
    'SDMMC2_S': None,
    'SPDIFRX_S': None,
    'SPI1_S': None,
    'SPI2_S': None,
    'SPI3_S': None,
    'SPI4_S': None,
    'SPI5_S': None,
    'SPI6_S': None,
    'SYSCFG_S': None,
    'TAMP_S': None,
    'TIM10_S': None,
    'TIM11_S': None,
    'TIM12_S': None,
    'TIM13_S': None,
    'TIM14_S': None,
    'TIM15_S': None,
    'TIM16_S': None,
    'TIM17_S': None,
    'TIM18_S': None,
    'TIM1_S': None,
    'TIM2_S': None,
    'TIM3_S': None,
    'TIM4_S': None,
    'TIM5_S': None,
    'TIM6_S': None,
    'TIM7_S': None,
    'TIM8_S': None,
    'TIM9_S': None,
    'UART4_S': None,
    'UART5_S': None,
    'UART7_S': None,
    'UART8_S': None,
    'UART9_S': None,
    'UCPD_S': None,
    'USART10_S': None,
    'USART1_S': None,
    'USART2_S': None,
    'USART3_S': None,
    'USART6_S': None,
    'VENC_S': None,
    'VREFBUF_S': None,
    'WWDG_S': None,
    'XSPI1_S': None,
    'XSPI2_S': None,
    'XSPI3_S': None,
    'XSPIM_S': None,
    'ADC1': 'ADC',
    'ADC2': 'ADC',
    'ADC12': 'ADC_Common',
    'TIM1': 'AdvCtrlTimer',
    'TIM8': 'AdvCtrlTimer',
    'TIM6': 'BasicTimer',
    'TIM7': 'BasicTimer',
    'FDCAN1': 'FDCAN',
    'FDCAN2': 'FDCAN',
    'FDCAN3': 'FDCAN',
    'FMC1': 'FMC',
    'GPIOA': 'GPIO',
    'GPIOB': 'GPIO',
    'GPIOC': 'GPIO',
    'GPIOD': 'GPIO',
    'GPIOE': 'GPIO',
    'GPIOF': 'GPIO',
    'GPIOG': 'GPIO',
    'GPIOH': 'GPIO',
    'GPION': 'GPIO',
    'GPIOO': 'GPIO',
    'GPIOP': 'GPIO',
    'GPIOQ': 'GPIO',
    'TIM10': 'GpTimer',
    'TIM11': 'GpTimer',
    'TIM12': 'GpTimer',
    'TIM13': 'GpTimer',
    'TIM14': 'GpTimer',
    'TIM15': 'GpTimer',
    'TIM16': 'GpTimer',
    'TIM17': 'GpTimer',
    'TIM18': 'GpTimer',
    'TIM2': 'GpTimer',
    'TIM3': 'GpTimer',
    'TIM4': 'GpTimer',
    'TIM5': 'GpTimer',
    'TIM9': 'GpTimer',
    'I2C1': 'I2C',
    'I2C2': 'I2C',
    'I2C3': 'I2C',
    'I2C4': 'I2C',
    'I3C1': 'I3C',
    'I3C2': 'I3C',
    'LPTIM1': 'LPTIM',
    'LPTIM2': 'LPTIM',
    'LPTIM3': 'LPTIM',
    'LPTIM4': 'LPTIM',
    'LPTIM5': 'LPTIM',
    'LPUART1': 'LPUART',
    'MDF1': 'MDF',
    'OTG1': 'OTG',
    'OTG2': 'OTG',
    'SAI1': 'SAI',
    'SAI2': 'SAI',
    'SDMMC1': 'SDMMC',
    'SDMMC2': 'SDMMC',
    'SPI1': 'SPI',
    'SPI2': 'SPI',
    'SPI3': 'SPI',
    'SPI4': 'SPI',
    'SPI5': 'SPI',
    'SPI6': 'SPI',
    'UART4': 'USART',
    'UART5': 'USART',
    'UART7': 'USART',
    'UART8': 'USART',
    'UART9': 'USART',
    'USART1': 'USART',
    'USART10': 'USART',
    'USART2': 'USART',
    'USART3': 'USART',
    'USART6': 'USART',
    'XSPI1': 'XSPI',
    'XSPI2': 'XSPI',
    'XSPI3': 'XSPI',
}



def main():
    if len(sys.argv) < 3:
        print("Usage: generate_stm32n6_models.py <zip_path> <output_dir>")
        sys.exit(1)

    zip_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not zip_path.exists():
        print(f"Error: {zip_path} not found")
        sys.exit(1)

    print(f"Extracting STM32N6 models from {zip_path}")
    print(f"Output directory: {output_dir}\n")

    # ================================================================================
    # PASS 1: Collect blocks from all families
    # ================================================================================
    print(f"{'='*60}")
    print("PASS 1: Collecting blocks from all families")
    print(f"{'='*60}")

    all_blocks = defaultdict(lambda: defaultdict(list))

    for family_name, family_info in STM32N6_FAMILIES.items():
        print(f"\nProcessing {family_name} family...")

        for chip_name in family_info['chips']:
            try:
                svd_content = svd.extractFromZip(zip_path, chip_name)
                if svd_content is not None:
                    with tempfile.NamedTemporaryFile(mode='wb', suffix='.svd', delete=False) as tf:
                        tf.write(svd_content)
                        temp_svd = tf.name

                    try:
                        root = svd.parse(temp_svd)
                        blocks, _, _ = svd.processChip(root, chip_name, NAME_MAP)

                        for block_name, block_data in blocks.items():
                            block_hash = svd.hashBlockStructure(block_data)
                            all_blocks[block_name][family_name].append({
                                'hash': block_hash,
                                'data': block_data,
                                'chip': chip_name
                            })
                    finally:
                        os.unlink(temp_svd)

            except Exception as e:
                print(f"  ERROR processing {chip_name}: {e}")

    # ================================================================================
    # PASS 2: Analyze compatibility and generate models
    # ================================================================================
    print(f"\n{'='*60}")
    print("PASS 2: Analyzing compatibility and generating models")
    print(f"{'='*60}")

    common_blocks_dir = output_dir / 'N6'
    common_blocks_dir.mkdir(parents=True, exist_ok=True)

    common_count = 0
    family_specific_count = 0

    for block_name in sorted(all_blocks.keys()):
        block_families = all_blocks[block_name]

        families_present = set(block_families.keys())

        # Check if block is identical across all subfamilies that have it
        hashes = {block_families[f][0]['hash'] for f in families_present}

        if len(hashes) == 1:
            # Block is identical everywhere it appears -> common dir
            common_count += 1
            first_family = next(iter(families_present))
            block_data = block_families[first_family][0]['data']
            block_file = common_blocks_dir / block_name
            svd.dumpModel(block_data, block_file)
            print(f"  + {block_name:20} -> N6 (shared)")
            continue

        # Block differs between subfamilies -> subfamily-specific
        for family_name in STM32N6_FAMILIES:
            if family_name in families_present:
                family_specific_count += 1
                family_dir = output_dir / 'N6' / family_name
                family_dir.mkdir(parents=True, exist_ok=True)

                block_data = block_families[family_name][0]['data']
                block_file = family_dir / block_name
                svd.dumpModel(block_data, block_file)

    # ================================================================================
    # Summary
    # ================================================================================
    print(f"\n{'='*60}")
    print(f"Generation Summary:")
    print(f"  Common blocks (N6):     {common_count}")
    print(f"  Family-specific blocks:        {family_specific_count}")
    print(f"  Total block types processed:   {len(all_blocks)}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
