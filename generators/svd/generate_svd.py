#!/usr/bin/env python3
"""Generate SVD (System View Description) XML from sodaCat YAML models.

This is the reverse of the normal pipeline: instead of SVD → YAML, this goes
YAML → SVD, producing "fixed" SVD files that incorporate all transformations
applied during model creation.

Dependencies:
    Required: ruamel.yaml (pip install ruamel.yaml) or PyYAML (pip install PyYAML)
    Optional: lxml (pip install lxml) — only needed for --validate

Usage:
    python3 generators/svd/generate_svd.py <chip_model.yaml> [--models-dir <dir>] [-o <output.svd>]

Examples:
    python3 generators/svd/generate_svd.py models/ST/C5/C59x_C5A3/STM32C5A3.yaml
    python3 generators/svd/generate_svd.py models/ST/H7/H742_H753/STM32H743.yaml -o STM32H743_fixed.svd
    python3 generators/svd/generate_svd.py models/ST/C5/C59x_C5A3/STM32C5A3.yaml --validate
"""

import argparse
import os
import re
import sys
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

try:
    from ruamel.yaml import YAML
    _yaml = YAML(typ='safe')
    def _load_yaml(stream):
        return _yaml.load(stream)
except ImportError:
    try:
        import yaml
        def _load_yaml(stream):
            return yaml.safe_load(stream)
    except ImportError:
        print('Error: ruamel.yaml or PyYAML is required.\n'
              'Install one with:  pip install ruamel.yaml\n'
              '               or: pip install PyYAML', file=sys.stderr)
        sys.exit(1)


