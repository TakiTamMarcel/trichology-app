import logging
import sys
import os
import json
import traceback
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import sqlite3
from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from fastapi import File, UploadFile
from werkzeug.utils import secure_filename
import uvicorn
import base64
import requests
from bs4 import BeautifulSoup
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google_auth_oauthlib.flow import Flow
import secrets
from cloudinary_utils import upload_file_to_cloudinary, init_cloudinary, get_optimized_url

# Development mode - disable authentication for local development
DEV_MODE = os.environ.get('DEV_MODE', 'true').lower() == 'true'

# Configure logging to output to both console and file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Middleware for global error catching
@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"message": f"Internal Server Error: {str(e)}", "traceback": traceback.format_exc()}
        )

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up Jinja2 templates with url_for support
templates = Jinja2Templates(directory="test_templates")
templates.env.globals["url_for"] = lambda name, **path_params: app.url_path_for(name, **path_params) if name != "static" else f"/static/{path_params.get('filename', '')}"

# Dodanie filtru split do Jinja2
def jinja2_split(value, delimiter=','):
    """Filter do dzielenia stringów w Jinja2"""
    if value is None:
        return []
    return value.split(delimiter)

templates.env.filters["split"] = jinja2_split

# Database functions
from database import (
    init_db as db_init_db,
    save_patient as db_save_patient,
    get_patient, get_patients, update_patient_photo, search_patients,
    # Dodanie nowych importów dla płatności
    add_payment, get_patient_payments, get_payment_summary,
    add_visit as db_add_visit, get_patient_visits as db_get_patient_visits, 
    add_treatment_pricing, get_patient_treatments, update_payment_for_item,
    sync_clinic_treatments_to_billing, get_patient_visits_for_billing,
    # Dodanie nowych importów dla zarządzania zabiegami
    get_available_treatments, add_available_treatment, update_available_treatment,
    delete_available_treatment, get_treatment_price,
    # Dodanie importów dla autoryzacji
    create_user, authenticate_user, get_user_by_id, get_user_by_google_id,
    create_session, get_session_user, delete_session, cleanup_expired_sessions,
    update_user_profile, change_user_password
)

