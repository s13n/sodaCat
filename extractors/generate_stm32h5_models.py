#!/usr/bin/env python3
"""
Extract and generate YAML models for all STM32H5 family members.
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

# Define STM32H5 family information
STM32H5_FAMILIES = {
    'H503': {
        'chips': ['STM32H503'],
        'cores': {'': None},  # Single core
    },
    'H52x_H53x': {
        'chips': ['STM32H523', 'STM32H533'],
        'cores': {'': None},
    },
    'H56x_H57x': {
        'chips': ['STM32H562', 'STM32H563', 'STM32H573'],
        'cores': {'': None},
    }
}


# Map SVD peripheral instance names to canonical block type names.
# Entries where canonical == instance name are omitted (handled by .get() default).
# None means the peripheral is skipped (ARM core internals, security shadows, etc.).
NAME_MAP = {
    'DLYBOS1': None,
    'DLYBOS1_S': None,
    'DLYBSD1': None,
    'DLYBSD1_S': None,
    'DLYBSD2': None,
    'GTZC1': None,
    'GTZC1_MPCBB1': None,
    'GTZC1_MPCBB2': None,
    'GTZC1_MPCBB3': None,
    'GTZC1_TZIC': None,
    'GTZC1_TZIC_S': None,
    'GTZC1_TZSC': None,
    'GTZC1_TZSC_S': None,
    'SEC_ADC1': None,
    'SEC_ADC2': None,
    'SEC_ADCC': None,
    'SEC_AES': None,
    'SEC_CORDIC': None,
    'SEC_CRC': None,
    'SEC_CRS': None,
    'SEC_DAC': None,
    'SEC_DCACHE': None,
    'SEC_DCMI': None,
    'SEC_DLYBOS1': None,
    'SEC_DLYBSD1': None,
    'SEC_DLYBSD2': None,
    'SEC_DTS': None,
    'SEC_ETH': None,
    'SEC_EXTI': None,
    'SEC_FDCAN1': None,
    'SEC_FDCAN2': None,
    'SEC_FLASH': None,
    'SEC_FMAC': None,
    'SEC_FMC': None,
    'SEC_GPDMA1': None,
    'SEC_GPDMA2': None,
    'SEC_GPIOA': None,
    'SEC_GPIOB': None,
    'SEC_GPIOC': None,
    'SEC_GPIOD': None,
    'SEC_GPIOE': None,
    'SEC_GPIOF': None,
    'SEC_GPIOG': None,
    'SEC_GPIOH': None,
    'SEC_GPIOI': None,
    'SEC_GTZC1_MPCBB1': None,
    'SEC_GTZC1_MPCBB2': None,
    'SEC_GTZC1_MPCBB3': None,
    'SEC_GTZC1_TZIC': None,
    'SEC_GTZC1_TZSC': None,
    'SEC_HASH': None,
    'SEC_I2C1': None,
    'SEC_I2C2': None,
    'SEC_I2C3': None,
    'SEC_I2C4': None,
    'SEC_I3C': None,
    'SEC_ICACHE': None,
    'SEC_IWDG': None,
    'SEC_LPTIM1': None,
    'SEC_LPTIM2': None,
    'SEC_LPTIM3': None,
    'SEC_LPTIM4': None,
    'SEC_LPTIM5': None,
    'SEC_LPTIM6': None,
    'SEC_LPUART1': None,
    'SEC_OCTOSPI': None,
    'SEC_OTFDEC1': None,
    'SEC_PKA': None,
    'SEC_PSSI': None,
    'SEC_PWR': None,
    'SEC_RAMCFG': None,
    'SEC_RCC': None,
    'SEC_RNG': None,
    'SEC_RTC': None,
    'SEC_SAES': None,
    'SEC_SAI1': None,
    'SEC_SAI2': None,
    'SEC_SBS': None,
    'SEC_SDMMC1': None,
    'SEC_SDMMC2': None,
    'SEC_SPI1': None,
    'SEC_SPI2': None,
    'SEC_SPI3': None,
    'SEC_SPI4': None,
    'SEC_SPI5': None,
    'SEC_SPI6': None,
    'SEC_TAMP': None,
    'SEC_TIM1': None,
    'SEC_TIM12': None,
    'SEC_TIM13': None,
    'SEC_TIM14': None,
    'SEC_TIM15': None,
    'SEC_TIM16': None,
    'SEC_TIM17': None,
    'SEC_TIM2': None,
    'SEC_TIM3': None,
    'SEC_TIM4': None,
    'SEC_TIM5': None,
    'SEC_TIM6': None,
    'SEC_TIM7': None,
    'SEC_TIM8': None,
    'SEC_UART12': None,
    'SEC_UART4': None,
    'SEC_UART5': None,
    'SEC_UART7': None,
    'SEC_UART8': None,
    'SEC_UART9': None,
    'SEC_UCPD1': None,
    'SEC_USART1': None,
    'SEC_USART10': None,
    'SEC_USART11': None,
    'SEC_USART2': None,
    'SEC_USART3': None,
    'SEC_USART6': None,
    'SEC_USB': None,
    'SEC_VREFBUF': None,
    'SEC_WWDG': None,
    'ADC1': 'ADC',
    'ADC2': 'ADC',
    'ADC2_S': 'ADC',
    'ADC_S': 'ADC',
    'ADCC': 'ADC_Common',
    'TIM1': 'AdvCtrlTimer',
    'TIM8': 'AdvCtrlTimer',
    'TIM6': 'BasicTimer',
    'TIM7': 'BasicTimer',
    'FDCAN1': 'FDCAN',
    'FDCAN2': 'FDCAN',
    'FDCAN2_S': 'FDCAN',
    'FDCAN_S': 'FDCAN',
    'FLASH': 'Flash',
    'GPDMA1': 'GPDMA',
    'GPDMA2': 'GPDMA',
    'GPDMA2_S': 'GPDMA',
    'GPDMA_S': 'GPDMA',
    'GPIOA': 'GPIO',
    'GPIOA_S': 'GPIO',
    'GPIOB': 'GPIO',
    'GPIOB_S': 'GPIO',
    'GPIOC': 'GPIO',
    'GPIOC_S': 'GPIO',
    'GPIOD': 'GPIO',
    'GPIOD_S': 'GPIO',
    'GPIOE': 'GPIO',
    'GPIOE_S': 'GPIO',
    'GPIOF': 'GPIO',
    'GPIOF_S': 'GPIO',
    'GPIOG': 'GPIO',
    'GPIOG_S': 'GPIO',
    'GPIOH': 'GPIO',
    'GPIOH_S': 'GPIO',
    'GPIOI': 'GPIO',
    'TIM12': 'GpTimer',
    'TIM13': 'GpTimer',
    'TIM14': 'GpTimer',
    'TIM15': 'GpTimer',
    'TIM15_S': 'GpTimer',
    'TIM16': 'GpTimer',
    'TIM17': 'GpTimer',
    'TIM1_S': 'GpTimer',
    'TIM2': 'GpTimer',
    'TIM2_S': 'GpTimer',
    'TIM3': 'GpTimer',
    'TIM3_S': 'GpTimer',
    'TIM4': 'GpTimer',
    'TIM4_S': 'GpTimer',
    'TIM5': 'GpTimer',
    'TIM5_S': 'GpTimer',
    'TIM6_S': 'GpTimer',
    'TIM7_S': 'GpTimer',
    'TIM8_S': 'GpTimer',
    'I2C1': 'I2C',
    'I2C2': 'I2C',
    'I2C2_S': 'I2C',
    'I2C3': 'I2C',
    'I2C3_S': 'I2C',
    'I2C4': 'I2C',
    'I2C_S': 'I2C',
    'I3C1': 'I3C',
    'I3C2': 'I3C',
    'I3C2_S': 'I3C',
    'I3C_S': 'I3C',
    'LPTIM1': 'LPTIM',
    'LPTIM1_S': 'LPTIM',
    'LPTIM2': 'LPTIM',
    'LPTIM2_S': 'LPTIM',
    'LPTIM3': 'LPTIM',
    'LPTIM4': 'LPTIM',
    'LPTIM5': 'LPTIM',
    'LPTIM6': 'LPTIM',
    'LPUART_S': 'LPUART',
    'OPAMP1': 'OPAMP',
    'OTFDEC1': 'OTFDEC',
    'OTFDEC_S': 'OTFDEC',
    'SAI1': 'SAI',
    'SAI2': 'SAI',
    'SDMMC1': 'SDMMC',
    'SDMMC2': 'SDMMC',
    'SDMMC_S': 'SDMMC',
    'SPI1': 'SPI',
    'SPI2': 'SPI',
    'SPI2_S': 'SPI',
    'SPI3': 'SPI',
    'SPI3_S': 'SPI',
    'SPI4': 'SPI',
    'SPI4_S': 'SPI',
    'SPI5': 'SPI',
    'SPI6': 'SPI',
    'SPI_S': 'SPI',
    'UCPD1': 'UCPD',
    'UCPD_S': 'UCPD',
    'UART12': 'USART',
    'UART4': 'USART',
    'UART4_S': 'USART',
    'UART5': 'USART',
    'UART5_S': 'USART',
    'UART7': 'USART',
    'UART8': 'USART',
    'UART9': 'USART',
    'USART1': 'USART',
    'USART10': 'USART',
    'USART11': 'USART',
    'USART2': 'USART',
    'USART2_S': 'USART',
    'USART3': 'USART',
    'USART3_S': 'USART',
    'USART6': 'USART',
    'USART6_S': 'USART',
    'USART_S': 'USART',
}



def main():
    if len(sys.argv) < 3:
        print("Usage: generate_stm32h5_models.py <zip_path> <output_dir>")
        sys.exit(1)

    zip_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not zip_path.exists():
        print(f"Error: {zip_path} not found")
        sys.exit(1)

    print(f"Extracting STM32H5 models from {zip_path}")
    print(f"Output directory: {output_dir}\n")

    # ================================================================================
    # PASS 1: Collect blocks from all families
    # ================================================================================
    print(f"{'='*60}")
    print("PASS 1: Collecting blocks from all families")
    print(f"{'='*60}")

    all_blocks = defaultdict(lambda: defaultdict(list))

    for family_name, family_info in STM32H5_FAMILIES.items():
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

    common_blocks_dir = output_dir / 'H5'
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
            print(f"  + {block_name:20} -> H5 (shared)")
            continue

        # Block differs between subfamilies -> subfamily-specific
        for family_name in STM32H5_FAMILIES:
            if family_name in families_present:
                family_specific_count += 1
                family_dir = output_dir / 'H5' / family_name
                family_dir.mkdir(parents=True, exist_ok=True)

                block_data = block_families[family_name][0]['data']
                block_file = family_dir / block_name
                svd.dumpModel(block_data, block_file)

    # ================================================================================
    # Summary
    # ================================================================================
    print(f"\n{'='*60}")
    print(f"Generation Summary:")
    print(f"  Common blocks (H5):     {common_count}")
    print(f"  Family-specific blocks:        {family_specific_count}")
    print(f"  Total block types processed:   {len(all_blocks)}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
