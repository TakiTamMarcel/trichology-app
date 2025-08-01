#!/usr/bin/env python3
"""
Integracja z Google Calendar API
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GoogleCalendarIntegration:
    """
    Klasa do integracji z Google Calendar API
    """
    
    def __init__(self):
        self.scopes = ['https://www.googleapis.com/auth/calendar']
        self.credentials_file = 'google_calendar_credentials.json'
        self.token_file = 'google_calendar_token.json'
        self.calendar_id = 'primary'  # Główny kalendarz użytkownika
        
    def setup_oauth_flow(self, client_secrets_file: str) -> Optional[str]:
        """
        Rozpoczyna proces OAuth2 i zwraca URL autoryzacji
        """
        try:
            flow = Flow.from_client_secrets_file(
                client_secrets_file,
                scopes=self.scopes,
                redirect_uri='http://localhost:5001/google-calendar-callback'
            )
            
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )
            
            return auth_url
            
        except Exception as e:
            logger.error(f"Błąd podczas konfiguracji OAuth: {str(e)}")
            return None
    
    def handle_oauth_callback(self, auth_code: str, client_secrets_file: str) -> bool:
        """
        Obsługuje callback OAuth2 i zapisuje token
        """
        try:
            flow = Flow.from_client_secrets_file(
                client_secrets_file,
                scopes=self.scopes,
                redirect_uri='http://localhost:5001/google-calendar-callback'
            )
            
            flow.fetch_token(code=auth_code)
            
            # Zapisz credentials
            with open(self.token_file, 'w') as token:
                token.write(flow.credentials.to_json())
            
            logger.info("Pomyślnie autoryzowano Google Calendar")
            return True
            
        except Exception as e:
            logger.error(f"Błąd podczas autoryzacji OAuth: {str(e)}")
            return False
    
    def get_credentials(self) -> Optional[Credentials]:
        """
        Pobiera credentials z zapisanego tokena
        """
        try:
            if os.path.exists(self.token_file):
                return Credentials.from_authorized_user_file(self.token_file)
            return None
        except Exception as e:
            logger.error(f"Błąd podczas ładowania credentials: {str(e)}")
            return None
    
    def get_calendar_service(self):
        """
        Tworzy serwis Google Calendar
        """
        try:
            credentials = self.get_credentials()
            if not credentials:
                return None
                
            if credentials.expired and credentials.refresh_token:
                from google.auth.transport.requests import Request
                credentials.refresh(Request())
                
            return build('calendar', 'v3', credentials=credentials)
            
        except Exception as e:
            logger.error(f"Błąd podczas tworzenia serwisu Calendar: {str(e)}")
            return None
    
    def get_events(self, start_date: str, end_date: str) -> List[Dict]:
        """
        Pobiera wydarzenia z Google Calendar w zadanym okresie
        """
        try:
            service = self.get_calendar_service()
            if not service:
                return []
            
            # Konwertuj daty na format RFC3339
            start_time = datetime.fromisoformat(start_date).isoformat() + 'Z'
            end_time = datetime.fromisoformat(end_date).isoformat() + 'Z'
            
            events_result = service.events().list(
                calendarId=self.calendar_id,
                timeMin=start_time,
                timeMax=end_time,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Konwertuj na format FullCalendar
            calendar_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                calendar_event = {
                    'id': f"gcal_{event['id']}",
                    'title': event.get('summary', 'Bez tytułu'),
                    'start': start,
                    'end': end,
                    'color': '#4285f4',  # Niebieski kolor Google
                    'description': event.get('description', ''),
                    'source': 'google_calendar',
                    'google_event_id': event['id']
                }
                calendar_events.append(calendar_event)
            
            return calendar_events
            
        except HttpError as error:
            logger.error(f"Błąd HTTP podczas pobierania wydarzeń: {error}")
            return []
        except Exception as e:
            logger.error(f"Błąd podczas pobierania wydarzeń: {str(e)}")
            return []
    
    def create_event(self, title: str, start_time: str, end_time: str, 
                    description: str = "", location: str = "") -> Optional[str]:
        """
        Tworzy nowe wydarzenie w Google Calendar
        """
        try:
            service = self.get_calendar_service()
            if not service:
                return None
            
            event = {
                'summary': title,
                'description': description,
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'Europe/Warsaw',
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'Europe/Warsaw',
                },
            }
            
            if location:
                event['location'] = location
            
            event = service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            
            logger.info(f"Utworzono wydarzenie w Google Calendar: {event.get('id')}")
            return event.get('id')
            
        except HttpError as error:
            logger.error(f"Błąd HTTP podczas tworzenia wydarzenia: {error}")
            return None
        except Exception as e:
            logger.error(f"Błąd podczas tworzenia wydarzenia: {str(e)}")
            return None
    
    def update_event(self, event_id: str, title: str, start_time: str, 
                    end_time: str, description: str = "") -> bool:
        """
        Aktualizuje wydarzenie w Google Calendar
        """
        try:
            service = self.get_calendar_service()
            if not service:
                return False
            
            event = service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            event['summary'] = title
            event['description'] = description
            event['start'] = {
                'dateTime': start_time,
                'timeZone': 'Europe/Warsaw',
            }
            event['end'] = {
                'dateTime': end_time,
                'timeZone': 'Europe/Warsaw',
            }
            
            updated_event = service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            logger.info(f"Zaktualizowano wydarzenie w Google Calendar: {event_id}")
            return True
            
        except HttpError as error:
            logger.error(f"Błąd HTTP podczas aktualizacji wydarzenia: {error}")
            return False
        except Exception as e:
            logger.error(f"Błąd podczas aktualizacji wydarzenia: {str(e)}")
            return False
    
    def delete_event(self, event_id: str) -> bool:
        """
        Usuwa wydarzenie z Google Calendar
        """
        try:
            service = self.get_calendar_service()
            if not service:
                return False
            
            service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info(f"Usunięto wydarzenie z Google Calendar: {event_id}")
            return True
            
        except HttpError as error:
            logger.error(f"Błąd HTTP podczas usuwania wydarzenia: {error}")
            return False
        except Exception as e:
            logger.error(f"Błąd podczas usuwania wydarzenia: {str(e)}")
            return False 