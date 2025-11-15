#!/usr/bin/env python3
"""
PDF Table Extractor with Line Detection
Uses pdfplumber for precise table recognition based on lines in the PDF

Installation:
pip install pdfplumber requests

Usage:
python pdf_table_extractor.py <pdf_path> <csv_path> [--table NUMBER] [--pages START-END]

Examples:
  python pdf_table_extractor.py input.pdf output.csv
  python pdf_table_extractor.py input.pdf output.csv --table 9 --pages 87..88
  python pdf_table_extractor.py https://example.com/file.pdf output.csv --pages ..10
"""

import pdfplumber
import requests
import csv
import argparse
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

def download_pdf(url):
    """Download PDF from URL and return temporary file"""
    print(f"Downloading PDF from: {url}")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    # Create temporary file
    temp_file = NamedTemporaryFile(delete=False, suffix='.pdf')
    
    with open(temp_file.name, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"PDF downloaded")
    return temp_file.name

def find_table_pages(pdf, table_number):
    """
    Search for the specified table number in the PDF and return page numbers
    
    Returns:
        tuple: (start_page, end_page) or (None, None) if not found
    """
    print(f"Searching for Table {table_number}...")
    
    start_page = None
    end_page = None
    
    for page_num, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text:
            # Search for "Table X" pattern
            import re
            pattern = rf'\bTable\s+{table_number}\b'
            
            if re.search(pattern, text, re.IGNORECASE):
                if start_page is None:
                    start_page = page_num + 1
                    print(f"  Table {table_number} found on page {start_page}")
                end_page = page_num + 1
            elif start_page is not None:
                # Check if we've reached the next table
                next_pattern = rf'\bTable\s+{int(table_number) + 1}\b'
                if re.search(next_pattern, text, re.IGNORECASE):
                    print(f"  Table {table_number} ends on page {end_page}")
                    break
    
    if start_page and not end_page:
        end_page = start_page
    
    return start_page, end_page

def parse_page_range(page_spec, total_pages):
    """
    Parse page range like "87-88" or "..10" or "50.."
    
    Args:
        page_spec: String with page specification
        total_pages: Total number of pages in PDF
    
    Returns:
        tuple: (start_page, end_page)
    """
    # Support both '-' and '..' as separators
    if '-' in page_spec or '..' in page_spec:
        separator = '..' if '..' in page_spec else '-'
        parts = page_spec.split(separator)
        
        if len(parts) != 2:
            raise ValueError(f"Invalid page range: {page_spec}")
        
        start_str, end_str = parts
        
        # Open ranges
        if not start_str:
            start = 1
        else:
            start = int(start_str)
        
        if not end_str:
            end = total_pages
        else:
            end = int(end_str)
        
        return start, end
    else:
        # Single page
        page = int(page_spec)
        return page, page

def parse_column_spec(column_spec, max_columns=None):
    """
    Parse column specification like "0,2,5" or "0-2,5" or "0.." into a set of indices
    
    Args:
        column_spec: String with column specification
        max_columns: Maximum number of columns (for open ranges)
    
    Returns:
        Set of integer indices
    """
    if not column_spec:
        return set()
    
    columns = set()
    parts = column_spec.split(',')
    
    for part in parts:
        part = part.strip()
        
        # Support both '-' and '..' as separators
        if '-' in part or '..' in part:
            separator = '..' if '..' in part else '-'
            range_parts = part.split(separator)
            
            if len(range_parts) != 2:
                raise ValueError(f"Invalid range: {part}")
            
            start_str, end_str = range_parts
            
            # Open ranges like "..5" or "3.." or ".."
            if not start_str:
                start = 0
            else:
                start = int(start_str)
            
            if not end_str:
                if max_columns is None:
                    raise ValueError(f"Open range '{part}' requires knowledge of total number of columns")
                end = max_columns - 1
            else:
                end = int(end_str)
            
            columns.update(range(start, end + 1))
        else:
            # Single column
            columns.add(int(part))
    
    return columns

