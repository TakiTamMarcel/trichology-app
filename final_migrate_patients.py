#!/usr/bin/env python3
"""
FINALNA migracja pacjentów na Railway po reset bazy danych
"""

import sqlite3
import json
import requests

# Konfiguracja
LOCAL_DB = 'trichology.db'
RAILWAY_URL = 'https://web-production-74f1.up.railway.app'
MIGRATE_ENDPOINT = f'{RAILWAY_URL}/api/final-migrate-patient'
MIGRATE_PASSWORD = 'FINAL_MIGRATE_AUG_2025'

def get_local_patients():
    """Pobiera wszystkich pacjentów z lokalnej bazy"""
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM patients')
        patients = cursor.fetchall()
        
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
    """Czyści i przygotowuje dane pacjenta"""
    # Usuń ID - Railway wygeneruje nowe
    if 'id' in patient:
        del patient['id']
    
    # Konwersja JSON fields
    json_fields = ['medication_list', 'supplements_list', 'allergens', 'diseases', 'treatments',
                   'shampoo_brand', 'shampoo_type', 'shampoo_details', 'treatment_type', 
                   'treatment_duration', 'treatment_details', 'care_product_type', 
                   'care_product_name', 'care_product_dose', 'care_product_frequency',
                   'care_procedure_type', 'care_procedure_frequency', 'care_procedure_details',
                   'chronic_diseases', 'skin_conditions', 'autoimmune', 'allergies', 
                   'family_conditions', 'diet', 'styling', 'problem_description', 
                   'problem_periodicity', 'previous_procedures', 'follicles_state', 'skin_condition']
    
    for field in json_fields:
        if field in patient and patient[field]:
            if isinstance(patient[field], str):
                try:
                    patient[field] = json.loads(patient[field])
                except:
                    patient[field] = []
            elif patient[field] is None:
                patient[field] = []
    
    # Wymagane pola
    required_fields = ['name', 'surname', 'pesel', 'birthdate', 'gender']
    for field in required_fields:
        if field not in patient or patient[field] is None:
            if field == 'birthdate':
                patient[field] = '1990-01-01'
            elif field == 'gender':
                patient[field] = 'male'
            else:
                patient[field] = ''
    
    return patient

def migrate_patient(patient_data):
    """Migruje pojedynczego pacjenta na Railway"""
    try:
        clean_data = clean_patient_data(patient_data.copy())
        clean_data['migrate_password'] = MIGRATE_PASSWORD
        
        response = requests.post(MIGRATE_ENDPOINT, json=clean_data, headers={
            'Content-Type': 'application/json'
        })
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success') == True:
                print(f"✅ {clean_data.get('name')} {clean_data.get('surname')} - ZMIGROWANO")
                return True
            else:
                print(f"❌ {clean_data.get('name')} {clean_data.get('surname')} - BŁĄD: {result.get('error')}")
                return False
        else:
            print(f"❌ {clean_data.get('name')} {clean_data.get('surname')} - HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ {patient_data.get('name')} {patient_data.get('surname')} - WYJĄTEK: {str(e)}")
        return False

def main():
    print("🚀 FINALNA MIGRACJA PACJENTÓW NA RAILWAY")
    print("=" * 50)
    print("Railway zresetowało bazę - przeprowadzam ponowną migrację")
    print("")
    
    # Pobierz pacjentów
    patients = get_local_patients()
    if not patients:
        print("❌ Brak pacjentów do migracji")
        return
    
    print(f"📋 Lista {len(patients)} pacjentów do migracji:")
    for i, patient in enumerate(patients, 1):
        print(f"{i:2d}. {patient.get('name', '???')} {patient.get('surname', '???')} (PESEL: {patient.get('pesel', '???')})")
    
    # Potwierdzenie
    confirm = input(f"\n⚠️  FINALNA migracja {len(patients)} pacjentów na Railway? (tak/nie): ").lower().strip()
    if confirm != 'tak':
        print("❌ Migracja anulowana")
        return
    
    print("\n🔄 ROZPOCZYNAM FINALNĄ MIGRACJĘ...")
    print("-" * 40)
    
    # Migruj każdego pacjenta
    success_count = 0
    failed_count = 0
    
    for i, patient in enumerate(patients, 1):
        print(f"\n[{i}/{len(patients)}] {patient.get('name')} {patient.get('surname')}...")
        if migrate_patient(patient):
            success_count += 1
        else:
            failed_count += 1
    
    # Podsumowanie
    print("\n" + "=" * 50)
    print("📊 FINALNE PODSUMOWANIE MIGRACJI:")
    print(f"✅ Udanych: {success_count}")
    print(f"❌ Nieudanych: {failed_count}")
    print(f"📋 Razem: {len(patients)}")
    
    if success_count > 0:
        print(f"\n🎉 FINALNA MIGRACJA ZAKOŃCZONA!")
        print(f"👉 Sprawdź Railway: {RAILWAY_URL}")
    else:
        print(f"\n😞 Żadna migracja nie powiodła się")

if __name__ == "__main__":
    main() 