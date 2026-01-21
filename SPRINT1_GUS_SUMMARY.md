# SPRINT 1: Dane GUS - Demografia & Praca ✅

## 🎯 Status: KOMPLETNY (Backend)

**Data ukończenia:** 2026-01-14

---

## 📦 Co zostało zrobione

### 1. Backend Integration - GUS API Client

**Utworzono:** `backend/src/integrations/gus_api.py`

Klasa `GUSDataService` - Client dla API GUS (Bank Danych Lokalnych):
- ✅ `get_population_stats()` - Statystyki demograficzne
- ✅ `get_employment_stats()` - Statystyki rynku pracy
- ✅ `search_variables()` - Wyszukiwanie zmiennych (eksploracja)
- ✅ `get_unit_info()` - Informacje o jednostce terytorialnej

**Funkcjonalności:**
- Asynchroniczne requesty (aiohttp)
- Timeout handling (30s default)
- Error handling & retry logic
- Logging

**Dane pobierane:**
```python
# Demografia
- Ludność ogółem
- Ludność w wieku produkcyjnym
- Gęstość zaludnienia (os/km²)
- Przyrost naturalny

# Rynek pracy
- Stopa bezrobocia (%)
- Liczba bezrobotnych
- Liczba pracujących
- Przeciętne wynagrodzenie brutto (PLN)
```

---

### 2. Database Schema

**Zaktualizowano:** `backend/src/database/schema.py`

Dodano nową tabelę `gus_statistics`:
```python
class GUSStatistic(SQLModel, table=True):
    id: int (PK)
    category: str                # "demographics" lub "employment"
    year: int                    # Rok danych (np. 2025)
    data: JSONB                  # Wszystkie statystyki
    fetched_at: datetime
    updated_at: datetime
    population_total: int        # Denormalizacja (szybki dostęp)
    unemployment_rate: float     # Denormalizacja
```

**Indexes:**
- `idx_gus_category_year` (unique) - zapobiega duplikatom

---

### 3. API Endpoints

**Zaktualizowano:** `backend/src/api/main.py`

Dodano 3 nowe endpointy:

#### GET /api/stats/demographics
Zwraca statystyki demograficzne.

**Query params:**
- `year` (optional) - Konkretny rok (domyślnie: najnowszy)

**Response:**
```json
{
  "total": 57850,
  "working_age": 36200,
  "density": 44.2,
  "growth": -150,
  "year": 2024,
  "fetched_at": "2026-01-14T12:00:00",
  "updated_at": "2026-01-14T12:00:00"
}
```

#### GET /api/stats/employment
Zwraca statystyki rynku pracy.

**Query params:**
- `year` (optional) - Konkretny rok (domyślnie: najnowszy)

**Response:**
```json
{
  "unemployment_rate": 8.5,
  "unemployed_count": 1200,
  "employed_count": 22000,
  "avg_salary": 6500.00,
  "year": 2024,
  "fetched_at": "2026-01-14T12:00:00",
  "updated_at": "2026-01-14T12:00:00"
}
```

#### POST /api/stats/update
Ręczne uruchomienie aktualizacji danych GUS.

**Response:**
```json
{
  "message": "GUS statistics updated successfully",
  "demographics": {...},
  "employment": {...}
}
```

---

### 4. Scheduler Job

**Utworzono:** `backend/src/scheduler/gus_job.py`

Job uruchamiany **codziennie o 6:00 AM** przez APScheduler:
1. Pobiera dane z API GUS
2. Zapisuje do tabeli `gus_statistics` (upsert)
3. Loguje wyniki

**Zaktualizowano:** `backend/src/scheduler/scheduler.py`
- Dodano `run_gus_job` do schedulera
- Job ID: `gus_update`
- Trigger: `CronTrigger(hour=6, minute=0)`

---

### 5. Test Scripts

**Utworzono:** `backend/scripts/tests/test_gus_api.py`

Test API GUS (bez bazy):
- Sprawdza Unit ID dla Powiatu Działdowskiego
- Testuje pobieranie statystyk demograficznych
- Testuje pobieranie statystyk rynku pracy
- Wyszukiwanie zmiennych (eksploracja)

**Uruchomienie:**
```bash
cd backend
python scripts/tests/test_gus_api.py
```

**Utworzono:** `backend/scripts/tests/test_gus_job.py`

Test pełnego pipeline z bazą danych:
- Uruchamia GUS job
- Weryfikuje zapis do bazy
- Sprawdza poprawność danych

**Uruchomienie:**
```bash
cd backend
python scripts/tests/test_gus_job.py
```

---

### 6. Dependencies

**Zaktualizowano:** `backend/requirements.txt`

Dodano:
```
aiohttp>=3.9.0
```

---

## 📋 Jak uruchomić SPRINT 1

### Krok 1: Instalacja zależności
```bash
cd backend
pip install -r requirements.txt
```

### Krok 2: Migracja bazy danych
```bash
# Tabela gus_statistics zostanie automatycznie utworzona przy starcie serwera
# Jeśli używasz Alembic:
alembic revision --autogenerate -m "Add GUS statistics table"
alembic upgrade head
```

### Krok 3: Test API GUS (opcjonalnie)
```bash
python scripts/tests/test_gus_api.py
```

**Oczekiwany wynik:**
- ✅ Unit ID zweryfikowany
- ✅ Statystyki demograficzne pobrane
- ✅ Statystyki rynku pracy pobrane

### Krok 4: Test GUS Job z bazą
```bash
python scripts/tests/test_gus_job.py
```