def get_db_connection():
    """
    Create a connection to the database with row factory set to sqlite3.Row
    """
    conn = sqlite3.connect('trichology.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initialize the database with required tables if they don't exist.
    Returns True if successful, False otherwise.
    """
    # Użyj funkcji z database.py
    return db_init_db()

# Słownik tłumaczeń z angielskiego na polski
TRANSLATIONS = {
    "mechanical": "Mechaniczny",
    "chemical": "Chemiczny", 
    "enzymatic": "Enzymatyczny",
    "thin": "Cienkie",
    "medium": "Średnie",
    "thick": "Grube",
    "low": "Niska",
    "medium_density": "Średnia",
    "high": "Wysoka",
    "daily": "Codziennie",
    "weekly": "Tygodniowo",
    "monthly": "Miesięcznie",
    "occasionally": "Okazjonalnie",
    "never": "Nigdy"
}

def translate_value(value):
    """Tłumaczy wartość z angielskiego na polski, używając słownika TRANSLATIONS"""
    if isinstance(value, str):
        return TRANSLATIONS.get(value, value)
    elif isinstance(value, list):
        return [translate_value(item) for item in value]
    return value

def reverse_translate_value(value):
    """Tłumaczy wartość z polskiego na angielski, używając odwróconego słownika TRANSLATIONS"""
    if not isinstance(value, str):
        return value
    
    polish_to_english = {v: k for k, v in TRANSLATIONS.items()}
    return polish_to_english.get(value, value)

# =============================================================================
# AUTHENTICATION HELPERS
# =============================================================================

def get_current_user(request: Request):
    """
    Get current authenticated user from session cookie.
    Returns user data or None if not authenticated.
    """
    # In development mode, return fake user
    if DEV_MODE:
        return {
            'id': 1,
            'email': 'dev@trichology.local',
            'first_name': 'Developer',
            'last_name': 'User',
            'role': 'trichologist',
            'is_active': 1,
            'profile_picture': None
        }
    
    try:
        # Get session token from cookie
        session_token = request.cookies.get("session_token")
        if not session_token:
            return None
        
        # Get user from session
        user = get_session_user(session_token)
        return user
        
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        return None

def require_auth(request: Request):
    """
    Dependency that requires authentication.
    Raises HTTPException if user not authenticated.
    """
    # In development mode, return fake user
    if DEV_MODE:
        return {
            'id': 1,
            'email': 'dev@trichology.local',
            'first_name': 'Developer',
            'last_name': 'User',
            'role': 'trichologist',
            'is_active': 1,
            'profile_picture': None
        }
    
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user

def require_admin(request: Request):
    """
    Dependency that requires admin role.
    Raises HTTPException if user not admin.
    """
    user = require_auth(request)
    if user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

async def optional_auth(request: Request):
    """
    Optional authentication - returns user if authenticated, None otherwise.
    Used for pages that work both with and without authentication.
    """
    return get_current_user(request)

def get_patient(pesel):
    """
    Get patient data by PESEL.
    Returns patient data or None if not found.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM patients WHERE pesel = ?', (pesel,))
        row = cursor.fetchone()
        
        if row is None:
            print(f"No patient found with PESEL {pesel}")
            return None
            
        # Convert row to dict
        column_names = [description[0] for description in cursor.description]
        patient_data = dict(zip(column_names, row))
        
        # Add first_name and last_name fields, mapped from name and surname
        if 'name' in patient_data:
            patient_data['first_name'] = patient_data['name']
        if 'surname' in patient_data:
            patient_data['last_name'] = patient_data['surname']
        # Map birthdate back to birth_date for frontend
        if 'birthdate' in patient_data:
            patient_data['birth_date'] = patient_data['birthdate']
        
        # Process JSON fields - deserializacja stringów JSON na obiekty Pythona
        json_fields = ['medication_list', 'supplements_list', 'allergens', 'diseases', 'treatments', 'styling', 
                    'problem_description', 'problem_periodicity', 'previous_procedures', 'care_product_type', 
                    'care_product_name', 'care_product_dose', 'care_product_frequency', 'care_procedure_type', 
                    'care_procedure_frequency', 'care_procedure_details', 'treatment_type', 'treatment_duration', 
                    'treatment_details', 'shampoo_type', 'shampoo_brand', 'shampoo_details', 'diet',
                    'chronic_diseases', 'skin_conditions', 'autoimmune', 'allergies', 'family_conditions',
                    'follicles_state', 'skin_condition', 'problem_description']
        
        print("Przetwarzanie pól JSON w get_patient:")
        for field in json_fields:
            if field in patient_data and patient_data[field]:
                print(f"  - {field} przed przetworzeniem: {patient_data[field]}")
                # Sprawdź, czy pole jest już listą (nie wymaga deserializacji)
                if isinstance(patient_data[field], list):
                    print(f"  - {field} już jest listą, pomijanie deserializacji")
                    continue
                # Jeśli to string, deserializuj go
                try:
                    patient_data[field] = json.loads(patient_data[field])
                    print(f"  - {field} po przetworzeniu: {patient_data[field]}")
                    
                    # Specyficzne debugowanie dla diety
                    if field == 'diet':
                        print(f"  - wartości diety po przetworzeniu: {patient_data[field]}")
                        if isinstance(patient_data[field], list):
                            print(f"  - liczba elementów diety: {len(patient_data[field])}")
                            for item in patient_data[field]:
                                print(f"  - element diety: {item}")
                
                except json.JSONDecodeError as e:
                    print(f"Błąd podczas dekodowania JSON dla pola {field}: {str(e)}")
                    patient_data[field] = []
            else:
                print(f"  - {field} nie istnieje lub jest puste w danych pacjenta")
                patient_data[field] = []
        
        # Dodatkowe sprawdzenie dla schedule
        if 'schedule' in patient_data:
            if isinstance(patient_data['schedule'], str) and patient_data['schedule']:
                try:
                    patient_data['schedule'] = json.loads(patient_data['schedule'])
                except json.JSONDecodeError:
                    patient_data['schedule'] = {}
            print(f"Schedule po przetworzeniu: {patient_data['schedule']}")
            
        # Dodajemy mapowanie dla szablonów
        if 'medication_list' in patient_data:
            patient_data['medications'] = patient_data['medication_list']
        if 'supplements_list' in patient_data:
            patient_data['supplements'] = patient_data['supplements_list']
        
        # Przetłumacz wartości z angielskiego na polski
        if 'allergens' in patient_data and patient_data['allergens']:
            if isinstance(patient_data['allergens'], list):
                # Tłumaczenie listy alergii
                patient_data['allergies_display'] = [translate_value(allergy) for allergy in patient_data['allergens']]
            else:
                patient_data['allergies_display'] = patient_data['allergens']
        
        # Popraw wartości specyficznych pól - peeling
        if 'peeling_type' in patient_data and patient_data['peeling_type']:
            # Zapisz oryginalną wartość angielską
            original_value = patient_data['peeling_type']
            # Dodaj pole do wyświetlania z tłumaczeniem
            patient_data['peeling_type_display'] = translate_value(original_value)
            print(f"Tłumaczenie peeling_type: {original_value} -> {patient_data['peeling_type_display']}")
            # NIE tłumacz głównego pola, aby działały porównania w formularzu
        if 'peeling_frequency' in patient_data and patient_data['peeling_frequency']:
            # Zapisz oryginalną wartość angielską
            original_value = patient_data['peeling_frequency']
            # Dodaj pole do wyświetlania z tłumaczeniem
            patient_data['peeling_frequency_display'] = translate_value(original_value)
            print(f"Tłumaczenie peeling_frequency: {original_value} -> {patient_data['peeling_frequency_display']}")
            # NIE tłumacz głównego pola, aby działały porównania w formularzu
        
        # Dodanie obsługi dla pól coloring_type i coloring_frequency
        if 'coloring_type' in patient_data and patient_data['coloring_type']:
            # Zapisz oryginalną wartość angielską
            original_value = patient_data['coloring_type']
            # Dodaj pole do wyświetlania z tłumaczeniem
            patient_data['coloring_type_display'] = translate_value(original_value)
            print(f"Tłumaczenie coloring_type: {original_value} -> {patient_data['coloring_type_display']}")
            # NIE tłumacz głównego pola, aby działały porównania w formularzu
        if 'coloring_frequency' in patient_data and patient_data['coloring_frequency']:
            # Zapisz oryginalną wartość angielską
            original_value = patient_data['coloring_frequency']
            # Dodaj pole do wyświetlania z tłumaczeniem
            patient_data['coloring_frequency_display'] = translate_value(original_value)
            print(f"Tłumaczenie coloring_frequency: {original_value} -> {patient_data['coloring_frequency_display']}")
            # NIE tłumacz głównego pola, aby działały porównania w formularzu
        
        # Obsługa tłumaczeń dla pola styling (stylizacji)
        if 'styling' in patient_data and patient_data['styling'] and isinstance(patient_data['styling'], list):
            # Zastąp stare nazwy nowymi dla zachowania kompatybilności
            updated_styling = []
            for style in patient_data['styling']:
                # Konwersja starszej nazwy flat_iron na straightener
                if style == 'flat_iron':
                    updated_styling.append('straightener')
                    print(f"Zastąpiono starszą nazwę 'flat_iron' na 'straightener'")
                else:
                    updated_styling.append(style)
            
            # Aktualizacja listy stylizacji
            patient_data['styling'] = updated_styling
            
            # Tworzenie listy tłumaczeń na podstawie zaktualizowanych wartości angielskich
            styling_translations = []
            for style in patient_data['styling']:
                translated = translate_value(style)
                styling_translations.append(translated)
                print(f"Tłumaczenie styling: {style} -> {translated}")
            # Dodanie pola z tłumaczeniami
            patient_data['styling_display'] = styling_translations
            # NIE tłumacz głównego pola styling, aby działały porównania w formularzu
        
        # Obsługa tłumaczeń dla pola problem_description (charakterystyka problemu)
        if 'problem_description' in patient_data and patient_data['problem_description'] and isinstance(patient_data['problem_description'], list):
            # Tworzenie listy tłumaczeń na podstawie oryginalnych wartości angielskich
            problem_desc_translations = []
            for problem in patient_data['problem_description']:
                translated = translate_value(problem)
                problem_desc_translations.append(translated)
                print(f"Tłumaczenie problem_description: {problem} -> {translated}")
            # Dodanie pola z tłumaczeniami
            patient_data['problem_description_display'] = problem_desc_translations
            # NIE tłumacz głównego pola problem_description, aby działały porównania w formularzu
        
        # Obsługa tłumaczeń dla pola problem_periodicity (okresowość problemów)
        if 'problem_periodicity' in patient_data and patient_data['problem_periodicity'] and isinstance(patient_data['problem_periodicity'], list):
            # Tworzenie listy tłumaczeń na podstawie oryginalnych wartości angielskich
            problem_period_translations = []
            for period in patient_data['problem_periodicity']:
                translated = translate_value(period)
                problem_period_translations.append(translated)
                print(f"Tłumaczenie problem_periodicity: {period} -> {translated}")
            # Dodanie pola z tłumaczeniami
            patient_data['problem_periodicity_display'] = problem_period_translations
            # NIE tłumacz głównego pola problem_periodicity, aby działały porównania w formularzu
        
        # Obsługa tłumaczeń dla pola previous_procedures (zabiegi na skórę głowy)
        if 'previous_procedures' in patient_data and patient_data['previous_procedures'] and isinstance(patient_data['previous_procedures'], list):
            # Tworzenie listy tłumaczeń na podstawie oryginalnych wartości angielskich
            previous_proc_translations = []
            for procedure in patient_data['previous_procedures']:
                translated = translate_value(procedure)
                previous_proc_translations.append(translated)
                print(f"Tłumaczenie previous_procedures: {procedure} -> {translated}")
            # Dodanie pola z tłumaczeniami
            patient_data['previous_procedures_display'] = previous_proc_translations
            # NIE tłumacz głównego pola previous_procedures, aby działały porównania w formularzu
        
        # Obsługa tłumaczeń dla pola follicles_state (stan mieszków włosowych)
        if 'follicles_state' in patient_data and patient_data['follicles_state'] and isinstance(patient_data['follicles_state'], list):
            # Tworzenie listy tłumaczeń na podstawie oryginalnych wartości angielskich
            follicles_state_translations = []
            for state in patient_data['follicles_state']:
                translated = translate_value(state)
                follicles_state_translations.append(translated)
                print(f"Tłumaczenie follicles_state: {state} -> {translated}")
            # Dodanie pola z tłumaczeniami
            patient_data['follicles_state_display'] = follicles_state_translations
            # NIE tłumacz głównego pola follicles_state, aby działały porównania w formularzu
        
        # Przetwarzanie pola skin_condition
        if 'skin_condition' in patient_data and patient_data['skin_condition']:
            try:
                # Jeśli to string JSON, próbujemy go sparsować
                if isinstance(patient_data['skin_condition'], str) and patient_data['skin_condition'].startswith('['):
                    try:
                        patient_data['skin_condition'] = json.loads(patient_data['skin_condition'])
                        print(f"Sparsowano skin_condition z JSON: {patient_data['skin_condition']}")
                    except json.JSONDecodeError as e:
                        print(f"Błąd parsowania JSON dla skin_condition: {e}")
                        # Jeśli nie można sparsować, zachowujemy jako jest
                
                # Teraz sprawdzamy, czy mamy listę do przetłumaczenia
                if isinstance(patient_data['skin_condition'], list):
                    # Tłumaczenie listy warunków skóry
                    skin_condition_translations = []
                    for condition in patient_data['skin_condition']:
                        translated = translate_value(condition)
                        skin_condition_translations.append(translated)
                        print(f"Tłumaczenie skin_condition: {condition} -> {translated}")
                    
                    # Dodanie pola z tłumaczeniami
                    patient_data['skin_condition_display'] = skin_condition_translations
                    # NIE tłumacz głównego pola skin_condition, aby działały porównania w formularzu
                else:
                    # Jeśli to nadal nie jest lista, traktujemy jako pojedynczą wartość
                    print(f"skin_condition nie jest listą: {patient_data['skin_condition']}, typ: {type(patient_data['skin_condition'])}")
                    patient_data['skin_condition_display'] = translate_value(patient_data['skin_condition'])
            except Exception as e:
                print(f"Nieoczekiwany błąd podczas przetwarzania skin_condition: {e}")
                patient_data['skin_condition_display'] = patient_data['skin_condition']
        
        # Tworzenie struktury shampoos dla szablonu - teraz z poprawną obsługą JSON
        if 'shampoo_type' in patient_data and 'shampoo_brand' in patient_data and 'shampoo_details' in patient_data:
            shampoos = []
            
            # Upewnij się, że wszystkie pola są listami
            shampoo_types = patient_data['shampoo_type'] if isinstance(patient_data['shampoo_type'], list) else []
            shampoo_brands = patient_data['shampoo_brand'] if isinstance(patient_data['shampoo_brand'], list) else []
            shampoo_details = patient_data['shampoo_details'] if isinstance(patient_data['shampoo_details'], list) else []
            
            # Określenie maksymalnej długości list
            max_length = max(len(shampoo_types), len(shampoo_brands), len(shampoo_details))
            
            # Tworzenie listy szamponów
            for i in range(max_length):
                shampoo_type = shampoo_types[i] if i < len(shampoo_types) else ''
                shampoo_brand = shampoo_brands[i] if i < len(shampoo_brands) else ''
                shampoo_detail = shampoo_details[i] if i < len(shampoo_details) else ''
                
                shampoo = {
                    'type': translate_value(shampoo_type),
                    'brand': shampoo_brand,
                    'details': shampoo_detail
                }
                shampoos.append(shampoo)
            
            patient_data['shampoos'] = shampoos
        
        conn.close()
        return patient_data
        
    except sqlite3.Error as e:
        print(f"SQLite error in get_patient: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None
    except Exception as e:
        print(f"Unexpected error in get_patient: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None

def get_patients():
    """
    Get all patients.
    Returns a list of patients or empty list if none found.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.pesel, p.name, p.surname, p.phone, p.email, MAX(v.visit_date) as last_visit
            FROM patients p
            LEFT JOIN visits v ON p.pesel = v.pesel
            GROUP BY p.pesel
            ORDER BY p.surname, p.name
        ''')
        
        rows = cursor.fetchall()
        
        patients = []
        for row in rows:
            # Używamy nazw, które są zgodne z frontendem (first_name, last_name)
            patient = {
                'pesel': row[0],
                'first_name': row[1],  # 'name' w bazie -> 'first_name' dla frontendu
                'last_name': row[2],   # 'surname' w bazie -> 'last_name' dla frontendu
                'phone': row[3],
                'email': row[4],
                'last_visit': row[5]   # Dodajemy ostatnią wizytę z LEFT JOIN
            }
            patients.append(patient)
        
        conn.close()
        return patients
        
    except sqlite3.Error as e:
        print(f"SQLite error in get_patients: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return []
    except Exception as e:
        print(f"Unexpected error in get_patients: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return []

def update_patient_photo(pesel, photo_path):
    """
    Update patient photo path.
    Returns True if successful, False otherwise.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE patients SET photo = ? WHERE pesel = ?', (photo_path, pesel))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        
        return success
        
    except sqlite3.Error as e:
        print(f"SQLite error in update_patient_photo: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return False
    except Exception as e:
        print(f"Unexpected error in update_patient_photo: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return False

def search_patients(query):
    """
    Search for patients by name, surname, or PESEL.
    Returns a list of matching patients or empty list if none found.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        search_pattern = f"%{query}%"
        
        # Zapytanie się nie zmienia - szukamy po kolumnach name i surname w bazie
        cursor.execute('''
            SELECT p.pesel, p.name, p.surname, p.phone, p.email, MAX(v.visit_date) as last_visit
            FROM patients p
            LEFT JOIN visits v ON p.pesel = v.pesel
            WHERE p.pesel LIKE ? OR p.name LIKE ? OR p.surname LIKE ?
            GROUP BY p.pesel
            ORDER BY p.surname, p.name
        ''', (search_pattern, search_pattern, search_pattern))
        
        rows = cursor.fetchall()
        
        patients = []
        for row in rows:
            # Mapujemy nazwy kolumn na te używane przez frontend
            patient = {
                'pesel': row[0],
                'first_name': row[1],  # 'name' w bazie -> 'first_name' dla frontendu
                'last_name': row[2],   # 'surname' w bazie -> 'last_name' dla frontendu
                'phone': row[3],
                'email': row[4],
                'last_visit': row[5]  # Dodajemy ostatnią wizytę z LEFT JOIN
            }
            patients.append(patient)
        
        conn.close()
        return patients
        
    except sqlite3.Error as e:
        print(f"SQLite error in search_patients: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return []
    except Exception as e:
        print(f"Unexpected error in search_patients: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return []

def save_patient(data):
    """
    Save patient data to the database.
    Returns a dict with success/error information.
    """
    try:
        print("\n=== Starting save_patient function ===")
        print(f"Received data keys: {list(data.keys())}")
        
        # Create a copy of data to avoid modifying the original
        patient_data = data.copy()
        
        # Map frontend field names to database column names - NAJPIERW
        if 'first_name' in patient_data:
            patient_data['name'] = patient_data.pop('first_name')
            print(f"Mapped first_name to name: {patient_data['name']}")
        if 'last_name' in patient_data:
            patient_data['surname'] = patient_data.pop('last_name')
            print(f"Mapped last_name to surname: {patient_data['surname']}")
        if 'birth_date' in patient_data:
            patient_data['birthdate'] = patient_data.pop('birth_date')
            print(f"Mapped birth_date to birthdate: {patient_data['birthdate']}")
        
        # Process checkbox arrays (convert to JSON strings)
        checkbox_fields = ['chronic_diseases', 'allergies', 'habits', 'diet', 'physical_activity']
        for field in checkbox_fields:
            if field in patient_data:
                if isinstance(patient_data[field], list):
                    patient_data[field] = json.dumps(patient_data[field], ensure_ascii=False)
                elif not isinstance(patient_data[field], str):
                    patient_data[field] = json.dumps([], ensure_ascii=False)
        
        # Process range fields (convert to strings)
        range_fields = ['work_stress', 'life_stress', 'sleep_hours']
        for field in range_fields:
            if field in patient_data:
                patient_data[field] = str(patient_data[field])
        
        # Process text fields (ensure they're strings) - DODAJ birthdate do listy
        text_fields = ['pesel', 'birthdate', 'address', 'occupation', 'chronic_diseases_other', 'surgeries', 
                      'other_conditions', 'scalp_history', 'trichology_treatments', 'allergies_details',
                      'allergic_reactions', 'cosmetic_allergies', 'habits_details', 'diet_details',
                      'activity_details', 'sleep_quality', 'family_hair_loss', 'family_hair_loss_details',
                      'family_genetic_diseases', 'family_skin_diseases', 'additional_notes', 'email', 'phone']
        for field in text_fields:
            if field in patient_data:
                if patient_data[field] is None:
                    patient_data[field] = ''
                else:
                    patient_data[field] = str(patient_data[field])
        
        # Check required fields
        required_fields = ['name', 'surname', 'pesel']
        missing_fields = [field for field in required_fields if not patient_data.get(field)]
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            print(error_msg)
            return {'success': False, 'error': error_msg}
        
        # Inicjalizacja połączenia z bazą danych na początku funkcji
        conn = get_db_connection()
        
        # Obsługa pola care_procedure_count
        if 'care_procedure_count' in patient_data:
            print(f"CARE_PROCEDURE_COUNT przed przetwarzaniem: {patient_data['care_procedure_count']}, typ: {type(patient_data['care_procedure_count'])}")
            
            # Jeśli care_procedure_count jest już listą, przekształć go na string JSON
            if isinstance(patient_data['care_procedure_count'], list):
                patient_data['care_procedure_count'] = json.dumps(patient_data['care_procedure_count'], ensure_ascii=False)
                print(f"CARE_PROCEDURE_COUNT po konwersji na JSON string: {patient_data['care_procedure_count']}")
            elif isinstance(patient_data['care_procedure_count'], str):
                # Jeśli to string, sprawdź czy jest poprawnym JSON
                try:
                    # Walidacja czy to poprawny JSON
                    json.loads(patient_data['care_procedure_count'])
                    print("CARE_PROCEDURE_COUNT jest już poprawnym stringiem JSON")
                except json.JSONDecodeError:
                    print("CARE_PROCEDURE_COUNT nie jest poprawnym JSON, ustawiam na pusty obiekt")
                    patient_data['care_procedure_count'] = '[]'
            else:
                print(f"CARE_PROCEDURE_COUNT ma nieprawidłowy typ: {type(patient_data['care_procedure_count'])}, ustawiam na pusty obiekt")
                patient_data['care_procedure_count'] = '[]'
        else:
            print("CARE_PROCEDURE_COUNT nie został przekazany w danych")
            patient_data['care_procedure_count'] = '[]'
        
        # Sprawdzenie danych harmonogramu
        if 'schedule' in patient_data:
            print(f"SCHEDULE przed przetwarzaniem: {patient_data['schedule']}, typ: {type(patient_data['schedule'])}")
            
            # Jeśli schedule jest już słownikiem, przekształć go na string JSON
            if isinstance(patient_data['schedule'], dict):
                patient_data['schedule'] = json.dumps(patient_data['schedule'], ensure_ascii=False)
                print(f"SCHEDULE po konwersji na JSON string: {patient_data['schedule']}")
            elif isinstance(patient_data['schedule'], str):
                # Jeśli to string, sprawdź czy jest poprawnym JSON
                try:
                    # Walidacja czy to poprawny JSON
                    json.loads(patient_data['schedule'])
                    print("SCHEDULE jest już poprawnym stringiem JSON")
                except json.JSONDecodeError:
                    print("SCHEDULE nie jest poprawnym JSON, ustawiam na pusty obiekt")
                    patient_data['schedule'] = '{}'
            else:
                print(f"SCHEDULE ma nieprawidłowy typ: {type(patient_data['schedule'])}, ustawiam na pusty obiekt")
                patient_data['schedule'] = '{}'
        else:
            print("SCHEDULE nie został przekazany w danych")
            patient_data['schedule'] = '{}'
        
        # Sprawdź skin_condition
        if 'skin_condition' in data:
            print(f"SKIN CONDITION przed przetwarzaniem: {data['skin_condition']}, typ: {type(data['skin_condition'])}")
            
            # Konwersja listy oddzielonej przecinkami na listę JSON
            if data['skin_condition'] and data['skin_condition'].strip():
                # Sprawdź czy to już jest lista Pythona
                if isinstance(data['skin_condition'], list):
                    patient_data['skin_condition'] = json.dumps(data['skin_condition'], ensure_ascii=False)
                    print(f"SKIN CONDITION to lista, przekonwertowano do JSON: {patient_data['skin_condition']}")
                elif isinstance(data['skin_condition'], str):
                    try:
                        # Próba parsowania jako JSON
                        json_obj = json.loads(data['skin_condition'])
                        patient_data['skin_condition'] = json.dumps(json_obj, ensure_ascii=False)
                        print(f"SKIN CONDITION to już poprawny JSON string")
                    except json.JSONDecodeError:
                        # Podziel po przecinkach i usuń białe znaki
                        skin_condition_values = [value.strip() for value in data['skin_condition'].split(',') if value.strip()]
                        # Konwertuj na format JSON
                        patient_data['skin_condition'] = json.dumps(skin_condition_values, ensure_ascii=False)
                        print(f"SKIN CONDITION po konwersji na JSON: {patient_data['skin_condition']}")
            else:
                patient_data['skin_condition'] = '[]'
                print("SKIN CONDITION ustawione na pustą tablicę '[]'")
        else:
            print("SKIN CONDITION DATA: Not provided in request")
            patient_data['skin_condition'] = '[]'
        
        # Debug problematic fields
        print(f"Peeling type before processing: {patient_data.get('peeling_type', 'NOT PROVIDED')}, type: {type(patient_data.get('peeling_type', None))}")
        print(f"Peeling frequency before processing: {patient_data.get('peeling_frequency', 'NOT PROVIDED')}, type: {type(patient_data.get('peeling_frequency', None))}")
        
        # Process shampoo data
        shampoo_fields = ['shampoo_name', 'shampoo_frequency', 'shampoo_brand']
        for field in shampoo_fields:
            if field in patient_data and (patient_data[field] is None or patient_data[field] == 'null'):
                patient_data[field] = ''
                print(f"Set {field} from None/null to empty string")
                
        # Process peeling data
        if 'peeling_type' in patient_data:
            if patient_data['peeling_type'] is None or patient_data['peeling_type'] == 'null':
                patient_data['peeling_type'] = ''
                print("Set peeling_type from None/null to empty string")
            else:
                # Mapowanie odwrotne z polskiego na angielski
                original_value = patient_data['peeling_type']
                patient_data['peeling_type'] = reverse_translate_value(patient_data['peeling_type'])
                if original_value != patient_data['peeling_type']:
                    print(f"Converting peeling_type from Polish '{original_value}' to English '{patient_data['peeling_type']}'")
            print(f"Final peeling_type value for saving: {patient_data['peeling_type']}")
        else:
            patient_data['peeling_type'] = ''
            print("Added missing peeling_type field with empty string")
        
        if 'peeling_frequency' in patient_data:
            if patient_data['peeling_frequency'] is None or patient_data['peeling_frequency'] == 'null':
                patient_data['peeling_frequency'] = ''
                print("Set peeling_frequency from None/null to empty string")
            else:
                # Mapowanie odwrotne z polskiego na angielski
                original_value = patient_data['peeling_frequency']
                patient_data['peeling_frequency'] = reverse_translate_value(patient_data['peeling_frequency'])
                if original_value != patient_data['peeling_frequency']:
                    print(f"Converting peeling_frequency from Polish '{original_value}' to English '{patient_data['peeling_frequency']}'")
            print(f"Final peeling_frequency value for saving: {patient_data['peeling_frequency']}")
        else:
            patient_data['peeling_frequency'] = ''
            print("Added missing peeling_frequency field with empty string")
            
        # Process coloring data
        if 'coloring_type' in patient_data:
            if patient_data['coloring_type'] is None or patient_data['coloring_type'] == 'null':
                patient_data['coloring_type'] = ''
                print("Set coloring_type from None/null to empty string")
            else:
                # Mapowanie odwrotne z polskiego na angielski
                original_value = patient_data['coloring_type']
                patient_data['coloring_type'] = reverse_translate_value(patient_data['coloring_type'])
                if original_value != patient_data['coloring_type']:
                    print(f"Converting coloring_type from Polish '{original_value}' to English '{patient_data['coloring_type']}'")
            print(f"Final coloring_type value for saving: {patient_data['coloring_type']}")
        else:
            patient_data['coloring_type'] = ''
            print("Added missing coloring_type field with empty string")
            
        if 'coloring_frequency' in patient_data:
            if patient_data['coloring_frequency'] is None or patient_data['coloring_frequency'] == 'null':
                patient_data['coloring_frequency'] = ''
                print("Set coloring_frequency from None/null to empty string")
            else:
                # Mapowanie odwrotne z polskiego na angielski
                original_value = patient_data['coloring_frequency']
                patient_data['coloring_frequency'] = reverse_translate_value(patient_data['coloring_frequency'])
                if original_value != patient_data['coloring_frequency']:
                    print(f"Converting coloring_frequency from Polish '{original_value}' to English '{patient_data['coloring_frequency']}'")
            print(f"Final coloring_frequency value for saving: {patient_data['coloring_frequency']}")
        else:
            patient_data['coloring_frequency'] = ''
            print("Added missing coloring_frequency field with empty string")
        
        # Process hair density and thickness data
        if 'hair_density' in patient_data:
            if patient_data['hair_density'] is None or patient_data['hair_density'] == 'null':
                patient_data['hair_density'] = ''
                print("Set hair_density from None/null to empty string")
        else:
            patient_data['hair_density'] = ''
            print("Added missing hair_density field with empty string")
            
        if 'hair_thickness' in patient_data:
            if patient_data['hair_thickness'] is None or patient_data['hair_thickness'] == 'null':
                patient_data['hair_thickness'] = ''
                print("Set hair_thickness from None/null to empty string")
        else:
            patient_data['hair_thickness'] = ''
            print("Added missing hair_thickness field with empty string")
        
        print(f"Peeling type after processing: {patient_data.get('peeling_type', 'NOT PROVIDED')}")
        print(f"Peeling frequency after processing: {patient_data.get('peeling_frequency', 'NOT PROVIDED')}")
        print(f"Hair density after processing: {patient_data.get('hair_density', 'NOT PROVIDED')}")
        print(f"Hair thickness after processing: {patient_data.get('hair_thickness', 'NOT PROVIDED')}")
        
        # Obsługa konwersji 'straightener' na 'flat_iron' dla kompatybilności wstecznej
        if 'styling' in patient_data and isinstance(patient_data['styling'], list):
            print(f"Przetwarzanie pola styling przed zapisem: {patient_data['styling']}")
            # Sprawdź czy w tablicy styling znajduje się 'straightener' i zastąp go 'flat_iron'
            for i, style in enumerate(patient_data['styling']):
                if style == 'straightener':
                    patient_data['styling'][i] = 'flat_iron'
                    print(f"Zastąpiono 'straightener' na 'flat_iron' dla kompatybilności wstecznej")
        
        # Process JSON fields - converts string lists like "['a', 'b']" to proper JSON
        json_fields = ['medication_list', 'supplements_list', 'allergens', 'diseases', 'treatments', 
                    'chronic_diseases', 'skin_conditions', 'autoimmune', 'allergies', 'family_conditions', 
                    'diet', 'styling', 'problem_description', 'problem_periodicity', 'previous_procedures', 
                    'follicles_state', 
                    'shampoo_brand', 'shampoo_type', 'shampoo_details', 
                    'treatment_type', 'treatment_duration', 'treatment_details',
                    'care_product_type', 'care_product_name', 'care_product_dose', 'care_product_frequency',
                    'care_procedure_type', 'care_procedure_frequency', 'care_procedure_details',
                    'skin_condition', 'care_procedure_count', 'hair_styling', 'habits'
        ]
        
        for field in json_fields:
            if field in patient_data:
                print(f"Processing JSON field: {field}")
                
                # Specjalne logowanie dla pola diet
                if field == 'diet':
                    print(f"DIET przed przetworzeniem: {patient_data[field]}, typ: {type(patient_data[field])}")
                
                # Sprawdź czy pole już jest listą lub słownikiem
                if isinstance(patient_data[field], (list, dict)):
                    # Konwertujemy listę lub słownik na string JSON
                    patient_data[field] = json.dumps(patient_data[field], ensure_ascii=False)
                    if field == 'diet':
                        print(f"DIET po przetworzeniu JSON: {patient_data[field]}")
                elif isinstance(patient_data[field], str):
                    # Jeśli to już string, sprawdzamy czy to poprawny JSON
                    try:
                        # Próbujemy przekonwertować string na obiekt Pythona
                        json_obj = json.loads(patient_data[field])
                        # Konwertujemy z powrotem na string JSON przed zapisem do bazy
                        patient_data[field] = json.dumps(json_obj, ensure_ascii=False)
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON for field {field}: {str(e)}")
                        patient_data[field] = '[]'
                else:
                    patient_data[field] = '[]'
                
                # Log after processing
                if field == 'skin_condition':
                    print(f"SKIN CONDITION po przetworzeniu JSON: {patient_data[field]}")
                elif field == 'diet':
                    print(f"DIET po przetworzeniu JSON: {patient_data[field]}")
        
        # Process boolean fields (checkbox yes/no)
        boolean_fields = ['uses_peeling', 'uses_minoxidil']
        for field in boolean_fields:
            if field in patient_data:
                # Convert checkbox value to boolean
                patient_data[field] = 1 if patient_data[field] == 'yes' else 0
                print(f"Set {field} to boolean: {patient_data[field]}")
            else:
                patient_data[field] = 0
                print(f"Set missing {field} to 0")

        # Process text fields
        text_fields = ['name', 'surname', 'pesel', 'phone', 'email', 'birthdate', 'gender', 'height', 'weight',
                      'current_shampoo', 'peeling_details', 'minoxidil_details', 'styling_details', 'other_treatments']
        for field in text_fields:
            if field in patient_data:
                if patient_data[field] is None:
                    patient_data[field] = ''
                    print(f"Set {field} from None to empty string")
                # Ensure it's a string
                patient_data[field] = str(patient_data[field])
        
        # Add creation timestamp
        patient_data['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Remove fields that should be skipped (including array fields with [])
        fields_to_skip = ['csrfmiddlewaretoken', 'medication_name', 'medication_dose', 'medication_schedule', 
                         'supplement_name', 'supplement_dose', 'supplement_schedule',
                         'medication_name[]', 'medication_dose[]', 'medication_schedule[]',
                         'supplement_name[]', 'supplement_dose[]', 'supplement_schedule[]']

        # Przetwarzanie danych leków i suplementów
        if 'medication_list' in patient_data:
            if isinstance(patient_data['medication_list'], list):
                patient_data['medication_list'] = json.dumps(patient_data['medication_list'], ensure_ascii=False)
                print(f"Przekonwertowano medication_list na JSON: {patient_data['medication_list']}")
            elif isinstance(patient_data['medication_list'], str):
                print(f"medication_list już jest stringiem: {patient_data['medication_list']}")
        else:
            patient_data['medication_list'] = '[]'
            print("Ustawiono pustą medication_list")

        if 'supplements_list' in patient_data:
            if isinstance(patient_data['supplements_list'], list):
                patient_data['supplements_list'] = json.dumps(patient_data['supplements_list'], ensure_ascii=False)
                print(f"Przekonwertowano supplements_list na JSON: {patient_data['supplements_list']}")
            elif isinstance(patient_data['supplements_list'], str):
                print(f"supplements_list już jest stringiem: {patient_data['supplements_list']}")
        else:
            patient_data['supplements_list'] = '[]'
            print("Ustawiono pustą supplements_list")

        # Przetwarzanie danych szamponów jako struktury shampoos
        print("Przetwarzanie danych szamponów")
        if all(field in patient_data for field in ['shampoo_type', 'shampoo_brand', 'shampoo_details']):
            # Sprawdzamy i konwertujemy pola szamponów na listy, jeśli są stringami JSON
            for field in ['shampoo_type', 'shampoo_brand', 'shampoo_details']:
                if isinstance(patient_data[field], str):
                    try:
                        # Próba konwersji stringa JSON na listę
                        patient_data[field] = json.loads(patient_data[field])
                        print(f"Przekonwertowano {field} z JSON string na listę: {patient_data[field]}")
                    except json.JSONDecodeError:
                        # Jeśli to nie jest poprawny JSON, traktuj jako pojedynczą wartość
                        if patient_data[field].strip():
                            patient_data[field] = [patient_data[field].strip()]
                        else:
                            patient_data[field] = []
                        print(f"Pole {field} nie jest poprawnym JSON, utworzono listę: {patient_data[field]}")
                elif not isinstance(patient_data[field], list):
                    patient_data[field] = []
                    print(f"Pole {field} nie jest ani stringiem, ani listą, utworzono pustą listę")
            
            # Teraz wszystkie pola powinny być listami
            shampoo_types = patient_data['shampoo_type']
            shampoo_brands = patient_data['shampoo_brand'] 
            shampoo_details = patient_data['shampoo_details']
            
            # Iteruj po najdłuższej z list, aby nie przeoczyć żadnych danych
            max_length = max(len(shampoo_types), len(shampoo_brands), len(shampoo_details))
            
            if max_length > 0:
                print(f"Znaleziono {max_length} pozycji szamponów do przetworzenia")
                for i in range(max_length):
                    shampoo_type = shampoo_types[i] if i < len(shampoo_types) else ""
                    shampoo_brand = shampoo_brands[i] if i < len(shampoo_brands) else ""
                    shampoo_detail = shampoo_details[i] if i < len(shampoo_details) else ""
                    print(f"Szampon {i+1}: Rodzaj: {shampoo_type}, Marka: {shampoo_brand}, Szczegóły: {shampoo_detail}")
                
                # Konwertuj listy z powrotem na stringi JSON przed zapisem do bazy
                patient_data['shampoo_type'] = json.dumps(shampoo_types, ensure_ascii=False)
                patient_data['shampoo_brand'] = json.dumps(shampoo_brands, ensure_ascii=False)
                patient_data['shampoo_details'] = json.dumps(shampoo_details, ensure_ascii=False)
                print("Przekonwertowano pola szamponów z powrotem na stringi JSON")
            else:
                print("Nie znaleziono żadnych danych szamponów")
                # Ustaw puste tablice JSON
                patient_data['shampoo_type'] = '[]'
                patient_data['shampoo_brand'] = '[]'
                patient_data['shampoo_details'] = '[]'
        else:
            print("Brak wszystkich wymaganych pól szamponów")
            # Ustaw brakujące pola jako puste tablice JSON
            for field in ['shampoo_type', 'shampoo_brand', 'shampoo_details']:
                if field not in patient_data or not patient_data[field]:
                    patient_data[field] = '[]'
                    print(f"Ustawiono brakujące pole {field} jako pustą tablicę JSON")

        for field in fields_to_skip:
            if field in patient_data:
                print(f"Removed field: {field}")
                del patient_data[field]
        
        # Upewnij się, że care_procedure_count jest przetworzony jako JSON string
        if 'care_procedure_count' in patient_data and isinstance(patient_data['care_procedure_count'], list):
            patient_data['care_procedure_count'] = json.dumps(patient_data['care_procedure_count'], ensure_ascii=False)
            print(f"Skonwertowano care_procedure_count na format JSON: {patient_data['care_procedure_count']}")
        
        # Utwórz połączenie z bazą danych
        conn = get_db_connection()
        
        try:
            # Get all column names from the database schema
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(patients)")
            columns = [row[1] for row in cursor.fetchall()]
        
        except sqlite3.Error as e:
            print(f"SQLite error: {str(e)}")
            return {'success': False, 'error': f'Database error: {str(e)}'}
        except Exception as e:
            print(f"General error: {str(e)}")
            return {'success': False, 'error': f'Unexpected error: {str(e)}'}
        
        # Prepare the SQL query
        columns = ', '.join(patient_data.keys())
        placeholders = ', '.join(['?' for _ in patient_data])
        values = tuple(patient_data.values())
        
        # Use INSERT OR REPLACE to handle both new patients and updates
        query = f"""
        INSERT OR REPLACE INTO patients ({columns})
        VALUES ({placeholders})
        """
        
        print(f"Executing SQL query: {query}")
        print(f"With values length: {len(values)}")
        
        # Sprawdźmy czy liczba kolumn i placeholderów się zgadza
        if len(patient_data.keys()) != len(values):
            print(f"ERROR: Liczba kolumn ({len(patient_data.keys())}) nie zgadza się z liczbą wartości ({len(values)})!")
            return {'success': False, 'error': f'Column count ({len(patient_data.keys())}) does not match value count ({len(values)})'}
        
        # Execute query
        try:
            cursor.execute(query, values)
            conn.commit()
            print("Patient data saved successfully")
            conn.close()
            return {'success': True}
        except sqlite3.Error as e:
            error_msg = str(e)
            print(f"SQLite error during execute: {error_msg}")
            
            # Próbujemy zidentyfikować problematyczne pola
            if "has no column named" in error_msg:
                column_name = error_msg.split("has no column named")[1].strip().strip("'")
                print(f"Column '{column_name}' does not exist in the database schema.")
                
                # Wypisz wszystkie kolumny dla łatwiejszego debugowania
                cursor.execute("PRAGMA table_info(patients)")
                schema_columns = cursor.fetchall()
                print("Available columns in schema:")
                for col in schema_columns:
                    print(f"  - {col[1]} ({col[2]})")
            
            conn.rollback()
            conn.close()
            return {'success': False, 'error': f'Database error: {error_msg}'}
    except sqlite3.Error as e:
        print(f"SQLite error: {str(e)}")
        try:
            conn.rollback()
        except:
            pass
        finally:
            if 'conn' in locals() and conn:
                conn.close()
        return {'success': False, 'error': f'Database error: {str(e)}'}
    except Exception as e:
        print(f"General error in save_patient: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        try:
            if 'conn' in locals() and conn:
                conn.rollback()
        except:
            pass
        finally:
            if 'conn' in locals() and conn:
                conn.close()
        return {'success': False, 'error': f'Unexpected error: {str(e)}'}

def save_trichoscopy_photo(pesel, photo_url, note, visit_id=None):
    # Implementation of save_trichoscopy_photo function
    pass

def get_patient_history(pesel):
    """
    Get patient history including visits and photos.
    Returns patient history data or None if not found.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get patient basic info
        cursor.execute('SELECT * FROM patients WHERE pesel = ?', (pesel,))
        patient = cursor.fetchone()
        
        if not patient:
            conn.close()
            return None
            
        # Get visits
        cursor.execute('''
            SELECT * FROM visits 
            WHERE pesel = ? 
            ORDER BY visit_date DESC
        ''', (pesel,))
        visits = cursor.fetchall()
        
        # Get trichoscopy photos
        cursor.execute('''
            SELECT * FROM trichoscopy_photos 
            WHERE pesel = ? 
            ORDER BY created_at DESC
        ''', (pesel,))
        photos = cursor.fetchall()
        
        conn.close()
        
        # Convert to dictionaries
        patient_dict = dict(patient)
        visits_list = [dict(row) for row in visits]
        photos_list = [dict(row) for row in photos]
        
        return {
            'patient': patient_dict,
            'visits': visits_list,
            'photos': photos_list
        }
        
    except sqlite3.Error as e:
        print(f"SQLite error in get_patient_history: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error in get_patient_history: {str(e)}")
        return None

def save_visit(data):
    """
    Save visit data to database.
    Returns dict with success status and visit_id if successful.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Extract data from input
        pesel = data.get('pesel')
        visit_date = data.get('visit_date')
        treatments = data.get('treatments', '')
        recommendations = data.get('recommendations', '')
        notes = data.get('notes', '')
        visit_id = data.get('visit_id')
        visit_type = data.get('visit_type', 'consultation')
        images = data.get('images', [])
        
        # Process images if any
        images_json = json.dumps([]) if not images else json.dumps(images)
        
        if visit_id:
            # Update existing visit
            cursor.execute("""
                UPDATE visits 
                SET visit_date = ?, treatments = ?, recommendations = ?, notes = ?, visit_type = ?, images = ?
                WHERE id = ? AND pesel = ?
            """, (visit_date, treatments, recommendations, notes, visit_type, images_json, visit_id, pesel))
            
            if cursor.rowcount == 0:
                raise Exception(f"Nie można zaktualizować wizyty o ID {visit_id}")
        else:
            # Create new visit
            cursor.execute("""
                INSERT INTO visits (pesel, visit_date, visit_type, purpose, diagnosis, treatments, recommendations, notes, images)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (pesel, visit_date, visit_type, data.get('purpose'), data.get('diagnosis'), treatments, recommendations, notes, images_json))
            
            visit_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'visit_id': visit_id,
            'message': 'Dane wizyty zostały zapisane pomyślnie'
        }
        
    except Exception as e:
        print(f"Błąd podczas zapisywania wizyty: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

# Care Plan Functions
def get_home_care_plan(pesel):
    """Pobierz plan pielęgnacyjny domowy dla pacjenta"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Sprawdź czy istnieje aktywny plan
        cursor.execute("""
            SELECT * FROM home_care_plans 
            WHERE pesel = ? AND is_active = 1
            ORDER BY created_at DESC LIMIT 1
        """, (pesel,))
        
        plan = cursor.fetchone()
        if not plan:
            conn.close()
            return None
        
        # Pobierz elementy planu
        cursor.execute("""
            SELECT * FROM home_care_items 
            WHERE plan_id = ?
            ORDER BY day_of_week, time_of_day
        """, (plan[0],))
        
        items = cursor.fetchall()
        
        # Konwertuj na słownik
        plan_dict = {
            'id': plan[0],
            'pesel': plan[1],
            'name': plan[2],
            'description': plan[3],
            'is_active': plan[4],
            'created_at': plan[5],
            'updated_at': plan[6],
            'items': []
        }
        
        for item in items:
            plan_dict['items'].append({
                'id': item[0],
                'plan_id': item[1],
                'product_name': item[2],
                'product_type': item[3],
                'frequency': item[4],
                'day_of_week': item[5],
                'time_of_day': item[6],
                'instructions': item[7],
                'position_x': item[8],
                'position_y': item[9],
                'created_at': item[10]
            })
        
        conn.close()
        return plan_dict
        
    except Exception as e:
        print(f"Błąd podczas pobierania planu domowego: {str(e)}")
        return None

def get_clinic_treatment_plan(pesel):
    """Pobierz plan zabiegów gabinetowych dla pacjenta"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Sprawdź czy istnieje aktywny plan
        cursor.execute("""
            SELECT * FROM clinic_treatment_plans 
            WHERE pesel = ? AND is_active = 1
            ORDER BY created_at DESC LIMIT 1
        """, (pesel,))
        
        plan = cursor.fetchone()
        if not plan:
            conn.close()
            return None
        
        # Pobierz zabiegi
        cursor.execute("""
            SELECT * FROM clinic_treatments 
            WHERE plan_id = ?
            ORDER BY position, created_at
        """, (plan[0],))
        
        treatments = cursor.fetchall()
        
        # Konwertuj na słownik
        plan_dict = {
            'id': plan[0],
            'pesel': plan[1],
            'name': plan[2],
            'description': plan[3],
            'is_active': plan[4],
            'created_at': plan[5],
            'updated_at': plan[6],
            'treatments': []
        }
        
        for treatment in treatments:
            # Parsuj historię z JSON
            history_json = treatment[12] if treatment[12] else '[]'
            try:
                history = json.loads(history_json)
            except json.JSONDecodeError:
                history = []
            
            plan_dict['treatments'].append({
                'id': treatment[0],
                'plan_id': treatment[1],
                'treatment_name': treatment[2],
                'treatment_type': treatment[3],
                'quantity': treatment[4],
                'completed_count': treatment[5],
                'status': treatment[6],
                'scheduled_date': treatment[7],
                'completed_date': treatment[8],
                'notes': treatment[9],
                'position': treatment[10],
                'created_at': treatment[11],
                'history': history
            })
        
        conn.close()
        return plan_dict
        
    except Exception as e:
        print(f"Błąd podczas pobierania planu gabinetowego: {str(e)}")
        return None

def save_home_care_plan(pesel, plan_data):
    """Zapisz plan pielęgnacyjny domowy"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Sprawdź czy pacjent istnieje
        cursor.execute("SELECT 1 FROM patients WHERE pesel = ?", (pesel,))
        if not cursor.fetchone():
            conn.close()
            raise Exception(f"Pacjent o PESEL {pesel} nie istnieje")
        
        # Pobierz ID aktywnych planów przed dezaktywacją
        cursor.execute("""
            SELECT id FROM home_care_plans 
            WHERE pesel = ? AND is_active = 1
        """, (pesel,))
        
        old_plan_ids = [row[0] for row in cursor.fetchall()]
        
        # Usuń stare elementy planów
        for plan_id in old_plan_ids:
            cursor.execute("DELETE FROM home_care_items WHERE plan_id = ?", (plan_id,))
        
        # Dezaktywuj poprzednie plany
        cursor.execute("""
            UPDATE home_care_plans 
            SET is_active = 0 
            WHERE pesel = ? AND is_active = 1
        """, (pesel,))
        
        # Utwórz nowy plan
        cursor.execute("""
            INSERT INTO home_care_plans (pesel, name, description, is_active, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
        """, (pesel, plan_data.get('name', 'Plan pielęgnacyjny domowy'), 
              plan_data.get('description', ''), 
              datetime.now().isoformat(), 
              datetime.now().isoformat()))
        
        plan_id = cursor.lastrowid
        
        # Dodaj elementy planu
        items = plan_data.get('items', [])
        for item in items:
            cursor.execute("""
                INSERT INTO home_care_items 
                (plan_id, product_name, product_type, frequency, day_of_week, 
                 time_of_day, instructions, position_x, position_y, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (plan_id, item.get('product_name'), item.get('product_type'),
                  item.get('frequency'), item.get('day_of_week'), 
                  item.get('time_of_day'), item.get('instructions'),
                  item.get('position_x', 0), item.get('position_y', 0),
                  datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        return {'success': True, 'plan_id': plan_id}
        
    except Exception as e:
        print(f"Błąd podczas zapisywania planu domowego: {str(e)}")
        return {'success': False, 'error': str(e)}

def save_clinic_treatment_plan(pesel, plan_data):
    """Zapisz plan zabiegów gabinetowych"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Sprawdź czy pacjent istnieje
        cursor.execute("SELECT 1 FROM patients WHERE pesel = ?", (pesel,))
        if not cursor.fetchone():
            conn.close()
            raise Exception(f"Pacjent o PESEL {pesel} nie istnieje")
        
        # Dezaktywuj poprzednie plany
        cursor.execute("""
            UPDATE clinic_treatment_plans 
            SET is_active = 0 
            WHERE pesel = ? AND is_active = 1
        """, (pesel,))
        
        # Utwórz nowy plan
        cursor.execute("""
            INSERT INTO clinic_treatment_plans (pesel, name, description, is_active, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
        """, (pesel, plan_data.get('name', 'Plan zabiegów gabinetowych'), 
              plan_data.get('description', ''), 
              datetime.now().isoformat(), 
              datetime.now().isoformat()))
        
        plan_id = cursor.lastrowid
        
        # Dodaj zabiegi
        treatments = plan_data.get('treatments', [])
        for treatment in treatments:
            # Konwertuj historię na JSON
            history = treatment.get('history', [])
            history_json = json.dumps(history) if history else '[]'
            
            cursor.execute("""
                INSERT INTO clinic_treatments 
                (plan_id, treatment_name, treatment_type, quantity, completed_count, 
                 status, scheduled_date, completed_date, notes, position, created_at, history)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (plan_id, treatment.get('treatment_name'), treatment.get('treatment_type'),
                  treatment.get('quantity', 1), treatment.get('completed_count', 0),
                  treatment.get('status', 'todo'), treatment.get('scheduled_date'),
                  treatment.get('completed_date'), treatment.get('notes'),
                  treatment.get('position', 0), datetime.now().isoformat(), history_json))
        
        conn.commit()
        conn.close()
        
        return {'success': True, 'plan_id': plan_id}
        
    except Exception as e:
        print(f"Błąd podczas zapisywania planu gabinetowego: {str(e)}")
        return {'success': False, 'error': str(e)}

def update_home_care_item(item_id, updates):
    """Aktualizuj element planu domowego"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Przygotuj zapytanie aktualizujące
        set_clauses = []
        values = []
        
        for key, value in updates.items():
            if key in ['product_name', 'product_type', 'frequency', 'day_of_week', 
                      'time_of_day', 'instructions', 'position_x', 'position_y']:
                set_clauses.append(f"{key} = ?")
                values.append(value)
        
        if not set_clauses:
            conn.close()
            return {'success': False, 'error': 'Brak danych do aktualizacji'}
        
        values.append(item_id)
        
        cursor.execute(f"UPDATE home_care_items SET {', '.join(set_clauses)} WHERE id = ?", values)
        
        if cursor.rowcount == 0:
            conn.close()
            return {'success': False, 'error': 'Element nie znaleziony'}
        
        conn.commit()
        conn.close()
        
        return {'success': True}
        
    except Exception as e:
        print(f"Błąd podczas aktualizacji elementu planu domowego: {str(e)}")
        return {'success': False, 'error': str(e)}

def update_clinic_treatment(treatment_id, updates):
    """Aktualizuj zabieg gabinetowy"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Przygotuj zapytanie aktualizujące
        set_clauses = []
        values = []
        
        for key, value in updates.items():
            if key in ['treatment_name', 'treatment_type', 'quantity', 'completed_count', 
                      'status', 'scheduled_date', 'completed_date', 'notes', 'position']:
                set_clauses.append(f"{key} = ?")
                values.append(value)
        
        # Dodaj aktualizację historii jeśli zmieniono status
        if 'status' in updates:
            # Pobierz aktualny status
            cursor.execute("SELECT status, history FROM clinic_treatments WHERE id = ?", (treatment_id,))
            current_data = cursor.fetchone()
            
            if current_data:
                current_status = current_data[0]
                current_history = current_data[1] or '[]'
                
                # Parsuj historię
                try:
                    history = json.loads(current_history)
                except json.JSONDecodeError:
                    history = []
                
                # Dodaj nowy wpis do historii jeśli status się zmienił
                if current_status != updates['status']:
                    history.append({
                        'from': current_status,
                        'to': updates['status'],
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    set_clauses.append("history = ?")
                    values.append(json.dumps(history))
        
        if not set_clauses:
            conn.close()
            return {'success': False, 'error': 'Brak danych do aktualizacji'}
        
        values.append(treatment_id)
        
        cursor.execute(f"UPDATE clinic_treatments SET {', '.join(set_clauses)} WHERE id = ?", values)
        
        if cursor.rowcount == 0:
            conn.close()
            return {'success': False, 'error': 'Zabieg nie znaleziony'}
        
        conn.commit()
        conn.close()
        
        return {'success': True}
        
    except Exception as e:
        print(f"Błąd podczas aktualizacji zabiegu gabinetowego: {str(e)}")
        return {'success': False, 'error': str(e)}

# Initialize DB at startup
init_db()

# Log development mode status
try:
    if DEV_MODE:
        logger.warning("⚠️  DEVELOPMENT MODE ENABLED - Authentication is disabled!")
    else:
        logger.info("🔒 Production mode - Authentication required")
except NameError:
    logger.error("❌ DEV_MODE not defined - defaulting to production mode")
    DEV_MODE = False
    logger.info("🔒 Production mode - Authentication required")

# =============================================================================
# GOOGLE OAUTH CONFIGURATION
# =============================================================================

# Google OAuth settings
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5001/auth/google/callback')

def create_google_oauth_flow():
    """Create Google OAuth flow"""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return None
    
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_REDIRECT_URI]
            }
        },
        scopes=['openid', 'https://www.googleapis.com/auth/userinfo.profile', 'https://www.googleapis.com/auth/userinfo.email']
    )
    flow.redirect_uri = GOOGLE_REDIRECT_URI
    return flow

def get_or_create_google_user(google_id, email, first_name, last_name, picture=None):
    """Get existing Google user or create if email is on allowed list"""
    try:
        # Use new invitation-based system
        from database import get_or_create_google_user_new
        return get_or_create_google_user_new(google_id, email, first_name, last_name, picture)
        
    except Exception as e:
        logger.error(f"Error in get_or_create_google_user: {str(e)}")
        return None

# API routes
@app.get("/", name="home")
async def home(request: Request):
    try:
        user = require_auth(request)
        return templates.TemplateResponse("index.html", {"request": request, "user": user})
    except HTTPException:
        # If not authenticated, redirect to login
        return RedirectResponse("/login", status_code=302)


@app.get("/new-documentation", name="new_documentation")
async def new_documentation(request: Request, user = Depends(require_auth)):
    try:
        import os
        template_path = os.path.join("test_templates", "documentation_form.html")
        if not os.path.exists(template_path):
            logger.error(f"Template file not found: {template_path}")
            return JSONResponse(
                status_code=404,
                content={"message": f"Template file not found: {template_path}"}
            )
        
        logger.info("Rendering documentation_form.html template from new-documentation route")
        # Przekazujemy pustą zmienną patient, ponieważ szablon jej wymaga
        return templates.TemplateResponse("documentation_form.html", {
            "request": request,
            "patient": None,
            "is_edit": False,
            "form_action": "/api/save-patient"
        })
    except Exception as e:
        logger.error(f"Error in new_documentation route: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"message": f"Error rendering template: {str(e)}", "traceback": traceback.format_exc()}
        )

@app.get("/documentation_form", name="documentation_form")
async def documentation_form(request: Request):
    try:
        import os
        template_path = os.path.join("test_templates", "documentation_form.html")
        if not os.path.exists(template_path):
            logger.error(f"Template file not found: {template_path}")
            return JSONResponse(
                status_code=404,
                content={"message": f"Template file not found: {template_path}"}
            )
        
        logger.info("Rendering documentation_form.html template")
        # Przekazujemy pustą zmienną patient, ponieważ szablon jej wymaga
        return templates.TemplateResponse("documentation_form.html", {
            "request": request,
            "patient": None,
            "is_edit": False
        })
    except Exception as e:
        logger.error(f"Error in documentation_form route: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"message": f"Error rendering template: {str(e)}", "traceback": traceback.format_exc()}
        )

@app.get("/new-visit/{pesel}", name="new_visit")
async def new_visit(request: Request, pesel: str):
    patient_data = get_patient(pesel)
    if not patient_data:
        return templates.TemplateResponse("error.html", {
            "request": request, 
            "error_message": "Nie znaleziono pacjenta o podanym numerze PESEL."
        }, status_code=404)
    
    # Get the date from query parameters if provided
    date = request.query_params.get("date", datetime.now().strftime("%Y-%m-%d"))
    return_to = request.query_params.get("return_to", "")
    
    return templates.TemplateResponse("visit_form.html", {
        "request": request, 
        "patient": patient_data,
        "date": date,
        "return_to": return_to
    })

@app.get("/patient/{pesel}", name="patient")
async def patient(request: Request, pesel: str, user = Depends(require_auth)):
    patient_data = get_patient(pesel)
    if patient_data:
        # Pobierz historię wizyt pacjenta
        history = get_patient_history(pesel)
        return templates.TemplateResponse("patient.html", {
            "request": request, 
            "patient": patient_data,
            "visits": history
        })
    else:
        return templates.TemplateResponse("error.html", {
            "request": request, 
            "error_message": "Nie znaleziono pacjenta o podanym numerze PESEL."
        }, status_code=404)

@app.get("/edit-patient/{pesel}", name="edit_patient")
async def edit_patient(request: Request, pesel: str):
    patient_data = get_patient(pesel)
    if not patient_data:
        return templates.TemplateResponse("error.html", {
            "request": request, 
            "error_message": "Nie znaleziono pacjenta o podanym numerze PESEL."
        }, status_code=404)
    
    # Map database field names to form field names
    # The database uses 'name' and 'surname', but the form uses 'first_name' and 'last_name'
    if 'name' in patient_data:
        patient_data['first_name'] = patient_data['name']
    if 'surname' in patient_data:
        patient_data['last_name'] = patient_data['surname']
    
    # Convert empty values to empty strings to avoid None in form fields
    for key, value in patient_data.items():
        if value is None:
            patient_data[key] = ""
    
    # Print debug info
    print(f"Editing patient with PESEL: {pesel}")
    print(f"Patient data: {patient_data}")
    
    return templates.TemplateResponse("documentation_form.html", {
        "request": request, 
        "patient": patient_data, 
        "is_edit": True
    })

@app.post("/api/save-patient", name="save_patient_api")
async def save_patient_api(request: Request, user = Depends(require_auth)):
    # Log request method and content type
    logging.info(f"Received {request.method} request to /api/save-patient with content type: {request.headers.get('content-type')}")
    
    try:
        # Get form data
        data = await request.json()
        logging.info(f"Received data keys: {list(data.keys())}")
        
        # Logujemy szczegóły PESEL bo to jest klucz główny
        if 'pesel' in data:
            logging.info(f"PESEL received: {data['pesel']}, type: {type(data['pesel'])}")
        else:
            logging.warning("No PESEL in request data!")
        
        # Logujemy także first_name i last_name
        if 'first_name' in data:
            logging.info(f"first_name received: {data['first_name']}, type: {type(data['first_name'])}")
        if 'last_name' in data:
            logging.info(f"last_name received: {data['last_name']}, type: {type(data['last_name'])}")
        
        # Log if schedule data is present
        if 'schedule' in data:
            logging.info(f"Schedule data received, type: {type(data['schedule'])}")
            # Ensure it's properly formatted if it's a string
            if isinstance(data['schedule'], str):
                try:
                    # Try to parse it to validate and then reserialize
                    schedule_data = json.loads(data['schedule'])
                    data['schedule'] = json.dumps(schedule_data, ensure_ascii=False)
                    logging.info("Schedule data validated and reformatted as JSON string")
                except json.JSONDecodeError as e:
                    logging.error(f"Invalid JSON in schedule data: {e}")
                    # Set to empty object if invalid
                    data['schedule'] = '{}'
        else:
            logging.warning("No schedule data in request")
            data['schedule'] = '{}'
            
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'pesel']
        missing_fields = [field for field in required_fields if field not in data or not data[field]]
        
        if missing_fields:
            logging.error(f"Missing required fields: {missing_fields}")
            return JSONResponse(
                status_code=400, 
                content={
                    "success": False, 
                    "error": f"Missing required fields: {', '.join(missing_fields)}"
                }
            )
        
        # Map form field names to database field names
        if 'first_name' in data:
            data['name'] = data.pop('first_name')
            logging.info("Mapped first_name to name")
        if 'last_name' in data:
            data['surname'] = data.pop('last_name')
            logging.info("Mapped last_name to surname")
        
        # Check specifically for problematic fields
        logging.info(f"Received peeling_type: {data.get('peeling_type', 'NOT PROVIDED')}, type: {type(data.get('peeling_type', None))}")
        logging.info(f"Received peeling_frequency: {data.get('peeling_frequency', 'NOT PROVIDED')}, type: {type(data.get('peeling_frequency', None))}")
        logging.info(f"Received hair_density: {data.get('hair_density', 'NOT PROVIDED')}, type: {type(data.get('hair_density', None))}")
        logging.info(f"Received hair_thickness: {data.get('hair_thickness', 'NOT PROVIDED')}, type: {type(data.get('hair_thickness', None))}")
        
        # Process all list fields to ensure they are valid
        list_fields = [
            'medication_list', 'supplements_list', 'allergens', 'diseases', 'treatments', 
            'chronic_diseases', 'skin_conditions', 'autoimmune', 'allergies', 'family_conditions', 
            'diet', 'styling', 'problem_description', 'problem_periodicity', 'previous_procedures', 
            'follicles_state', 
            'shampoo_brand', 'shampoo_type', 'shampoo_details', 
            'treatment_type', 'treatment_duration', 'treatment_details',
            'care_product_type', 'care_product_name', 'care_product_dose', 'care_product_frequency',
            'care_procedure_type', 'care_procedure_frequency', 'care_procedure_details',
            'skin_condition', 'care_procedure_count'
        ]
        for field in list_fields:
            if field in data:
                logging.info(f"Processing list field {field}: {data[field]}, type: {type(data[field])}")
                
                # Specjalna obsługa dla pola diet, aby upewnić się, że jest przetwarzane jako lista
                if field == 'diet':
                    logging.info(f"Specjalna obsługa pola diet: {data['diet']}")
                    # Jeśli diet jest już listą, nie trzeba nic robić
                    if isinstance(data['diet'], list):
                        logging.info("Pole diet jest już listą")
                    # Jeśli to string, próbujemy go przekonwertować na listę
                    elif isinstance(data['diet'], str):
                        try:
                            data['diet'] = json.loads(data['diet'])
                            logging.info(f"Przekonwertowano string diet na listę: {data['diet']}")
                        except json.JSONDecodeError:
                            # Jeśli to pojedyncza wartość, umieszczamy ją w liście
                            if data['diet'].strip() != '':
                                data['diet'] = [data['diet'].strip()]
                            else:
                                data['diet'] = []
                            logging.info(f"Utworzono listę diet z pojedynczej wartości: {data['diet']}")
                    else:
                        data['diet'] = []
                        logging.info("Ustawiono diet jako pustą listę")
                    # Upewnij się, że wartości nie są zduplikowane
                    if isinstance(data['diet'], list):
                        data['diet'] = list(dict.fromkeys(data['diet']))
                        logging.info(f"Usunięto duplikaty z diety: {data['diet']}")
                # Standardowe przetwarzanie dla innych pól
                elif isinstance(data[field], list):
                    continue
                # Convert string representation of list to actual list if needed
                elif isinstance(data[field], str):
                    try:
                        data[field] = json.loads(data[field])
                        logging.info(f"Converted string to list for {field}: {data[field]}")
                    except json.JSONDecodeError as e:
                        logging.error(f"Error converting string to list for {field}: {e}")
                        if data[field].strip() == '':
                            data[field] = []
        
        # Extra validation for specific fields
        for field in ['peeling_type', 'peeling_frequency', 'hair_density', 'hair_thickness']:
            if field in data and data[field] is None:
                data[field] = ''
                logging.info(f"Set {field} from None to empty string")
            # Ensure the field exists even if not present in the form data
            elif field not in data:
                data[field] = ''
                logging.info(f"Added missing {field} field with empty string")
        
        # Convert all list fields back to JSON strings for SQLite
        for field in list_fields:
            if field in data and isinstance(data[field], list):
                data[field] = json.dumps(data[field], ensure_ascii=False)
                logging.info(f"Converted list to JSON string for {field}")

        # Attempt to save the patient
        logging.info("Calling save_patient function with the validated data")
        db_response = save_patient(data)
        logging.info(f"save_patient function returned: {db_response}")
        
        # Return the response
        if db_response.get('success', False):
            return JSONResponse(content={"success": True, "message": "Dane pacjenta zostały zapisane pomyślnie"})
        else:
            error_msg = db_response.get('error', 'Unknown database error')
            logging.error(f"Database error: {error_msg}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": error_msg}
            )
    
    except json.JSONDecodeError as e:
        error_message = f"Invalid JSON format: {str(e)}"
        logging.error(error_message)
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": error_message}
        )
    
    except Exception as e:
        error_traceback = traceback.format_exc()
        error_message = f"Unexpected error: {str(e)}\n{error_traceback}"
        logging.error(error_message)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# TYMCZASOWY ENDPOINT DO AKTUALIZACJI ŚCIEŻEK PLIKÓW
@app.post("/api/update-file-path", name="update_file_path")
async def update_file_path(request: Request):
    """Aktualizuje ścieżki plików w bazie Railway na Cloudinary URLs"""
    try:
        data = await request.json()
        
        # Hasło
        if data.get('migrate_password', '') != 'UPDATE_PATHS_AUG_03':
            return JSONResponse(status_code=403, content={"success": False, "error": "Wrong password"})
        
        old_path = data.get('old_path')
        new_path = data.get('new_path')
        
        if not old_path or not new_path:
            return JSONResponse(status_code=400, content={"success": False, "error": "Missing paths"})
        
        # Aktualizuj w bazach
        conn = sqlite3.connect('trichology.db')
        cursor = conn.cursor()
        
        updated = 0
        
        # Trichoscopy photos
        cursor.execute("UPDATE trichoscopy_photos SET photo_path = ? WHERE photo_path = ?", (new_path, old_path))
        updated += cursor.rowcount
        
        # Clinical photos  
        cursor.execute("UPDATE clinical_photos SET photo_path = ? WHERE photo_path = ?", (new_path, old_path))
        updated += cursor.rowcount
        
        # Documents
        cursor.execute("UPDATE patient_documents SET document_path = ? WHERE document_path = ?", (new_path, old_path))
        updated += cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return JSONResponse(content={"success": True, "updated": updated})
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

# Tymczasowy endpoint migracji został usunięty po zakończeniu migracji (2025-08-03) 
@app.get("/api/calendar-events", name="calendar_events")
async def calendar_events(start: Optional[str] = None, end: Optional[str] = None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Pobierz wszystkie wizyty z bazy danych
        if start and end:
            # Jeśli podano zakres dat, pobierz wizyty tylko z tego okresu
            cursor.execute("""
                SELECT v.id, v.pesel, v.visit_date, p.name, p.surname
                FROM visits v
                JOIN patients p ON v.pesel = p.pesel
                WHERE v.visit_date >= ? AND v.visit_date <= ?
                ORDER BY v.visit_date
            """, (start[:10], end[:10]))  # Bierzemy tylko część YYYY-MM-DD z daty
        else:
            # Jeśli nie podano zakresu dat, pobierz wszystkie wizyty
            cursor.execute("""
                SELECT v.id, v.pesel, v.visit_date, p.name, p.surname
                FROM visits v
                JOIN patients p ON v.pesel = p.pesel
                ORDER BY v.visit_date
            """)
        
        rows = cursor.fetchall()
        conn.close()
        
        # Przekształć wyniki zapytania na format dla kalendarza
        events = []
        for row in rows:
            visit_id, pesel, visit_date, name, surname = row
            
            # Przyjmujemy, że wizyta trwa 1 godzinę
            start_time = visit_date
            end_time = None
            
            # Jeśli format daty to tylko data (bez godziny), dodaj domyślną godzinę
            if len(start_time) <= 10:
                start_time = f"{start_time} 10:00:00"
                end_time = f"{visit_date} 11:00:00"
            # Jeśli już jest godzina, dodaj 1 godzinę do końca
            else:
                try:
                    start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    end_dt = start_dt + timedelta(hours=1)
                    end_time = end_dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    # Jeśli nie udało się sparsować daty, użyj tylko daty bez godziny
                    start_time = f"{visit_date[:10]} 10:00:00"
                    end_time = f"{visit_date[:10]} 11:00:00"
            
            # Dodaj wydarzenie do listy
            event = {
                "id": visit_id,
                "title": f"Wizyta: {name} {surname}",
                "start": start_time,
                "end": end_time,
                "color": "#28a745",  # Zielony kolor dla wizyt
                "pesel": pesel,  # Dodaj PESEL, żeby można było przejść do karty pacjenta
                "url": f"/patient/{pesel}"  # URL do karty pacjenta
            }
            events.append(event)
        
        return JSONResponse(content=events)
    except Exception as e:
        print(f"Błąd podczas pobierania wydarzeń kalendarza: {str(e)}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/patients", name="patients_list")
async def patients_list(request: Request, user = Depends(require_auth)):
    patients = get_patients()
    return templates.TemplateResponse("patients.html", {"request": request, "patients": patients, "user": user})

@app.get("/api/search-patients", name="search_patients_api")
async def search_patients_api(request: Request, query: str = ""):
    patients = search_patients(query)
    
    # Mapuj nazwy pól dla zgodności z frontendem
    mapped_patients = []
    for patient in patients:
        mapped_patient = {
            'pesel': patient.get('pesel', ''),
            'first_name': patient.get('first_name', patient.get('name', '')),  # Najpierw spróbuj first_name, potem name
            'last_name': patient.get('last_name', patient.get('surname', '')),  # Najpierw spróbuj last_name, potem surname
            'phone': patient.get('phone', ''),
            'email': patient.get('email', ''),
            'last_visit': patient.get('last_visit', None)
        }
        mapped_patients.append(mapped_patient)
    
    return JSONResponse(content={"success": True, "patients": mapped_patients})

@app.post("/api/search-patients", name="search_patients_post_api")
async def search_patients_post_api(request: Request):
    try:
        data = await request.json()
        query = data.get("query", "")
        patients = search_patients(query)
        
        # Mapuj nazwy pól dla zgodności z frontendem
        mapped_patients = []
        for patient in patients:
            mapped_patient = {
                'pesel': patient.get('pesel', ''),
                'first_name': patient.get('first_name', patient.get('name', '')),  # Najpierw spróbuj first_name, potem name
                'last_name': patient.get('last_name', patient.get('surname', '')),  # Najpierw spróbuj last_name, potem surname
                'phone': patient.get('phone', ''),
                'email': patient.get('email', ''),
                'last_visit': patient.get('last_visit', None)
            }
            mapped_patients.append(mapped_patient)
        
        return JSONResponse(content={"success": True, "patients": mapped_patients})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/upload-photo/{pesel}", name="upload_photo")
async def upload_photo(pesel: str, file: UploadFile = File(...)):
    if not file:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "No file provided"}
        )
    
    try:
        if not file.filename:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No filename provided"}
            )
        filename = secure_filename(file.filename)
        extension = os.path.splitext(filename)[1].lower()
        
        if extension not in ['.jpg', '.jpeg', '.png']:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Only JPG and PNG files are allowed"}
            )
        
        # Create a unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        new_filename = f"{pesel}_{timestamp}{extension}"
        
        # Save the file
        file_path = os.path.join(UPLOAD_FOLDER, new_filename)
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # Update the patient record with the photo path
        rel_path = f"uploads/{new_filename}"
        update_success = update_patient_photo(pesel, rel_path)
        
        if update_success:
            return JSONResponse(content={"success": True, "photo_path": rel_path})
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Failed to update patient record"}
            )
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/save-visit", name="save_visit_api")
async def save_visit_api(
    request: Request,
    pesel: str = Form(...),
    visit_date: str = Form(...),
    treatments: str = Form(None),
    recommendations: str = Form(None),
    notes: str = Form(None),
    visit_id: Optional[int] = Form(None),
    visit_type: str = Form(None),
    images: List[UploadFile] = File([])
):
    try:
        # Process uploaded images
        image_paths = []
        if images:
            # Create visits directory if it doesn't exist
            visits_dir = os.path.join(UPLOAD_FOLDER, 'visits', pesel)
            os.makedirs(visits_dir, exist_ok=True)
            
            for image in images:
                if image.filename and image.filename.strip():
                    # Generate unique filename
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    file_extension = os.path.splitext(image.filename)[1].lower()
                    if not file_extension:
                        file_extension = '.jpg'  # Default extension
                    
                    filename = f"{timestamp}_{secure_filename(image.filename)}"
                    file_path = os.path.join(visits_dir, filename)
                    
                    # Save file
                    contents = await image.read()
                    with open(file_path, "wb") as buffer:
                        buffer.write(contents)
                    
                    # Store relative path for database
                    relative_path = f"/static/uploads/visits/{pesel}/{filename}"
                    image_paths.append(relative_path)
        
        # Przygotuj dane do zapisania
        data = {
            'pesel': pesel,
            'visit_date': visit_date,
            'treatments': treatments,
            'recommendations': recommendations,
            'notes': notes,
            'visit_id': visit_id,
            'visit_type': visit_type,
            'images': image_paths  # Now this is a list of strings, not UploadFile objects
        }
        
        # Zapisz dane wizyty
        result = save_visit(data)
        
        if result.get('success'):
            return JSONResponse(content=result)
        else:
            return JSONResponse(
                status_code=500,
                content=result
            )
    except Exception as e:
        logger.error(f"Error in save_visit_api: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                'success': False,
                'error': str(e)
            }
        )

