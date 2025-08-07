# 🔄 Instrukcja Migracji Pacjentów z Lokalnej Bazy do Produkcyjnej

## Problem
Pacjenci są widoczni lokalnie na `localhost:8000`, ale nie wyświetlają się w wersji online na Railway, ponieważ:
- Lokalna baza SQLite (`trichology.db`) nie jest synchronizowana z produkcją
- W `.gitignore` są wykluczone pliki bazy danych
- W produkcji tworzy się nowa, pusta baza danych

## Rozwiązanie

### Krok 1: Eksport pacjentów z lokalnej bazy ✅ WYKONANE

```bash
python3 export_patients.py
```

**Wynik:** Utworzono plik `patients_export_20250807_221052.json` z 17 pacjentami.

### Krok 2: Wdrożenie kodu do produkcji

1. **Zacommituj zmiany:**
```bash
git add .
git commit -m "Dodano funkcję importu/eksportu pacjentów"
git push origin main
```

2. **Poczekaj na deployment na Railway**

### Krok 3: Import pacjentów w produkcji

1. **Otwórz stronę importu w produkcji:**
   - Przejdź na: `https://twoja-domena-railway.up.railway.app/import-patients`

2. **Wgraj plik JSON:**
   - Kliknij na obszar uploadu
   - Wybierz plik `patients_export_20250807_221052.json`
   - Kliknij "📤 Importuj Pacjentów"

3. **Zweryfikuj import:**
   - Sprawdź komunikat o pomyślnym imporcie
   - Przejdź na główną stronę aplikacji
   - Powinnieneś zobaczyć wszystkich 17 pacjentów

### Krok 4: Weryfikacja (opcjonalnie)

Sprawdź czy endpoint API działa w produkcji:
```bash
curl -X POST -H "Content-Type: application/json" -d '{"query":""}' "https://twoja-domena-railway.up.railway.app/api/search-patients"
```

---

## 📋 Podsumowanie eksportowanych danych

- **Liczba pacjentów:** 17
- **Plik eksportu:** `patients_export_20250807_221052.json`
- **Przykładowi pacjenci:**
  - Marcel Kollek (PESEL: 324234)
  - Jakub Ciołek (PESEL: 92060207477)
  - Monika Block (PESEL: 83062611126)
  - I 14 innych...

## 🛡️ Bezpieczeństwo

- Endpoint importu nie wymaga autoryzacji (można to zmienić)
- Nie importuje duplikatów (sprawdza PESEL)
- Ogranicza wyświetlanie błędów do 10

## 🔧 Dodatkowe opcje

### Jeśli chcesz zabezpieczyć endpoint importu:

Zmień w `main.py` linię:
```python
@app.post("/api/import-patients")
async def import_patients_api(request: Request, file: UploadFile = File(...)):
```

Na:
```python
@app.post("/api/import-patients")
async def import_patients_api(request: Request, file: UploadFile = File(...), user = Depends(require_auth)):
```

### Jeśli chcesz usunąć endpoint po imporcie:

Usuń lub zakomentuj funkcje:
- `import_patients_api()`
- `import_patients_page()`

---

## ⚠️ Uwagi

1. **Ten proces jest jednorazowy** - po imporcie pacjentów do produkcji, należy dodawać nowych pacjentów bezpośrednio w aplikacji online
2. **Backup lokalny** - plik JSON służy również jako backup lokalnych danych
3. **Testowanie** - proces został przetestowany lokalnie i powinien działać w produkcji
