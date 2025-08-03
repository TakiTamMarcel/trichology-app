#!/usr/bin/env python3
"""
Skrypt do migracji pacjentów z lokalnej bazy SQLite na Railway
"""

import sqlite3
import json
import requests
import os
from datetime import datetime

# Konfiguracja
LOCAL_DB = 'trichology.db'
RAILWAY_URL = 'https://web-production-74f1.up.railway.app'
RAILWAY_API_URL = f'{RAILWAY_URL}/api/import-patient'
IMPORT_PASSWORD = 'MIGRATION_2025_TEMP'

# Headers dla Railway API (będziemy potrzebować uwierzytelnienia)
HEADERS = {
    'Content-Type': 'application/json',
    'User-Agent': 'Patient Migration Script'
}

def get_local_patients():
    """Pobiera wszystkich pacjentów z lokalnej bazy SQLite"""
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row  # Zwraca wiersze jako słowniki
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM patients')
        patients = cursor.fetchall()
        
        # Konwertuj na słowniki
        patients_list = []
        for patient in patients:
            patient_dict = dict(patient)
            patients_list.append(patient_dict)
        
        print(f"✅ Znaleziono {len(patients_list)} pacjentów w lokalnej bazie")
        return patients_list
        
    except Exception as e:
        print(f"❌ Błąd pobierania pacjentów: {str(e)}")
        return []
    finally:
        conn.close()

def clean_patient_data(patient):
    """Czyści i przygotowuje dane pacjenta do wysłania"""
    # Usuń pola które mogą być problemem
    if 'id' in patient:
        del patient['id']  # Railway wygeneruje nowe ID
    
    # Upewnij się że JSON pola są właściwe
    json_fields = ['medication_list', 'supplements_list', 'allergens', 'diseases', 'treatments']
    for field in json_fields:
        if field in patient and patient[field]:
            if isinstance(patient[field], str):
                try:
                    patient[field] = json.loads(patient[field])
                except:
                    patient[field] = []
            elif patient[field] is None:
                patient[field] = []
    
    # Upewnij się że wymagane pola istnieją
    required_fields = ['name', 'surname', 'pesel', 'birthdate', 'gender']
    for field in required_fields:
        if field not in patient or patient[field] is None:
            if field == 'birthdate':
                patient[field] = '1990-01-01'  # Domyślna data
            elif field == 'gender':
                patient[field] = 'male'  # Domyślna płeć
            else:
                patient[field] = ''  # Puste string
    
    return patient

def migrate_patient(patient_data):
    """Migruje pojedynczego pacjenta na Railway"""
    try:
        # Wyczyść dane
        clean_data = clean_patient_data(patient_data.copy())
        
        # Dodaj hasło importu
        clean_data['import_password'] = IMPORT_PASSWORD
        
        # Wyślij POST request
        response = requests.post(RAILWAY_API_URL, json=clean_data, headers=HEADERS)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success') == True:
                print(f"✅ Pacjent {clean_data.get('name')} {clean_data.get('surname')} (PESEL: {clean_data.get('pesel')}) - MIGRACJA UDANA")
                return True
            else:
                print(f"❌ Pacjent {clean_data.get('name')} {clean_data.get('surname')} - BŁĄD API: {result.get('error', 'Nieznany błąd')}")
                return False
        else:
            print(f"❌ Pacjent {clean_data.get('name')} {clean_data.get('surname')} - BŁĄD HTTP {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Pacjent {patient_data.get('name')} {patient_data.get('surname')} - WYJĄTEK: {str(e)}")
        return False

def main():
    """Główna funkcja migracji"""
    print("🚀 ROZPOCZYNAM MIGRACJĘ PACJENTÓW Z LOKALNEJ BAZY NA RAILWAY")
    print("=" * 60)
    
    # Pobierz pacjentów z lokalnej bazy
    patients = get_local_patients()
    if not patients:
        print("❌ Brak pacjentów do migracji")
        return
    
    # Wyświetl listę pacjentów
    print("\n📋 LISTA PACJENTÓW DO MIGRACJI:")
    for i, patient in enumerate(patients, 1):
        print(f"{i:2d}. {patient.get('name', '???')} {patient.get('surname', '???')} (PESEL: {patient.get('pesel', '???')})")
    
    # Potwierdzenie
    print(f"\n⚠️  UWAGA: Zostanie zmigrowanych {len(patients)} pacjentów na Railway")
    confirm = input("Czy kontynuować? (tak/nie): ").lower().strip()
    
    if confirm != 'tak':
        print("❌ Migracja anulowana")
        return
    
    print("\n🔄 ROZPOCZYNAM MIGRACJĘ...")
    print("-" * 40)
    
    # Migruj każdego pacjenta
    success_count = 0
    failed_count = 0
    
    for i, patient in enumerate(patients, 1):
        print(f"\n[{i}/{len(patients)}] Migracja pacjenta...")
        if migrate_patient(patient):
            success_count += 1
        else:
            failed_count += 1
    
    # Podsumowanie
    print("\n" + "=" * 60)
    print("📊 PODSUMOWANIE MIGRACJI:")
    print(f"✅ Udanych migracji: {success_count}")
    print(f"❌ Nieudanych migracji: {failed_count}")
    print(f"📋 Razem pacjentów: {len(patients)}")
    
    if success_count > 0:
        print(f"\n🎉 Migracja zakończona! Sprawdź Railway: {RAILWAY_URL}")
    else:
        print(f"\n😞 Żadna migracja nie powiodła się. Sprawdź czy jesteś zalogowany na Railway.")

if __name__ == "__main__":
    main() 