@app.delete("/api/delete-visit/{pesel}/{visit_id}", name="delete_visit_api")
async def delete_visit_api(pesel: str, visit_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Usuń wizytę z bazy danych
        cursor.execute("DELETE FROM visits WHERE pesel = ? AND id = ?", (pesel, visit_id))
        
        if cursor.rowcount == 0:
            conn.close()
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Wizyta nie została znaleziona"}
            )
            
        conn.commit()
        conn.close()
        
        return JSONResponse(content={"success": True, "message": "Wizyta została usunięta pomyślnie"})
    except Exception as e:
        print(f"Błąd podczas usuwania wizyty: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/edit-visit/{pesel}/{visit_id}", name="edit_visit")
async def edit_visit(request: Request, pesel: str, visit_id: int):
    patient_data = get_patient(pesel)
    if not patient_data:
        return templates.TemplateResponse("error.html", {
            "request": request, 
            "error_message": "Nie znaleziono pacjenta o podanym numerze PESEL."
        }, status_code=404)
    
    # Pobierz dane wizyty
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, visit_date, visit_type, notes, treatments, recommendations, images
        FROM visits
        WHERE pesel = ? AND id = ?
    """, (pesel, visit_id))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return templates.TemplateResponse("error.html", {
            "request": request, 
            "error_message": "Nie znaleziono wizyty o podanym ID."
        }, status_code=404)
        
    # Konwertuj JSON do obiektów Pythona
    treatments = row[4]
    if treatments:
        try:
            treatments = json.loads(treatments)
        except json.JSONDecodeError:
            treatments = []
    else:
        treatments = []
        
    recommendations = row[5]
    if recommendations:
        try:
            recommendations = json.loads(recommendations)
        except json.JSONDecodeError:
            recommendations = []
    else:
        recommendations = []
        
    images = row[6]
    if images:
        try:
            images = json.loads(images)
        except json.JSONDecodeError:
            images = []
    else:
        images = []
        
    visit = {
        'id': row[0],
        'visit_date': row[1],
        'visit_type': row[2],
        'notes': row[3],
        'treatments': treatments,
        'recommendations': recommendations,
        'images': images
    }
    
    return templates.TemplateResponse("visit_form.html", {
        "request": request, 
        "patient": patient_data,
        "visit": visit,
        "is_edit": True
    })

# Endpoint do pobierania zdjęć pacjenta
@app.get("/api/patient-photos/{pesel}")
async def get_patient_photos(pesel: str, date: str = "", area: str = "", sort: str = "newest"):
    try:
        # W rzeczywistej aplikacji tutaj byłoby pobieranie danych z bazy
        # Na potrzeby demonstracji zwracamy dane testowe
        photos = []
        
        # Symulacja sortowania
        if sort == "oldest":
            # Sortowanie od najstarszych
            photos.reverse()
            
        return JSONResponse(content=photos)
    except Exception as e:
        logger.error(f"Error getting patient photos: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

# Endpoint do pobierania dokumentów pacjenta
@app.get("/api/patient-documents/{pesel}")
async def get_patient_documents(pesel: str, date: str = "", type: str = "", sort: str = "newest"):
    try:
        # W rzeczywistej aplikacji tutaj byłoby pobieranie danych z bazy
        # Na potrzeby demonstracji zwracamy dane testowe
        documents = []
        
        # Symulacja sortowania
        if sort == "oldest":
            # Sortowanie od najstarszych
            documents.reverse()
            
        return JSONResponse(content=documents)
    except Exception as e:
        logger.error(f"Error getting patient documents: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

# Endpoint do dodawania zdjęcia pacjenta
@app.post("/api/upload-patient-photo/{pesel}")
async def upload_patient_photo(pesel: str, file: UploadFile = File(...)):
    try:
        # Zapisz plik
        if not file.filename:
            return JSONResponse(content={"error": "No filename provided"}, status_code=400)
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # W rzeczywistej aplikacji tutaj byłoby zapisywanie danych do bazy
        
        return JSONResponse(content={"message": "Photo uploaded successfully", "filename": filename})
    except Exception as e:
        logger.error(f"Error uploading photo: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

# Endpoint do dodawania dokumentu pacjenta
@app.post("/api/upload-patient-document/{pesel}")
async def upload_patient_document(pesel: str, file: UploadFile = File(...)):
    try:
        # Zapisz plik
        if not file.filename:
            return JSONResponse(content={"error": "No filename provided"}, status_code=400)
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # W rzeczywistej aplikacji tutaj byłoby zapisywanie danych do bazy
        
        return JSONResponse(content={"message": "Document uploaded successfully", "filename": filename})
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

# Strona dodawania nowej wizyty
@app.get("/add-visit/{pesel}", response_class=HTMLResponse)
async def add_visit_page(request: Request, pesel: str):
    try:
        # Pobierz dane pacjenta przy użyciu istniejącej funkcji get_patient
        patient = get_patient(pesel)
        
        if not patient:
            return JSONResponse(content={"error": "Patient not found"}, status_code=404)
            
        return templates.TemplateResponse("visit_form.html", {
            "request": request,
            "patient": patient
        })
    except Exception as e:
        logger.error(f"Error displaying add visit page: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

# Endpoint do dodawania nowej wizyty
@app.post("/api/add-visit/{pesel}")
async def add_visit(pesel: str, 
                    visit_date: str = Form(...),
                    visit_type: str = Form(...),
                    purpose: str = Form(None),
                    diagnosis: str = Form(None),
                    treatments: str = Form(None),
                    recommendations: str = Form(None),
                    notes: str = Form(None),
                    cost: float = Form(0.0)):
    try:
        logger.info(f"Adding new visit for patient {pesel} on {visit_date}")
        
        # Sprawdź czy pacjent istnieje
        conn = get_db_connection()
        patient = conn.execute("SELECT * FROM patients WHERE pesel = ?", (pesel,)).fetchone()
        
        if not patient:
            conn.close()
            logger.error(f"Patient with PESEL {pesel} not found")
            return JSONResponse(content={"error": "Patient not found"}, status_code=404)
        
        # Przygotuj dane wizyty
        visit_data = {
            "pesel": pesel,
            "visit_date": visit_date,
            "visit_type": visit_type,
            "purpose": purpose,
            "diagnosis": diagnosis,
            "treatments": treatments,
            "recommendations": recommendations,
            "notes": notes,
            "cost": cost
        }
        
        # Dodaj nową wizytę
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO visits (pesel, visit_date, visit_type, purpose, diagnosis, treatments, recommendations, notes, cost, paid_amount) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (pesel, visit_date, visit_type, purpose, diagnosis, treatments, recommendations, notes, cost, 0)
        )
        
        conn.commit()
        visit_id = cursor.lastrowid
        conn.close()
        
        logger.info(f"Successfully added visit with ID {visit_id} for patient {pesel}")
        return JSONResponse(content={"message": "Visit added successfully", "visit_id": visit_id})
    except Exception as e:
        logger.error(f"Error adding visit: {str(e)}")
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/trichoscopy/{pesel}")
async def trichoscopy_page(request: Request, pesel: str):
    try:
        patient = get_patient(pesel)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        return templates.TemplateResponse(
            "trichoscopy.html",
            {"request": request, "patient": patient}
        )
    except Exception as e:
        print(f"Error rendering trichoscopy page: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/get-trichoscopy-photos/{pesel}")
async def get_trichoscopy_photos(pesel: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, pesel, photo_url, note, created_at, head_region
            FROM trichoscopy_photos
            WHERE pesel = ?
            ORDER BY created_at DESC
        """, (pesel,))
        
        photos = []
        for row in cursor.fetchall():
            photos.append({
                "id": row[0],
                "pesel": row[1],
                "photo_url": row[2],
                "note": row[3] or "",
                "created_at": row[4],
                "head_region": row[5] or "Nie wybrano",
                "point": {
                    "region": row[5] or "Nie wybrano",
                    "note": row[3] or ""
                }
            })
        
        conn.close()
        return photos
    except Exception as e:
        print(f"Błąd podczas pobierania zdjęć trychoskopii: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/api/get-clinical-photos/{pesel}")
