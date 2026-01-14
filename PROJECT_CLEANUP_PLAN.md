# Plan Porządkowania Projektu

## 📁 Nowa Struktura Backend

```
backend/
├── scripts/                    ← UPORZĄDKOWANE
│   ├── tests/                 ← Testy (test_*.py)
│   │   ├── test_ai_pipeline.py
│   │   ├── test_article_job.py
│   │   ├── test_daily_summary.py
│   │   ├── test_facebook_scraper.py
│   │   ├── test_gazeta_olsztynska_rss.py
│   │   ├── test_integration.py
│   │   ├── test_new_scrapers.py
│   │   ├── test_radio7_rss.py
│   │   ├── test_registry.py
│   │   ├── test_rss_scraper.py
│   │   └── test_weather.py
│   │
│   ├── debug/                 ← Debug & diagnostyka
│   │   ├── debug_klikajinfo.py
│   │   ├── debug_mojedzialdowo.py
│   │   ├── debug_rss.py
│   │   ├── debug_rybno.py
│   │   ├── diagnose_pipeline.py
│   │   └── diagnose_summary_dates.py
│   │
│   ├── migrations/            ← Migracje bazy danych
│   │   ├── add_event_unique_constraint.py
│   │   ├── remove_duplicate_events.py
│   │   └── clean_database.py
│   │
│   ├── setup/                 ← Inicjalizacja źródeł
│   │   ├── init_sources.py
│   │   ├── init_new_sources.py
│   │   ├── add_facebook_sources.py
│   │   ├── add_rss_source.py
│   │   ├── add_working_rss_sources.py
│   │   └── find_rss_feeds.py
│   │
│   ├── utils/                 ← Narzędzia pomocnicze
│   │   ├── check_data_async.py
│   │   ├── check_data_status.py
│   │   ├── check_database.py
│   │   ├── check_latest_articles.py
│   │   ├── verify_data.py
│   │   ├── verify_db_save.py
│   │   └── view_daily_summary.py
│   │
│   ├── production/            ← Pipeline produkcyjny
│   │   ├── process_all_articles.py
│   │   ├── regenerate_daily_summary.py
│   │   └── generate_daily_summary_test.py
│   │
│   └── README.md              ← Dokumentacja struktury
│
└── notebooks/                 ← Jupyter notebooks
    ├── analysis.ipynb
    ├── testy.ipynb
    └── daily_summary_data_analysis.ipynb
```

## 📦 Katalogi Tymczasowe (do archiwizacji/usunięcia)

```
/
├── widget_trafic/             ← Prototyp traffic widget (przenieść do archive/)
│   ├── check_models.py
│   ├── debug_traffic.py
│   └── test_gemini_standalone.py
│
└── temp_bus_monitoring/       ← Prototyp bus tracking (przenieść do archive/)
```

## 🗂️ Nowa Struktura Archive

```
archive/
├── prototypes/
│   ├── widget_trafic/         ← Z głównego katalogu
│   └── temp_bus_monitoring/   ← Z głównego katalogu
│
└── old_docs/                  ← Stare dokumenty (jeśli potrzeba)
```

## 📝 Klasyfikacja Plików

### TESTY (11 plików) → `scripts/tests/`
✅ Pliki zaczynające się od `test_*.py`
- Używane do testowania scraperów, AI, pipeline

### DEBUG (6 plików) → `scripts/debug/`
✅ Pliki `debug_*.py` i `diagnose_*.py`
- Używane do debugowania problemów

### MIGRATIONS (3 pliki) → `scripts/migrations/`
✅ Zmiany w schemacie bazy danych
- Uruchamiane raz, potem archiwizowane

### SETUP (6 plików) → `scripts/setup/`
✅ Inicjalizacja źródeł danych
- Uruchamiane przy dodawaniu nowych scraperów

### UTILS (7 plików) → `scripts/utils/`
✅ Narzędzia do sprawdzania statusu
- Regularnie używane do weryfikacji

### PRODUCTION (3 pliki) → `scripts/production/`
✅ Gotowe skrypty do produkcji
- Główny pipeline przetwarzania

## ✅ Akcje do Wykonania

1. **Utworzyć katalogi**
   ```bash
   cd backend/scripts
   mkdir -p tests debug migrations setup utils production
   ```

2. **Przenieść pliki** (zachowując ścieżki importów)
   ```bash
   mv test_*.py tests/
   mv debug_*.py diagnose_*.py debug/
   mv add_event_unique_constraint.py remove_duplicate_events.py clean_database.py migrations/
   mv init_*.py add_*_sources.py find_rss_feeds.py setup/
   mv check_*.py verify_*.py view_*.py utils/
   mv process_all_articles.py regenerate_daily_summary.py generate_daily_summary_test.py production/
   ```

3. **Archiwizować prototypy**
   ```bash
   cd ../..
   mkdir -p archive/prototypes
   mv widget_trafic archive/prototypes/
   mv temp_bus_monitoring archive/prototypes/
   ```

4. **Utworzyć README.md** w `backend/scripts/`

5. **Zaktualizować CLAUDE.md** z nową strukturą

## 🔧 Importy - Do Sprawdzenia

**WAŻNE:** Pliki w podkatalogach będą wymagały aktualizacji importów:

```python
# PRZED (w backend/scripts/test_ai_pipeline.py):
sys.path.insert(0, str(backend_dir))

# PO (w backend/scripts/tests/test_ai_pipeline.py):
sys.path.insert(0, str(backend_dir.parent))  # O jeden poziom wyżej
```

Wszystkie pliki używają wzorca:
```python
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))
```

Po przeniesieniu do podkatalogu będzie:
```python
backend_dir = Path(__file__).parent.parent.parent  # +1 parent
sys.path.insert(0, str(backend_dir))
```

## 📋 Korzyści

✅ **Łatwiejsze zarządzanie** - wiadomo co gdzie
✅ **Szybsze wyszukiwanie** - testy w tests/, debug w debug/
✅ **Przejrzysta struktura** - nowi deweloperzy wiedzą gdzie co jest
✅ **Oddzielenie odpowiedzialności** - produkcja oddzielona od testów

---

**Ready to execute?** 🚀
