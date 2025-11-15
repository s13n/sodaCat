#!/usr/bin/env python3
"""
PDF Tabellen Extraktor mit Linienerkennung
Verwendet pdfplumber zur präzisen Tabellenerkennung basierend auf Linien im PDF

Installation:
pip install pdfplumber requests

Verwendung:
python pdf_table_extractor.py <pdf_pfad> <csv_pfad> [--table NUMMER] [--pages START-ENDE]

Beispiele:
  python pdf_table_extractor.py input.pdf output.csv
  python pdf_table_extractor.py input.pdf output.csv --table 9 --pages 87-88
  python pdf_table_extractor.py https://example.com/file.pdf output.csv --pages 1-5
"""

import pdfplumber
import requests
import csv
import argparse
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

def download_pdf(url):
    """PDF von URL herunterladen und temporäre Datei zurückgeben"""
    print(f"Lade PDF herunter von: {url}")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    # Erstelle temporäre Datei
    temp_file = NamedTemporaryFile(delete=False, suffix='.pdf')
    
    with open(temp_file.name, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"PDF heruntergeladen")
    return temp_file.name

def find_table_pages(pdf, table_number):
    """
    Sucht nach der angegebenen Tabellennummer im PDF und gibt die Seitenzahlen zurück
    
    Returns:
        tuple: (start_page, end_page) oder (None, None) wenn nicht gefunden
    """
    print(f"Suche nach Table {table_number}...")
    
    start_page = None
    end_page = None
    
    for page_num, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text:
            # Suche nach "Table X" Pattern
            import re
            pattern = rf'\bTable\s+{table_number}\b'
            
            if re.search(pattern, text, re.IGNORECASE):
                if start_page is None:
                    start_page = page_num + 1
                    print(f"  Table {table_number} gefunden auf Seite {start_page}")
                end_page = page_num + 1
            elif start_page is not None:
                # Prüfe ob wir zur nächsten Tabelle gekommen sind
                next_pattern = rf'\bTable\s+{int(table_number) + 1}\b'
                if re.search(next_pattern, text, re.IGNORECASE):
                    print(f"  Table {table_number} endet auf Seite {end_page}")
                    break
    
    if start_page and not end_page:
        end_page = start_page
    
    return start_page, end_page