async def get_clinical_photos(pesel: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, pesel, photo_url, note, created_at, photo_type
            FROM clinical_photos
            WHERE pesel = ?
            ORDER BY created_at DESC
        """, (pesel,))
        
        photos = []
        for row in cursor.fetchall():
            photos.append({
                "id": row[0],
                "pesel": row[1],
                "photo_url": row[2],
                "note": row[3] or "",
                "created_at": row[4],
                "photo_type": row[5] or "clinical"
            })
        
        conn.close()
        return photos
    except Exception as e:
        print(f"Błąd podczas pobierania obrazów klinicznych: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.delete("/api/delete-trichoscopy-photo/{pesel}/{photo_id}")
async def delete_trichoscopy_photo(pesel: str, photo_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Najpierw pobierz ścieżkę do pliku, żeby go usunąć
        cursor.execute("""
            SELECT photo_url FROM trichoscopy_photos
            WHERE id = ? AND pesel = ?
        """, (photo_id, pesel))
        
        result = cursor.fetchone()
        if result:
            photo_url = result[0]
            # Usuń z bazy
            cursor.execute("""
                DELETE FROM trichoscopy_photos
                WHERE id = ? AND pesel = ?
            """, (photo_id, pesel))
            
            conn.commit()
            
            # Usuń plik z dysku
            if photo_url and photo_url.startswith("/static/"):
                file_path = photo_url[1:]  # usuń pierwszy slash
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"Usunięto plik: {file_path}")
                except Exception as e:
                    print(f"Nie można usunąć pliku {file_path}: {str(e)}")
        
        conn.close()
        
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Zdjęcie zostało usunięte"}
        )
        
    except Exception as e:
        print(f"Błąd podczas usuwania zdjęcia: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.delete("/api/delete-clinical-photo/{pesel}/{photo_id}")
async def delete_clinical_photo(pesel: str, photo_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Najpierw pobierz ścieżkę do pliku, żeby go usunąć
        cursor.execute("""
            SELECT photo_url FROM clinical_photos
            WHERE id = ? AND pesel = ?
        """, (photo_id, pesel))
        
        result = cursor.fetchone()
        if result:
            photo_url = result[0]
            # Usuń z bazy
            cursor.execute("""
                DELETE FROM clinical_photos
                WHERE id = ? AND pesel = ?
            """, (photo_id, pesel))
            
            conn.commit()
            
            # Usuń plik z dysku
            if photo_url and photo_url.startswith("/static/"):
                file_path = photo_url[1:]  # usuń pierwszy slash
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"Usunięto plik: {file_path}")
                except Exception as e:
                    print(f"Nie można usunąć pliku {file_path}: {str(e)}")
        
        conn.close()
        
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Obraz kliniczny został usunięty"}
        )
        
    except Exception as e:
        print(f"Błąd podczas usuwania obrazu klinicznego: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/api/get-patient-visits/{pesel}")
async def get_patient_visits(pesel: str):
    """Get all visits for a patient"""
    try:
        patient_history = get_patient_history(pesel)
        
        # Format visits for frontend
        formatted_visits = []
        if patient_history and 'visits' in patient_history:
            visits = patient_history['visits']
            for visit in visits:
                formatted_visit = {
                    'id': visit.get('id', ''),
                    'date': visit.get('visit_date', ''),
                    'type': visit.get('visit_type', ''),
                    'doctor': 'Dr Kowalski',  # Default doctor name
                    'notes': visit.get('notes', ''),
                    'treatments': visit.get('treatments', []),
                    'recommendations': visit.get('recommendations', [])
                }
                formatted_visits.append(formatted_visit)
        
        return JSONResponse(content=formatted_visits)
        
    except Exception as e:
        print(f"Error getting patient visits: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/api/dashboard-stats")
async def get_dashboard_stats():
    """Get dashboard statistics including patient count, visits this month, and tasks count"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get total patients count
        cursor.execute("SELECT COUNT(*) as count FROM patients")
        patients_count = cursor.fetchone()['count']
        
        # Get visits count for current month
        current_month = datetime.now().strftime('%Y-%m')
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM visits 
            WHERE strftime('%Y-%m', visit_date) = ?
        """, (current_month,))
        visits_count = cursor.fetchone()['count']
        
        # Get tasks count (assuming we have a tasks table)
        cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE status = 'todo'")
        tasks_count = cursor.fetchone()['count']
        
        conn.close()
        
        return {
            "success": True,
            "data": {
                "patients_count": patients_count,
                "visits_count": visits_count,
                "tasks_count": tasks_count
            }
        }
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/save-trichoscopy-photo/{pesel}")
async def save_trichoscopy_photo_api(pesel: str, 
                                     photo: UploadFile = File(...), 
                                     note: str = Form(""),
                                     head_region: str = Form("Nie wybrano")):
    try:
        print(f"Próba zapisania zdjęcia dla pacjenta {pesel}")
        print(f"Otrzymane dane: note={note}, head_region={head_region}")
        
        # Sprawdź czy pacjent istnieje
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT pesel FROM patients WHERE pesel = ?", (pesel,))
        if not cursor.fetchone():
            conn.close()
            print(f"Pacjent o PESEL {pesel} nie istnieje")
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Pacjent nie istnieje"}
            )
        
        # Sprawdź czy otrzymano plik
        if not photo:
            conn.close()
            print("Nie otrzymano pliku zdjęcia")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Nie otrzymano pliku zdjęcia"}
            )
        
        # Odczytaj zawartość pliku
        try:
            contents = await photo.read()
            if not contents:
                conn.close()
                print("Plik zdjęcia jest pusty")
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": "Plik zdjęcia jest pusty"}
                )
        except Exception as e:
            conn.close()
            print(f"Błąd podczas odczytu pliku: {str(e)}")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"Błąd podczas odczytu pliku: {str(e)}"}
            )
        
        # Generuj unikalną nazwę pliku
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_trichoscopy.jpg"
        
        # Upload na Cloudinary
        try:
            cloudinary_result = upload_file_to_cloudinary(
                file_content=contents,
                filename=filename,
                folder="trichoscopy",
                patient_pesel=pesel
            )
            
            if not cloudinary_result['success']:
                conn.close()
                print(f"Błąd podczas uploadu na Cloudinary: {cloudinary_result.get('error')}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": f"Błąd podczas uploadu: {cloudinary_result.get('error')}"}
                )
            
            photo_url = cloudinary_result['url']
            print(f"Plik przesłany na Cloudinary: {photo_url}")
            
        except Exception as e:
            conn.close()
            print(f"Błąd podczas uploadu na Cloudinary: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Błąd podczas uploadu: {str(e)}"}
            )
        
        # Zapisz dane do bazy
        try:
            cursor.execute("""
                INSERT INTO trichoscopy_photos (pesel, photo_url, note, head_region, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (pesel, photo_url, note, head_region, datetime.now().isoformat()))
            
            photo_id = cursor.lastrowid
            conn.commit()
            print("Zdjęcie zostało pomyślnie zapisane do bazy")
        except Exception as e:
            conn.rollback()
            print(f"Błąd podczas zapisywania do bazy: {str(e)}")
            # Plik już jest na Cloudinary, więc nie usuwamy go lokalnie
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Błąd podczas zapisywania do bazy: {str(e)}"}
            )
        finally:
            conn.close()
        
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Zdjęcie zostało zapisane", "photo_url": photo_url, "photo_id": photo_id}
        )
        
    except Exception as e:
        print(f"Nieoczekiwany błąd podczas zapisywania zdjęcia: {str(e)}")
        if 'conn' in locals():
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/save-clinical-photo/{pesel}")
async def save_clinical_photo_api(pesel: str, 
                                  photo: UploadFile = File(...), 
                                  note: str = Form(""),
                                  photo_type: str = Form("clinical")):
    try:
        print(f"Próba zapisania obrazu klinicznego dla pacjenta {pesel}")
        print(f"Otrzymane dane: note={note}, photo_type={photo_type}")
        
        # Sprawdź czy pacjent istnieje
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT pesel FROM patients WHERE pesel = ?", (pesel,))
        if not cursor.fetchone():
            conn.close()
            print(f"Pacjent o PESEL {pesel} nie istnieje")
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Pacjent nie istnieje"}
            )
        
        # Sprawdź czy otrzymano plik
        if not photo:
            conn.close()
            print("Nie otrzymano pliku zdjęcia")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Nie otrzymano pliku zdjęcia"}
            )
        
        # Odczytaj zawartość pliku
        try:
            contents = await photo.read()
            if not contents:
                conn.close()
                print("Plik zdjęcia jest pusty")
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": "Plik zdjęcia jest pusty"}
                )
        except Exception as e:
            conn.close()
            print(f"Błąd podczas odczytu pliku: {str(e)}")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"Błąd podczas odczytu pliku: {str(e)}"}
            )
        
        # Generuj unikalną nazwę pliku
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{timestamp}_clinical.jpg"
        
        # Upload na Cloudinary
        try:
            cloudinary_result = upload_file_to_cloudinary(
                file_content=contents,
                filename=filename,
                folder="clinical",
                patient_pesel=pesel
            )
            
            if not cloudinary_result['success']:
                conn.close()
                print(f"Błąd podczas uploadu na Cloudinary: {cloudinary_result.get('error')}")
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "error": f"Błąd podczas uploadu: {cloudinary_result.get('error')}"}
                )
            
            photo_url = cloudinary_result['url']
            print(f"Plik przesłany na Cloudinary: {photo_url}")
            
        except Exception as e:
            conn.close()
            print(f"Błąd podczas uploadu na Cloudinary: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Błąd podczas uploadu: {str(e)}"}
            )
        
        # Zapisz dane do bazy
        try:
            cursor.execute("""
                INSERT INTO clinical_photos (pesel, photo_url, note, photo_type, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (pesel, photo_url, note, photo_type, datetime.now().isoformat()))
            
            photo_id = cursor.lastrowid
            conn.commit()
            print("Obraz kliniczny został pomyślnie zapisany do bazy")
        except Exception as e:
            conn.rollback()
            print(f"Błąd podczas zapisywania do bazy: {str(e)}")
            # Plik już jest na Cloudinary, więc nie usuwamy go lokalnie
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": f"Błąd podczas zapisywania do bazy: {str(e)}"}
            )
        finally:
            conn.close()
        
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Obraz kliniczny został zapisany", "photo_url": photo_url, "photo_id": photo_id}
        )
        
    except Exception as e:
        print(f"Nieoczekiwany błąd podczas zapisywania obrazu klinicznego: {str(e)}")
        if 'conn' in locals():
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# Care Plan API Endpoints

@app.get("/care-plan/{pesel}")
async def care_plan_page(request: Request, pesel: str):
    """Strona planu pielęgnacyjnego"""
    try:
        # Pobierz dane pacjenta
        patient = get_patient(pesel)
        if not patient:
            return JSONResponse(
                status_code=404,
                content={"error": "Pacjent nie znaleziony"}
            )
        
        return templates.TemplateResponse("care_plan.html", {
            "request": request,
            "patient": patient,
            "pesel": pesel
        })
        
    except Exception as e:
        print(f"Błąd podczas ładowania strony planu pielęgnacyjnego: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/api/get-home-care-plan/{pesel}")
async def get_home_care_plan_api(pesel: str):
    """Pobierz plan pielęgnacyjny domowy"""
    try:
        plan = get_home_care_plan(pesel)
        if not plan:
            return JSONResponse(content={"plan": None})
        
        return JSONResponse(content={"plan": plan})
        
    except Exception as e:
        print(f"Błąd podczas pobierania planu domowego: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/api/get-clinic-treatment-plan/{pesel}")
async def get_clinic_treatment_plan_api(pesel: str):
    """Pobierz plan zabiegów gabinetowych"""
    try:
        plan = get_clinic_treatment_plan(pesel)
        if not plan:
            return JSONResponse(content={"plan": None})
        
        return JSONResponse(content={"plan": plan})
        
    except Exception as e:
        print(f"Błąd podczas pobierania planu gabinetowego: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/save-home-care-plan/{pesel}")
async def save_home_care_plan_api(pesel: str, request: Request):
    """Zapisz plan pielęgnacyjny domowy"""
    try:
        data = await request.json()
        result = save_home_care_plan(pesel, data)
        
        if result['success']:
            return JSONResponse(content=result)
        else:
            return JSONResponse(
                status_code=400,
                content=result
            )
            
    except Exception as e:
        print(f"Błąd podczas zapisywania planu domowego: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/save-clinic-treatment-plan/{pesel}")
async def save_clinic_treatment_plan_api(pesel: str, request: Request):
    """Zapisz plan zabiegów gabinetowych"""
    try:
        data = await request.json()
        result = save_clinic_treatment_plan(pesel, data)
        
        if result['success']:
            return JSONResponse(content=result)
        else:
            return JSONResponse(
                status_code=400,
                content=result
            )
            
    except Exception as e:
        print(f"Błąd podczas zapisywania planu gabinetowego: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.patch("/api/update-home-care-item/{item_id}")
async def update_home_care_item_api(item_id: int, request: Request):
    """Aktualizuj element planu domowego"""
    try:
        data = await request.json()
        result = update_home_care_item(item_id, data)
        
        if result['success']:
            return JSONResponse(content=result)
        else:
            return JSONResponse(
                status_code=400,
                content=result
            )
            
    except Exception as e:
        print(f"Błąd podczas aktualizacji elementu planu domowego: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.patch("/api/update-clinic-treatment/{treatment_id}")
async def update_clinic_treatment_api(treatment_id: int, request: Request):
    """Aktualizuj zabieg gabinetowy"""
    try:
        data = await request.json()
        result = update_clinic_treatment(treatment_id, data)
        
        if result['success']:
            return JSONResponse(content=result)
        else:
            return JSONResponse(
                status_code=400,
                content=result
            )
            
    except Exception as e:
        print(f"Błąd podczas aktualizacji zabiegu gabinetowego: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.delete("/api/delete-home-care-item/{item_id}")
async def delete_home_care_item_api(item_id: int):
    """Usuń element planu domowego"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM home_care_items WHERE id = ?", (item_id,))
        
        if cursor.rowcount == 0:
            conn.close()
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Element nie znaleziony"}
            )
        
        conn.commit()
        conn.close()
        
        return JSONResponse(content={"success": True})
        
    except Exception as e:
        print(f"Błąd podczas usuwania elementu planu domowego: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.delete("/api/delete-clinic-treatment/{treatment_id}")
async def delete_clinic_treatment_api(treatment_id: int):
    """Usuń zabieg gabinetowy"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM clinic_treatments WHERE id = ?", (treatment_id,))
        
        if cursor.rowcount == 0:
            conn.close()
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Zabieg nie znaleziony"}
            )
        
        conn.commit()
        conn.close()
        
        return JSONResponse(content={"success": True})
        
    except Exception as e:
        print(f"Błąd podczas usuwania zabiegu gabinetowego: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.delete("/api/delete-all-clinic-treatments/{pesel}")
async def delete_all_clinic_treatments_api(pesel: str):
    """Usuń wszystkie zabiegi gabinetowe dla pacjenta"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Sprawdź czy pacjent istnieje
        cursor.execute("SELECT 1 FROM patients WHERE pesel = ?", (pesel,))
        if not cursor.fetchone():
            conn.close()
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Pacjent nie znaleziony"}
            )
        
        # Pobierz aktywny plan gabinetowy
        cursor.execute("""
            SELECT id FROM clinic_treatment_plans 
            WHERE pesel = ? AND is_active = 1
            ORDER BY created_at DESC LIMIT 1
        """, (pesel,))
        
        plan = cursor.fetchone()
        if not plan:
            conn.close()
            return JSONResponse(content={"success": True, "message": "Brak aktywnego planu gabinetowego"})
        
        plan_id = plan[0]
        
        # Usuń wszystkie zabiegi z aktywnego planu
        cursor.execute("DELETE FROM clinic_treatments WHERE plan_id = ?", (plan_id,))
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return JSONResponse(content={
            "success": True, 
            "message": f"Usunięto {deleted_count} zabiegów gabinetowych"
        })
        
    except Exception as e:
        print(f"Błąd podczas usuwania wszystkich zabiegów gabinetowych: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# =============================================================================
# PAYMENT MANAGEMENT API ENDPOINTS
# =============================================================================

@app.get("/billing/{pesel}")
async def billing_page(request: Request, pesel: str):
    """Strona płatności/fakturowania dla pacjenta"""
    try:
        # Pobierz dane pacjenta
        patient = get_patient(pesel)
        if not patient:
            return JSONResponse(
                status_code=404,
                content={"error": "Pacjent nie znaleziony"}
            )
        
        return templates.TemplateResponse("billing.html", {
            "request": request,
            "patient": patient,
            "pesel": pesel
        })
        
    except Exception as e:
        print(f"Błąd podczas ładowania strony płatności: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/api/get-payment-summary/{pesel}")
async def get_payment_summary_api(pesel: str):
    """Pobierz podsumowanie płatności dla pacjenta"""
    try:
        summary = get_payment_summary(pesel)
        return JSONResponse(content=summary)
        
    except Exception as e:
        print(f"Błąd podczas pobierania podsumowania płatności: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/api/get-patient-payments/{pesel}")
async def get_patient_payments_api(pesel: str):
    """Pobierz historię płatności pacjenta"""
    try:
        payments = get_patient_payments(pesel)
        return JSONResponse(content={"payments": payments})
        
    except Exception as e:
        print(f"Błąd podczas pobierania płatności pacjenta: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/add-payment/{pesel}")
async def add_payment_api(pesel: str, request: Request):
    """Dodaj nową płatność"""
    try:
        data = await request.json()
        
        # Wyciągnij dane z request
        amount = data.get('amount')
        payment_type = data.get('payment_type')
        description = data.get('description', '')
        reference_id = data.get('reference_id')
        reference_type = data.get('reference_type')
        payment_method = data.get('payment_method', 'cash')
        notes = data.get('notes', '')
        
        # Sprawdź czy pacjent istnieje
        patient = get_patient(pesel)
        if not patient:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Pacjent nie znaleziony"}
            )
        
        # Dodaj płatność
        payment_id = add_payment(pesel, amount, payment_type, description, reference_id, reference_type, payment_method, notes)
        
        if payment_id:
            # Jeśli płatność jest przypisana do konkretnego elementu, zaktualizuj jego status
            if reference_id and reference_type:
                update_payment_for_item(pesel, reference_type, reference_id, amount)
            
            return JSONResponse(content={"success": True, "payment_id": payment_id})
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Nie udało się dodać płatności"}
            )
            
    except Exception as e:
        print(f"Błąd podczas dodawania płatności: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/api/get-patient-visits-billing/{pesel}")
