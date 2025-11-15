#!/usr/bin/env python3
"""
PDF Tabellen Extraktor mit Linienerkennung
Verwendet pdfplumber zur präzisen Tabellenerkennung basierend auf Linien im PDF

Installation:
pip install pdfplumber requests

Verwendung:
python pdf_table_extractor.py
"""

import pdfplumber
import requests
import csv
from pathlib import Path

def download_pdf(url, output_path="downloaded.pdf"):
    """PDF von URL herunterladen"""
    print(f"Lade PDF herunter von: {url}")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"PDF gespeichert als: {output_path}")
    return output_path

def extract_table_from_pdf(pdf_path, start_page, end_page, output_csv="output.csv"):
    """
    Extrahiert Tabelle aus PDF unter Verwendung der Linien zur Zellerkennung
    
    Args:
        pdf_path: Pfad zur PDF-Datei
        start_page: Start-Seite (1-basiert)
        end_page: End-Seite (1-basiert)
        output_csv: Ausgabe CSV-Datei
    """
    print(f"\nÖffne PDF: {pdf_path}")
    
    all_rows = []
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"PDF hat {len(pdf.pages)} Seiten")
        
        # Iteriere über die angegebenen Seiten
        for page_num in range(start_page - 1, end_page):
            if page_num >= len(pdf.pages):
                print(f"Warnung: Seite {page_num + 1} existiert nicht")
                continue
                
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

def main():
    # Konfiguration
    PDF_URL = "https://www.st.com/resource/en/datasheet/stm32h745zg.pdf"
    START_PAGE = 87
    END_PAGE = 88
    OUTPUT_CSV = "table_9.csv"
    
    print("=" * 60)
    print("PDF Tabellen Extraktor mit Linienerkennung")
    print("=" * 60)
    
    # Option 1: PDF von URL herunterladen
    try:
        pdf_path = download_pdf(PDF_URL, "stm32h745zg.pdf")
    except Exception as e:
        print(f"Fehler beim Herunterladen: {e}")
        print("\nAlternativ: Legen Sie die PDF-Datei manuell in dieses Verzeichnis")
        print("und geben Sie den Dateinamen ein:")
        pdf_path = input("PDF-Dateiname: ").strip()
        
        if not Path(pdf_path).exists():
            print(f"Fehler: Datei '{pdf_path}' nicht gefunden!")
            return
    
    # Extrahiere Tabelle
    success = extract_table_from_pdf(
        pdf_path=pdf_path,
        start_page=START_PAGE,
        end_page=END_PAGE,
        output_csv=OUTPUT_CSV
    )
    
    if success:
        print("\n" + "=" * 60)
        print("✓ Extraktion abgeschlossen!")
        print(f"✓ CSV-Datei: {OUTPUT_CSV}")
        print("=" * 60)
    else:
        print("\n✗ Extraktion fehlgeschlagen!")

if __name__ == "__main__":
    main()