def extract_table_from_pdf(pdf_path, start_page, end_page, output_csv, skip_header_rows=None, drop_columns_spec=None):
    """
    Extrahiert Tabelle aus PDF unter Verwendung der Linien zur Zellerkennung
    
    Args:
        pdf_path: Pfad zur PDF-Datei
        start_page: Start-Seite (1-basiert)
        end_page: End-Seite (1-basiert)
        output_csv: Ausgabe CSV-Datei
        skip_header_rows: Anzahl der Header-Zeilen die wiederholt werden (None für automatisch)
        drop_columns_spec: String-Spezifikation der zu entfernenden Spalten
    """
    print(f"\nÖffne PDF: {pdf_path}")
    
    all_rows = []
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"PDF hat {total_pages} Seiten")
        
        # Validiere Seitenzahlen
        if start_page < 1 or end_page > total_pages or start_page > end_page:
            print(f"Fehler: Ungültige Seitenzahlen (1-{total_pages})")
            return False
        
        # Iteriere über die angegebenen Seiten
        for page_num in range(start_page - 1, end_page):
            page = pdf.pages[page_num]
            print(f"\nVerarbeite Seite {page_num + 1}...")
            
            # Strategie 1: Versuche mit table_settings für bessere Erkennung
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
            
            # Versuche Tabellen auf der Seite zu finden
            tables = page.extract_tables(table_settings)
            
            if tables:
                print(f"  Gefunden: {len(tables)} Tabelle(n)")
                for idx, table in enumerate(tables):
                    print(f"  Tabelle {idx + 1}: {len(table)} Zeilen, {len(table[0]) if table else 0} Spalten")
                    all_rows.extend(table)
            else:
                # Fallback: Versuche ohne Linien (text-basiert)
                print("  Keine Tabellen mit Linien gefunden, versuche text-basierte Extraktion...")
                table_settings["vertical_strategy"] = "text"
                table_settings["horizontal_strategy"] = "text"
                tables = page.extract_tables(table_settings)
                
                if tables:
                    print(f"  Gefunden (text-basiert): {len(tables)} Tabelle(n)")
                    for table in tables:
                        all_rows.extend(table)
                else:
                    print("  Keine Tabellen gefunden")
    
    if not all_rows:
        print("\nFehler: Keine Tabellendaten extrahiert!")
        return False
    
    # Bereinige die Daten
    cleaned_rows = []
    for row in all_rows:
        if row and any(cell for cell in row if cell):  # Überspringe komplett leere Zeilen
            # Bereinige jede Zelle
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_row.append("")
                else:
                    # Entferne überflüssige Whitespace und Zeilenumbrüche
                    cleaned_cell = " ".join(str(cell).split())
                    cleaned_row.append(cleaned_cell)
            cleaned_rows.append(cleaned_row)
    
    # Entferne wiederholte Header-Zeilen
    print("\nEntferne wiederholte Header-Zeilen...")
    if len(cleaned_rows) > 1:
        num_header_rows = skip_header_rows
        
        # Automatische Erkennung wenn nicht manuell angegeben
        if num_header_rows is None:
            print("  Automatische Header-Erkennung...")
            # Identifiziere potenzielle Header (erste Zeile(n))
            header_candidates = []
            
            # Prüfe die ersten 1-5 Zeilen als mögliche Header
            max_header_rows = min(5, len(cleaned_rows))
            
            for num_headers in range(1, max_header_rows + 1):
                potential_headers = cleaned_rows[:num_headers]
                duplicates_found = 0
                
                # Suche nach Wiederholungen dieser Header-Zeilen im Rest
                for i in range(num_headers, len(cleaned_rows) - num_headers + 1):
                    if cleaned_rows[i:i+num_headers] == potential_headers:
                        duplicates_found += 1
                
                if duplicates_found > 0:
                    header_candidates.append((num_headers, duplicates_found))
            
            # Wähle die Header-Konfiguration mit den meisten Duplikaten
            if header_candidates:
                best_header = max(header_candidates, key=lambda x: x[1])
                num_header_rows = best_header[0]
                num_duplicates = best_header[1]
                print(f"  Erkannt: {num_header_rows} Header-Zeile(n), {num_duplicates} Wiederholung(en) gefunden")
            else:
                print("  Keine wiederholten Header gefunden")
                num_header_rows = 0
        else:
            print(f"  Verwende manuelle Angabe: {num_header_rows} Header-Zeile(n)")
        
        # Entferne Duplikate wenn Header gefunden
        if num_header_rows > 0 and num_header_rows < len(cleaned_rows):
            header_rows = cleaned_rows[:num_header_rows]
            deduplicated_rows = [header_rows]
            
            i = num_header_rows
            while i < len(cleaned_rows):
                # Prüfe ob die nächsten N Zeilen die Header sind
                if (i + num_header_rows <= len(cleaned_rows) and 
                    cleaned_rows[i:i+num_header_rows] == header_rows):
                    # Überspringe diese Header-Wiederholung
                    print(f"  Überspringe Header-Wiederholung bei Zeile {i+1}")
                    i += num_header_rows
                else:
                    # Normale Datenzeile
                    deduplicated_rows.append([cleaned_rows[i]])
                    i += 1
            
            # Flache Liste erstellen
            cleaned_rows = [row for sublist in deduplicated_rows for row in sublist]
            print(f"  Nach Deduplizierung: {len(cleaned_rows)} Zeilen")
        else:
            print("  Keine wiederholten Header gefunden")
    
    # Entferne Spalten falls angegeben
    if drop_columns_spec:
        original_cols = len(cleaned_rows[0]) if cleaned_rows else 0
        
        # Parse mit Kenntnis der Gesamtspaltenanzahl für offene Bereiche
        drop_columns = parse_column_spec(drop_columns_spec, original_cols)
        
        print(f"\nEntferne Spalten: {sorted(drop_columns)}")
        
        cleaned_rows = [
            [cell for idx, cell in enumerate(row) if idx not in drop_columns]
            for row in cleaned_rows
        ]
        
        new_cols = len(cleaned_rows[0]) if cleaned_rows else 0
        print(f"  Spalten: {original_cols} → {new_cols}")
    
    print(f"\nGesamt extrahiert: {len(cleaned_rows)} Zeilen")
    
    # Speichere als CSV
    print(f"Speichere CSV: {output_csv}")
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(cleaned_rows)
    
    print(f"✓ Erfolgreich gespeichert: {output_csv}")
    
    # Zeige Vorschau
    print("\n--- Vorschau (erste 5 Zeilen) ---")
    for i, row in enumerate(cleaned_rows[:5]):
        print(f"Zeile {i+1}: {row}")
    
    return True