async def get_patient_visits_billing(pesel: str):
    """Pobierz wizyty pacjenta do fakturowania"""
    try:
        visits = get_patient_visits_for_billing(pesel)
        return JSONResponse(content={"visits": visits})
        
    except Exception as e:
        print(f"Błąd podczas pobierania wizyt: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/api/get-patient-treatments-billing/{pesel}")
async def get_patient_treatments_billing(pesel: str):
    """Pobierz zabiegi pacjenta do fakturowania"""
    try:
        # Najpierw zsynchronizuj zabiegi z planu gabinetowego
        sync_clinic_treatments_to_billing(pesel)
        
        # Następnie pobierz wszystkie zabiegi
        treatments = get_patient_treatments(pesel)
        return JSONResponse(content={"treatments": treatments})
        
    except Exception as e:
        print(f"Błąd podczas pobierania zabiegów: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/add-visit-billing/{pesel}")
async def add_visit_billing(pesel: str, request: Request):
    """Dodaj wizytę do fakturowania"""
    try:
        data = await request.json()
        
        visit_date = data.get('visit_date')
        visit_type = data.get('visit_type', 'consultation')
        description = data.get('description', '')
        cost = data.get('cost', 0)
        
        # Sprawdź czy pacjent istnieje
        patient = get_patient(pesel)
        if not patient:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Pacjent nie znaleziony"}
            )
        
        # Dodaj wizytę
        visit_id = db_add_visit(pesel, visit_date, visit_type, description, cost)
        
        if visit_id:
            return JSONResponse(content={"success": True, "visit_id": visit_id})
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Nie udało się dodać wizyty"}
            )
            
    except Exception as e:
        print(f"Błąd podczas dodawania wizyty: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/add-treatment-pricing/{pesel}")