**Oczekiwany wynik:**
- ✅ Job zakończony pomyślnie
- ✅ Dane zapisane w tabeli `gus_statistics`
- ✅ 2 rekordy (demographics + employment)

### Krok 5: Uruchom serwer
```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Scheduler automatycznie uruchomi się i zarejestruje GUS job (6:00 AM daily).

### Krok 6: Test endpointów API
```bash
# Demografia
curl http://localhost:8000/api/stats/demographics

# Rynek pracy
curl http://localhost:8000/api/stats/employment

# Ręczna aktualizacja (POST)
curl -X POST http://localhost:8000/api/stats/update
```

**Lub w przeglądarce:**
- http://localhost:8000/docs (Swagger UI)

---

## 🔧 Konfiguracja

### Unit ID - Powiat Działdowski
**Obecnie:** `1403000000` (przykładowy)

**Jeśli niepoprawny:**
1. Uruchom `test_gus_api.py` - sprawdzi poprawność Unit ID
2. Jeśli błąd - zaktualizuj w `backend/src/integrations/gus_api.py`:
   ```python
   UNIT_ID_DZIALDOWO = "POPRAWNY_ID"
   ```

### Variable IDs
**Obecnie używane (przykładowe):**
- `72305` - Ludność ogółem
- `60270` - Stopa bezrobocia
- `27112` - Liczba bezrobotnych
- `63658` - Przeciętne wynagrodzenie

**Jeśli niepoprawne:**
1. Użyj `test_gus_api.py` Test 4 - wyszuka zmienne po keyword
2. Zaktualizuj w `gus_api.py`:
   ```python
   VARS = {
       "population_total": "WŁAŚCIWE_ID",
       # ...
   }
   ```

---

## 📊 Struktura Bazy Danych

```sql
-- Tabela: gus_statistics
CREATE TABLE gus_statistics (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,     -- "demographics" lub "employment"
    year INTEGER NOT NULL,             -- Rok danych
    data JSONB NOT NULL,               -- Pełne dane statystyczne
    fetched_at TIMESTAMP NOT NULL,     -- Kiedy pobrano z API
    updated_at TIMESTAMP NOT NULL,     -- Ostatnia aktualizacja
    population_total INTEGER,          -- Ludność (denormalizacja)
    unemployment_rate FLOAT            -- Bezrobocie % (denormalizacja)
);

-- Index
CREATE UNIQUE INDEX idx_gus_category_year ON gus_statistics (category, year);
```

---

## 🚀 Co dalej?

### SPRINT 1: ✅ Backend GOTOWY

**Brakujące (opcjonalne):**
- [ ] Frontend widgets (Dashboard GUS)
- [ ] Widget: Statystyki demograficzne
- [ ] Widget: Stopa bezrobocia + wykres

### SPRINT 2: Nieruchomości & Pozwolenia
- [ ] Integracja dane.gov.pl API
- [ ] Ceny transakcyjne (RCiWN)
- [ ] Pozwolenia na budowę (RWDZ)
- [ ] Mienie komunalne

### SPRINT 3: Finanse Publiczne & Przetargi
- [ ] Sprawozdania budżetowe JST
- [ ] Przetargi BZP
- [ ] Budżet gminy/powiatu

---

## 🐛 Troubleshooting

### Problem: Unit ID niepoprawny
**Objaw:** `test_gus_api.py` zwraca błąd `404` lub brak danych

**Rozwiązanie:**
1. Sprawdź dokumentację GUS API: https://api.stat.gov.pl/Home/BdlApi
2. Wyszukaj "Powiat działdowski" w API:
   ```bash
   curl "https://bdl.stat.gov.pl/api/v1/units/search?name=działdowski"
   ```
3. Zaktualizuj `UNIT_ID_DZIALDOWO` w `gus_api.py`

### Problem: Variable IDs niepoprawne
**Objaw:** API zwraca puste dane lub błędy

**Rozwiązanie:**
1. Użyj `test_gus_api.py` Test 4
2. Wyszukaj zmienne ręcznie przez API:
   ```bash
   curl "https://bdl.stat.gov.pl/api/v1/variables?subject-id=K1"
   ```
3. Zaktualizuj `VARS` dictionary w `gus_api.py`

### Problem: Brak danych w bazie
**Objaw:** `GET /api/stats/demographics` zwraca 404

**Rozwiązanie:**
1. Uruchom ręcznie:
   ```bash
   python scripts/tests/test_gus_job.py
   ```
2. Lub trigger API update:
   ```bash
   curl -X POST http://localhost:8000/api/stats/update
   ```

---

## 💰 Koszty

**API GUS (BDL):**
- **Darmowe:** Do 100 zapytań/15 min (bez rejestracji)
- **Po rejestracji:** ~1000 zapytań/dzień (FREE)
- **Koszt:** 0 PLN/miesiąc ✅

**Częstotliwość:**
- 1× dziennie (6:00 AM)
- ~30 wywołań/miesiąc
- **Koszt całkowity:** 0 PLN ✅

---

## 📚 Dokumentacja Powiązana

- **DATA_OTWARTE_SZKIELET.md** - Plan kompletny (7 modułów)
- **CLAUDE.md** - Status projektu
- **backend/scripts/README.md** - Dokumentacja skryptów
- **API GUS:** https://api.stat.gov.pl/Home/BdlApi

---

**Ostatnia aktualizacja:** 2026-01-14
**Status:** ✅ SPRINT 1 Backend KOMPLETNY
**Następny krok:** Test + Frontend widgets (opcjonalne) LUB SPRINT 2
