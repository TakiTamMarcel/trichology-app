#!/usr/bin/env python3
"""
Eksport tylko podstawowych danych pacjentów (kompatybilnych z Railway)
"""
import json
import sqlite3
from datetime import datetime

def export_basic_patients():
    """Eksportuje pacjentów z tylko podstawowymi polami kompatybilnymi z Railway"""
    try:
        # Połączenie z lokalną bazą danych
        conn = sqlite3.connect('trichology.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Eksport tylko podstawowych kolumn
        basic_columns = [
            'pesel', 'name', 'surname', 'birthdate', 'gender', 
            'phone', 'email', 'height', 'weight', 'photo',
            'medication_list', 'supplements_list', 'allergens', 
            'diseases', 'treatments', 'notes', 'created_at',
            'peeling_type', 'peeling_frequency', 'shampoo_name', 
            'shampoo_brand', 'shampoo_frequency'
        ]
        
        columns_str = ', '.join(basic_columns)
        cursor.execute(f'SELECT {columns_str} FROM patients')
        rows = cursor.fetchall()
        
        # Konwersja wierszy na słowniki
        patients = []
        for row in rows:
            patient = {}
            for col in basic_columns:
                try:
                    patient[col] = row[col]
                except (IndexError, KeyError):
                    patient[col] = None  # Jeśli kolumna nie istnieje, ustaw None
            patients.append(patient)
        
        # Eksport do pliku
        filename = f"basic_patients_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(patients, f, indent=2, ensure_ascii=False)
        
        conn.close()
        
        print(f"✅ Wyeksportowano {len(patients)} pacjentów (podstawowe dane) do pliku: {filename}")
        
        # Wyświetl przykład
        if patients:
            first_patient = patients[0]
            print(f"\n📋 Przykład pierwszego pacjenta:")
            print(f"   - PESEL: {first_patient.get('pesel', 'brak')}")
            print(f"   - Imię: {first_patient.get('name', 'brak')}")
            print(f"   - Nazwisko: {first_patient.get('surname', 'brak')}")
        
        return filename
        
    except Exception as e:
        print(f"❌ Błąd: {e}")
        return None

if __name__ == "__main__":
    print("🔄 Eksport podstawowych danych pacjentów dla Railway...")
    result = export_basic_patients()
    if result:
        print(f"\n🎉 Eksport zakończony! Plik: {result}")
    else:
        print(f"\n💥 Eksport nieudany!")
