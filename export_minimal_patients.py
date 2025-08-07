#!/usr/bin/env python3
"""
Eksport TYLKO najważniejszych danych pacjentów
"""
import json
import sqlite3
from datetime import datetime

def export_minimal_patients():
    """Eksportuje pacjentów z tylko najważniejszymi polami"""
    try:
        conn = sqlite3.connect('trichology.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # TYLKO najważniejsze kolumny które są w każdej wersji bazy
        minimal_columns = [
            'pesel', 'name', 'surname', 'birthdate', 'gender', 
            'phone', 'email', 'height', 'weight',
            'medication_list', 'supplements_list', 'allergens', 
            'diseases', 'treatments', 'notes'
        ]
        
        columns_str = ', '.join(minimal_columns)
        cursor.execute(f'SELECT {columns_str} FROM patients')
        rows = cursor.fetchall()
        
        patients = []
        for row in rows:
            patient = {}
            for col in minimal_columns:
                try:
                    value = row[col]
                    # Konwersja pustych JSON-ów na puste stringi
                    if value == '[]' or value == 'null':
                        value = '[]'
                    patient[col] = value
                except (IndexError, KeyError):
                    patient[col] = '' if col in ['notes', 'height', 'weight'] else '[]'
            
            # Dodaj created_at jeśli brak
            patient['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            patients.append(patient)
        
        filename = f"minimal_patients_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(patients, f, indent=2, ensure_ascii=False)
        
        conn.close()
        
        print(f"✅ Wyeksportowano {len(patients)} pacjentów (minimalne dane)")
        print(f"📁 Plik: {filename}")
        
        if patients:
            first = patients[0]
            print(f"\n📋 Przykład: {first.get('name', '')} {first.get('surname', '')} ({first.get('pesel', '')})")
        
        return filename
        
    except Exception as e:
        print(f"❌ Błąd: {e}")
        return None

if __name__ == "__main__":
    print("🔄 Eksport minimalnych danych pacjentów...")
    result = export_minimal_patients()
    if result:
        print(f"🎉 Gotowe!")
