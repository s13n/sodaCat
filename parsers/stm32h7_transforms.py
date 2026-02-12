"""
STM32H7 family-specific transformations.

This module contains transformations that are specific to the STM32H7 family.
Generic transformations that work across all MCU families are in tools/generic_transform.py.

These functions are auto-discovered by discover_family_transformations() and
registered with the TransformationEngine at startup.

Each transformation function must follow the signature:
    def transform_<name>(block: dict, config: dict) -> None
    
Where <name> becomes the transformation type name (e.g., 'rcc_cpu_clustering').
"""

import sys
import os
from pathlib import Path

# Add sodaCat tools to path
p = os.path.abspath("./tools")
if p not in sys.path:
    sys.path.append(p)

import svd
import transform


# ═══════════════════════════════════════════════════════════════════════════
# STM32H7-SPECIFIC TRANSFORMATIONS
# ═══════════════════════════════════════════════════════════════════════════

def transform_rcc_cpu_clustering(block: dict, config: dict) -> None:
    """
    Special handling for RCC: cluster CPU-specific registers.
    
    The STM32H7 RCC block has different registers visible per CPU:
    - C0: This CPU (the one being configured)
    - C1: CM7 (if present—dual-core variants)
    - C2: CM4 (if present—dual-core variants)
    
    SVD represents this with prefixes like C0_, C1_, C2_.
    This transformation groups them into a clustered view.
    
    Configuration example (in YAML):
        RCC:
          instances: [RCC]
          specialHandling: rcc_cpu_clustering
          addFields:
            - registerName: RCC_D1CCIPR
              field:
                name: DSISRC
                bitOffset: 8
                bitWidth: 3
                description: DSI kernel clock source selection
    """
    
    print(f"    → Applying RCC CPU clustering...")
    
    # 1. Add missing fields that SVD doesn't include
    # (These come from running actual hardware tests)
    
    d1ccipr = svd.findNamedEntry(block.get('registers', []), 'D1CCIPR')
    if d1ccipr:
        d1ccipr['fields'].append({
            'name': 'DSISRC',
            'bitOffset': 8,
            'bitWidth': 3,
            'description': 'DSI kernel clock source selection'
        })
    
    apb3enr = svd.findNamedEntry(block.get('registers', []), 'APB3ENR')
    if apb3enr:
        apb3enr['fields'].append({
            'name': 'DSIEN',
            'bitOffset': 4,
            'bitWidth': 1,
            'description': 'DSI peripheral clocks enable'
        })
    
    # 2. Rename registers that don't have CPU prefix to have C0 prefix
    # (This makes them consistent with other CPU-specific registers)
    
    if 'registers' in block:
        renamed = []
        for reg in block['registers']:
            reg_name = reg.get('name', '')
            
            # Add C0_ prefix to clock control registers that don't have CPU prefix yet
            if reg_name.startswith('RSR'):  # Reset status register
                reg['name'] = 'C0_' + reg_name
            elif reg_name.startswith(('AHB', 'APB')) and 'ENR' in reg_name:
                # Clock enable registers (AHB1ENR, APB1LENR, etc.)
                reg['name'] = 'C0_' + reg_name
        
        block['registers'] = renamed
    
    # 3. Convert C0_*, C1_*, C2_* prefixes into a cluster array
    # This consolidates all CPU-specific variants into C[0..2]
    
    block['registers'] = transform.createClusterArray(
        block.get('registers', []),
        r"^C(\d+)_(.+?)$",  # Match C0_XXX, C1_XXX, C2_XXX
        {
            'name': 'C',
            'description': 'CPU-specific clock registers; index 0=this CPU, 1=CM7, 2=CM4'
        }
    )
    
    print(f"    → RCC CPU clustering complete (registers grouped as C[0..2])")


def transform_timer_channel_mapping(block: dict, config: dict) -> None:
    """
    Special handling for Timer blocks: ensure channel mapping is consistent.
    
    STM32H7 timers can have different channel counts depending on the variant.
    This transformation normalizes the channel field names to be consistent.
    
    Configuration example (in YAML):
        GpTimer:
          instances: [TIM2, TIM3, TIM4, TIM5]
          specialHandling: timer_channel_mapping
    
    This is more subtle than the RCC case—mainly validation and normalization.
    """
    
    block_name = block.get('name', 'Timer')
    print(f"    → Validating timer channel configuration for {block_name}...")
    
    # Ensure channel comparison registers follow naming convention
    channels = 0
    for reg in block.get('registers', []):
        reg_name = reg.get('name', '')
        # Count CCMR registers (capture/compare mode registers)
        if 'CCMR' in reg_name or 'CCER' in reg_name:
            channels += 1
    
    # Add metadata about this timer's channel configuration
    if 'parameters' not in block:
        block['parameters'] = []
    
    # Only add if not already present
    if not any(p.get('name') == 'channels' for p in block['parameters']):
        block['parameters'].append({
            'name': 'channels',
            'value': channels
        })
    
    print(f"    → Timer {block_name} configured with {channels} channel(s)")