def extract_table_from_pdf(pdf_path, start_page, end_page, output_csv, skip_header_rows=None, drop_columns_spec=None):
    """
    Extract table from PDF using lines for cell recognition
    
    Args:
        pdf_path: Path to PDF file
        start_page: Start page (1-based)
        end_page: End page (1-based)
        output_csv: Output CSV file
        skip_header_rows: Number of header rows that are repeated (None for automatic)
        drop_columns_spec: String specification of columns to remove
    """
    print(f"\nOpening PDF: {pdf_path}")
    
    all_rows = []
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"PDF has {total_pages} pages")
        
        # Validate page numbers
        if start_page < 1 or end_page > total_pages or start_page > end_page:
            print(f"Error: Invalid page numbers (1-{total_pages})")
            return False
        
        # Iterate over specified pages
        for page_num in range(start_page - 1, end_page):
            page = pdf.pages[page_num]
            print(f"\nProcessing page {page_num + 1}...")
            
            # Strategy 1: Try with table_settings for better recognition
            table_settings = {
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "explicit_vertical_lines": [],
                "explicit_horizontal_lines": [],
                "snap_tolerance": 3,
                "join_tolerance": 3,
                "edge_min_length": 3,
                "min_words_vertical": 1,
                "min_words_horizontal": 1,
                "intersection_tolerance": 3,
            }
            
            # Try to find tables on the page
            tables = page.extract_tables(table_settings)
            
            if tables:
                print(f"  Found: {len(tables)} table(s)")
                for idx, table in enumerate(tables):
                    print(f"  Table {idx + 1}: {len(table)} rows, {len(table[0]) if table else 0} columns")
                    all_rows.extend(table)
            else:
                # Fallback: Try without lines (text-based)
                print("  No tables found with lines, trying text-based extraction...")
                table_settings["vertical_strategy"] = "text"
                table_settings["horizontal_strategy"] = "text"
                tables = page.extract_tables(table_settings)
                
                if tables:
                    print(f"  Found (text-based): {len(tables)} table(s)")
                    for table in tables:
                        all_rows.extend(table)
                else:
                    print("  No tables found")
    
    if not all_rows:
        print("\nError: No table data extracted!")
        return False
    
    # Clean the data
    cleaned_rows = []
    for row in all_rows:
        if row and any(cell for cell in row if cell):  # Skip completely empty rows
            # Clean each cell
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_row.append("")
                else:
                    # Remove excess whitespace and line breaks
                    cleaned_cell = " ".join(str(cell).split())
                    cleaned_row.append(cleaned_cell)
            cleaned_rows.append(cleaned_row)
    
    # Remove repeated header rows
    print("\nRemoving repeated header rows...")
    if len(cleaned_rows) > 1:
        num_header_rows = skip_header_rows
        
        # Automatic detection if not manually specified
        if num_header_rows is None:
            print("  Automatic header detection...")
            # Identify potential headers (first row(s))
            header_candidates = []
            
            # Check first 1-5 rows as possible headers
            max_header_rows = min(5, len(cleaned_rows))
            
            for num_headers in range(1, max_header_rows + 1):
                potential_headers = cleaned_rows[:num_headers]
                duplicates_found = 0
                
                # Search for repetitions of these header rows in the rest
                for i in range(num_headers, len(cleaned_rows) - num_headers + 1):
                    if cleaned_rows[i:i+num_headers] == potential_headers:
                        duplicates_found += 1
                
                if duplicates_found > 0:
                    header_candidates.append((num_headers, duplicates_found))
            
            # Choose header configuration with most duplicates
            if header_candidates:
                best_header = max(header_candidates, key=lambda x: x[1])
                num_header_rows = best_header[0]
                num_duplicates = best_header[1]
                print(f"  Detected: {num_header_rows} header row(s), {num_duplicates} repetition(s) found")
            else:
                print("  No repeated headers found")
                num_header_rows = 0
        else:
            print(f"  Using manual specification: {num_header_rows} header row(s)")
        
        # Remove duplicates if headers found
        if num_header_rows > 0 and num_header_rows < len(cleaned_rows):
            header_rows = cleaned_rows[:num_header_rows]
            deduplicated_rows = [header_rows]
            
            i = num_header_rows
            while i < len(cleaned_rows):
                # Check if next N rows are the headers
                if (i + num_header_rows <= len(cleaned_rows) and 
                    cleaned_rows[i:i+num_header_rows] == header_rows):
                    # Skip this header repetition
                    print(f"  Skipping header repetition at row {i+1}")
                    i += num_header_rows
                else:
                    # Normal data row
                    deduplicated_rows.append([cleaned_rows[i]])
                    i += 1
            
            # Create flat list
            cleaned_rows = [row for sublist in deduplicated_rows for row in sublist]
            print(f"  After deduplication: {cleaned_rows} rows")
        else:
            print("  No repeated headers found")
    
    # Remove columns if specified
    if drop_columns_spec:
        original_cols = len(cleaned_rows[0]) if cleaned_rows else 0
        
        # Parse with knowledge of total column count for open ranges
        drop_columns = parse_column_spec(drop_columns_spec, original_cols)
        
        print(f"\nRemoving columns: {sorted(drop_columns)}")
        
        cleaned_rows = [
            [cell for idx, cell in enumerate(row) if idx not in drop_columns]
            for row in cleaned_rows
        ]
        
        new_cols = len(cleaned_rows[0]) if cleaned_rows else 0
        print(f"  Columns: {original_cols} → {new_cols}")
    
    print(f"\nTotal extracted: {len(cleaned_rows)} rows")
    
    # Save as CSV
    print(f"Saving CSV: {output_csv}")
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(cleaned_rows)
    
    print(f"✓ Successfully saved: {output_csv}")
    
    # Show preview
    print("\n--- Preview (first 5 rows) ---")
    for i, row in enumerate(cleaned_rows[:5]):
        print(f"Row {i+1}: {row}")
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description='Extract tables from PDF files based on lines',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.pdf output.csv
  %(prog)s input.pdf output.csv --table 9 --pages 87..88
  %(prog)s input.pdf output.csv --pages ..10
  %(prog)s input.pdf output.csv --pages 50..
  %(prog)s input.pdf output.csv --drop-columns "0,3"
  %(prog)s input.pdf output.csv --drop-columns "..2,5"
  %(prog)s input.pdf output.csv --drop-columns "10.."
  %(prog)s https://example.com/file.pdf output.csv -t 9 -s 1 -d "0..2,5"
        """
    )
    
    parser.add_argument('pdf_path', 
                       help='Path to PDF file or URL')
    parser.add_argument('csv_path', 
                       help='Path to output CSV file')
    parser.add_argument('--table', '-t', 
                       type=int, 
                       help='Table number (e.g. 9 for "Table 9")')
    parser.add_argument('--pages', '-p', 
                       help='Page range (e.g. "87-88", "87..88", "..10", "50..", or "5")')
    parser.add_argument('--skip-header', '-s',
                       type=int,
                       metavar='N',
                       help='Number of header rows to remove on subsequent pages (default: automatic)')
    parser.add_argument('--drop-columns', '-d',
                       metavar='COLS',
                       help='Columns to remove (e.g. "0,2,5", "0-2,5", "0..2", "..5", "10..")')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("PDF Table Extractor with Line Detection")
    print("=" * 60)
    
    # Determine if PDF path is a URL
    pdf_path = args.pdf_path
    is_url = pdf_path.startswith('http://') or pdf_path.startswith('https://')
    temp_file = None
    
    try:
        if is_url:
            temp_file = download_pdf(pdf_path)
            pdf_path = temp_file
        elif not Path(pdf_path).exists():
            print(f"Error: File '{pdf_path}' not found!")
            return 1
        
        # Open PDF to determine page numbers
        with pdfplumber.open(pdf_path) as pdf:
            # Determine page range
            if args.table:
                # Search for table number
                start_page, end_page = find_table_pages(pdf, args.table)
                
                if start_page is None:
                    print(f"\nError: Table {args.table} not found!")
                    return 1
                
                # Override with --pages if specified
                if args.pages:
                    print(f"Note: --pages overrides automatically found pages")
                    start_page, end_page = parse_page_range(args.pages, len(pdf.pages))
                
            elif args.pages:
                # Only page range specified
                start_page, end_page = parse_page_range(args.pages, len(pdf.pages))
            else:
                # Neither table nor pages specified - use all pages
                start_page = 1
                end_page = len(pdf.pages)
                print(f"Note: Extracting from all pages (1-{end_page})")
        
        print(f"\nExtracting pages {start_page} to {end_page}")
        
        # Extract table
        success = extract_table_from_pdf(
            pdf_path=pdf_path,
            start_page=start_page,
            end_page=end_page,
            output_csv=args.csv_path,
            skip_header_rows=args.skip_header,
            drop_columns_spec=args.drop_columns
        )
        
        if success:
            print("\n" + "=" * 60)
            print("✓ Extraction complete!")
            print(f"✓ CSV file: {args.csv_path}")
            print("=" * 60)
            return 0
        else:
            print("\n✗ Extraction failed!")
            return 1
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        # Delete temporary file if created
        if temp_file and Path(temp_file).exists():
            Path(temp_file).unlink()

if __name__ == "__main__":
    sys.exit(main())