#!/usr/bin/env python3
import sqlite3, json, requests

# Config
LOCAL_DB = 'trichology.db'
ENDPOINT = 'https://web-production-74f1.up.railway.app/api/speed-migrate-patient'
PASSWORD = 'SPEED_MIGRATE_AUG_03'

def get_patients():
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM patients')
    patients = [dict(p) for p in cursor.fetchall()]
    conn.close()
    return patients

def clean_data(patient):
    if 'id' in patient:
        del patient['id']
    
    json_fields = ['medication_list', 'supplements_list', 'allergens', 'diseases', 'treatments',
                   'shampoo_brand', 'shampoo_type', 'shampoo_details', 'treatment_type', 
                   'treatment_duration', 'treatment_details', 'care_product_type', 
                   'care_product_name', 'care_product_dose', 'care_product_frequency',
                   'care_procedure_type', 'care_procedure_frequency', 'care_procedure_details',
                   'chronic_diseases', 'skin_conditions', 'autoimmune', 'allergies', 
                   'family_conditions', 'diet', 'styling', 'problem_description', 
                   'problem_periodicity', 'previous_procedures', 'follicles_state', 'skin_condition']
    
    for field in json_fields:
        if field in patient:
            if patient[field] is None:
                patient[field] = '[]'
            elif isinstance(patient[field], str):
                try:
                    json.loads(patient[field])
                except:
                    patient[field] = '[]'
            elif isinstance(patient[field], list):
                patient[field] = json.dumps(patient[field])
            else:
                patient[field] = '[]'
    
    # Required fields
    for field in ['name', 'surname', 'pesel', 'birthdate', 'gender']:
        if field not in patient or patient[field] is None:
            if field == 'birthdate':
                patient[field] = '1990-01-01'
            elif field == 'gender':
                patient[field] = 'male'
            else:
                patient[field] = ''
    
    return patient

def migrate_patient(patient):
    clean_data(patient)
    patient['migrate_password'] = PASSWORD
    
    try:
        response = requests.post(ENDPOINT, json=patient, headers={'Content-Type': 'application/json'})
        if response.status_code in [200, 201]:
            result = response.json()
            return result.get('success', False)
        return False
    except:
        return False

def main():
    print("🚀 SZYBKA MIGRACJA RAILWAY")
    patients = get_patients()
    print(f"📋 {len(patients)} pacjentów")
    
    success = 0
    for i, patient in enumerate(patients, 1):
        print(f"[{i}/{len(patients)}] {patient.get('name')} {patient.get('surname')}...", end="")
        if migrate_patient(patient):
            print(" ✅")
            success += 1
        else:
            print(" ❌")
    
    print(f"\n🎉 SUKCES: {success}/{len(patients)} pacjentów zmigrowanych!")

if __name__ == "__main__":
    main() 