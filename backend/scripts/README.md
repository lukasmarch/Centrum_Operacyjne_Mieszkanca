# Backend Scripts - Dokumentacja Struktury

## 📁 Struktura Katalogów

```
scripts/
├── tests/              ← Testy (test_*.py) - 11 plików
├── debug/              ← Debug & diagnostyka - 6 plików
├── migrations/         ← Migracje bazy danych - 3 pliki
├── setup/              ← Inicjalizacja źródeł - 6 plików
├── utils/              ← Narzędzia pomocnicze - 7 plików
├── production/         ← Pipeline produkcyjny - 3 pliki
└── README.md           ← Ten plik
```

---

## 🧪 tests/ - Testy (11 plików)

Pliki testowe dla scraperów, AI pipeline i innych komponentów.

### Uruchamianie:
```bash
cd backend

# Test AI Pipeline (kategoryzacja + wydarzenia)
python scripts/tests/test_ai_pipeline.py

# Test scraperów
python scripts/tests/test_article_job.py
python scripts/tests/test_registry.py

# Test Daily Summary
python scripts/tests/test_daily_summary.py

# Test konkretnych scraperów
python scripts/tests/test_facebook_scraper.py
python scripts/tests/test_rss_scraper.py
python scripts/tests/test_radio7_rss.py
python scripts/tests/test_gazeta_olsztynska_rss.py

# Test pogody
python scripts/tests/test_weather.py
```

### Pliki:
- `test_ai_pipeline.py` - Test AI (ArticleProcessor + EventExtractor)
- `test_article_job.py` - Test scrapowania wszystkich źródeł
- `test_daily_summary.py` - Test generowania podsumowań dziennych
- `test_facebook_scraper.py` - Test Apify Facebook scraper
- `test_gazeta_olsztynska_rss.py` - Test RSS Gazeta Olsztyńska
- `test_integration.py` - Testy integracyjne
- `test_new_scrapers.py` - Test nowych scraperów
- `test_radio7_rss.py` - Test RSS Radio 7
- `test_registry.py` - Test Scraper Registry
- `test_rss_scraper.py` - Test uniwersalnego RSS scrapera
- `test_weather.py` - Test OpenWeatherMap API

---

## 🐛 debug/ - Debug & Diagnostyka (6 plików)

Narzędzia do debugowania problemów z scraperami i pipeline.

### Uruchamianie:
```bash
cd backend

# Debug konkretnych scraperów
python scripts/debug/debug_klikajinfo.py
python scripts/debug/debug_mojedzialdowo.py
python scripts/debug/debug_rss.py
python scripts/debug/debug_rybno.py

# Diagnoza pipeline
python scripts/debug/diagnose_pipeline.py
python scripts/debug/diagnose_summary_dates.py
```

### Pliki:
- `debug_klikajinfo.py` - Debug scrapera Klikaj.info
- `debug_mojedzialdowo.py` - Debug scrapera Moje Działdowo
- `debug_rss.py` - Debug RSS scraperów
- `debug_rybno.py` - Debug scrapera Gmina Rybno
- `diagnose_pipeline.py` - Diagnoza całego AI pipeline
- `diagnose_summary_dates.py` - Diagnoza dat w daily summaries

---

## 🔧 migrations/ - Migracje Bazy Danych (3 pliki)

Skrypty do jednorazowych zmian w schemacie bazy danych.

### Uruchamianie:
```bash
cd backend

# UWAGA: Uruchom raz, potem nie używaj ponownie!

# Krok 1: Usuń duplikaty wydarzeń (przed dodaniem constraint)
python scripts/migrations/remove_duplicate_events.py

# Krok 2: Dodaj unique constraint dla Event
python scripts/migrations/add_event_unique_constraint.py

# Opcjonalnie: Wyczyść bazę (UWAGA: usuwa dane!)
python scripts/migrations/clean_database.py
```

### Pliki:
- `add_event_unique_constraint.py` - Dodaje unique index (title, event_date, location)
- `remove_duplicate_events.py` - Usuwa duplikaty wydarzeń z bazy
- `clean_database.py` - Czyści bazę danych (OSTROŻNIE!)

**WAŻNE:** Migracje uruchamia się tylko raz. Zobacz: `SCRAPING_IMPROVEMENTS.md`

---

## ⚙️ setup/ - Inicjalizacja Źródeł (6 plików)

Skrypty do dodawania nowych źródeł danych do bazy.

### Uruchamianie:
```bash
cd backend

# Inicjalizacja podstawowych źródeł (pierwsze uruchomienie)
python scripts/setup/init_sources.py

# Dodaj nowe źródła
python scripts/setup/init_new_sources.py

# Dodaj źródła Facebook (wymaga APIFY_API_KEY)
python scripts/setup/add_facebook_sources.py

# Dodaj źródła RSS
python scripts/setup/add_working_rss_sources.py

# Dodaj pojedyncze źródło RSS
python scripts/setup/add_rss_source.py

# Znajdź RSS feedy dla strony
python scripts/setup/find_rss_feeds.py
```

### Pliki:
- `init_sources.py` - Inicjalizacja podstawowych źródeł (Klikaj.info)
- `init_new_sources.py` - Dodanie nowych źródeł (Gmina Rybno, Moje Działdowo)
- `add_facebook_sources.py` - Dodanie kont Facebook przez Apify
- `add_rss_source.py` - Dodanie pojedynczego źródła RSS
- `add_working_rss_sources.py` - Dodanie sprawdzonych RSS (Radio 7, Gazeta)
- `find_rss_feeds.py` - Szukanie RSS feedów na stronie

---

## 🛠️ utils/ - Narzędzia Pomocnicze (7 plików)

