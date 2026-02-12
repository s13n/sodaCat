"""
Generic transformation framework for hardware peripheral models.

This module provides a plugin-based transformation system that allows:
1. Transformations defined in configuration files (YAML, JSON, etc.)
2. Transformation dispatch based on configuration (not hardcoded per-block)
3. Easy addition of new transformation types via function registration
4. Generic core transformations (rename, array, etc.) reusable across MCU families
5. Family-specific transformations in subfolders when needed

Architecture:
  TransformationRegistry
    └─ Stores {type_name: function} mappings
       ├─ Built-in generic transformations (rename, array, etc.)
       └─ Family-specific transformations (registered at startup)
  
  TransformationEngine
    └─ Loads config, discovers what transformations apply to each instance
       ├─ Only calls applicable transformations (config-driven)
       └─ Maps transformation names to registered functions

Usage:
  # Initialize engine
  engine = TransformationEngine()
  
  # Register custom family-specific transformations
  engine.register_transformation('custom_rcc_cpu_clustering', custom_rcc_handler)
  
  # Load configuration and apply transformations
  config = load_yaml('stm32h7-transforms.yaml')
  for instance_name in chip['peripherals']:
    block = chip['peripherals'][instance_name]
    engine.apply_transformations(block, instance_name, config)

(C) 2024 Stefan Heinzmann
"""

import re
import sys
from typing import Dict, List, Callable, Any, Optional
import inspect


