import xml.etree.ElementTree as ET
import yaml
import sys

def parse_stm32_xml(xml_path, yaml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Extract family and version
    family = root.attrib.get("Family", "STM32H745")
    version = root.attrib.get("Version", "")

    # Extract documents
    documents = []
    for doc in root.findall("Documents/Document"):
        name = doc.attrib.get("Name")
        if name:
            documents.append(name)

    # Extract pads and alternate functions
    pads = {}
    for pin in root.findall("Pins/Pin"):
        pad_name = pin.attrib.get("Name")
        if not pad_name:
            continue
        afs = ["" for _ in range(16)]
        for signal in pin.findall("Signal"):
            af_index = signal.attrib.get("AlternateFunction")
            name = signal.attrib.get("Name")
            if af_index and af_index.isdigit() and name:
                afs[int(af_index)] = name
        pads[pad_name] = {
            "type": "digital",
            "functions": afs
        }

    # Extract packages and pin mappings
    packages = {}
    for pkg in root.findall("Packages/Package"):
        pkg_name = pkg.attrib.get("Name")
        pin_map = {}
        for pin in pkg.findall("PinMapping"):
            pin_name = pin.attrib.get("PinName")
            pad_name = pin.attrib.get("PadName")
            if pin_name and pad_name:
                pin_map[pin_name] = pad_name
        packages[pkg_name] = pin_map

    # Build final YAML structure
    yaml_data = {
        "family": family,
        "version": version,
        "documents": documents,
        "pads": pads,
        "packages": packages
    }

    # Write to YAML file
    with open(yaml_path, "w") as f:
        yaml.dump(yaml_data, f, sort_keys=False)

    print(f"YAML file written to: {yaml_path}")

parse_stm32_xml(sys.argv[1], sys.argv[2])
# "STM32H745XIHx.xml", "stm32h745_pin_list.yaml"