# SVD CPU name mapping: sodaCat short names → CMSIS-SVD canonical names
CPU_NAME_MAP = {
    'CM0': 'CM0',
    'CM0+': 'CM0+',
    'CM0PLUS': 'CM0+',
    'CM3': 'CM3',
    'CM4': 'CM4',
    'CM7': 'CM7',
    'CM23': 'CM23',
    'CM33': 'CM33',
    'CM35P': 'CM35P',
    'CM55': 'CM55',
    'CM85': 'CM85',
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def hex_str(value, width=8):
    """Format an integer as a zero-padded hex string (e.g., 0x40000000)."""
    return f'0x{value:0{width}X}'


def to_int(value):
    """Convert a value that may be int or hex string to int."""
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.startswith('0x'):
        return int(value, 16)
    return int(value)


def add_text_element(parent, tag, text):
    """Add a child element with text content."""
    el = SubElement(parent, tag)
    el.text = str(text)
    return el


def load_yaml(path):
    """Load a YAML file."""
    with open(path, 'r') as f:
        return _load_yaml(f)


def resolve_model_path(model_ref, models_dir):
    """Resolve a model reference (e.g., 'ST/C5/ADC') to a filesystem path."""
    return os.path.join(models_dir, model_ref + '.yaml')


def build_device_element(chip, peripherals):
    """Build the root <device> SVD element from chip model and peripheral blocks.

    Args:
        chip: Parsed chip model dict.
        peripherals: Dict of {model_ref: parsed_peripheral_dict}.

    Returns:
        xml.etree.ElementTree.Element: The root <device> element.
    """
    device = Element('device')
    device.set('schemaVersion', '1.3')
    device.set('xmlns:xs', 'http://www.w3.org/2001/XMLSchema-instance')
    device.set('xs:noNamespaceSchemaLocation', 'CMSIS-SVD.xsd')

    add_text_element(device, 'vendor', 'STMicroelectronics')
    add_text_element(device, 'name', chip['name'])
    add_text_element(device, 'version', '1.0')
    add_text_element(device, 'description',
                     f'{chip["name"]} device generated from sodaCat models')

    build_cpu_element(device, chip['cpu'])

    add_text_element(device, 'addressUnitBits', '8')
    add_text_element(device, 'width', '32')

    # Default register properties
    add_text_element(device, 'size', '0x20')
    add_text_element(device, 'access', 'read-write')
    add_text_element(device, 'resetValue', '0x00000000')
    add_text_element(device, 'resetMask', '0xFFFFFFFF')
    build_peripherals_element(device, chip, peripherals)

    return device


def build_cpu_element(device, cpu):
    """Build the <cpu> element."""
    cpu_el = SubElement(device, 'cpu')
    svd_name = CPU_NAME_MAP.get(cpu['name'], cpu['name'])
    add_text_element(cpu_el, 'name', svd_name)
    add_text_element(cpu_el, 'revision', cpu['revision'])
    add_text_element(cpu_el, 'endian', cpu['endian'])
    add_text_element(cpu_el, 'mpuPresent', str(cpu['mpuPresent']).lower())
    add_text_element(cpu_el, 'fpuPresent', str(cpu['fpuPresent']).lower())
    if 'vtorPresent' in cpu:
        add_text_element(cpu_el, 'vtorPresent', str(cpu['vtorPresent']).lower())
    add_text_element(cpu_el, 'nvicPrioBits', str(cpu['nvicPrioBits']))
    add_text_element(cpu_el, 'vendorSystickConfig',
                     str(cpu['vendorSystickConfig']).lower())


def build_peripherals_element(device, chip, peripherals):
    """Build the <peripherals> element with all instances."""
    periphs_el = SubElement(device, 'peripherals')

    # Group instances by model to use derivedFrom for duplicates
    model_first_instance = {}  # model_ref → first instance name

    # Sort instances by base address for deterministic output
    sorted_instances = sorted(chip['instances'].items(),
                              key=lambda x: x[1]['baseAddress'])

    for inst_name, inst_data in sorted_instances:
        model_type = inst_data['model']
        model_ref = chip['models'].get(model_type)
        if model_ref is None:
            print(f'Warning: no model path for type {model_type}, '
                  f'skipping {inst_name}', file=sys.stderr)
            continue

        block = peripherals.get(model_ref)
        if block is None:
            print(f'Warning: could not load model {model_ref}, '
                  f'skipping {inst_name}', file=sys.stderr)
            continue

        is_derived = model_ref in model_first_instance
        first_inst = model_first_instance.get(model_ref)

        if is_derived:
            periph_el = SubElement(periphs_el, 'peripheral')
            periph_el.set('derivedFrom', first_inst)
            add_text_element(periph_el, 'name', inst_name)
            add_text_element(periph_el, 'baseAddress',
                             hex_str(inst_data['baseAddress']))
            build_interrupts_on_peripheral(periph_el, inst_name, inst_data)
        else:
            model_first_instance[model_ref] = inst_name
            periph_el = build_full_peripheral(
                periphs_el, inst_name, inst_data, block)

    return periphs_el


def build_full_peripheral(parent, inst_name, inst_data, block):
    """Build a full <peripheral> element with registers."""
    periph_el = SubElement(parent, 'peripheral')
    add_text_element(periph_el, 'name', inst_name)

    if block.get('description'):
        add_text_element(periph_el, 'description', block['description'])
    if block.get('groupName'):
        add_text_element(periph_el, 'groupName', block['groupName'])

    add_text_element(periph_el, 'baseAddress',
                     hex_str(inst_data['baseAddress']))

    # Address block
    if block.get('addressBlocks'):
        for ab in block['addressBlocks']:
            ab_el = SubElement(periph_el, 'addressBlock')
            add_text_element(ab_el, 'offset', hex_str(to_int(ab['offset']), 1))
            add_text_element(ab_el, 'size', hex_str(to_int(ab['size']), 1))
            add_text_element(ab_el, 'usage', ab.get('usage', 'registers'))
    else:
        # SVD requires addressBlock; synthesize one from register span
        ab_el = SubElement(periph_el, 'addressBlock')
        add_text_element(ab_el, 'offset', '0x0')
        size = compute_register_span(block.get('registers', []))
        add_text_element(ab_el, 'size', hex_str(size, 1))
        add_text_element(ab_el, 'usage', 'registers')

    build_interrupts_on_peripheral(periph_el, inst_name, inst_data)

    # Registers
    regs = block.get('registers', [])
    if regs:
        regs_el = SubElement(periph_el, 'registers')
        for reg_or_cluster in regs:
            if 'registers' in reg_or_cluster:
                build_cluster(regs_el, reg_or_cluster)
            else:
                build_register(regs_el, reg_or_cluster)

    return periph_el


def build_interrupts_on_peripheral(periph_el, inst_name, inst_data):
    """Add <interrupt> elements to a peripheral."""
    for intr in inst_data.get('interrupts', []):
        intr_el = SubElement(periph_el, 'interrupt')
        # SVD convention: interrupt name is typically INSTANCE_SIGNAL
        signal = intr['name']
        svd_intr_name = f'{inst_name}_{signal}' if signal != 'INTR' else inst_name
        add_text_element(intr_el, 'name', svd_intr_name)
        add_text_element(intr_el, 'value', str(intr['value']))


def compute_register_span(registers):
    """Compute the address span covered by a list of registers/clusters."""
    max_end = 0
    for reg in registers:
        offset = to_int(reg.get('addressOffset', 0))
        if 'registers' in reg:
            # Cluster
            flat_dim, flat_inc = flatten_dim(
                reg.get('dim', 1), reg.get('dimIncrement', 0))
            inner_span = compute_register_span(reg['registers'])
            end = offset + (flat_dim - 1) * flat_inc + inner_span
        else:
            size_bits = reg.get('size', 32)
            size_bytes = size_bits // 8
            flat_dim, flat_inc = flatten_dim(
                reg.get('dim', 1), reg.get('dimIncrement', size_bytes))
            end = offset + (flat_dim - 1) * flat_inc + size_bytes
        max_end = max(max_end, end)

    # Round up to next power of 2 that is at least 4
    if max_end <= 4:
        return 4
    # Round up to next nice boundary (0x400 = 1KB is common for STM32)
    for boundary in [0x100, 0x400, 0x800, 0x1000, 0x2000, 0x4000]:
        if max_end <= boundary:
            return boundary
    return max_end


def flatten_dim(dim, dim_increment):
    """Flatten multi-dimensional dim/dimIncrement to SVD-compatible single dimension.

    sodaCat models support multi-dimensional arrays like dim=[4,16],
    dimIncrement=[64,4]. SVD only supports single-dimension arrays.
    When dimensions are contiguous, we flatten to a single dimension
    with the innermost stride.

    Returns:
        (flat_dim, flat_increment): Flattened values.
    """
    if not isinstance(dim, list):
        inc = to_int(dim_increment) if dim_increment is not None else 4
        return (dim, inc)

    total = 1
    for d in dim:
        total *= d

    # Use innermost (last) increment
    if isinstance(dim_increment, list):
        inc = to_int(dim_increment[-1])
    elif dim_increment is not None:
        inc = to_int(dim_increment)
    else:
        inc = 4

    return (total, inc)


def flatten_dim_name(name):
    """Simplify multi-dimensional array name for SVD.

    Converts 'FOO[%s][%s]' → 'FOO[%s]' since SVD only supports 1D arrays.
    """
    return re.sub(r'(\[%s\])+', '[%s]', name)


def build_register(parent, reg):
    """Build a <register> element."""
    reg_el = SubElement(parent, 'register')

    # Dimensional array support
    dim = reg.get('dim')
    if dim is not None:
        flat_dim, flat_inc = flatten_dim(dim, reg.get('dimIncrement'))
        add_text_element(reg_el, 'dim', str(flat_dim))
        add_text_element(reg_el, 'dimIncrement', hex_str(flat_inc, 1))

    reg_name = flatten_dim_name(reg['name']) if dim is not None and isinstance(dim, list) else reg['name']
    add_text_element(reg_el, 'name', reg_name)
    if reg.get('displayName'):
        add_text_element(reg_el, 'displayName', reg['displayName'])
    if reg.get('description'):
        add_text_element(reg_el, 'description', reg['description'])

    offset = to_int(reg.get('addressOffset', 0))
    add_text_element(reg_el, 'addressOffset', hex_str(offset, 1))

    size = reg.get('size', 32)
    add_text_element(reg_el, 'size', hex_str(size, 1))

    if reg.get('access'):
        add_text_element(reg_el, 'access', reg['access'])

    reset_value = reg.get('resetValue')
    if reset_value is not None:
        add_text_element(reg_el, 'resetValue', hex_str(to_int(reset_value)))

    reset_mask = reg.get('resetMask')
    if reset_mask is not None:
        add_text_element(reg_el, 'resetMask', hex_str(to_int(reset_mask)))

    # Fields
    fields = reg.get('fields', [])
    if fields:
        fields_el = SubElement(reg_el, 'fields')
        for field in fields:
            build_field(fields_el, field)

    return reg_el


def build_cluster(parent, cluster):
    """Build a <cluster> element."""
    cluster_el = SubElement(parent, 'cluster')

    dim = cluster.get('dim')
    if dim is not None:
        flat_dim, flat_inc = flatten_dim(dim, cluster.get('dimIncrement'))
        add_text_element(cluster_el, 'dim', str(flat_dim))
        add_text_element(cluster_el, 'dimIncrement', hex_str(flat_inc, 1))

    cluster_name = flatten_dim_name(cluster['name']) if dim is not None and isinstance(dim, list) else cluster['name']
    add_text_element(cluster_el, 'name', cluster_name)
    if cluster.get('description'):
        add_text_element(cluster_el, 'description', cluster['description'])

    offset = to_int(cluster.get('addressOffset', 0))
    add_text_element(cluster_el, 'addressOffset', hex_str(offset, 1))

    for reg_or_cluster in cluster.get('registers', []):
        if 'registers' in reg_or_cluster:
            build_cluster(cluster_el, reg_or_cluster)
        else:
            build_register(cluster_el, reg_or_cluster)

    return cluster_el


def build_field(parent, field):
    """Build a <field> element."""
    field_el = SubElement(parent, 'field')
    add_text_element(field_el, 'name', field['name'])
    if field.get('description'):
        add_text_element(field_el, 'description', field['description'])
    add_text_element(field_el, 'bitOffset', str(field['bitOffset']))
    add_text_element(field_el, 'bitWidth', str(field['bitWidth']))

    if field.get('access'):
        add_text_element(field_el, 'access', field['access'])

    enums = field.get('enumeratedValues')
    if enums:
        enums_el = SubElement(field_el, 'enumeratedValues')
        for ev in enums:
            ev_el = SubElement(enums_el, 'enumeratedValue')
            add_text_element(ev_el, 'name', ev['name'])
            if ev.get('description'):
                add_text_element(ev_el, 'description', ev['description'])
            add_text_element(ev_el, 'value', hex_str(to_int(ev['value']), 1))

    return field_el


def generate_svd(chip_model_path, models_dir=None, output_path=None):
    """Generate an SVD file from a chip model.

    Args:
        chip_model_path: Path to the chip-level YAML model.
        models_dir: Root directory for model lookups. If None, inferred from
                     chip_model_path by walking up to find 'models/'.
        output_path: Output SVD file path. If None, derived from chip name.

    Returns:
        The output file path.
    """
    chip = load_yaml(chip_model_path)

    # Infer models directory if not given
    if models_dir is None:
        # Walk up from chip model to find the models root
        # e.g., models/ST/C5/C59x_C5A3/STM32C5A3.yaml → models/
        path = os.path.abspath(chip_model_path)
        while path != '/':
            path = os.path.dirname(path)
            if os.path.basename(path) == 'models':
                models_dir = path
                break
        if models_dir is None:
            print('Error: could not infer models directory. '
                  'Use --models-dir.', file=sys.stderr)
            sys.exit(1)

    # Load all referenced peripheral block models
    peripherals = {}
    for model_type, model_ref in chip.get('models', {}).items():
        model_path = resolve_model_path(model_ref, models_dir)
        if os.path.exists(model_path):
            peripherals[model_ref] = load_yaml(model_path)
        else:
            print(f'Warning: model file not found: {model_path}',
                  file=sys.stderr)

    # Build SVD XML
    device = build_device_element(chip, peripherals)

    # Pretty-print
    indent(device, space='  ')

    # Write output
    if output_path is None:
        output_path = f'{chip["name"]}.svd'

    tree = ElementTree(device)
    with open(output_path, 'wb') as f:
        tree.write(f, encoding='utf-8', xml_declaration=True)

    # ElementTree doesn't add a trailing newline
    with open(output_path, 'a') as f:
        f.write('\n')

    return output_path


def validate_svd(svd_path):
    """Validate an SVD file against the CMSIS-SVD XSD schema.

    Requires the 'lxml' package for XSD validation.
    The CMSIS-SVD.xsd schema file is expected alongside this script.
    """
    try:
        from lxml import etree
    except ImportError:
        print('Error: lxml is required for --validate.\n'
              'Install it with:  pip install lxml', file=sys.stderr)
        return False

    schema_path = os.path.join(SCRIPT_DIR, 'CMSIS-SVD.xsd')
    if not os.path.exists(schema_path):
        print(f'Error: CMSIS-SVD.xsd not found at {schema_path}\n'
              f'This file should be distributed alongside {os.path.basename(__file__)}.',
              file=sys.stderr)
        return False

    try:
        schema_doc = etree.parse(schema_path)
        schema = etree.XMLSchema(schema_doc)
        doc = etree.parse(svd_path)
        if schema.validate(doc):
            print(f'Validation passed: {svd_path}')
            return True
        else:
            print(f'Validation failed: {svd_path}')
            for error in schema.error_log:
                print(f'  Line {error.line}: {error.message}',
                      file=sys.stderr)
            return False
    except etree.XMLSchemaParseError as e:
        print(f'Error parsing XSD schema: {e}', file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Generate SVD file from sodaCat YAML models')
    parser.add_argument('chip_model',
                        help='Path to chip-level YAML model')
    parser.add_argument('--models-dir', '-m',
                        help='Root models directory (default: auto-detect)')
    parser.add_argument('-o', '--output',
                        help='Output SVD file path (default: <ChipName>.svd)')
    parser.add_argument('--validate', action='store_true',
                        help='Validate output against CMSIS-SVD XSD schema '
                             '(requires lxml)')
    args = parser.parse_args()

    output_path = generate_svd(args.chip_model, args.models_dir, args.output)
    print(f'Generated: {output_path}')

    if args.validate:
        if not validate_svd(output_path):
            sys.exit(1)


if __name__ == '__main__':
    main()