async def add_treatment_pricing_api(pesel: str, request: Request):
    """Dodaj cenę zabiegu"""
    try:
        data = await request.json()
        
        treatment_name = data.get('treatment_name')
        treatment_type = data.get('treatment_type')
        price = data.get('price')
        reference_id = data.get('reference_id')
        
        # Sprawdź czy pacjent istnieje
        patient = get_patient(pesel)
        if not patient:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Pacjent nie znaleziony"}
            )
        
        # Dodaj cenę zabiegu
        pricing_id = add_treatment_pricing(pesel, treatment_name, treatment_type, price, reference_id)
        
        if pricing_id:
            return JSONResponse(content={"success": True, "pricing_id": pricing_id})
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Nie udało się dodać ceny zabiegu"}
            )
            
    except Exception as e:
        print(f"Błąd podczas dodawania ceny zabiegu: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.patch("/api/update-item-payment/{pesel}")
async def update_item_payment_api(pesel: str, request: Request):
    """Aktualizuj płatność dla konkretnego elementu"""
    try:
        data = await request.json()
        
        item_type = data.get('item_type')  # 'treatment', 'visit', 'product'
        item_id = data.get('item_id')
        amount = data.get('amount')
        
        # Sprawdź czy pacjent istnieje
        patient = get_patient(pesel)
        if not patient:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Pacjent nie znaleziony"}
            )
        
        # Aktualizuj płatność
        success = update_payment_for_item(pesel, item_type, item_id, amount)
        
        if success:
            return JSONResponse(content={"success": True})
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Nie udało się zaktualizować płatności"}
            )
            
    except Exception as e:
        print(f"Błąd podczas aktualizacji płatności: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# === SETTINGS AND TREATMENTS MANAGEMENT ===

@app.get("/settings")
async def settings_page(request: Request):
    """Strona ustawień systemu"""
    return templates.TemplateResponse("settings.html", {"request": request})

@app.get("/api/treatments")
async def get_treatments_api():
    """Pobierz listę dostępnych zabiegów"""
    try:
        treatments = get_available_treatments()
        return JSONResponse(content=treatments)
        
    except Exception as e:
        print(f"Błąd podczas pobierania zabiegów: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/treatments")
async def add_treatment_api(request: Request):
    """Dodaj nowy zabieg"""
    try:
        data = await request.json()
        
        name = data.get('name')
        treatment_type = data.get('type')
        default_price = data.get('default_price')
        description = data.get('description', '')
        
        # Walidacja danych
        if not name or not treatment_type or default_price is None:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Brak wymaganych danych"}
            )
        
        # Dodaj zabieg
        result = add_available_treatment(name, treatment_type, default_price, description)
        
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"Błąd podczas dodawania zabiegu: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.put("/api/treatments/{treatment_id}")
async def update_treatment_api(treatment_id: int, request: Request):
    """Zaktualizuj zabieg"""
    try:
        data = await request.json()
        
        name = data.get('name')
        treatment_type = data.get('type')
        default_price = data.get('default_price')
        description = data.get('description')
        
        # Aktualizuj zabieg
        result = update_available_treatment(
            treatment_id, 
            name=name, 
            treatment_type=treatment_type, 
            default_price=default_price, 
            description=description
        )
        
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"Błąd podczas aktualizacji zabiegu: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.delete("/api/treatments/{treatment_id}")
async def delete_treatment_api(treatment_id: int):
    """Usuń (dezaktywuj) zabieg"""
    try:
        result = delete_available_treatment(treatment_id)
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"Błąd podczas usuwania zabiegu: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# =============================================================================
# AUTHENTICATION ENDPOINTS
# =============================================================================

