#!/usr/bin/env python3
"""
Skrypt do eksportu pacjentów z lokalnej bazy SQLite do pliku JSON
"""

import json
import sqlite3
from datetime import datetime

def export_patients_to_json():
    """Eksportuje wszystkich pacjentów z lokalnej bazy do pliku JSON"""
    try:
        # Połączenie z lokalną bazą danych
        conn = sqlite3.connect('trichology.db')
        conn.row_factory = sqlite3.Row  # Umożliwia dostęp do kolumn przez nazwę
        cursor = conn.cursor()
        
        # Pobranie wszystkich pacjentów
        cursor.execute('SELECT * FROM patients')
        rows = cursor.fetchall()
        
        # Konwersja wierszy SQLite na słowniki
        patients = []
        for row in rows:
            patient = dict(row)
            patients.append(patient)
        
        # Eksport do pliku JSON
        filename = f"patients_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(patients, f, indent=2, ensure_ascii=False)
        
        conn.close()
        
        print(f"✅ Wyeksportowano {len(patients)} pacjentów do pliku: {filename}")
        print(f"📁 Plik znajduje się w katalogu projektu")
        
        # Wyświetl przykład pierwszego pacjenta
        if patients:
            print(f"\n📋 Przykład pierwszego pacjenta:")
            first_patient = patients[0]
            print(f"   - PESEL: {first_patient.get('pesel', 'brak')}")
            print(f"   - Imię: {first_patient.get('name', 'brak')}")
            print(f"   - Nazwisko: {first_patient.get('surname', 'brak')}")
            print(f"   - Telefon: {first_patient.get('phone', 'brak')}")
        
        return filename
        
    except sqlite3.Error as e:
        print(f"❌ Błąd bazy danych: {e}")
        return None
    except Exception as e:
        print(f"❌ Błąd ogólny: {e}")
        return None

if __name__ == "__main__":
    print("🔄 Rozpoczynanie eksportu pacjentów...")
    result = export_patients_to_json()
    if result:
        print(f"\n🎉 Eksport zakończony pomyślnie!")
        print(f"📤 Następny krok: Wgraj ten plik na serwer Railway i zaimportuj pacjentów")
    else:
        print(f"\n💥 Eksport nieudany!")
