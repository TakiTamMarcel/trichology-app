import sqlite3
import json
import os
from datetime import datetime

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
    try:
        print("Initializing database...")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create patients table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                pesel TEXT PRIMARY KEY,
                name TEXT,
                surname TEXT,
                birthdate TEXT,
                gender TEXT,
                phone TEXT,
                email TEXT,
                height TEXT,
                weight TEXT,
                photo TEXT,
                medication_list TEXT,
                supplements_list TEXT,
                allergens TEXT,
                diseases TEXT,
                treatments TEXT,
                notes TEXT,
                peeling_type TEXT,
                peeling_frequency TEXT,
                shampoo_name TEXT,
                shampoo_brand TEXT,
                shampoo_frequency TEXT,
                created_at TEXT
            )
        ''')
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(patients)")
        columns = {row[1] for row in cursor.fetchall()}
        
        # Add any missing columns
        missing_columns = [
            ('peeling_type', 'TEXT'),
            ('peeling_frequency', 'TEXT'),
            ('shampoo_name', 'TEXT'),
            ('shampoo_brand', 'TEXT'),
            ('shampoo_frequency', 'TEXT'),
            ('treatment_type', 'TEXT'),
            ('treatment_duration', 'TEXT'),
            ('treatment_details', 'TEXT'),
            ('medication_list', 'TEXT'),
            ('supplements_list', 'TEXT'),
            ('allergens', 'TEXT'),
            ('diseases', 'TEXT'),
            ('treatments', 'TEXT'),
            ('notes', 'TEXT'),
            ('created_at', 'TEXT'),
            # Nowe pola pielęgnacji domowej
            ('current_shampoo', 'TEXT'),
            ('uses_peeling', 'INTEGER DEFAULT 0'),
            ('peeling_details', 'TEXT'),
            ('uses_minoxidil', 'INTEGER DEFAULT 0'),
            ('minoxidil_details', 'TEXT'),
            ('hair_styling', 'TEXT'),
            ('styling_details', 'TEXT'),
            ('other_treatments', 'TEXT'),
            ('habits', 'TEXT')
        ]
        
        for col_name, col_type in missing_columns:
            if col_name not in columns:
                try:
                    print(f"Adding missing column: {col_name}")
                    cursor.execute(f"ALTER TABLE patients ADD COLUMN {col_name} {col_type}")
                except sqlite3.Error as e:
                    print(f"Error adding column {col_name}: {str(e)}")
        
        conn.commit()
        conn.close()
        
        # Create payments table for billing management
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_pesel TEXT NOT NULL,
                payment_date TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'PLN',
                payment_type TEXT NOT NULL,
                reference_id TEXT,
                reference_type TEXT,
                description TEXT,
                status TEXT DEFAULT 'paid',
                payment_method TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (patient_pesel) REFERENCES patients(pesel)
            )
        ''')
        
        # Create visits table for billing
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pesel TEXT NOT NULL,
                visit_date TEXT NOT NULL,
                visit_type TEXT DEFAULT 'consultation',
                purpose TEXT,
                diagnosis TEXT,
                treatments TEXT,
                recommendations TEXT,
                notes TEXT,
                images TEXT,
                cost REAL DEFAULT 0,
                paid_amount REAL DEFAULT 0,
                external_id TEXT,
                source TEXT DEFAULT 'internal',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pesel) REFERENCES patients(pesel)
            )
        ''')
        
        # Check if visits table has all required columns, add if missing
        cursor.execute("PRAGMA table_info(visits)")
        visits_columns = {row[1] for row in cursor.fetchall()}
        
        visits_missing_columns = [
            ('cost', 'REAL'),
            ('paid_amount', 'REAL'),
            ('external_id', 'TEXT'),
            ('source', 'TEXT'),
            ('created_at', 'TEXT'),
            ('updated_at', 'TEXT'),
            ('purpose', 'TEXT'),
            ('diagnosis', 'TEXT'),
            ('treatments', 'TEXT'),
            ('recommendations', 'TEXT'),
            ('notes', 'TEXT'),
            ('images', 'TEXT')
        ]
        
        for col_name, col_type in visits_missing_columns:
            if col_name not in visits_columns:
                try:
                    print(f"Adding missing column to visits: {col_name}")
                    cursor.execute(f"ALTER TABLE visits ADD COLUMN {col_name} {col_type}")
                except sqlite3.Error as e:
                    print(f"Error adding visits column {col_name}: {str(e)}")
        
        # Dodaj indeks dla lepszej wydajności
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_visits_external ON visits(external_id, source)")
            print("Creating index for external visits")
        except sqlite3.OperationalError:
            pass
        
        # Aktualizuj istniejące rekordy z pustymi timestampami i wartościami domyślnymi
        try:
            current_time = datetime.now().isoformat()
            cursor.execute("""
                UPDATE visits SET 
                    created_at = ?, 
                    updated_at = ?,
                    cost = COALESCE(cost, 0),
                    paid_amount = COALESCE(paid_amount, 0),
                    source = COALESCE(source, 'internal')
                WHERE created_at IS NULL OR created_at = '' OR cost IS NULL OR paid_amount IS NULL OR source IS NULL
            """, (current_time, current_time))
            if cursor.rowcount > 0:
                print(f"Updated {cursor.rowcount} visits with timestamps and default values")
        except sqlite3.Error as e:
            print(f"Error updating timestamps: {str(e)}")
        
        # Create treatment_pricing table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS treatment_pricing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_pesel TEXT NOT NULL,
                treatment_name TEXT NOT NULL,
                treatment_type TEXT,
                price REAL NOT NULL,
                paid_amount REAL DEFAULT 0,
                reference_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (patient_pesel) REFERENCES patients(pesel)
            )
        ''')
        
        # Create product_sales table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_pesel TEXT NOT NULL,
                product_name TEXT NOT NULL,
                product_type TEXT,
                quantity INTEGER DEFAULT 1,
                unit_price REAL NOT NULL,
                total_price REAL NOT NULL,
                paid_amount REAL DEFAULT 0,
                sale_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (patient_pesel) REFERENCES patients(pesel)
            )
        ''')
        
        # Create available_treatments table for managing treatment types and prices
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS available_treatments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL,
                default_price REAL NOT NULL,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Insert default treatments if table is empty
        cursor.execute('SELECT COUNT(*) FROM available_treatments')
        if cursor.fetchone()[0] == 0:
            default_treatments = [
                ('Mezoterapia mikroigłowa', 'mesotherapy', 300.0, 'Wprowadzanie substancji aktywnych do skóry głowy za pomocą mikroigieł'),
                ('Terapia laserowa', 'laser', 200.0, 'Nieinwazyjne leczenie laserowe pobudzające wzrost włosów'),
                ('Mikronakłuwanie (microneedling)', 'microneedling', 250.0, 'Stymulacja skóry głowy za pomocą mikronakłuć'),
                ('Karboksyterapia', 'carboxytherapy', 180.0, 'Terapia z użyciem dwutlenku węgla'),
                ('Terapia PRP', 'prp', 400.0, 'Osocze bogatopłytkowe z krwi własnej pacjenta'),
                ('Terapia LED', 'led', 100.0, 'Fototerapia LED stymulująca wzrost włosów'),
                ('Masaż skóry głowy', 'massage', 150.0, 'Terapeutyczny masaż poprawiający krążenie'),
                ('Zastrzyki witaminowe', 'injection', 350.0, 'Docelowe zastrzyki z witaminami i minerałami'),
                ('Peeling skóry głowy', 'peeling', 120.0, 'Oczyszczanie i złuszczanie skóry głowy'),
                ('Konsultacja trychologiczna', 'consultation', 80.0, 'Badanie i konsultacja specjalistyczna')
            ]
            
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for name, treatment_type, price, description in default_treatments:
                cursor.execute('''
                    INSERT INTO available_treatments (name, type, default_price, description, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (name, treatment_type, price, description, current_time, current_time))
        
        # Create users table for authentication
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                role TEXT DEFAULT 'trichologist',
                is_active INTEGER DEFAULT 1,
                google_id TEXT,
                profile_picture TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Create sessions table for managing user sessions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Add new columns to users table for invitation system
        cursor.execute("PRAGMA table_info(users)")
        users_columns = {row[1] for row in cursor.fetchall()}
        
        users_new_columns = [
            ('invited_by', 'INTEGER'),
            ('invited_at', 'TEXT'),
            ('first_login_at', 'TEXT'),
            ('last_login_at', 'TEXT'),
            ('invitation_status', 'TEXT DEFAULT "pending"')  # pending, accepted, revoked
        ]
        
        for col_name, col_type in users_new_columns:
            if col_name not in users_columns:
                try:
                    print(f"Adding missing column to users: {col_name}")
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                except sqlite3.Error as e:
                    print(f"Error adding users column {col_name}: {str(e)}")
        
        # Update existing users table to use new role system (admin/user instead of trichologist)
        try:
            cursor.execute("UPDATE users SET role = 'admin' WHERE role = 'trichologist' OR email LIKE '%admin%'")
            cursor.execute("UPDATE users SET role = 'user' WHERE role NOT IN ('admin', 'user')")
            if cursor.rowcount > 0:
                print(f"Updated {cursor.rowcount} users with new role system")
        except sqlite3.Error as e:
            print(f"Error updating user roles: {str(e)}")
        
        # Create default admin user if no users exist
        cursor.execute('SELECT COUNT(*) FROM users')
        if cursor.fetchone()[0] == 0:
            # Get admin email from environment variable, fallback to default
            admin_email = os.environ.get('ADMIN_EMAIL', 'admin@yourdomain.com')
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
                INSERT INTO users (email, password_hash, first_name, last_name, role, invitation_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (admin_email, '', 'Admin', 'Administrator', 'admin', 'accepted', current_time, current_time))
            
            if admin_email == 'admin@yourdomain.com':
                print("📧 Created default admin user: admin@yourdomain.com")
                print("⚠️  IMPORTANT: Change this email to your Google account email in Railway environment variables!")
                print("🔧 Set ADMIN_EMAIL=your-google-email@gmail.com in Railway Variables")
            else:
                print(f"✅ Created admin user: {admin_email}")
                print("🔒 Production admin user configured successfully!")
        
        conn.commit()
        conn.close()
        print("Database initialization completed successfully")
        return True
        
    except sqlite3.Error as e:
        print(f"SQLite error in init_db: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return False
    except Exception as e:
        print(f"Unexpected error in init_db: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return False

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
            patient_data['peeling_type'] = ''
            print("Added missing peeling_type field with empty string")
            
        if 'peeling_frequency' in patient_data:
            if patient_data['peeling_frequency'] is None or patient_data['peeling_frequency'] == 'null':
                patient_data['peeling_frequency'] = ''
                print("Set peeling_frequency from None/null to empty string")
        else:
            patient_data['peeling_frequency'] = ''
            print("Added missing peeling_frequency field with empty string")
            
        print(f"Peeling type after processing: {patient_data.get('peeling_type', 'NOT PROVIDED')}")
        print(f"Peeling frequency after processing: {patient_data.get('peeling_frequency', 'NOT PROVIDED')}")
        
        # Process JSON fields
        json_fields = ['medication_list', 'supplements_list', 'allergens', 'diseases', 'treatments']
        for field in json_fields:
            if field in patient_data:
                # If it's already a dict or list, convert to JSON string
                if isinstance(patient_data[field], (dict, list)):
                    patient_data[field] = json.dumps(patient_data[field], ensure_ascii=False)
                    print(f"Converted {field} to JSON string")
                # If it's a string but not a valid JSON, ensure it's a valid JSON string
                elif isinstance(patient_data[field], str):
                    try:
                        # Try to parse it as JSON to validate
                        json.loads(patient_data[field])
                        # If it works, it's already a valid JSON string
                    except json.JSONDecodeError:
                        # If it's not a valid JSON string, make it an empty array
                        patient_data[field] = '[]'
                        print(f"Set invalid JSON in {field} to empty array")
                else:
                    # If it's None or other type, set to empty array
                    patient_data[field] = '[]'
                    print(f"Set {field} to empty array because it was {type(patient_data[field])}")
        
        # Process text fields
        text_fields = ['name', 'surname', 'pesel', 'phone', 'email', 'birthdate', 'gender', 'height', 'weight']
        for field in text_fields:
            if field in patient_data:
                if patient_data[field] is None:
                    patient_data[field] = ''
                    print(f"Set {field} from None to empty string")
                # Ensure it's a string
                patient_data[field] = str(patient_data[field])
        
        # Add creation timestamp
        patient_data['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Remove fields that should be skipped
        fields_to_skip = ['csrfmiddlewaretoken', 'medication_name', 'medication_dose', 'medication_schedule', 
                         'supplement_name', 'supplement_dose', 'supplement_schedule']
        for field in fields_to_skip:
            if field in patient_data:
                patient_data.pop(field)
                print(f"Removed field: {field}")
        
        # Get database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get table schema to check fields
        cursor.execute("PRAGMA table_info(patients)")
        schema = cursor.fetchall()
        schema_columns = {col[1] for col in schema}
        
        # Check if all fields in patient_data exist in schema
        for field in list(patient_data.keys()):
            if field not in schema_columns:
                print(f"Warning: Field '{field}' not in database schema, removing")
                patient_data.pop(field)
        
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
        print(f"With values: {values}")
        
        # Execute query
        cursor.execute(query, values)
        conn.commit()
        
        print("Patient data saved successfully")
        conn.close()
        
        return {'success': True}
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
        import traceback
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
        
        # Process JSON fields
        json_fields = ['medication_list', 'supplements_list', 'allergens', 'diseases', 'treatments', 'hair_styling', 'habits']
        for field in json_fields:
            if field in patient_data and patient_data[field]:
                try:
                    patient_data[field] = json.loads(patient_data[field])
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON for field {field}: {str(e)}")
                    patient_data[field] = []
            else:
                patient_data[field] = []
        
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
        
        cursor.execute('SELECT pesel, name, surname, phone, email FROM patients')
        rows = cursor.fetchall()
        
        patients = []
        for row in rows:
            column_names = ['pesel', 'name', 'surname', 'phone', 'email']
            patient = dict(zip(column_names, row))
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
        
        cursor.execute('''
            SELECT pesel, name, surname, phone, email
            FROM patients
            WHERE pesel LIKE ? OR name LIKE ? OR surname LIKE ?
            ORDER BY surname, name
        ''', (search_pattern, search_pattern, search_pattern))
        
        rows = cursor.fetchall()
        
        patients = []
        for row in rows:
            column_names = ['pesel', 'name', 'surname', 'phone', 'email']
            patient = dict(zip(column_names, row))
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

# =============================================================================
# PAYMENT MANAGEMENT FUNCTIONS
# =============================================================================

def add_payment(patient_pesel, amount, payment_type, description="", reference_id=None, reference_type=None, payment_method="cash", notes=""):
    """
    Add a new payment record.
    Returns payment ID if successful, None otherwise.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO payments (patient_pesel, payment_date, amount, payment_type, description, 
                                reference_id, reference_type, payment_method, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (patient_pesel, now, amount, payment_type, description, reference_id, reference_type, payment_method, notes, now, now))
        
        payment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return payment_id
        
    except sqlite3.Error as e:
        print(f"SQLite error in add_payment: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return None
    except Exception as e:
        print(f"Unexpected error in add_payment: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return None

def get_patient_payments(patient_pesel):
    """
    Get all payments for a patient.
    Returns list of payments or empty list if none found.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM payments 
            WHERE patient_pesel = ? 
            ORDER BY payment_date DESC
        ''', (patient_pesel,))
        
        rows = cursor.fetchall()
        
        payments = []
        for row in rows:
            column_names = [description[0] for description in cursor.description]
            payment = dict(zip(column_names, row))
            payments.append(payment)
        
        conn.close()
        return payments
        
    except sqlite3.Error as e:
        print(f"SQLite error in get_patient_payments: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return []
    except Exception as e:
        print(f"Unexpected error in get_patient_payments: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return []

def get_payment_summary(patient_pesel):
    """
    Get payment summary for a patient.
    Returns dict with totals and balances.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get total paid amount
        cursor.execute('''
            SELECT SUM(amount) as total_paid
            FROM payments 
            WHERE patient_pesel = ? AND status = 'paid'
        ''', (patient_pesel,))
        
        total_paid = cursor.fetchone()[0] or 0
        
        # Get treatment costs
        cursor.execute('''
            SELECT SUM(price) as total_treatments, SUM(paid_amount) as paid_treatments
            FROM treatment_pricing 
            WHERE patient_pesel = ?
        ''', (patient_pesel,))
        
        treatment_data = cursor.fetchone()
        total_treatments = treatment_data[0] or 0
        paid_treatments = treatment_data[1] or 0
        
        # Get product sales
        cursor.execute('''
            SELECT SUM(total_price) as total_products, SUM(paid_amount) as paid_products
            FROM product_sales 
            WHERE patient_pesel = ?
        ''', (patient_pesel,))
        
        product_data = cursor.fetchone()
        total_products = product_data[0] or 0
        paid_products = product_data[1] or 0
        
        # Get visits
        cursor.execute('''
            SELECT SUM(cost) as total_visits, SUM(paid_amount) as paid_visits
            FROM visits 
            WHERE pesel = ?
        ''', (patient_pesel,))
        
        visit_data = cursor.fetchone()
        total_visits = visit_data[0] or 0
        paid_visits = visit_data[1] or 0
        
        conn.close()
        
        total_due = total_treatments + total_products + total_visits
        total_paid_specific = paid_treatments + paid_products + paid_visits
        balance = total_paid - total_due
        
        return {
            'total_paid': total_paid,
            'total_due': total_due,
            'balance': balance,
            'treatments': {
                'total': total_treatments,
                'paid': paid_treatments,
                'outstanding': total_treatments - paid_treatments
            },
            'products': {
                'total': total_products,
                'paid': paid_products,
                'outstanding': total_products - paid_products
            },
            'visits': {
                'total': total_visits,
                'paid': paid_visits,
                'outstanding': total_visits - paid_visits
            }
        }
        
    except sqlite3.Error as e:
        print(f"SQLite error in get_payment_summary: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return {}
    except Exception as e:
        print(f"Unexpected error in get_payment_summary: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return {}

def add_visit(patient_pesel, visit_date, visit_type="consultation", description="", cost=0):
    """
    Add a new visit record.
    Returns visit ID if successful, None otherwise.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO visits (pesel, visit_date, visit_type, purpose, cost, paid_amount)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (patient_pesel, visit_date, visit_type, description, cost, 0))
        
        visit_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return visit_id
        
    except sqlite3.Error as e:
        print(f"SQLite error in add_visit: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return None
    except Exception as e:
        print(f"Unexpected error in add_visit: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return None

def get_patient_visits(patient_pesel):
    """
    Get all visits for a patient.
    Returns list of visits or empty list if none found.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM visits 
            WHERE pesel = ? 
            ORDER BY visit_date DESC
        ''', (patient_pesel,))
        
        rows = cursor.fetchall()
        
        visits = []
        for row in rows:
            column_names = [description[0] for description in cursor.description]
            visit = dict(zip(column_names, row))
            visits.append(visit)
        
        conn.close()
        return visits
        
    except sqlite3.Error as e:
        print(f"SQLite error in get_patient_visits: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return []
    except Exception as e:
        print(f"Unexpected error in get_patient_visits: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return []

def add_treatment_pricing(patient_pesel, treatment_name, treatment_type, price, reference_id=None):
    """
    Add treatment pricing for a patient.
    Returns pricing ID if successful, None otherwise.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO treatment_pricing (patient_pesel, treatment_name, treatment_type, price, reference_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (patient_pesel, treatment_name, treatment_type, price, reference_id, now, now))
        
        pricing_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return pricing_id
        
    except sqlite3.Error as e:
        print(f"SQLite error in add_treatment_pricing: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return None
    except Exception as e:
        print(f"Unexpected error in add_treatment_pricing: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return None

def get_patient_treatments(patient_pesel):
    """
    Get all treatment pricing for a patient.
    Returns list of treatments or empty list if none found.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM treatment_pricing 
            WHERE patient_pesel = ? 
            ORDER BY created_at DESC
        ''', (patient_pesel,))
        
        rows = cursor.fetchall()
        
        treatments = []
        for row in rows:
            column_names = [description[0] for description in cursor.description]
            treatment = dict(zip(column_names, row))
            treatments.append(treatment)
        
        conn.close()
        return treatments
        
    except sqlite3.Error as e:
        print(f"SQLite error in get_patient_treatments: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return []
    except Exception as e:
        print(f"Unexpected error in get_patient_treatments: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return []

def update_payment_for_item(patient_pesel, item_type, item_id, amount):
    """
    Update paid amount for specific item (treatment, visit, product).
    Returns True if successful, False otherwise.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if item_type == 'treatment':
            cursor.execute('''
                UPDATE treatment_pricing 
                SET paid_amount = paid_amount + ?, updated_at = ?
                WHERE id = ? AND patient_pesel = ?
            ''', (amount, now, item_id, patient_pesel))
        elif item_type == 'visit':
            cursor.execute('''
                UPDATE visits 
                SET paid_amount = paid_amount + ?
                WHERE id = ? AND pesel = ?
            ''', (amount, item_id, patient_pesel))
        elif item_type == 'product':
            cursor.execute('''
                UPDATE product_sales 
                SET paid_amount = paid_amount + ?, updated_at = ?
                WHERE id = ? AND patient_pesel = ?
            ''', (amount, now, item_id, patient_pesel))
        else:
            return False
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
        
    except sqlite3.Error as e:
        print(f"SQLite error in update_payment_for_item: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return False
    except Exception as e:
        print(f"Unexpected error in update_payment_for_item: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return False

def sync_clinic_treatments_to_billing(patient_pesel):
    """
    Synchronize clinic treatments to billing system.
    Adds treatments from clinic plan to treatment_pricing table if they don't exist.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get clinic treatments that are not yet in billing system
        cursor.execute('''
            SELECT DISTINCT ct.treatment_name, ct.treatment_type, ct.quantity, cp.pesel, ct.id
            FROM clinic_treatments ct
            JOIN clinic_treatment_plans cp ON ct.plan_id = cp.id
            WHERE cp.pesel = ?
            AND NOT EXISTS (
                SELECT 1 FROM treatment_pricing tp 
                WHERE tp.patient_pesel = cp.pesel 
                AND tp.treatment_name = ct.treatment_name 
                AND tp.treatment_type = ct.treatment_type
                AND tp.reference_id = ct.id
            )
        ''', (patient_pesel,))
        
        treatments = cursor.fetchall()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Add treatments to billing system
        for treatment in treatments:
            treatment_name = treatment[0]
            treatment_type = treatment[1]
            quantity = treatment[2]
            
            # Get price from available_treatments table by name
            price = get_treatment_price(treatment_name)
            if price is None:
                # Fallback to default prices if treatment not found in available_treatments
                default_prices = {
                    'injection': 350.0,
                    'laser': 200.0,
                    'massage': 150.0,
                    'mesotherapy': 300.0,
                    'led': 100.0,
                    'microneedling': 250.0,
                    'prp': 400.0,
                    'carboxytherapy': 180.0,
                    'peeling': 120.0,
                    'consultation': 80.0,
                    'other': 100.0
                }
                price = default_prices.get(treatment_type, 100.0)
            
            total_price = price * quantity
            
            cursor.execute('''
                INSERT INTO treatment_pricing (patient_pesel, treatment_name, treatment_type, price, reference_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (patient_pesel, treatment_name, treatment_type, total_price, treatment[4], now, now))
        
        conn.commit()
        conn.close()
        
        return len(treatments)
        
    except sqlite3.Error as e:
        print(f"SQLite error in sync_clinic_treatments_to_billing: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return 0
    except Exception as e:
        print(f"Unexpected error in sync_clinic_treatments_to_billing: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return 0

def get_patient_visits_for_billing(patient_pesel):
    """
    Get all visits for a patient that have costs > 0 for billing system.
    Returns list of visits or empty list if none found.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, visit_date, visit_type, purpose, cost, paid_amount,
                   (cost - COALESCE(paid_amount, 0)) as outstanding
            FROM visits 
            WHERE pesel = ? AND COALESCE(cost, 0) > 0
            ORDER BY visit_date DESC
        ''', (patient_pesel,))
        
        rows = cursor.fetchall()
        
        visits = []
        for row in rows:
            visits.append({
                'id': row[0],
                'visit_date': row[1],
                'visit_type': row[2],
                'description': row[3],
                'cost': row[4],
                'paid_amount': row[5] or 0,
                'outstanding': row[6],
                'status': 'paid' if row[6] <= 0 else 'unpaid'
            })
        
        conn.close()
        return visits
        
    except sqlite3.Error as e:
        print(f"SQLite error in get_patient_visits_for_billing: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return []
    except Exception as e:
        print(f"Unexpected error in get_patient_visits_for_billing: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return []

# === AVAILABLE TREATMENTS MANAGEMENT ===

def get_available_treatments():
    """
    Get all available treatments for selection in care plans.
    Returns list of available treatments or empty list if none found.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, type, default_price, description, is_active, created_at, updated_at
            FROM available_treatments 
            WHERE is_active = 1
            ORDER BY name ASC
        ''')
        
        rows = cursor.fetchall()
        
        treatments = []
        for row in rows:
            treatments.append({
                'id': row[0],
                'name': row[1],
                'type': row[2],
                'default_price': row[3],
                'description': row[4],
                'is_active': row[5],
                'created_at': row[6],
                'updated_at': row[7]
            })
        
        conn.close()
        return treatments
        
    except sqlite3.Error as e:
        print(f"SQLite error in get_available_treatments: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return []
    except Exception as e:
        print(f"Unexpected error in get_available_treatments: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return []

def add_available_treatment(name, treatment_type, default_price, description=""):
    """
    Add new available treatment.
    Returns dict with success/error information.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO available_treatments (name, type, default_price, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, treatment_type, default_price, description, current_time, current_time))
        
        treatment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {'success': True, 'id': treatment_id}
        
    except sqlite3.IntegrityError as e:
        if 'UNIQUE constraint failed' in str(e):
            return {'success': False, 'error': 'Zabieg o tej nazwie już istnieje'}
        return {'success': False, 'error': f'Błąd integralności danych: {str(e)}'}
    except sqlite3.Error as e:
        print(f"SQLite error in add_available_treatment: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Błąd bazy danych: {str(e)}'}
    except Exception as e:
        print(f"Unexpected error in add_available_treatment: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Nieoczekiwany błąd: {str(e)}'}

def update_available_treatment(treatment_id, name=None, treatment_type=None, default_price=None, description=None, is_active=None):
    """
    Update existing available treatment.
    Returns dict with success/error information.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if treatment exists
        cursor.execute('SELECT 1 FROM available_treatments WHERE id = ?', (treatment_id,))
        if not cursor.fetchone():
            conn.close()
            return {'success': False, 'error': 'Zabieg nie znaleziony'}
        
        # Build update query
        updates = []
        values = []
        
        if name is not None:
            updates.append('name = ?')
            values.append(name)
        if treatment_type is not None:
            updates.append('type = ?')
            values.append(treatment_type)
        if default_price is not None:
            updates.append('default_price = ?')
            values.append(default_price)
        if description is not None:
            updates.append('description = ?')
            values.append(description)
        if is_active is not None:
            updates.append('is_active = ?')
            values.append(is_active)
        
        if not updates:
            conn.close()
            return {'success': False, 'error': 'Brak danych do aktualizacji'}
        
        # Add updated_at
        updates.append('updated_at = ?')
        values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        values.append(treatment_id)
        
        query = f"UPDATE available_treatments SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, values)
        
        conn.commit()
        conn.close()
        
        return {'success': True}
        
    except sqlite3.IntegrityError as e:
        if 'UNIQUE constraint failed' in str(e):
            return {'success': False, 'error': 'Zabieg o tej nazwie już istnieje'}
        return {'success': False, 'error': f'Błąd integralności danych: {str(e)}'}
    except sqlite3.Error as e:
        print(f"SQLite error in update_available_treatment: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Błąd bazy danych: {str(e)}'}
    except Exception as e:
        print(f"Unexpected error in update_available_treatment: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Nieoczekiwany błąd: {str(e)}'}

def delete_available_treatment(treatment_id):
    """
    Delete (deactivate) available treatment.
    Returns dict with success/error information.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if treatment exists
        cursor.execute('SELECT 1 FROM available_treatments WHERE id = ?', (treatment_id,))
        if not cursor.fetchone():
            conn.close()
            return {'success': False, 'error': 'Zabieg nie znaleziony'}
        
        # Deactivate instead of deleting to preserve data integrity
        cursor.execute('''
            UPDATE available_treatments 
            SET is_active = 0, updated_at = ?
            WHERE id = ?
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), treatment_id))
        
        conn.commit()
        conn.close()
        
        return {'success': True}
        
    except sqlite3.Error as e:
        print(f"SQLite error in delete_available_treatment: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Błąd bazy danych: {str(e)}'}
    except Exception as e:
        print(f"Unexpected error in delete_available_treatment: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Nieoczekiwany błąd: {str(e)}'}

def get_treatment_price(treatment_name):
    """
    Get default price for a treatment by name.
    Returns price or None if not found.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT default_price FROM available_treatments 
            WHERE name = ? AND is_active = 1
        ''', (treatment_name,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
        
    except sqlite3.Error as e:
        print(f"SQLite error in get_treatment_price: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None
    except Exception as e:
        print(f"Unexpected error in get_treatment_price: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None

# =============================================================================
# USER AUTHENTICATION AND SESSION MANAGEMENT
# =============================================================================

def create_user(email, password, first_name, last_name, role='trichologist', google_id=None):
    """
    Create a new user account.
    Returns dict with success/error information and user_id.
    """
    try:
        import hashlib
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            return {'success': False, 'error': 'Użytkownik z tym emailem już istnieje'}
        
        # Hash password
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO users (email, password_hash, first_name, last_name, role, google_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (email, password_hash, first_name, last_name, role, google_id, current_time, current_time))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {'success': True, 'user_id': user_id}
        
    except sqlite3.Error as e:
        print(f"SQLite error in create_user: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Błąd bazy danych: {str(e)}'}
    except Exception as e:
        print(f"Unexpected error in create_user: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Nieoczekiwany błąd: {str(e)}'}

def authenticate_user(email, password):
    """
    Authenticate user by email and password.
    Returns user data if successful, None otherwise.
    """
    try:
        import hashlib
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        cursor.execute('''
            SELECT id, email, first_name, last_name, role, is_active, profile_picture
            FROM users 
            WHERE email = ? AND password_hash = ? AND is_active = 1
        ''', (email, password_hash))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'email': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'role': row[4],
                'is_active': row[5],
                'profile_picture': row[6]
            }
        
        return None
        
    except sqlite3.Error as e:
        print(f"SQLite error in authenticate_user: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None
    except Exception as e:
        print(f"Unexpected error in authenticate_user: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None

def get_user_by_id(user_id):
    """
    Get user data by ID.
    Returns user data or None if not found.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, email, first_name, last_name, role, is_active, profile_picture, google_id
            FROM users 
            WHERE id = ? AND is_active = 1
        ''', (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'email': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'role': row[4],
                'is_active': row[5],
                'profile_picture': row[6],
                'google_id': row[7]
            }
        
        return None
        
    except sqlite3.Error as e:
        print(f"SQLite error in get_user_by_id: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None
    except Exception as e:
        print(f"Unexpected error in get_user_by_id: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None

def get_user_by_google_id(google_id):
    """
    Get user data by Google ID.
    Returns user data or None if not found.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, email, first_name, last_name, role, is_active, profile_picture
            FROM users 
            WHERE google_id = ? AND is_active = 1
        ''', (google_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'email': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'role': row[4],
                'is_active': row[5],
                'profile_picture': row[6],
                'google_id': google_id
            }
        
        return None
        
    except sqlite3.Error as e:
        print(f"SQLite error in get_user_by_google_id: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None
    except Exception as e:
        print(f"Unexpected error in get_user_by_google_id: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None

def create_session(user_id):
    """
    Create a new session for user.
    Returns session token or None if failed.
    """
    try:
        import secrets
        from datetime import timedelta
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Generate session token
        session_token = secrets.token_urlsafe(32)
        
        # Set expiration to 30 days from now
        expires_at = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO sessions (user_id, session_token, expires_at, created_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, session_token, expires_at, created_at))
        
        conn.commit()
        conn.close()
        
        return session_token
        
    except sqlite3.Error as e:
        print(f"SQLite error in create_session: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return None
    except Exception as e:
        print(f"Unexpected error in create_session: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return None

def get_session_user(session_token):
    """
    Get user data from valid session token.
    Returns user data or None if session invalid/expired.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            SELECT u.id, u.email, u.first_name, u.last_name, u.role, u.is_active, u.profile_picture
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.session_token = ? AND s.expires_at > ? AND u.is_active = 1
        ''', (session_token, current_time))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'email': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'role': row[4],
                'is_active': row[5],
                'profile_picture': row[6]
            }
        
        return None
        
    except sqlite3.Error as e:
        print(f"SQLite error in get_session_user: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None
    except Exception as e:
        print(f"Unexpected error in get_session_user: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None

def delete_session(session_token):
    """
    Delete/invalidate a session.
    Returns True if successful, False otherwise.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM sessions WHERE session_token = ?', (session_token,))
        
        conn.commit()
        conn.close()
        
        return True
        
    except sqlite3.Error as e:
        print(f"SQLite error in delete_session: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return False
    except Exception as e:
        print(f"Unexpected error in delete_session: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return False

def cleanup_expired_sessions():
    """
    Clean up expired sessions.
    Returns number of deleted sessions.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('DELETE FROM sessions WHERE expires_at <= ?', (current_time,))
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return deleted_count
        
    except sqlite3.Error as e:
        print(f"SQLite error in cleanup_expired_sessions: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return 0
    except Exception as e:
        print(f"Unexpected error in cleanup_expired_sessions: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return 0

def update_user_profile(user_id, first_name=None, last_name=None, email=None, profile_picture=None):
    """
    Update user profile information.
    Returns dict with success/error information.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT 1 FROM users WHERE id = ?', (user_id,))
        if not cursor.fetchone():
            conn.close()
            return {'success': False, 'error': 'Użytkownik nie znaleziony'}
        
        # Build update query
        updates = []
        values = []
        
        if first_name is not None:
            updates.append('first_name = ?')
            values.append(first_name)
        if last_name is not None:
            updates.append('last_name = ?')
            values.append(last_name)
        if email is not None:
            updates.append('email = ?')
            values.append(email)
        if profile_picture is not None:
            updates.append('profile_picture = ?')
            values.append(profile_picture)
        
        if not updates:
            conn.close()
            return {'success': False, 'error': 'Brak danych do aktualizacji'}
        
        # Add updated_at
        updates.append('updated_at = ?')
        values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        values.append(user_id)
        
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, values)
        
        conn.commit()
        conn.close()
        
        return {'success': True}
        
    except sqlite3.IntegrityError as e:
        if 'UNIQUE constraint failed' in str(e):
            return {'success': False, 'error': 'Użytkownik z tym emailem już istnieje'}
        return {'success': False, 'error': f'Błąd integralności danych: {str(e)}'}
    except sqlite3.Error as e:
        print(f"SQLite error in update_user_profile: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Błąd bazy danych: {str(e)}'}
    except Exception as e:
        print(f"Unexpected error in update_user_profile: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Nieoczekiwany błąd: {str(e)}'}

def change_user_password(user_id, new_password):
    """
    Change user password.
    Returns dict with success/error information.
    """
    try:
        import hashlib
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute('SELECT 1 FROM users WHERE id = ?', (user_id,))
        if not cursor.fetchone():
            conn.close()
            return {'success': False, 'error': 'Użytkownik nie znaleziony'}
        
        # Hash new password
        password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            UPDATE users SET password_hash = ?, updated_at = ?
            WHERE id = ?
        ''', (password_hash, updated_at, user_id))
        
        conn.commit()
        conn.close()
        
        return {'success': True}
        
    except sqlite3.Error as e:
        print(f"SQLite error in change_user_password: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Błąd bazy danych: {str(e)}'}
    except Exception as e:
        print(f"Unexpected error in change_user_password: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Nieoczekiwany błąd: {str(e)}'}

# =============================================================================
# GOOGLE OAUTH & INVITATION SYSTEM FUNCTIONS
# =============================================================================

def is_user_allowed(email):
    """
    Check if email is allowed to login (invited or admin)
    Returns user data if allowed, None otherwise
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, email, first_name, last_name, role, is_active, google_id, invitation_status
            FROM users 
            WHERE email = ? AND is_active = 1 AND invitation_status = 'accepted'
        ''', (email,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'email': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'role': row[4],
                'is_active': row[5],
                'google_id': row[6],
                'invitation_status': row[7]
            }
        
        return None
        
    except sqlite3.Error as e:
        print(f"SQLite error in is_user_allowed: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None

def get_or_create_google_user_new(google_id, email, first_name, last_name, picture=None):
    """
    Get existing Google user or create if email is on allowed list
    Returns user data if successful, None if not allowed
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First check if user exists by google_id
        cursor.execute('''
            SELECT id, email, first_name, last_name, role, is_active, google_id
            FROM users 
            WHERE google_id = ? AND is_active = 1
        ''', (google_id,))
        
        existing_user = cursor.fetchone()
        if existing_user:
            # Update last login
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('UPDATE users SET last_login_at = ? WHERE id = ?', 
                          (current_time, existing_user[0]))
            conn.commit()
            conn.close()
            
            return {
                'id': existing_user[0],
                'email': existing_user[1],
                'first_name': existing_user[2],
                'last_name': existing_user[3],
                'role': existing_user[4],
                'is_active': existing_user[5],
                'google_id': existing_user[6]
            }
        
        # Check if email is on allowed list
        cursor.execute('''
            SELECT id, role, invitation_status
            FROM users 
            WHERE email = ? AND is_active = 1
        ''', (email,))
        
        allowed_user = cursor.fetchone()
        if not allowed_user or allowed_user[2] != 'accepted':
            conn.close()
            return None  # User not invited or invitation not accepted
        
        # Update existing user with Google ID (first login)
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE users SET 
                google_id = ?, 
                first_name = ?, 
                last_name = ?, 
                profile_picture = ?,
                first_login_at = ?,
                last_login_at = ?,
                updated_at = ?
            WHERE email = ?
        ''', (google_id, first_name, last_name, picture, current_time, current_time, current_time, email))
        
        conn.commit()
        
        # Get updated user data
        cursor.execute('''
            SELECT id, email, first_name, last_name, role, is_active, google_id
            FROM users 
            WHERE email = ?
        ''', (email,))
        
        user_row = cursor.fetchone()
        conn.close()
        
        if user_row:
            return {
                'id': user_row[0],
                'email': user_row[1],
                'first_name': user_row[2],
                'last_name': user_row[3],
                'role': user_row[4],
                'is_active': user_row[5],
                'google_id': user_row[6]
            }
        
        return None
        
    except sqlite3.Error as e:
        print(f"SQLite error in get_or_create_google_user_new: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return None

def invite_user(admin_id, email, first_name='', last_name='', role='user'):
    """
    Invite a new user to the system (admin only)
    Returns dict with success/error information
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if inviter is admin
        cursor.execute('SELECT role FROM users WHERE id = ?', (admin_id,))
        admin_role = cursor.fetchone()
        if not admin_role or admin_role[0] != 'admin':
            conn.close()
            return {'success': False, 'error': 'Tylko admin może zapraszać użytkowników'}
        
        # Check if user already exists
        cursor.execute('SELECT id, invitation_status FROM users WHERE email = ?', (email,))
        existing = cursor.fetchone()
        if existing:
            if existing[1] == 'accepted':
                conn.close()
                return {'success': False, 'error': 'Użytkownik już istnieje w systemie'}
            elif existing[1] == 'pending':
                conn.close()
                return {'success': False, 'error': 'Zaproszenie już zostało wysłane'}
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if existing:
            # Update existing invitation
            cursor.execute('''
                UPDATE users SET 
                    first_name = ?, 
                    last_name = ?, 
                    role = ?, 
                    invited_by = ?, 
                    invited_at = ?,
                    invitation_status = 'pending',
                    updated_at = ?
                WHERE email = ?
            ''', (first_name, last_name, role, admin_id, current_time, current_time, email))
        else:
            # Create new invitation
            cursor.execute('''
                INSERT INTO users (email, first_name, last_name, role, invited_by, invited_at, invitation_status, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', 1, ?, ?)
            ''', (email, first_name, last_name, role, admin_id, current_time, current_time, current_time))
        
        conn.commit()
        conn.close()
        
        return {'success': True, 'message': f'Zaproszenie wysłane do {email}'}
        
    except sqlite3.Error as e:
        print(f"SQLite error in invite_user: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Błąd bazy danych: {str(e)}'}

def get_all_users(admin_id):
    """
    Get all users (admin only)
    Returns list of users or None if not admin
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if requester is admin
        cursor.execute('SELECT role FROM users WHERE id = ?', (admin_id,))
        admin_role = cursor.fetchone()
        if not admin_role or admin_role[0] != 'admin':
            conn.close()
            return None
        
        cursor.execute('''
            SELECT id, email, first_name, last_name, role, is_active, 
                   invitation_status, invited_at, first_login_at, last_login_at
            FROM users 
            ORDER BY created_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        users = []
        for row in rows:
            users.append({
                'id': row[0],
                'email': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'role': row[4],
                'is_active': row[5],
                'invitation_status': row[6],
                'invited_at': row[7],
                'first_login_at': row[8],
                'last_login_at': row[9]
            })
        
        return users
        
    except sqlite3.Error as e:
        print(f"SQLite error in get_all_users: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return None

def remove_user(admin_id, user_id):
    """
    Remove/deactivate user (admin only)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if requester is admin
        cursor.execute('SELECT role FROM users WHERE id = ?', (admin_id,))
        admin_role = cursor.fetchone()
        if not admin_role or admin_role[0] != 'admin':
            conn.close()
            return {'success': False, 'error': 'Tylko admin może usuwać użytkowników'}
        
        # Don't allow admin to remove themselves
        if admin_id == user_id:
            conn.close()
            return {'success': False, 'error': 'Nie możesz usunąć samego siebie'}
        
        # Deactivate user instead of deleting
        cursor.execute('UPDATE users SET is_active = 0 WHERE id = ?', (user_id,))
        
        if cursor.rowcount == 0:
            conn.close()
            return {'success': False, 'error': 'Użytkownik nie znaleziony'}
        
        conn.commit()
        conn.close()
        
        return {'success': True, 'message': 'Użytkownik został usunięty'}
        
    except sqlite3.Error as e:
        print(f"SQLite error in remove_user: {str(e)}")
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
        return {'success': False, 'error': f'Błąd bazy danych: {str(e)}'} 