Narzędzia do sprawdzania statusu i weryfikacji danych.

### Uruchamianie:
```bash
cd backend

# Sprawdź status danych
python scripts/utils/check_data_status.py
python scripts/utils/check_data_async.py

# Sprawdź bazę danych
python scripts/utils/check_database.py
python scripts/utils/check_latest_articles.py

# Weryfikacja
python scripts/utils/verify_data.py
python scripts/utils/verify_db_save.py

# Podgląd daily summary
python scripts/utils/view_daily_summary.py
```

### Pliki:
- `check_data_status.py` - Status danych w bazie (tabele, liczba rekordów)
- `check_data_async.py` - Asynchroniczny check statusu
- `check_database.py` - Sprawdzenie połączenia z bazą
- `check_latest_articles.py` - Wyświetl ostatnie artykuły
- `verify_data.py` - Weryfikacja jakości danych
- `verify_db_save.py` - Weryfikacja zapisu do bazy
- `view_daily_summary.py` - Podgląd daily summary (formatowany)

---

## 🚀 production/ - Pipeline Produkcyjny (3 pliki)

Gotowe skrypty do użycia w produkcji (ręcznie lub przez scheduler).

### Uruchamianie:
```bash
cd backend

# Przetwórz wszystkie nieprzetworzone artykuły przez AI
python scripts/production/process_all_articles.py

# Regeneruj daily summary (np. po poprawkach w AI)
python scripts/production/regenerate_daily_summary.py

# Test generowania daily summary
python scripts/production/generate_daily_summary_test.py
```

### Pliki:
- `process_all_articles.py` - Przetworzenie wszystkich artykułów przez AI (batch)
- `regenerate_daily_summary.py` - Regeneracja daily summary dla konkretnej daty
- `generate_daily_summary_test.py` - Test generowania podsumowań

**UWAGA:** Te skrypty są używane przez scheduler (`src/scheduler/`) automatycznie.

---

## 📝 Konwencje

### Importy w skryptach
Wszystkie skrypty w podkatalogach używają:
```python
from pathlib import Path
import sys

# Dodaj backend/ do PYTHONPATH
backend_path = Path(__file__).parent.parent.parent  # scripts/[kategoria]/script.py -> backend/
sys.path.insert(0, str(backend_path))

# Teraz można importować z src.*
from src.database.connection import async_session
```

### Nazewnictwo
- **test_*.py** - Testy
- **debug_*.py** - Debug konkretnego komponentu
- **diagnose_*.py** - Diagnoza problemów
- **check_*.py** - Sprawdzanie statusu
- **verify_*.py** - Weryfikacja danych
- **init_*.py** - Inicjalizacja
- **add_*.py** - Dodawanie danych

---

## 🔄 Workflow Użycia

### 1. Pierwsze uruchomienie projektu
```bash
# 1. Inicjalizacja źródeł
python scripts/setup/init_sources.py
python scripts/setup/add_working_rss_sources.py

# 2. Test scrapowania
python scripts/tests/test_article_job.py

# 3. Przetworzenie AI
python scripts/production/process_all_articles.py

# 4. Test daily summary
python scripts/tests/test_daily_summary.py
```

### 2. Dodanie nowego scrapera
```bash
# 1. Utwórz scraper w src/scrapers/
# 2. Zarejestruj w src/scrapers/registry.py
# 3. Dodaj źródło do bazy
python scripts/setup/init_new_sources.py  # (edytuj kod)

# 4. Test
python scripts/tests/test_registry.py
python scripts/tests/test_article_job.py
```

### 3. Debug problemów
```bash
# Problem ze scraperem?
python scripts/debug/debug_klikajinfo.py

# Problem z AI?
python scripts/debug/diagnose_pipeline.py

# Sprawdź status bazy
python scripts/utils/check_data_status.py
```

### 4. Produkcja (uruchamia się automatycznie przez scheduler)
```bash
# Ręczne uruchomienie jeśli potrzeba:
python scripts/production/process_all_articles.py
python scripts/production/regenerate_daily_summary.py
```

---

## 📚 Dokumentacja Powiązana

- **SCRAPING_IMPROVEMENTS.md** - Changelog usprawnień scraperów (2026-01-14)
- **CLAUDE.md** - Status projektu i historia rozwoju
- **DATA_OTWARTE_SZKIELET.md** - Plan integracji danych otwartych (GUS, dane.gov.pl)
- **docs/APIFY_SETUP.md** - Setup Apify Facebook scraper
- **docs/NEW_SCRAPERS.md** - Dokumentacja scraperów

---

## ❓ FAQ

**Q: Dlaczego skrypty są podzielone na katalogi?**
A: Dla łatwiejszego zarządzania. Teraz wiesz gdzie szukać testów, debugów, narzędzi produkcyjnych.

**Q: Czy mogę uruchomić skrypt bezpośrednio z jego katalogu?**
A: Tak, ale lepiej uruchamiać z `backend/`:
```bash
cd backend
python scripts/tests/test_ai_pipeline.py
```

**Q: Co jeśli dostanę błąd importu `ModuleNotFoundError: No module named 'src'`?**
A: Sprawdź czy skrypt ma poprawną ścieżkę:
```python
backend_path = Path(__file__).parent.parent.parent  # Powinno być 3× parent
```

**Q: Gdzie są stare prototypy (widget_trafic, temp_bus_monitoring)?**
A: Przeniesione do `archive/prototypes/`.

---

**Ostatnia aktualizacja:** 2026-01-14
**Liczba skryptów:** 36 (11 tests + 6 debug + 3 migrations + 6 setup + 7 utils + 3 production)