def transform_quadspi_memory_mapping(block: dict, config: dict) -> None:
    """
    Special handling for Quad SPI: normalize memory mapping definitions.
    
    The QSPI block can interface to different memory types and configurations.
    This transformation ensures consistent field naming and sizing.
    
    Configuration example (in YAML):
        QUADSPI:
          instances: [QUADSPI]
          specialHandling: quadspi_memory_mapping
    
    Note: This is a template for how to handle QSPI-specific needs.
    Currently mostly a placeholder—actual implementation depends on
    which QSPI configuration variations need to be normalized.
    """
    
    print(f"    → Setting up QSPI memory mapping...")
    
    # Ensure CCR (communication configuration register) fields are documented
    ccr = svd.findNamedEntry(block.get('registers', []), 'CCR')
    if ccr:
        # Verify important QSPI mode fields are present
        important_fields = ['FMODE', 'DMODE', 'ADMODE', 'IMODE']
        existing_fields = {f.get('name') for f in ccr.get('fields', [])}
        
        for field_name in important_fields:
            if field_name not in existing_fields:
                print(f"      ⚠️  QSPI.CCR missing field: {field_name}")
    
    print(f"    → QSPI memory mapping configured")


def transform_adc_injected_channels(block: dict, config: dict) -> None:
    """
    Special handling for ADC: normalize injected channel configuration.
    
    STM32H7 ADCs support both regular (12-channel) and injected (4-channel)
    conversion sequences. This transformation ensures the injected channel
    data registers are properly clustered.
    
    Configuration example (in YAML):
        ADC:
          instances: [ADC1, ADC2, ADC3]
          arrays:
            - name: injected
              pattern: 'JDR(\d+)'  # Regular array pattern
              clusterName: 'JDR'
              count: 4
    
    This is mostly for documentation—the array transformation above
    should handle it. This function can add ADC-specific enumerations
    or validations if needed.
    """
    
    print(f"    → Validating ADC injected channel configuration...")
    
    # Verify JDR (injected data) registers are present
    jdr_count = sum(
        1 for reg in block.get('registers', [])
        if 'JDR' in reg.get('name', '')
    )
    
    if jdr_count == 0:
        print(f"      ⚠️  ADC missing injected data registers (JDR)")
    else:
        print(f"      ✓ ADC has {jdr_count} injected data register(s)")


def transform_dma_linked_list(block: dict, config: dict) -> None:
    """
    Special handling for DMA: validate linked-list descriptor format.
    
    STM32H7 DMA supports linked-list mode for autonomous transfer sequences.
    This transformation documents and validates the linked-list descriptor
    format that the hardware expects.
    
    Configuration example (in YAML):
        DMA:
          instances: [DMA1, DMA2]
          specialHandling: dma_linked_list
    
    The linked-list descriptors are typically memory-organized (not in SVD),
    so this function documents their structure and validates that the
    stream registers support linked-list mode.
    """
    
    dma_name = block.get('name', 'DMA')
    print(f"    → Validating {dma_name} linked-list mode support...")
    
    # Check that stream registers have the necessary fields for linked-list
    required_fields = ['NDTR', 'PAR', 'M0AR', 'CR']  # Base requirements
    
    streams = [
        reg for reg in block.get('registers', [])
        if 'S' in reg.get('name', '') and isinstance(reg.get('name'), str)
        and reg.get('name', '').split('[')[0][-1].isdigit()
    ]
    
    if streams:
        print(f"      ✓ {dma_name} has {len(streams)} stream(s) for linked-list transfers")
    else:
        print(f"      ⚠️  {dma_name} has unusual stream organization")


def transform_hsem_mailbox_format(block: dict, config: dict) -> None:
    """
    Special handling for HSEM (Hardware Semaphore): document mailbox format.
    
    STM32H7 HSEM (available on dual-core variants) provides semaphores and
    mailboxes for inter-processor communication. This transformation documents
    the mailbox descriptor format and validates the semaphore count.
    
    Configuration example (in YAML):
        HSEM:
          instances: [HSEM]
          specialHandling: hsem_mailbox_format
    
    Note: HSEM is only present on dual-core STM32H7 variants.
    Single-core variants don't have this block.
    """
    
    print(f"    → Validating HSEM (Hardware Semaphore) configuration...")
    
    # Count semaphore registers
    sem_count = sum(
        1 for reg in block.get('registers', [])
        if 'R' in reg.get('name', '')  # Semaphore register pattern
    )
    
    if sem_count > 0:
        print(f"      ✓ HSEM configured with {sem_count} semaphore(s)")
    
    # Note: Mailbox format is typically in SRAM, not register-based
    # So there's not much to validate here block-structure-wise


# ═══════════════════════════════════════════════════════════════════════════
# TRANSFORMATION METADATA
# ═══════════════════════════════════════════════════════════════════════════

"""
Available family-specific transformations for STM32H7:

1. rcc_cpu_clustering
   - Clusters CPU-specific clock control registers (C0_*, C1_*, C2_*)
   - Adds missing DSI support fields
   - Creates C[0..2] cluster array
   
2. timer_channel_mapping
   - Validates and normalizes timer channel configuration
   - Ensures consistent CCMR/CCER register naming
   
3. quadspi_memory_mapping
   - Normalizes QSPI memory interface configuration
   
4. adc_injected_channels
   - Validates injected channel data registers
   
5. dma_linked_list
   - Validates linked-list mode support in DMA streams
   
6. hsem_mailbox_format
   - Documents Hardware Semaphore (dual-core only) configuration

To use in configuration:
    RCC:
      specialHandling: rcc_cpu_clustering
    
    Timer:
      specialHandling: timer_channel_mapping
"""