class TransformationRegistry:
    """Registry for transformation functions.
    
    Maps transformation names to their implementation functions.
    Supports both built-in generic transformations and family-specific ones.
    """
    
    def __init__(self):
        """Initialize registry with built-in generic transformations."""
        self._transformations: Dict[str, Callable] = {}
        self._register_builtin_transformations()
    
    def _register_builtin_transformations(self):
        """Register all built-in generic transformation types."""
        # These transformations are generic and work for any MCU family
        self.register('renameFields', self._transform_rename_fields)
        self.register('renameRegisters', self._transform_rename_registers)
        self.register('renameInterrupts', self._transform_rename_interrupts)
        self.register('createArrays', self._transform_create_arrays)
        self.register('setParameters', self._transform_set_parameters)
        self.register('setHeaderStructName', self._transform_set_header_struct_name)
        self.register('addFields', self._transform_add_fields)
    
    def register(self, name: str, func: Callable) -> None:
        """Register a transformation function.
        
        Args:
            name: Transformation type name (e.g., 'renameFields', 'custom_rcc_clustering')
            func: Callable that performs the transformation
                  Signature: func(block: dict, transform_config: dict) -> None
                  (modifications are in-place)
        
        Raises:
            ValueError: If transformation already registered
        """
        if name in self._transformations:
            raise ValueError(f"Transformation '{name}' already registered")
        self._transformations[name] = func
    
    def get(self, name: str) -> Optional[Callable]:
        """Get a registered transformation function.
        
        Args:
            name: Transformation type name
        
        Returns:
            Callable if found, None otherwise
        """
        return self._transformations.get(name)
    
    def has(self, name: str) -> bool:
        """Check if a transformation is registered."""
        return name in self._transformations
    
    def list_available(self) -> List[str]:
        """Return list of all registered transformation names."""
        return sorted(self._transformations.keys())
    
    # ═══════════════════════════════════════════════════════════════════════
    # BUILT-IN GENERIC TRANSFORMATIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def _transform_set_header_struct_name(block: dict, config: dict) -> None:
        """Set the headerStructName (block type).
        
        Configuration format (in YAML):
          headerStructName: AdvCtrlTimer
          
          OR (for instance-specific mapping):
          
          headerStructNameMap:
            TIM1: AdvCtrlTimer
            TIM2: GpTimer
        """
        if 'headerStructName' in config:
            block['headerStructName'] = config['headerStructName']
        elif 'headerStructNameMap' in config:
            # Would need instance name; handled at caller level
            # So we skip this here—caller handles the mapping
            pass
    
    @staticmethod
    def _transform_rename_fields(block: dict, config: dict) -> None:
        """Apply rename transformations to field names.
        
        Configuration format (in YAML):
          renames:
            - target: fields      # Which collection to rename
              field: name         # Which property of each entry to modify
              pattern: 'FIELD\d+_(.+)'
              replacement: '\1'
        
        Looks for 'renames' key with list of rename rules.
        Only processes rules where target=='fields'.
        """
        renames = config.get('renames', [])
        for rename_rule in renames:
            if rename_rule.get('target') != 'fields':
                continue
            
            _apply_rename_rule(
                block.get('fields', []),
                rename_rule['field'],
                rename_rule['pattern'],
                rename_rule['replacement']
            )
    
    @staticmethod
    def _transform_rename_registers(block: dict, config: dict) -> None:
        """Apply rename transformations to register names.
        
        Configuration format (in YAML):
          renames:
            - target: registers   # Which collection to rename
              field: name
              pattern: 'S(\d+)(.+)'
              replacement: '\2'
        
        Looks for 'renames' key with list of rename rules.
        Only processes rules where target=='registers'.
        """
        renames = config.get('renames', [])
        for rename_rule in renames:
            if rename_rule.get('target') != 'registers':
                continue
            
            _apply_rename_rule(
                block.get('registers', []),
                rename_rule['field'],
                rename_rule['pattern'],
                rename_rule['replacement']
            )
    
    @staticmethod
    def _transform_rename_interrupts(block: dict, config: dict) -> None:
        """Apply rename transformations to interrupt names.
        
        Configuration format (in YAML):
          renames:
            - target: interrupts  # Which collection to rename
              field: name
              pattern: 'USART\d+_(.+)'
              replacement: '\1'
        """
        renames = config.get('renames', [])
        for rename_rule in renames:
            if rename_rule.get('target') != 'interrupts':
                continue
            
            _apply_rename_rule(
                block.get('interrupts', []),
                rename_rule['field'],
                rename_rule['pattern'],
                rename_rule['replacement']
            )
    
    @staticmethod
    def _transform_create_arrays(block: dict, config: dict) -> None:
        """Convert repetitive registers into cluster arrays.
        
        Configuration format (in YAML):
          arrays:
            - name: streams                    # Name of array specification (for docs)
              description: DMA stream registers
              pattern: 'S(\d+)(.+)'           # Regex: group 1=index, group 2=name
              clusterName: 'S'                # Name of resulting cluster
              clusterDesc: 'DMA stream'       # Description of cluster
              count: 8                        # Expected number of elements
        
        Requires import of transform.createClusterArray from existing transform.py
        """
        # Lazy import to avoid circular dependency
        from transform import createClusterArray
        
        arrays_config = config.get('arrays', [])
        for array_spec in arrays_config:
            cluster_dict = {
                'name': array_spec['clusterName'],
                'description': array_spec.get('clusterDesc', '')
            }
            
            block['registers'] = createClusterArray(
                block.get('registers', []),
                array_spec['pattern'],
                cluster_dict
            )
    
    @staticmethod
    def _transform_set_parameters(block: dict, config: dict, instance_name: str = None) -> None:
        """Add capability parameters to the block (instance-specific).
        
        Configuration format (in YAML):
          parameters:
            TIM2:
              wide: 1              # 32-bit counter
              chan_max: 3          # 4 channels (0-3)
              rep: 0               # No repetition counter
            TIM3:
              wide: 0              # 16-bit counter
              chan_max: 3
              rep: 0
        
        Parameters can also be a simple dict for all instances:
          parameters:
            resolution_bits: 12
            channels: 21
        """
        params_config = config.get('parameters', {})
        
        if not params_config:
            return
        
        # Check if parameters are instance-specific (dict of dicts)
        # or generic (flat dict)
        is_instance_specific = (
            isinstance(params_config, dict) and
            instance_name and
            instance_name in params_config and
            isinstance(params_config[instance_name], dict)
        )
        
        if is_instance_specific:
            params = params_config[instance_name]
        elif isinstance(params_config, dict) and not any(
            isinstance(v, dict) for v in params_config.values()
        ):
            # Flat dict—apply to all instances
            params = params_config
        else:
            # Ambiguous or empty
            return
        
        # Convert dict to list of {name, value} dicts
        block['parameters'] = [
            {'name': k, 'value': v}
            for k, v in params.items()
        ]
    
    @staticmethod
    def _transform_add_fields(block: dict, config: dict) -> None:
        """Add missing fields to registers (for incomplete SVDs).
        
        Configuration format (in YAML):
          addFields:
            - registerName: RCC_D1CCIPR       # Which register to modify
              field:
                name: DSISRC
                bitOffset: 8
                bitWidth: 3
                description: DSI kernel clock source
            - registerName: RCC_APB3ENR
              field:
                name: DSIEN
                bitOffset: 4
                bitWidth: 1
        """
        add_fields_config = config.get('addFields', [])
        
        for field_spec in add_fields_config:
            reg_name = field_spec['registerName']
            field_def = field_spec['field']
            
            # Find the register
            for reg in block.get('registers', []):
                if reg['name'] == reg_name:
                    # Add field to register
                    if 'fields' not in reg:
                        reg['fields'] = []
                    reg['fields'].append(field_def)
                    break


