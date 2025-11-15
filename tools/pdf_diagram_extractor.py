"""
Block Diagram Analyzer for STM32 Reference Manual Style Diagrams

Extracts directed acyclic graph structures from block diagrams in PDF files.
Outputs JSON/YAML with nodes (functional blocks) and signals (connections).
"""

import sys
import json
import base64
from pathlib import Path
from io import BytesIO

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF not installed. Install with: pip install PyMuPDF")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Error: requests not installed. Install with: pip install requests")
    sys.exit(1)

try:
    import yaml
except ImportError:
    yaml = None
    print("Warning: PyYAML not installed. YAML output disabled. Install with: pip install PyYAML")


def extract_page_as_image(pdf_path, page_number):
    """
    Extract a specific page from PDF as a high-resolution image.
    
    Args:
        pdf_path: Path to the PDF file
        page_number: Page number (1-indexed)
    
    Returns:
        Base64 encoded PNG image
    """
    try:
        doc = fitz.open(pdf_path)
        
        if page_number < 1 or page_number > len(doc):
            raise ValueError(f"Page number {page_number} out of range (1-{len(doc)})")
        
        # Get the page (0-indexed in PyMuPDF)
        page = doc[page_number - 1]
        
        # Render at high resolution (300 DPI)
        zoom = 3.0  # Zoom factor (1.0 = 72 DPI, 3.0 = 216 DPI)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to PNG bytes
        img_bytes = pix.tobytes("png")
        
        # Encode as base64
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        
        doc.close()
        return img_base64
    
    except Exception as e:
        print(f"Error extracting page: {e}")
        sys.exit(1)


def analyze_diagram_with_claude(image_base64):
    """
    Send the diagram image to Claude API for analysis.
    
    Args:
        image_base64: Base64 encoded image
    
    Returns:
        Structured data dictionary with nodes and signals
    """
    
    prompt = """Analyze this block diagram and extract its structure as a directed acyclic graph.

The diagram shows functional blocks (nodes) connected by directional signal lines (edges).

Please provide your response ONLY as a JSON object with this exact structure (no markdown, no preamble):

{
  "nodes": [
    {
      "id": "unique_node_id",
      "label": "Node Label/Name",
      "type": "block_type_based_on_shape",
      "inputs": ["signal_id1", "signal_id2"],
      "outputs": ["signal_id3"]
    }
  ],
  "signals": [
    {
      "id": "unique_signal_id",
      "name": "Signal Name",
      "source": "source_node_id",
      "destinations": ["dest_node_id1", "dest_node_id2"]
    }
  ]
}

Guidelines:
- Each node should have a unique ID (e.g., "node_1", "rcc_block", etc.)
- Node types should be inferred from shape (e.g., "rectangle", "rounded_rectangle", "circle", "multiplexer", etc.)
- Each signal should have a unique ID
- Signal names should match the labels on the arrows/lines
- If a signal goes off-diagram, note "external" in destinations
- If a signal source is off-diagram, note "external" as source

Return ONLY the JSON object, nothing else."""

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4000,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            },
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"Error from Claude API: {response.status_code}")
            print(response.text)
            sys.exit(1)
        
        result = response.json()
        
        # Extract text from response
        text_content = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                text_content += block.get("text", "")
        
        # Parse JSON response (strip any markdown code fences if present)
        text_content = text_content.strip()
        if text_content.startswith("```"):
            # Remove markdown code fences
            lines = text_content.split("\n")
            text_content = "\n".join(lines[1:-1]) if len(lines) > 2 else text_content
        
        # Parse the JSON
        structured_data = json.loads(text_content)
        return structured_data
    
    except requests.exceptions.RequestException as e:
        print(f"Network error calling Claude API: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing Claude's response as JSON: {e}")
        print(f"Response was: {text_content[:500]}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


def save_output(data, output_path, format='json'):
    """
    Save the structured data to a file.
    
    Args:
        data: Dictionary with nodes and signals
        output_path: Path to output file
        format: 'json' or 'yaml'
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            if format == 'yaml' and yaml:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            else:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Output saved to: {output_path}")
    
    except Exception as e:
        print(f"Error saving output: {e}")
        sys.exit(1)


def print_summary(data):
    """Print a summary of the extracted structure."""
    nodes = data.get("nodes", [])
    signals = data.get("signals", [])
    
    print(f"\n{'='*60}")
    print(f"EXTRACTION SUMMARY")
    print(f"{'='*60}")
    print(f"Total Nodes: {len(nodes)}")
    print(f"Total Signals: {len(signals)}")
    
    if nodes:
        node_types = {}
        for node in nodes:
            node_type = node.get("type", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1
        
        print(f"\nNode Types:")
        for node_type, count in sorted(node_types.items()):
            print(f"  - {node_type}: {count}")
    
    print(f"{'='*60}\n")


def main():
    """Main entry point."""
    
    if len(sys.argv) < 3:
        print("Usage: python block_diagram_analyzer.py <pdf_file> <page_number> [output_file] [format]")
        print("\nArguments:")
        print("  pdf_file     : Path to the PDF file")
        print("  page_number  : Page number containing the diagram (1-indexed)")
        print("  output_file  : (Optional) Output file path (default: diagram_output.json)")
        print("  format       : (Optional) Output format: 'json' or 'yaml' (default: json)")
        print("\nExample:")
        print("  python block_diagram_analyzer.py rm0399.pdf 365 output.json json")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    page_number = int(sys.argv[2])
    output_file = sys.argv[3] if len(sys.argv) > 3 else "diagram_output.json"
    output_format = sys.argv[4].lower() if len(sys.argv) > 4 else "json"
    
    if output_format not in ['json', 'yaml']:
        print(f"Error: Invalid format '{output_format}'. Use 'json' or 'yaml'")
        sys.exit(1)
    
    if not Path(pdf_path).exists():
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)
    
    print(f"Analyzing diagram from {pdf_path}, page {page_number}...")
    print(f"Step 1/3: Extracting page as image...")
    image_base64 = extract_page_as_image(pdf_path, page_number)
    
    print(f"Step 2/3: Analyzing diagram with Claude API...")
    structured_data = analyze_diagram_with_claude(image_base64)
    
    print(f"Step 3/3: Saving output...")
    save_output(structured_data, output_file, output_format)
    
    print_summary(structured_data)
    print("✓ Done!")


if __name__ == "__main__":
    main()