@app.get("/auth/google")
async def google_login():
    """Initiate Google OAuth login"""
    try:
        # In development mode, redirect to home with mock authentication
        if DEV_MODE:
            return RedirectResponse("/")
        
        flow = create_google_oauth_flow()
        if not flow:
            return JSONResponse(
                status_code=500,
                content={"error": "Google OAuth nie jest skonfigurowane"}
            )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='select_account'
        )
        
        # Store state in session for security
        response = RedirectResponse(authorization_url)
        response.set_cookie("oauth_state", state, max_age=600, httponly=True)  # 10 minutes
        
        return response
        
    except Exception as e:
        logger.error(f"Error in google_login: {str(e)}")
        return RedirectResponse("/login?error=oauth_error")

@app.get("/auth/google/callback")
async def google_callback(request: Request, code: str = Query(None), state: str = Query(None)):
    """Handle Google OAuth callback"""
    try:
        # Verify state parameter
        stored_state = request.cookies.get("oauth_state")
        if not stored_state or stored_state != state:
            return RedirectResponse("/login?error=invalid_state")
        
        if not code:
            return RedirectResponse("/login?error=access_denied")
        
        flow = create_google_oauth_flow()
        if not flow:
            return RedirectResponse("/login?error=oauth_error")
        
        # Exchange authorization code for tokens
        try:
            flow.fetch_token(code=code)
        except Exception as fetch_error:
            logger.error(f"Failed to fetch OAuth token: {str(fetch_error)}")
            return RedirectResponse("/login?error=oauth_token_error")
        
        # Get user info from Google
        credentials = flow.credentials
        request_session = google_requests.Request()
        
        # Verify the token and get user info
        idinfo = id_token.verify_oauth2_token(
            credentials.id_token, 
            request_session, 
            GOOGLE_CLIENT_ID
        )
        
        google_id = idinfo['sub']
        email = idinfo['email']
        first_name = idinfo.get('given_name', '')
        last_name = idinfo.get('family_name', '')
        picture = idinfo.get('picture', '')
        
        # Get or create user
        user = get_or_create_google_user(google_id, email, first_name, last_name, picture)
        
        if not user:
            return RedirectResponse("/login?error=user_creation_failed")
        
        # Create session
        session_token = create_session(user['id'])
        
        if not session_token:
            return RedirectResponse("/login?error=session_creation_failed")
        
        # Redirect to main page with session cookie
        response = RedirectResponse("/")
        response.set_cookie(
            key="session_token",
            value=session_token,
            max_age=30 * 24 * 60 * 60,  # 30 days
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax"
        )
        
        # Clear oauth state cookie
        response.set_cookie("oauth_state", "", max_age=0)
        
        return response
        
    except Exception as e:
        logger.error(f"Error in google_callback: {str(e)}")
        return RedirectResponse("/login?error=oauth_error")

