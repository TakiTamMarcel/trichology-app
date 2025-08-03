#!/usr/bin/env python3
"""
Skrypt do migracji plików z lokalnego storage na Cloudinary
Migruje wszystkie zdjęcia trichoskopii, kliniczne i dokumenty wizyt
"""

import os
import sqlite3
import json
from cloudinary_utils import upload_file_to_cloudinary, init_cloudinary
import logging

# Configure logging  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konfiguracja
LOCAL_UPLOADS_DIR = 'static/uploads'
LOCAL_DB = 'trichology.db'

def scan_local_files():
    """Skanuje lokalne pliki i zwraca listę do migracji"""
    files_to_migrate = []
    
    if not os.path.exists(LOCAL_UPLOADS_DIR):
        logger.error(f"❌ Folder {LOCAL_UPLOADS_DIR} nie istnieje!")
        return files_to_migrate
    
    for root, dirs, files in os.walk(LOCAL_UPLOADS_DIR):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.pdf', '.doc', '.docx')):
                file_path = os.path.join(root, file)
                
                # Parsuj ścieżkę: static/uploads/{type}/{patient_pesel}/{filename}
                path_parts = root.replace(LOCAL_UPLOADS_DIR, '').strip('/').split('/')
                
                if len(path_parts) >= 2:
                    file_type = path_parts[0]  # trichoscopy, clinical, visits
                    patient_pesel = path_parts[1]
                    
                    files_to_migrate.append({
                        'local_path': file_path,
                        'filename': file,
                        'type': file_type,
                        'patient_pesel': patient_pesel,
                        'relative_path': os.path.relpath(file_path, LOCAL_UPLOADS_DIR)
                    })
    
    return files_to_migrate

def get_patient_info_from_db():
    """Pobiera informacje o pacjentach z bazy danych"""
    patients = {}
    
    try:
        conn = sqlite3.connect(LOCAL_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT pesel, name, surname FROM patients')
        rows = cursor.fetchall()
        
        for row in rows:
            patients[row['pesel']] = {
                'name': row['name'],
                'surname': row['surname']
            }
            
        conn.close()
        logger.info(f"✅ Załadowano informacje o {len(patients)} pacjentach")
        
    except Exception as e:
        logger.error(f"❌ Błąd pobierania pacjentów z bazy: {str(e)}")
    
    return patients

def migrate_file_to_cloudinary(file_info):
    """Migruje pojedynczy plik na Cloudinary"""
    try:
        # Odczytaj plik
        with open(file_info['local_path'], 'rb') as f:
            file_content = f.read()
        
        # Upload na Cloudinary
        result = upload_file_to_cloudinary(
            file_content=file_content,
            filename=file_info['filename'],
            folder=file_info['type'],
            patient_pesel=file_info['patient_pesel']
        )
        
        if result['success']:
            logger.info(f"✅ Migracja udana: {file_info['filename']} -> {result['url']}")
            return {
                'success': True,
                'local_path': file_info['local_path'],
                'cloudinary_url': result['url'],
                'public_id': result['public_id'],
                'type': file_info['type'],
                'patient_pesel': file_info['patient_pesel']
            }
        else:
            logger.error(f"❌ Migracja nieudana: {file_info['filename']} - {result.get('error')}")
            return {'success': False, 'error': result.get('error')}
            
    except Exception as e:
        logger.error(f"❌ Błąd migracji {file_info['filename']}: {str(e)}")
        return {'success': False, 'error': str(e)}

def save_migration_log(migration_results):
    """Zapisuje log migracji do pliku JSON"""
    log_file = 'cloudinary_migration_log.json'
    
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(migration_results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📝 Log migracji zapisany w: {log_file}")
        
    except Exception as e:
        logger.error(f"❌ Błąd zapisywania logu: {str(e)}")

def main():
    """Główna funkcja migracji"""
    print("🚀 ROZPOCZYNAM MIGRACJĘ PLIKÓW NA CLOUDINARY")
    print("=" * 60)
    
    # Inicjalizuj Cloudinary
    if not init_cloudinary():
        print("❌ Nie można zainicjalizować Cloudinary!")
        return
    
    # Skanuj lokalne pliki
    print("\n🔍 Skanowanie lokalnych plików...")
    files_to_migrate = scan_local_files()
    
    if not files_to_migrate:
        print("❌ Nie znaleziono plików do migracji!")
        return
    
    # Pobierz informacje o pacjentach
    patients = get_patient_info_from_db()
    
    # Wyświetl podsumowanie
    print(f"\n📊 PODSUMOWANIE MIGRACJI:")
    print(f"Plików do migracji: {len(files_to_migrate)}")
    
    # Grupuj pliki według typu
    file_types = {}
    for file_info in files_to_migrate:
        file_type = file_info['type']
        if file_type not in file_types:
            file_types[file_type] = 0
        file_types[file_type] += 1
    
    for file_type, count in file_types.items():
        print(f"  - {file_type}: {count} plików")
    
    # Potwierdź migrację
    print(f"\n⚠️  UWAGA: Pliki zostaną przesłane na Cloudinary")
    confirm = input("Czy kontynuować migrację? (tak/nie): ").lower().strip()
    
    if confirm != 'tak':
        print("❌ Migracja anulowana")
        return
    
    print(f"\n🔄 ROZPOCZYNAM MIGRACJĘ...")
    print("-" * 40)
    
    # Migruj pliki
    migration_results = []
    success_count = 0
    failed_count = 0
    
    for i, file_info in enumerate(files_to_migrate, 1):
        patient_info = patients.get(file_info['patient_pesel'], {})
        patient_name = f"{patient_info.get('name', '')} {patient_info.get('surname', '')}".strip()
        
        print(f"\n[{i}/{len(files_to_migrate)}] Migracja: {file_info['filename']}")
        print(f"    Pacjent: {patient_name} (PESEL: {file_info['patient_pesel']})")
        print(f"    Typ: {file_info['type']}")
        
        result = migrate_file_to_cloudinary(file_info)
        migration_results.append(result)
        
        if result['success']:
            success_count += 1
        else:
            failed_count += 1
    
    # Zapisz log migracji
    save_migration_log(migration_results)
    
    # Podsumowanie końcowe
    print("\n" + "=" * 60)
    print("📊 PODSUMOWANIE MIGRACJI:")
    print(f"✅ Udanych migracji: {success_count}")
    print(f"❌ Nieudanych migracji: {failed_count}")
    print(f"📋 Razem plików: {len(files_to_migrate)}")
    
    if success_count > 0:
        print(f"\n🎉 Migracja zakończona! Pliki dostępne na Cloudinary")
        print(f"📝 Szczegóły w pliku: cloudinary_migration_log.json")
    else:
        print(f"\n😞 Żadna migracja nie powiodła się.")

if __name__ == "__main__":
    main() 