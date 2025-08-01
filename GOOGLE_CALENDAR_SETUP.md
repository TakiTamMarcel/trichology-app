#!/usr/bin/env python3
"""
Eksport kalendarza do formatu iCal (.ics) 
Alternatywa dla integracji Google Calendar API
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict
import uuid

class ICalExporter:
    """
    Klasa do eksportu wizyt do formatu iCal
    """
    
    def __init__(self, db_path: str = 'trichology.db'):
        self.db_path = db_path
    
    def get_visits(self, days_ahead: int = 90) -> List[Dict]:
        """
        Pobiera wizyty z bazy danych
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Pobierz wizyty z następnych X dni
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=days_ahead)
        
        cursor.execute("""
            SELECT v.id, v.pesel, v.visit_date, v.description, v.procedures,
                   p.name, p.surname, p.phone, p.email
            FROM visits v
            JOIN patients p ON v.pesel = p.pesel
            WHERE DATE(v.visit_date) >= DATE(?) AND DATE(v.visit_date) <= DATE(?)
            ORDER BY v.visit_date
        """, (start_date.isoformat(), end_date.isoformat()))
        
        visits = cursor.fetchall()
        conn.close()
        
        return [dict(visit) for visit in visits]
    
    def format_datetime_for_ical(self, dt_string: str) -> str:
        """
        Konwertuje datę na format iCal
        """
        try:
            if len(dt_string) <= 10:
                # Tylko data - dodaj domyślną godzinę
                dt = datetime.strptime(dt_string, "%Y-%m-%d")
                dt = dt.replace(hour=10, minute=0, second=0)
            else:
                # Data z czasem
                dt = datetime.strptime(dt_string, "%Y-%m-%d %H:%M:%S")
            
            # Format iCal: YYYYMMDDTHHMMSSZ
            return dt.strftime("%Y%m%dT%H%M%S")
            
        except ValueError:
            # Fallback
            dt = datetime.now().replace(hour=10, minute=0, second=0)
            return dt.strftime("%Y%m%dT%H%M%S")
    
    def generate_ical(self, visits: List[Dict]) -> str:
        """
        Generuje treść pliku iCal
        """
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0", 
            "PRODID:-//Aplikacja Trychologa//Kalendarz Wizyt//PL",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:Wizyty Trychologa",
            "X-WR-TIMEZONE:Europe/Warsaw",
            "X-WR-CALDESC:Kalendarz wizyt pacjentów - aplikacja trychologa"
        ]
        
        for visit in visits:
            visit_id = visit['id']
            pesel = visit['pesel']
            name = visit['name']
            surname = visit['surname']
            phone = visit.get('phone', 'Brak telefonu')
            email = visit.get('email', 'Brak emaila')
            visit_date = visit['visit_date']
            procedures = visit.get('procedures', '')
            description = visit.get('description', '')
            
            # Wygeneruj UID
            uid = f"visit-{visit_id}-{pesel}@trichology-app.local"
            
            # Sformatuj daty
            start_time = self.format_datetime_for_ical(visit_date)
            
            # Dodaj 1 godzinę na koniec wizyty
            try:
                if len(visit_date) <= 10:
                    dt_start = datetime.strptime(visit_date, "%Y-%m-%d")
                    dt_start = dt_start.replace(hour=10, minute=0)
                else:
                    dt_start = datetime.strptime(visit_date, "%Y-%m-%d %H:%M:%S")
                
                dt_end = dt_start + timedelta(hours=1)
                end_time = dt_end.strftime("%Y%m%dT%H%M%S")
                
            except ValueError:
                dt_end = datetime.now().replace(hour=11, minute=0, second=0)
                end_time = dt_end.strftime("%Y%m%dT%H%M%S")
            
            # Opis wydarzenia
            summary = f"Wizyta: {name} {surname}"
            
            event_description = f"Pacjent: {name} {surname}\\nPESEL: {pesel}"
            if phone != 'Brak telefonu':
                event_description += f"\\nTelefon: {phone}"
            if email != 'Brak emaila':
                event_description += f"\\nEmail: {email}"
            if procedures:
                event_description += f"\\nZabiegi: {procedures}"
            if description:
                event_description += f"\\nUwagi: {description}"
            
            # Dodaj wydarzenie
            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTART:{start_time}",
                f"DTEND:{end_time}", 
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{event_description}",
                f"LOCATION:Gabinet trychologa",
                f"STATUS:CONFIRMED",
                f"TRANSP:OPAQUE",
                f"CATEGORIES:Medycyna,Wizyta",
                "END:VEVENT"
            ])
        
        lines.append("END:VCALENDAR")
        
        return "\r\n".join(lines)
    
    def export_to_file(self, filename: str = "wizyty_trychologa.ics", 
                      days_ahead: int = 90) -> str:
        """
        Eksportuje kalendarz do pliku .ics
        """
        visits = self.get_visits(days_ahead)
        ical_content = self.generate_ical(visits)
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(ical_content)
        
        return f"Wyeksportowano {len(visits)} wizyt do pliku: {filename}"

# Funkcja do użycia w main.py
def export_calendar_to_ical() -> str:
    """
    Eksportuje kalendarz i zwraca informacje o rezultacie
    """
    try:
        exporter = ICalExporter()
        result = exporter.export_to_file()
        return result
    except Exception as e:
        return f"Błąd podczas eksportu: {str(e)}"

# Uruchomienie bezpośrednie
if __name__ == "__main__":
    exporter = ICalExporter()
    result = exporter.export_to_file()
    print(result) 