@app.get("/login")
async def login_page(request: Request):
    """Show login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register")
async def register_page(request: Request):
    """Show registration page"""
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/logout")
async def logout(request: Request):
    """Logout user and destroy session"""
    try:
        # Get session token
        session_token = request.cookies.get("session_token")
        
        if session_token:
            # Delete session from database
            delete_session(session_token)
        
        # Redirect to login with cleared cookie
        response = RedirectResponse("/login", status_code=302)
        response.set_cookie("session_token", "", max_age=0)
        
        return response
        
    except Exception as e:
        logger.error(f"Error in logout: {str(e)}")
        response = RedirectResponse("/login", status_code=302) 
        response.set_cookie("session_token", "", max_age=0)
        return response

# =============================================================================
# ADMIN USER MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/admin/users")
async def admin_users_page(request: Request, user = Depends(require_auth)):
    """Admin panel for user management"""
    if user.get('role') != 'admin':
        raise HTTPException(status_code=403, detail="Tylko admin ma dostęp do tego panelu")
    
    return templates.TemplateResponse("admin_users.html", {"request": request, "user": user})

@app.get("/api/admin/users")
async def get_users_api(request: Request, user = Depends(require_auth)):
    """Get all users (admin only)"""
    try:
        if user.get('role') != 'admin':
            return JSONResponse(status_code=403, content={"error": "Dostęp tylko dla administratora"})
        
        from database import get_all_users
        users = get_all_users(user['id'])
        
        if users is None:
            return JSONResponse(status_code=403, content={"error": "Dostęp zabroniony"})
        
        return JSONResponse(content={"success": True, "users": users})
        
    except Exception as e:
        logger.error(f"Error in get_users_api: {str(e)}")
        return JSONResponse(status_code=500, content={"error": "Błąd serwera"})

@app.post("/api/admin/invite-user")
async def invite_user_api(request: Request, user = Depends(require_auth)):
    """Invite new user (admin only)"""
    try:
        if user.get('role') != 'admin':
            return JSONResponse(status_code=403, content={"error": "Dostęp tylko dla administratora"})
        
        form_data = await request.form()
        email = form_data.get('email', '').strip()
        first_name = form_data.get('first_name', '').strip()
        last_name = form_data.get('last_name', '').strip()
        role = form_data.get('role', 'user').strip()
        
        if not email:
            return JSONResponse(status_code=400, content={"error": "Email jest wymagany"})
        
        # Validate email format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return JSONResponse(status_code=400, content={"error": "Nieprawidłowy format email"})
        
        if role not in ['admin', 'user']:
            return JSONResponse(status_code=400, content={"error": "Nieprawidłowa rola"})
        
        from database import invite_user
        result = invite_user(user['id'], email, first_name, last_name, role)
        
        if result['success']:
            return JSONResponse(content={"success": True, "message": result['message']})
        else:
            return JSONResponse(status_code=400, content={"error": result['error']})
        
    except Exception as e:
        logger.error(f"Error in invite_user_api: {str(e)}")
        return JSONResponse(status_code=500, content={"error": "Błąd serwera"})

@app.delete("/api/admin/users/{user_id}")
async def remove_user_api(request: Request, user_id: int, user = Depends(require_auth)):
    """Remove user (admin only)"""
    try:
        if user.get('role') != 'admin':
            return JSONResponse(status_code=403, content={"error": "Dostęp tylko dla administratora"})
        
        from database import remove_user
        result = remove_user(user['id'], user_id)
        
        if result['success']:
            return JSONResponse(content={"success": True, "message": result['message']})
        else:
            return JSONResponse(status_code=400, content={"error": result['error']})
        
    except Exception as e:
        logger.error(f"Error in remove_user_api: {str(e)}")
        return JSONResponse(status_code=500, content={"error": "Błąd serwera"})

@app.post("/api/login")
async def login_api(request: Request, 
                   email: str = Form(...),
                   password: str = Form(...),
                   remember: str = Form(None)):
    """Handle login request"""
    try:
        # Authenticate user
        user = authenticate_user(email, password)
        
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Nieprawidłowy email lub hasło"}
            )
        
        # Create session
        session_token = create_session(user['id'])
        
        if not session_token:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Błąd podczas tworzenia sesji"}
            )
        
        # Create response with session cookie
        response = JSONResponse(content={
            "success": True,
            "redirect_url": "/",
            "user": {
                "id": user['id'],
                "email": user['email'],
                "first_name": user['first_name'],
                "last_name": user['last_name'],
                "role": user['role']
            }
        })
        
        # Set session cookie
        # Remember me = 30 days, otherwise session cookie
        max_age = 30 * 24 * 60 * 60 if remember else None
        response.set_cookie(
            key="session_token",
            value=session_token,
            max_age=max_age,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error in login_api: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Błąd serwera: {str(e)}"}
        )

@app.post("/api/register")
async def register_api(request: Request,
                      first_name: str = Form(...),
                      last_name: str = Form(...),
                      email: str = Form(...),
                      password: str = Form(...),
                      role: str = Form(...),
                      terms: str = Form(None)):
    """Handle registration request"""
    try:
        # Validate terms acceptance
        if not terms:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Musisz zaakceptować regulamin"}
            )
        
        # Validate password strength
        if len(password) < 8:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Hasło musi mieć minimum 8 znaków"}
            )
        
        # Create user
        result = create_user(email, password, first_name, last_name, role)
        
        if result['success']:
            return JSONResponse(content={
                "success": True,
                "message": "Konto zostało utworzone pomyślnie",
                "user_id": result['user_id']
            })
        else:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": result['error']}
            )
            
    except Exception as e:
        logger.error(f"Error in register_api: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Błąd serwera: {str(e)}"}
        )

@app.post("/api/logout")
async def logout_api(request: Request):
    """Handle logout request"""
    try:
        # Get session token from cookie
        session_token = request.cookies.get("session_token")
        
        if session_token:
            # Delete session from database
            delete_session(session_token)
        
        # Create response and clear cookie
        response = JSONResponse(content={"success": True})
        response.delete_cookie("session_token")
        
        return response
        
    except Exception as e:
        logger.error(f"Error in logout_api: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Błąd serwera: {str(e)}"}
        )

@app.post("/api/logout-all")
async def logout_all_api(request: Request):
    """Handle logout from all sessions"""
    try:
        # Get current user
        user = get_current_user(request)
        
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Nie jesteś zalogowany"}
            )
        
        # Delete all sessions for this user
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM sessions WHERE user_id = ?', (user['id'],))
        conn.commit()
        conn.close()
        
        # Create response and clear cookie
        response = JSONResponse(content={"success": True})
        response.delete_cookie("session_token")
        
        return response
        
    except Exception as e:
        logger.error(f"Error in logout_all_api: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Błąd serwera: {str(e)}"}
        )

@app.get("/api/user/profile")
async def get_user_profile_api(request: Request):
    """Get current user profile"""
    try:
        user = get_current_user(request)
        
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Nie jesteś zalogowany"}
            )
        
        return JSONResponse(content={
            "success": True,
            "user": user
        })
        
    except Exception as e:
        logger.error(f"Error in get_user_profile_api: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Błąd serwera: {str(e)}"}
        )

@app.put("/api/user/profile")
async def update_user_profile_api(request: Request,
                                 first_name: str = Form(...),
                                 last_name: str = Form(...),
                                 email: str = Form(...),
                                 profile_picture: UploadFile = File(None)):
    """Update user profile"""
    try:
        user = get_current_user(request)
        
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Nie jesteś zalogowany"}
            )
        
        # Handle profile picture upload
        profile_picture_path = None
        if profile_picture and profile_picture.filename:
            # Create uploads directory if it doesn't exist
            uploads_dir = os.path.join(UPLOAD_FOLDER, 'profiles')
            os.makedirs(uploads_dir, exist_ok=True)
            
            # Generate unique filename
            filename = f"{user['id']}_{int(datetime.now().timestamp())}_{secure_filename(profile_picture.filename)}"
            file_path = os.path.join(uploads_dir, filename)
            
            # Save file
            with open(file_path, "wb") as buffer:
                content = await profile_picture.read()
                buffer.write(content)
            
            profile_picture_path = f"/static/uploads/profiles/{filename}"
        
        # Update user profile
        result = update_user_profile(
            user['id'],
            first_name=first_name,
            last_name=last_name,
            email=email,
            profile_picture=profile_picture_path
        )
        
        if result['success']:
            # Get updated user data
            updated_user = get_user_by_id(user['id'])
            return JSONResponse(content={
                "success": True,
                "user": updated_user
            })
        else:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": result['error']}
            )
            
    except Exception as e:
        logger.error(f"Error in update_user_profile_api: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Błąd serwera: {str(e)}"}
        )

@app.post("/api/user/change-password")
async def change_password_api(request: Request,
                             current_password: str = Form(...),
                             new_password: str = Form(...)):
    """Change user password"""
    try:
        user = get_current_user(request)
        
        if not user:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": "Nie jesteś zalogowany"}
            )
        
        # Verify current password
        if not authenticate_user(user['email'], current_password):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Aktualne hasło jest nieprawidłowe"}
            )
        
        # Validate new password
        if len(new_password) < 8:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Nowe hasło musi mieć minimum 8 znaków"}
            )
        
        # Change password
        result = change_user_password(user['id'], new_password)
        
        if result['success']:
            return JSONResponse(content={
                "success": True,
                "message": "Hasło zostało zmienione pomyślnie"
            })
        else:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": result['error']}
            )
            
    except Exception as e:
        logger.error(f"Error in change_password_api: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Błąd serwera: {str(e)}"}
        )

@app.get("/api/get-all-photos/{pesel}")
async def get_all_photos(pesel: str):
    """Pobierz wszystkie zdjęcia (trychoskopowe i kliniczne) dla pacjenta"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Pobierz zdjęcia trychoskopowe
        cursor.execute("""
            SELECT id, pesel, photo_url, note, created_at, head_region, 'trichoscopy' as photo_type
            FROM trichoscopy_photos
            WHERE pesel = ?
        """, (pesel,))
        
        trichoscopy_photos = cursor.fetchall()
        
        # Pobierz obrazy kliniczne
        cursor.execute("""
            SELECT id, pesel, photo_url, note, created_at, 'Obraz kliniczny' as head_region, photo_type
            FROM clinical_photos
            WHERE pesel = ?
        """, (pesel,))
        
        clinical_photos = cursor.fetchall()
        
        # Połącz wszystkie zdjęcia
        all_photos = []
        
        # Dodaj zdjęcia trychoskopowe
        for row in trichoscopy_photos:
            all_photos.append({
                "id": row[0],
                "pesel": row[1],
                "photo_url": row[2],
                "note": row[3] or "",
                "created_at": row[4],
                "head_region": row[5] or "Nie wybrano",
                "photo_type": row[6],
                "point": {
                    "region": row[5] or "Nie wybrano",
                    "note": row[3] or ""
                }
            })
        
        # Dodaj obrazy kliniczne
        for row in clinical_photos:
            all_photos.append({
                "id": row[0],
                "pesel": row[1],
                "photo_url": row[2],
                "note": row[3] or "",
                "created_at": row[4],
                "head_region": row[5],
                "photo_type": row[6],
                "point": {
                    "region": row[5],
                    "note": row[3] or ""
                }
            })
        
        # Sortuj według daty (najnowsze pierwsze)
        all_photos.sort(key=lambda x: x['created_at'], reverse=True)
        
        conn.close()
        return all_photos
        
    except Exception as e:
        print(f"Błąd podczas pobierania wszystkich zdjęć: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# =============================================================================
# GOOGLE CALENDAR INTEGRATION (Simplified)
# =============================================================================

@app.post("/api/google-calendar-setup")
async def setup_google_calendar():
    """
    Rozpoczyna proces autoryzacji Google Calendar - uproszczona wersja
    """
    try:
        client_secrets_file = 'google_calendar_credentials.json'
        
        if not os.path.exists(client_secrets_file):
            return JSONResponse(
                status_code=400,
                content={
                    "success": False, 
                    "error": "Brak pliku credentials. Plik został już utworzony, spróbuj ponownie."
                }
            )
        
        # Zwróć URL autoryzacji Google (uproszczony)
        base_auth_url = "https://accounts.google.com/o/oauth2/auth"
        params = {
            "client_id": "704878279630-8u8un9mi76ppbdprsmk1hod6jm2v42pr.apps.googleusercontent.com",
            "redirect_uri": "http://localhost:5001/google-calendar-callback", 
            "scope": "https://www.googleapis.com/auth/calendar",
            "response_type": "code",
            "access_type": "offline",
            "include_granted_scopes": "true"
        }
        
        auth_url = f"{base_auth_url}?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
        return JSONResponse(content={
            "success": True,
            "auth_url": auth_url,
            "message": "Przekieruj do Google dla autoryzacji"
        })
            
    except Exception as e:
        logger.error(f"Błąd konfiguracji Google Calendar: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/google-calendar-callback")
async def google_calendar_callback(code: Optional[str] = None):
    """
    Endpoint callback dla autoryzacji Google Calendar - uproszczony
    """
    try:
        if not code:
            return RedirectResponse(
                url="/settings?error=authorization_denied",
                status_code=302
            )
        
        # W uproszczonej wersji zapisujemy tylko kod autoryzacji
        # (pełna implementacja wymagałaby bibliotek Google)
        with open('google_auth_code.txt', 'w') as f:
            f.write(code)
        
        return RedirectResponse(
            url="/settings?google_calendar=connected",
            status_code=302
        )
            
    except Exception as e:
        logger.error(f"Błąd podczas callback Google Calendar: {str(e)}")
        return RedirectResponse(
            url="/settings?error=callback_error",
            status_code=302
        )

@app.get("/api/google-calendar-status")
async def google_calendar_status():
    """
    Sprawdza status połączenia z Google Calendar
    """
    try:
        # Sprawdź czy mamy kod autoryzacji
        if os.path.exists('google_auth_code.txt') and os.path.exists('google_calendar_credentials.json'):
            return JSONResponse(content={
                "connected": True,
                "message": "Google Calendar jest skonfigurowany (uproszczona wersja)"
            })
        else:
            return JSONResponse(content={
                "connected": False,
                "message": "Google Calendar nie jest jeszcze skonfigurowany"
            })
            
    except Exception as e:
        logger.error(f"Błąd sprawdzania statusu Google Calendar: {str(e)}")
        return JSONResponse(content={
            "connected": False,
            "error": str(e)
        })

@app.post("/api/sync-to-google-calendar") 
async def sync_visits_to_google_calendar():
    """
    Placeholder - synchronizacja wizyt do Google Calendar (wymaga pełnej biblioteki)
    """
    return JSONResponse(content={
        "success": True,
        "message": "Aby włączyć pełną synchronizację, zainstaluj: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib",
        "synced_count": 0,
        "total_visits": 0,
        "note": "Użyj eksportu iCal jako alternatywy"
    })

@app.get("/api/calendar-events-combined", name="calendar_events_combined")
async def calendar_events_combined(start: Optional[str] = None, end: Optional[str] = None):
    """
    Fallback do lokalnych wydarzeń (bez Google Calendar)
    """
    return await calendar_events(start, end)

def save_patient_simple(data):
    """
    Prosta wersja zapisu pacjenta - tylko podstawowe pola, bez auto-dodawanych kolumn
    Używana do importu danych z lokalnej bazy do produkcyjnej
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Tylko podstawowe pola, które na pewno są w każdej wersji bazy
        basic_fields = {
            'pesel': data.get('pesel', ''),
            'name': data.get('name', ''),
            'surname': data.get('surname', ''),
            'birthdate': data.get('birthdate', ''),
            'gender': data.get('gender', ''),
            'phone': data.get('phone', ''),
            'email': data.get('email', ''),
            'height': data.get('height', ''),
            'weight': data.get('weight', ''),
            'medication_list': data.get('medication_list', '[]'),
            'supplements_list': data.get('supplements_list', '[]'),
            'allergens': data.get('allergens', '[]'),
            'diseases': data.get('diseases', '[]'),
            'treatments': data.get('treatments', '[]'),
            'notes': data.get('notes', ''),
            'created_at': data.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        }
        
        # Przygotuj zapytanie SQL
        columns = ', '.join(basic_fields.keys())
        placeholders = ', '.join(['?' for _ in basic_fields])
        values = tuple(basic_fields.values())
        
        query = f"INSERT OR REPLACE INTO patients ({columns}) VALUES ({placeholders})"
        
        cursor.execute(query, values)
        conn.commit()
        conn.close()
        
        return {'success': True, 'message': 'Patient saved successfully'}
        
    except sqlite3.Error as e:
        if 'conn' in locals() and conn:
            conn.close()
        return {'success': False, 'error': f'Database error: {str(e)}'}
    except Exception as e:
        if 'conn' in locals() and conn:
            conn.close()
        return {'success': False, 'error': f'Unexpected error: {str(e)}'}

@app.post("/api/import-patients")
async def import_patients_api(request: Request, file: UploadFile = File(...)):
    """
    Endpoint do importu pacjentów z pliku JSON.
    Używany do przeniesienia danych z lokalnej bazy do produkcyjnej.
    """
    try:
        # Sprawdź czy plik jest JSON
        if not file.filename.endswith('.json'):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Plik musi mieć rozszerzenie .json"}
            )
        
        # Odczytaj zawartość pliku
        content = await file.read()
        patients_data = json.loads(content.decode('utf-8'))
        
        if not isinstance(patients_data, list):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Plik JSON musi zawierać listę pacjentów"}
            )
        
        # Importuj każdego pacjenta
        imported_count = 0
        skipped_count = 0
        errors = []
        
        for patient_data in patients_data:
            try:
                # Sprawdź czy pacjent już istnieje
                existing_patient = get_patient(patient_data.get('pesel', ''))
                if existing_patient:
                    skipped_count += 1
                    continue
                
                # Zapisz pacjenta z prostą wersją (bez dodatkowych pól)
                result = save_patient_simple(patient_data)
                if result.get('success', False):
                    imported_count += 1
                else:
                    errors.append(f"PESEL {patient_data.get('pesel', 'unknown')}: {result.get('error', 'Nieznany błąd')}")
                    
            except Exception as e:
                errors.append(f"PESEL {patient_data.get('pesel', 'unknown')}: {str(e)}")
        
        return JSONResponse(content={
            "success": True,
            "message": f"Import zakończony",
            "imported": imported_count,
            "skipped": skipped_count,
            "errors": errors[:10]  # Maksymalnie 10 błędów do wyświetlenia
        })
        
    except json.JSONDecodeError as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": f"Nieprawidłowy format JSON: {str(e)}"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Błąd serwera: {str(e)}"}
        )

@app.get("/import-patients")
async def import_patients_page(request: Request):
    """Strona do importu pacjentów"""
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Import Pacjentów - Trichology</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
            .container {{ background: #f5f5f5; padding: 30px; border-radius: 10px; }}
            .upload-area {{ border: 2px dashed #ccc; padding: 40px; text-align: center; margin: 20px 0; }}
            .upload-area:hover {{ border-color: #007bff; }}
            button {{ background: #007bff; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; }}
            button:hover {{ background: #0056b3; }}
            .result {{ margin-top: 20px; padding: 15px; border-radius: 5px; }}
            .success {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
            .error {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔄 Import Pacjentów</h1>
            <p>Użyj tej strony do zaimportowania pacjentów z pliku JSON wyeksportowanego z lokalnej bazy danych.</p>
            
            <div class="upload-area" onclick="document.getElementById('fileInput').click()">
                <p>📁 Kliknij tutaj lub przeciągnij plik JSON z pacjentami</p>
                <input type="file" id="fileInput" accept=".json" style="display: none;" onchange="handleFileSelect(event)">
            </div>
            
            <button onclick="uploadFile()" id="uploadBtn" disabled>📤 Importuj Pacjentów</button>
            
            <div id="result"></div>
        </div>

        <script>
            let selectedFile = null;
            
            function handleFileSelect(event) {{
                selectedFile = event.target.files[0];
                if (selectedFile) {{
                    document.querySelector('.upload-area p').textContent = `Wybrano: ${{selectedFile.name}}`;
                    document.getElementById('uploadBtn').disabled = false;
                }}
            }}
            
            async function uploadFile() {{
                if (!selectedFile) return;
                
                const formData = new FormData();
                formData.append('file', selectedFile);
                
                document.getElementById('uploadBtn').textContent = '⏳ Importowanie...';
                document.getElementById('uploadBtn').disabled = true;
                
                try {{
                    const response = await fetch('/api/import-patients', {{
                        method: 'POST',
                        body: formData
                    }});
                    
                    const result = await response.json();
                    const resultDiv = document.getElementById('result');
                    
                    if (result.success) {{
                        resultDiv.innerHTML = `
                            <div class="result success">
                                <h3>✅ Import zakończony pomyślnie!</h3>
                                <p>📊 Zaimportowano: <strong>${{result.imported}}</strong> pacjentów</p>
                                <p>⏭️ Pominięto: <strong>${{result.skipped}}</strong> (już istniejący)</p>
                                ${{result.errors.length > 0 ? `<p>⚠️ Błędy: ${{result.errors.length}}</p>` : ''}}
                            </div>
                        `;
                    }} else {{
                        resultDiv.innerHTML = `
                            <div class="result error">
                                <h3>❌ Błąd importu</h3>
                                <p>${{result.error}}</p>
                            </div>
                        `;
                    }}
                }} catch (error) {{
                    document.getElementById('result').innerHTML = `
                        <div class="result error">
                            <h3>❌ Błąd połączenia</h3>
                            <p>${{error.message}}</p>
                        </div>
                    `;
                }}
                
                document.getElementById('uploadBtn').textContent = '📤 Importuj Pacjentów';
                document.getElementById('uploadBtn').disabled = false;
            }}
        </script>
    </body>
    </html>
    """)

@app.get("/api/export-ical")
async def export_calendar_ical():
    """
    Eksportuje kalendarz wizyt do formatu iCal (.ics)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Pobierz wizyty z następnych 90 dni
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=90)
        
        cursor.execute("""
            SELECT v.id, v.pesel, v.visit_date, v.notes, v.treatments,
                   p.name, p.surname, p.phone, p.email
            FROM visits v
            JOIN patients p ON v.pesel = p.pesel
            WHERE DATE(v.visit_date) >= DATE(?) AND DATE(v.visit_date) <= DATE(?)
            ORDER BY v.visit_date
        """, (start_date.isoformat(), end_date.isoformat()))
        
        visits = cursor.fetchall()
        conn.close()
        
        # Generuj zawartość iCal
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Aplikacja Trychologa//Kalendarz Wizyt//PL",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:Wizyty Trychologa",
            "X-WR-TIMEZONE:Europe/Warsaw"
        ]
        
        for visit in visits:
            visit_id, pesel, visit_date, notes, treatments, name, surname, phone, email = visit
            
            # UID
            uid = f"visit-{visit_id}-{pesel}@trichology-app.local"
            
            # Formatowanie daty
            try:
                if len(visit_date) <= 10:
                    dt_start = datetime.strptime(visit_date, "%Y-%m-%d")
                    dt_start = dt_start.replace(hour=10, minute=0)
                else:
                    dt_start = datetime.strptime(visit_date, "%Y-%m-%d %H:%M:%S")
                
                dt_end = dt_start + timedelta(hours=1)
                start_time = dt_start.strftime("%Y%m%dT%H%M%S")
                end_time = dt_end.strftime("%Y%m%dT%H%M%S")
                
            except ValueError:
                dt_start = datetime.now().replace(hour=10, minute=0, second=0)
                dt_end = dt_start + timedelta(hours=1)
                start_time = dt_start.strftime("%Y%m%dT%H%M%S")
                end_time = dt_end.strftime("%Y%m%dT%H%M%S")
            
            # Opis
            summary = f"Wizyta: {name} {surname}"
            event_description = f"Pacjent: {name} {surname}\\nPESEL: {pesel}"
            
            if phone:
                event_description += f"\\nTelefon: {phone}"
            if email:
                event_description += f"\\nEmail: {email}"
            if treatments:
                event_description += f"\\nZabiegi: {treatments}"
            if notes:
                event_description += f"\\nUwagi: {notes}"
            
            # Dodaj wydarzenie
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTART:{start_time}",
                f"DTEND:{end_time}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{event_description}",
                "LOCATION:Gabinet trychologa",
                "STATUS:CONFIRMED",
                "CATEGORIES:Medycyna,Wizyta",
                "END:VEVENT"
            ])
        
        lines.append("END:VCALENDAR")
        ical_content = "\r\n".join(lines)
        
        # Zwróć plik iCal
        return Response(
            content=ical_content,
            media_type="text/calendar",
            headers={
                "Content-Disposition": "attachment; filename=wizyty_trychologa.ics"
            }
        )
        
    except Exception as e:
        logger.error(f"Błąd podczas eksportu iCal: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/emergency-fix-database")
async def emergency_fix_database():
    """
    AWARYJNY endpoint - Railway zresetowało bazę ZNOWU!
    Odtwarza wszystkie tabele po resecie Railway
    """
    try:
        success = init_db()
        
        if success:
            return JSONResponse(content={
                "success": True,
                "message": "🚨 BAZA NAPRAWIONA po resecie Railway!",
                "tables_created": [
                    "patients", "trichoscopy_photos", "clinical_photos", "visits", 
                    "external_visits", "home_care_plans", "clinic_treatment_plans", 
                    "payments", "tasks", "users", "sessions", "available_treatments"
                ],
                "next_step": "Zaimportuj pacjentów przez /api/import-patients"
            })
        else:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Błąd inicjalizacji bazy"}
            )
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Błąd: {str(e)}"}
        )

@app.get("/calendar.ics")
async def calendar_feed():
    """
    Udostępnia kalendarz jako feed iCal dla urządzeń mobilnych
    """
    return await export_calendar_ical()


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False) 