def parse_page_range(page_spec, total_pages):
    """
    Parse Seitenbereich wie "87-88" oder "..10" oder "50.."
    
    Args:
        page_spec: String mit Seiten-Spezifikation
        total_pages: Gesamtanzahl Seiten im PDF
    
    Returns:
        tuple: (start_page, end_page)
    """
    # Unterstütze sowohl '-' als auch '..' als Trennzeichen
    if '-' in page_spec or '..' in page_spec:
        separator = '..' if '..' in page_spec else '-'
        parts = page_spec.split(separator)
        
        if len(parts) != 2:
            raise ValueError(f"Ungültiger Seitenbereich: {page_spec}")
        
        start_str, end_str = parts
        
        # Offene Bereiche
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
        # Einzelne Seite
        page = int(page_spec)
        return page, page
    """
    Parse Spalten-Spezifikation wie "0,2,5" oder "0-2,5" oder "0.." in ein Set von Indizes
    
    Args:
        column_spec: String mit Spalten-Spezifikation
        max_columns: Maximale Anzahl Spalten (für offene Bereiche)
    
    Returns:
        Set von Integer-Indizes
    """
    if not column_spec:
        return set()
    
    columns = set()
    parts = column_spec.split(',')
    
    for part in parts:
        part = part.strip()
        
        # Unterstütze sowohl '-' als auch '..' als Trennzeichen
        if '-' in part or '..' in part:
            separator = '..' if '..' in part else '-'
            range_parts = part.split(separator)
            
            if len(range_parts) != 2:
                raise ValueError(f"Ungültiger Bereich: {part}")
            
            start_str, end_str = range_parts
            
            # Offene Bereiche wie "..5" oder "3.." oder ".."
            if not start_str:
                start = 0
            else:
                start = int(start_str)
            
            if not end_str:
                if max_columns is None:
                    raise ValueError(f"Offener Bereich '{part}' benötigt Kenntnis der Gesamtanzahl Spalten")
                end = max_columns - 1
            else:
                end = int(end_str)
            
            columns.update(range(start, end + 1))
        else:
            # Einzelne Spalte
            columns.add(int(part))
    
    return columns

def main():
    parser = argparse.ArgumentParser(
        description='Extrahiert Tabellen aus PDF-Dateien basierend auf Linien',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
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
                       help='Pfad zur PDF-Datei oder URL')
    parser.add_argument('csv_path', 
                       help='Pfad zur Ausgabe-CSV-Datei')
    parser.add_argument('--table', '-t', 
                       type=int, 
                       help='Tabellennummer (z.B. 9 für "Table 9")')
    parser.add_argument('--pages', '-p', 
                       help='Seitenbereich (z.B. "87-88", "87..88", "..10", "50..", oder "5")')
    parser.add_argument('--skip-header', '-s',
                       type=int,
                       metavar='N',
                       help='Anzahl der Header-Zeilen, die auf Folgeseiten entfernt werden sollen (Standard: automatisch)')
    parser.add_argument('--drop-columns', '-d',
                       metavar='COLS',
                       help='Zu entfernende Spalten (z.B. "0,2,5", "0-2,5", "0..2", "..5", "10..")')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("PDF Tabellen Extraktor mit Linienerkennung")
    print("=" * 60)
    
    # Bestimme ob PDF-Pfad eine URL ist
    pdf_path = args.pdf_path
    is_url = pdf_path.startswith('http://') or pdf_path.startswith('https://')
    temp_file = None
    
    try:
        if is_url:
            temp_file = download_pdf(pdf_path)
            pdf_path = temp_file
        elif not Path(pdf_path).exists():
            print(f"Fehler: Datei '{pdf_path}' nicht gefunden!")
            return 1
        
        # Öffne PDF um Seitenzahlen zu bestimmen
        with pdfplumber.open(pdf_path) as pdf:
            # Bestimme Seitenbereich
            if args.table:
                # Suche nach Tabellennummer
                start_page, end_page = find_table_pages(pdf, args.table)
                
                if start_page is None:
                    print(f"\nFehler: Table {args.table} nicht gefunden!")
                    return 1
                
                # Override mit --pages falls angegeben
                if args.pages:
                    print(f"Hinweis: --pages überschreibt automatisch gefundene Seiten")
                    start_page, end_page = parse_page_range(args.pages, len(pdf.pages))
                
            elif args.pages:
                # Nur Seitenbereich angegeben
                start_page, end_page = parse_page_range(args.pages, len(pdf.pages))
            else:
                # Weder Tabelle noch Seiten angegeben - verwende alle Seiten
                start_page = 1
                end_page = len(pdf.pages)
                print(f"Hinweis: Extrahiere von allen Seiten (1-{end_page})")
        
        print(f"\nExtrahiere Seiten {start_page} bis {end_page}")
        
        # Extrahiere Tabelle
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
            print("✓ Extraktion abgeschlossen!")
            print(f"✓ CSV-Datei: {args.csv_path}")
            print("=" * 60)
            return 0
        else:
            print("\n✗ Extraktion fehlgeschlagen!")
            return 1
            
    except Exception as e:
        print(f"\n✗ Fehler: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        # Lösche temporäre Datei falls erstellt
        if temp_file and Path(temp_file).exists():
            Path(temp_file).unlink()

if __name__ == "__main__":
    sys.exit(main())