class TransformationEngine:
    """Engine for applying transformations to peripheral blocks.
    
    - Loads transformation configurations
    - Maintains transformation registry (built-in + custom)
    - Applies only configured transformations to each block
    - Logs which transformations were applied
    """
    
    def __init__(self, verbose: bool = False):
        """Initialize transformation engine.
        
        Args:
            verbose: If True, print debug info about transformations applied
        """
        self.registry = TransformationRegistry()
        self.verbose = verbose
        self._applied_log = []
    
    def register_transformation(self, name: str, func: Callable) -> None:
        """Register a family-specific or custom transformation.
        
        Args:
            name: Transformation type name (e.g., 'rcc_cpu_clustering')
            func: Callable with signature: func(block: dict, config: dict) -> None
        """
        self.registry.register(name, func)
    
    def apply_transformations(
        self,
        block: dict,
        instance_name: str,
        block_config: dict,
        default_priority: Optional[List[str]] = None
    ) -> None:
        """Apply all configured transformations to a block instance.
        
        Only transformations that appear in block_config are applied.
        This is the key feature: transformation dispatch is config-driven.
        
        Args:
            block: The peripheral block data structure
            instance_name: Name of this instance (e.g., 'TIM1', 'DMA1')
            block_config: Configuration for this block (from YAML)
            default_priority: If provided, apply transformations in this order.
                            If not provided, apply in order found in config.
        
        Returns:
            Log of transformations applied (if verbose=True)
        """
        self._applied_log.clear()
        
        # Determine which transformations to apply
        # Look for all known transformation types in block_config
        transformations_to_apply = []
        
        for transform_name in self.registry.list_available():
            if transform_name in block_config or _config_has_key(block_config, transform_name):
                transformations_to_apply.append(transform_name)
        
        # Apply in specified order (priority), or config order
        if default_priority:
            ordered_transforms = [t for t in default_priority if t in transformations_to_apply]
            # Add any remaining transforms not in priority list
            ordered_transforms.extend(t for t in transformations_to_apply if t not in ordered_transforms)
        else:
            ordered_transforms = transformations_to_apply
        
        # Apply each transformation
        for transform_name in ordered_transforms:
            transform_func = self.registry.get(transform_name)
            if not transform_func:
                if self.verbose:
                    print(f"  ⚠️  Transformation '{transform_name}' not registered")
                continue
            
            try:
                # Special handling for setParameters (needs instance name)
                if transform_name == 'setParameters':
                    transform_func(block, block_config, instance_name)
                else:
                    transform_func(block, block_config)
                
                self._applied_log.append((transform_name, 'success'))
                
                if self.verbose:
                    print(f"  ✓ Applied: {transform_name}")
            
            except Exception as e:
                self._applied_log.append((transform_name, f'error: {e}'))
                if self.verbose:
                    print(f"  ✗ Failed: {transform_name}: {e}")
    
    def get_transformation_log(self) -> List[tuple]:
        """Get log of transformations applied in last operation."""
        return self._applied_log.copy()
    
    def list_available_transformations(self) -> List[str]:
        """Return list of registered transformation names."""
        return self.registry.list_available()


# ═══════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _apply_rename_rule(
    collection: List[dict],
    field_name: str,
    pattern: str,
    replacement: str
) -> None:
    """Apply a regex rename rule to all entries in a collection.
    
    Args:
        collection: List of dicts (e.g., registers, fields, interrupts)
        field_name: Name of field to modify in each dict
        pattern: Regex pattern for matching
        replacement: Replacement string (supports backreferences like \1)
    """
    pat = re.compile(pattern)
    for entry in collection:
        if field_name in entry:
            entry[field_name] = pat.sub(replacement, entry[field_name])


def _config_has_key(config: dict, key: str) -> bool:
    """Check if a transformation config key exists.
    
    Handles both direct keys and keys within nested structures.
    E.g., 'renameFields' might appear as a dict with 'target: fields'.
    """
    if key in config:
        return True
    
    # Check for plural form in renames list
    if key in ['renameFields', 'renameRegisters', 'renameInterrupts']:
        if 'renames' in config:
            target_map = {
                'renameFields': 'fields',
                'renameRegisters': 'registers',
                'renameInterrupts': 'interrupts'
            }
            target = target_map[key]
            return any(r.get('target') == target for r in config.get('renames', []))
    
    return False


def discover_family_transformations(family_folder: str) -> Dict[str, Callable]:
    """Auto-discover and import family-specific transformations.
    
    Looks for Python modules in family folder that contain transformation
    functions named like: transform_<name>
    
    Args:
        family_folder: Path to folder containing family-specific transforms
                      (e.g., 'parsers/stm32h7/')
    
    Returns:
        Dict mapping transformation names to functions
    
    Example:
        # In parsers/stm32h7/stm32h7_transforms.py:
        def transform_rcc_cpu_clustering(block, config):
            # Custom RCC handling...
            pass
        
        # At startup:
        family_transforms = discover_family_transformations('parsers/stm32h7')
        engine.register_transformation('rcc_cpu_clustering', 
                                       family_transforms['rcc_cpu_clustering'])
    """
    import importlib.util
    from pathlib import Path
    
    transforms = {}
    family_path = Path(family_folder)
    
    # Look for *_transforms.py files
    for module_file in family_path.glob('*_transforms.py'):
        # Import the module dynamically
        spec = importlib.util.spec_from_file_location('family_transforms', module_file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find all functions named transform_*
            for name, obj in inspect.getmembers(module):
                if name.startswith('transform_') and callable(obj):
                    transform_name = name[len('transform_'):]  # Remove prefix
                    transforms[transform_name] = obj
    
    return transforms
