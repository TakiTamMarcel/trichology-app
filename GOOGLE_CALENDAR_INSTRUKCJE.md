# 📅 **Integracja z Google Calendar - Instrukcje konfiguracji**

## 🎯 **Przegląd**

Aplikacja oferuje **3 sposoby integracji** z Google Calendar:

1. **🔄 Pełna synchronizacja** (Google Calendar API) - *zalecana*
2. **📤 Eksport iCal** - prosta alternatywa  
3. **📥 Import iCal** - jednorazowy import

---

## **1. 🔄 Pełna synchronizacja (Google Calendar API)**

### **Krok 1: Konfiguracja w Google Cloud Console**

1. **Przejdź do**: [Google Cloud Console](https://console.cloud.google.com/)

2. **Utwórz nowy projekt** lub wybierz istniejący

3. **Włącz Google Calendar API:**
   - Idź do "APIs & Services" → "Library"
   - Wyszukaj "Google Calendar API"  
   - Kliknij "Enable"

4. **Utwórz credentials:**
   - Idź do "APIs & Services" → "Credentials"
   - Kliknij "Create Credentials" → "OAuth client ID"
   - Wybierz "Web application"
   - Dodaj Redirect URI: `http://localhost:5001/google-calendar-callback`
   - Pobierz plik JSON

### **Krok 2: Konfiguracja aplikacji**

1. **Skopiuj plik credentials:**
   ```bash
   # Przenieś pobrany plik do katalogu aplikacji
   mv ~/Downloads/client_secret_*.json ./google_calendar_credentials.json
   ```

2. **Zainstaluj zależności:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Uruchom aplikację:**
   ```bash
   python main.py
   ```

### **Krok 3: Autoryzacja**

1. **Przejdź do**: http://localhost:5001/settings
2. **Kliknij**: "Połącz z Google Calendar"
3. **Autoryzuj aplikację** w Google
4. **Kliknij**: "Synchronizuj wizyty"

### **✅ Rezultat:**
- ✅ **Wizyty pacjentów** automatycznie w Google Calendar
- ✅ **Wydarzenia Google** widoczne w aplikacji  
- ✅ **Automatyczna synchronizacja**
- ✅ **Kolory**: Wizyty (zielone), Google (niebieskie)

---

## **2. 📤 Eksport iCal (alternatywa prosta)**

### **Krok 1: Eksport pliku**
```bash
# Uruchom skrypt eksportu
python GOOGLE_CALENDAR_SETUP.py

# Zostanie utworzony plik: wizyty_trychologa.ics
```

### **Krok 2: Import do Google Calendar**
1. **Otwórz**: [Google Calendar](https://calendar.google.com)
2. **Kliknij**: ⚙️ Settings → "Import & export"
3. **Wybierz plik**: `wizyty_trychologa.ics`
4. **Wybierz kalendarz**: gdzie zaimportować
5. **Kliknij**: "Import"

### **✅ Rezultat:**
- ✅ **Wizyty** w Google Calendar
- ❌ Brak automatycznej synchronizacji
- ❌ Trzeba powtarzać eksport/import

---

## **3. 📱 Szybka synchronizacja mobilna**

### **Android:**
1. Otwórz **Google Calendar** 
2. Menu → **Settings** → **Add calendar** → **From URL**
3. **URL**: `http://[twoj-adres-ip]:5001/calendar.ics`

### **iPhone:**  
1. **Settings** → **Calendar** → **Add Account** → **Other**
2. **Add CalDAV Account**
3. **Server**: `http://[twoj-adres-ip]:5001`

---

## **❓ Rozwiązywanie problemów**

### **Błąd: "Brak pliku credentials"**
```bash
# Upewnij się, że plik istnieje:
ls -la google_calendar_credentials.json

# Powinien zawierać:
{
  "installed": {
    "client_id": "...",
    "client_secret": "...",
    "redirect_uris": ["http://localhost:5001/google-calendar-callback"]
  }
}
```

### **Błąd: "Authorization denied"**
- Sprawdź czy redirect URI w Google Cloud Console = `http://localhost:5001/google-calendar-callback`
- Wyczyść cookies i spróbuj ponownie

### **Błąd: "Calendar API not enabled"**
- Włącz Google Calendar API w Google Cloud Console
- Poczekaj 5-10 minut na propagację

---

## **🔧 Testowanie integracji**

### **Test 1: Sprawdź status**
```bash
curl http://localhost:5001/api/google-calendar-status
# Oczekiwany wynik: {"connected": true}
```

### **Test 2: Pobierz wydarzenia**
```bash
curl "http://localhost:5001/api/calendar-events-combined?start=2025-01-01&end=2025-01-31"
# Powinno zwrócić wydarzenia z obu źródeł
```

### **Test 3: Synchronizuj wizyty**
```bash
curl -X POST http://localhost:5001/api/sync-to-google-calendar
# Oczekiwany wynik: {"success": true, "synced_count": X}
```

---

## **📊 Porównanie opcji**

| Funkcja | Google API | iCal Export | CalDAV |
|---------|------------|-------------|--------|
| **Automatyczna sync** | ✅ | ❌ | ⚠️ |
| **Dwukierunkowa** | ✅ | ❌ | ❌ |
| **Setup** | Średni | Łatwy | Łatwy |
| **Mobilne** | ✅ | ✅ | ✅ |
| **Real-time** | ✅ | ❌ | ❌ |

---

## **🎯 Zalecenia**

### **Dla użytkowników zaawansowanych:**
→ **Google Calendar API** - pełna funkcjonalność

### **Dla szybkiego startu:**
→ **iCal Export** - prosta i niezawodna

### **Dla urządzeń mobilnych:**
→ **CalDAV URL** - automatyczne odświeżanie

---

**💡 Potrzebujesz pomocy?** Sprawdź logi aplikacji w pliku `app.log` 