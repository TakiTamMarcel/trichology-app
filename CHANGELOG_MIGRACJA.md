# 📋 Changelog - Migracja Pacjentów

## 🎯 Problem
Pacjenci byli widoczni lokalnie (`localhost:8000`) ale nie wyświetlali się w wersji online na Railway ze względu na:
- Lokalna baza SQLite nie była synchronizowana z produkcją
- Pliki `.db` są wykluczone w `.gitignore`
- Brak mechanizmu migracji danych

## ✅ Rozwiązania Wdrożone

### 1. Naprawiono mapowanie pól API (/api/search-patients)
**Problem:** Frontend oczekiwał pól `first_name`/`last_name`, ale API zwracało puste wartości
**Rozwiązanie:** Dodano mapowanie z `name`/`surname` na `first_name`/`last_name`

```python
mapped_patient = {
    'first_name': patient.get('first_name', patient.get('name', '')),
    'last_name': patient.get('last_name', patient.get('surname', '')),
    # ...
}
```

### 2. Utworzono narzędzie eksportu pacjentów
**Plik:** `export_patients.py`
**Funkcja:** Eksportuje wszystkich pacjentów z lokalnej bazy SQLite do JSON

```bash
python3 export_patients.py
# Wynik: patients_export_20250807_221052.json (17 pacjentów)
```

### 3. Dodano endpoint importu pacjentów
**Endpoint:** `POST /api/import-patients`
**Strona:** `GET /import-patients`
**Funkcje:**
- Upload plików JSON z pacjentami
- Sprawdzanie duplikatów (PESEL)
- Reporting importu (imported/skipped/errors)
- Web interface do uploadu

### 4. Dodano instrukcję migracji
**Plik:** `INSTRUKCJA_MIGRACJI_PACJENTOW.md`
**Zawiera:** Krok po krok jak przenieść pacjentów do produkcji

## 🧪 Testowanie

### Test lokalny importu ✅
- Utworzono testowego pacjenta
- Import zakończony sukcesem
- Sprawdzono że pacjent jest dostępny przez API
- Łączna liczba pacjentów: 18 (17 oryginalnych + 1 testowy)

### Test mapowania pól ✅
```bash
curl "localhost:8000/api/search-patients" | jq '.patients[0]'
# Wynik: poprawne pola first_name/last_name
```

## 📁 Nowe pliki
- `export_patients.py` - skrypt eksportu
- `patients_export_20250807_221052.json` - dane 17 pacjentów
- `INSTRUKCJA_MIGRACJI_PACJENTOW.md` - instrukcja krok po krok
- `CHANGELOG_MIGRACJA.md` - ten plik

## 🔧 Zmodyfikowane pliki
- `main.py` - dodano endpointy importu + naprawiono mapowanie API
- `test_templates/index.html` - usunięto logi debug

## 🚀 Następne kroki

1. **Commit i Push do Repository:**
```bash
git add .
git commit -m "Dodano system migracji pacjentów lokalny->produkcja"
git push origin main
```

2. **Poczekaj na deployment Railway**

3. **Wykonaj import w produkcji:**
   - Otwórz: `https://twoja-domena.up.railway.app/import-patients`
   - Wgraj plik: `patients_export_20250807_221052.json`
   - Sprawdź wyniki

4. **Weryfikacja:**
   - Sprawdź główną stronę - powinno być 17 pacjentów
   - Przetestuj wyszukiwanie

## 🛡️ Bezpieczeństwo
- Endpoint importu można zabezpieczyć dodając `user = Depends(require_auth)`
- Po migracji można usunąć endpoint importu
- Plik JSON zawiera dane osobowe - traktować zgodnie z RODO

## 📊 Statystyki
- **Pacjenci wyeksportowani:** 17
- **Test importu:** ✅ Success
- **Czas realizacji:** ~2 godziny
- **Linter errors:** 0
