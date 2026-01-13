# Status Projektu - Centrum Operacyjne Mieszkańca

## Obecny Etap
**FAZA 3 UKOŃCZONA ✅ - Daily Summaries działa!**
**GOTOWE DO: FAZA 4 (Frontend Integration)**

## Co zostało zrobione

### Faza 0: Planowanie ✅
- Plan projektu (PLAN_PROJEKTU.md)
- Plan biznesowy (dzialowo-live-plan-biznesowy.md)
- Źródła danych: 10 (media, urzędy, APIs)
- 8 modułów tematycznych
- Model biznesowy + roadmap 18 tygodni

### Faza 1 - Setup Backend ✅
**Struktura:**
- Backend: Python/FastAPI + PostgreSQL + Redis
- Database: SQLModel + Alembic migrations
- Scrapers: BaseScraper (async, retry, rate limit)
- Config: Pydantic v2 Settings (.env loading)

**Tabele DB:**
- sources, articles, events, weather, daily_summaries

**API Endpoints:**
- GET /health
- GET /api/sources
- GET /api/articles
- GET /api/weather, GET /api/weather/{location}

### Faza 1 - Krok 1: Pierwszy Scraper ✅
**KlikajInfoScraper** (`backend/src/scrapers/klikajinfo.py`)
- Scraping co 6h (APScheduler)
- 31 artykułów w bazie
- Deduplikacja URL + external_id

### Faza 1 - Krok 2: Weather API ✅
**OpenWeatherMap Integration**
- Lokalizacje: Rybno, Działdowo
- Update co 15min
- 24 pola danych (temp, humidity, wind, rain, sunrise/sunset)

### Faza 1 - Krok 3: AI Processing Pipeline ✅ **NOWE!**
**Zaimplementowano pełny "mózg AI":**

**1. ArticleProcessor** (`backend/src/ai/article_processor.py`)
- Model: GPT-4o-mini
- Kategoryzacja do 8 modułów: Urząd, Zdrowie, Edukacja, Biznes, Transport, Kultura, Nieruchomości, Rekreacja
- Ekstrakcja: tags (3-5), locations (Powiat Działdowski), key_entities
- Generowanie summary (2-3 zdania)
- Confidence: 0.90 (bardzo pewna kategoryzacja)

**2. EventExtractor** (`backend/src/ai/event_extractor.py`)
- Model: GPT-4o
- Identyfikacja wydarzeń (koncerty, spotkania, festyny, etc.)
- Ekstrakcja: data, godzina, lokalizacja, organizator, cena, kontakt
- Zapis do tabeli events

**3. AI Scheduler** (`backend/src/scheduler/ai_jobs.py`)
- Job co 30 minut: kategoryzacja + ekstrakcja wydarzeń
- Batch 20 artykułów na raz
- Automatyczne przetwarzanie nowych artykułów

**4. Database Schema**
- Tabela: daily_summaries (JSONB)
- Article.processed flag
- Article.summary, category, tags, location_mentioned

**5. Pydantic AI Models** (`backend/src/ai/models.py`)
- ArticleCategory (8 pól)
- ExtractedEvent (12 pól)
- DailySummary (6 pól)

**6. System Prompts** (`backend/src/ai/prompts.py`)
- CATEGORIZATION_PROMPT (8 modułów + lokalizacje)
- EVENT_EXTRACTION_PROMPT (identyfikacja wydarzeń)
- DAILY_SUMMARY_PROMPT (generowanie podsumowań)

**Test Results** (`backend/scripts/test_ai_pipeline.py`):
```
✅ 5 artykułów przetworzone w ~25 sekund
✅ Kategorie: Transport (3), Zdrowie (1), Rekreacja (1), Kultura (1)
✅ 90% confidence
✅ Tagi + lokalizacje wyekstrahowane
✅ Total: 15/31 artykułów przetworzonych (48.4%)
```

**Koszty AI (rzeczywiste):**
- ~6 sekund/artykuł (GPT-4o-mini)
- Szacowany koszt: ~60 PLN/miesiąc przy 3000 artykułów

**Dependencies dodane:**
- pydantic-ai>=0.0.14
- openai>=1.12.0
- apscheduler==3.10.4
- griffe (dependency fix)

### APScheduler Jobs ✅
**Działający scheduler** (`backend/src/scheduler/scheduler.py`):
1. Weather update - co 15min
2. Article scraping - co 6h
3. **AI processing - co 30min** ← NOWE!

### Faza 2 - Rozbudowa Scraperów ✅ **NOWE!**
**3 nowe scrapery utworzone:**

**1. GminaRybnoScraper** (`backend/src/scrapers/gmina_rybno.py`)
- Źródło: gminarybno.pl/aktualnosci.html
- 29 artykułów zscrapowanych ✓
- Kategorie: ogłoszenia urzędowe, inwestycje, wydarzenia

**2. MojeDzialdowoScraper** (`backend/src/scrapers/mojedzialdowo.py`)
- Źródło: mojedzialdowo.pl
- 1 artykuł zscrapowany ✓
- WordPress content extraction

**3. ApifyFacebookScraper** (`backend/src/scrapers/apify_facebook.py`)
- Actor: apify/facebook-posts-scraper
- Szablon gotowy (wymaga APIFY_API_KEY)
- Wspiera 10+ kont Facebook
- 3 konta skonfigurowane:
  - Facebook - Syla (serwis.informacyjny.syla)
  - Facebook - Gmina Działdowo
  - Facebook - Urząd Miasta Działdowo

**4. Scraper Registry Pattern** (`backend/src/scrapers/registry.py`)
- Centralny rejestr scraperów
- Pattern matching dla Facebook (wszystkie "Facebook - *")
- Funkcje: `get_scraper()`, `register_scraper()`, `list_scrapers()`

**5. Article Job Integration** (`backend/src/scheduler/article_job.py`)
- Dynamiczne ładowanie scraperów z registry
- Automatyczne scrapowanie wszystkich aktywnych źródeł
- Update `last_scraped` timestamp
- Szczegółowe logowanie + summary

**6. Helper Scripts**
- `scripts/add_facebook_sources.py` - dodawanie kont FB
- `scripts/test_registry.py` - test registry
- `scripts/test_article_job.py` - test całego pipeline
- `scripts/init_new_sources.py` - inicjalizacja źródeł

**7. Dokumentacja**
- `docs/APIFY_SETUP.md` - pełny setup guide Apify
- `docs/NEW_SCRAPERS.md` - dokumentacja scraperów
- `docs/SCRAPERS_QUICKSTART.md` - quick start

**Test Results** (test_article_job.py):
```
✓ Total sources processed: 3 (Klikaj.info, Gmina Rybno, Moje Działdowo)
✓ Total new articles saved: 30
✓ Failed sources: 0
✓ Łącznie w bazie: ~61 artykułów
```

**Źródła w bazie (7 total):**
- ID 1: Klikaj.info (active) - 31 artykułów
- ID 2: Gmina Rybno (active) - 29 artykułów
- ID 3: Moje Działdowo (active) - 1 artykuł
- ID 4: Gmina Działdowo Facebook (inactive) - legacy
- ID 5: Facebook - Syla (active) - 20 postów ✓ **TESTED!**
- ID 6: Facebook - Gmina Działdowo (active)
- ID 7: Facebook - Urząd Miasta Działdowo (active)

**Apify Integration ✅ DZIAŁAJĄCE!**
- Test pomyślny: 20 postów w 25 sekund
- Koszt: ~$0.11 per run ($0.006 start + $0.005/post)
- Actor: apify~facebook-posts-scraper (UWAGA: ~ nie /)
- Fix: Unix timestamp parsing (int -> datetime)

### Faza 3 - Daily Summaries ✅ **NOWE!**
**Zaimplementowano automatyczne dzienne podsumowania:**

**1. SummaryGenerator** (`backend/src/ai/summary_generator.py`)
- Model: GPT-4o (wyższa jakość tekstu)
- Agregacja artykułów z ostatnich 24h
- Grupowanie po 8 kategoriach
- Integracja z wydarzeniami i pogodą
- Generowanie przyjaznych podsumowań po polsku

**2. Daily Summary Scheduler** (`backend/src/scheduler/summary_job.py`)
- Job uruchamiany codziennie o 6:00 rano
- Automatyczne generowanie podsumowań
- Error handling + logging
- Async wrapper dla APScheduler

**3. API Endpoints** (`backend/src/api/main.py`)
- `GET /api/summary/daily` - najnowsze podsumowanie
- `GET /api/summary/daily/{date}` - podsumowanie z konkretnej daty (YYYY-MM-DD)
- Zwraca: headline, highlights, podsumowania per kategoria, wydarzenia, pogoda

**4. Database Integration**
- Tabela `daily_summaries` (date, headline, content JSONB)
- Unique index na date (jedno podsumowanie dziennie)
- Stats: total_articles, categories_count, events_count

**5. Scheduler Update** (`backend/src/scheduler/scheduler.py`)
- Dodany 4. job: Daily Summary (CronTrigger, 6:00 AM)
- Import CronTrigger z APScheduler

**Test Results** (`backend/scripts/test_daily_summary.py`):
```
✅ Podsumowanie wygenerowane w ~15 sekund
✅ Headline: "Wypadek w centrum Działdowa oraz największa zjeżdżalnia w Polsce pod Żurominem!"
✅ 5 highlights (top wiadomości)
✅ 5 kategorii z podsumowaniami (Urząd, Kultura, Zdrowie, Rekreacja, Transport)
✅ 3 nadchodzące wydarzenia
✅ Podsumowanie pogody (temperatura, warunki, wilgotność, wiatr)
✅ Stats: 15 artykułów, 6 kategorii
```

**Struktura podsumowania:**
- **Headline**: Chwytliwy nagłówek dnia (max 200 znaków)
- **Highlights**: Top 3-5 najważniejszych wiadomości
- **Summary by category**: Zwięzłe opisy per moduł (2-3 zdania)
- **Upcoming events**: Lista nadchodzących wydarzeń (7 dni)
- **Weather summary**: Podsumowanie warunków pogodowych

**Koszty AI:**
- GPT-4o: ~$0.015-0.025 per podsumowanie
- Miesięcznie: ~30 podsumowań × $0.02 = ~$0.60 (~2.50 PLN)

---

## Następne Kroki

### ~~FAZA 2: Rozbudowa Scraperów~~ ✅ UKOŃCZONA
**ZROBIONE:**
- [x] Scraper Registry Pattern (`backend/src/scrapers/registry.py`)
- [x] MojeDzialdowoScraper (HTML scraping)
- [x] GminaRybnoScraper (ogłoszenia urzędowe) - zamiast BIPRybno
- [x] ApifyFacebookScraper (szablon + 3 konta)
- [x] Aktualizacja article_job.py (dynamiczne ładowanie)
- [x] Init nowych źródeł w bazie
- [x] Dokumentacja Apify (APIFY_SETUP.md)

**Wynik:** 3 aktywne źródła + 3 Facebook (gotowe po dodaniu API key)

### ~~FAZA 3: Daily Summaries~~ ✅ UKOŃCZONA
**ZROBIONE:**
- [x] SummaryGenerator (`backend/src/ai/summary_generator.py`)
- [x] Daily summary job (scheduler o 6:00)
- [x] API endpoints: GET /api/summary/daily, GET /api/summary/daily/{date}
- [x] Zapis do tabeli daily_summaries
- [x] Test script (`scripts/test_daily_summary.py`)

**Wynik:** Automatyczne dzienne podsumowania AI + 2 endpointy

### FAZA 4: Frontend Integration
- [ ] Podłączyć widget pogody do API
- [ ] Lista artykułów z kategoryzacją
- [ ] Filtrowanie po kategoriach
- [ ] Wyświetlanie wydarzeń

---

## Kluczowa Struktura Backend

```
backend/
├── src/
│   ├── ai/                    ← AI Processing
│   │   ├── models.py          ← Pydantic response models
│   │   ├── prompts.py         ← System prompts
│   │   ├── article_processor.py
│   │   ├── event_extractor.py
│   │   └── summary_generator.py ← (NOWE!)
│   ├── scrapers/              ← 4 scrapery + registry
│   │   ├── base.py            ← BaseScraper
│   │   ├── registry.py        ← Scraper Registry (NOWE!)
│   │   ├── klikajinfo.py
│   │   ├── gmina_rybno.py     ← (NOWE!)
│   │   ├── mojedzialdowo.py   ← (NOWE!)
│   │   └── apify_facebook.py  ← (NOWE!)
│   ├── scheduler/
│   │   ├── scheduler.py       ← APScheduler (4 jobs)
│   │   ├── weather_job.py
│   │   ├── article_job.py     ← Zaktualizowany (dynamic loading)
│   │   ├── ai_jobs.py
│   │   └── summary_job.py     ← (NOWE!)
│   ├── database/schema.py     ← SQLModel (5 tabel)
│   ├── api/main.py           ← FastAPI
│   └── config.py             ← Pydantic v2 Settings
├── scripts/
│   ├── test_ai_pipeline.py
│   ├── test_daily_summary.py  ← (NOWE!)
│   ├── test_registry.py
│   ├── test_article_job.py
│   ├── test_new_scrapers.py
│   ├── add_facebook_sources.py
│   ├── init_sources.py
│   └── init_new_sources.py
├── docs/
│   ├── APIFY_SETUP.md         ← (NOWE!)
│   ├── NEW_SCRAPERS.md        ← (NOWE!)
│   └── SCRAPERS_QUICKSTART.md ← (NOWE!)
├── requirements.txt
└── .env
```

## Jak uruchomić

### 🚀 Uruchomienie Serwera Backend (API + Scheduler)

**Krok 1: Aktywuj wirtualne środowisko**
```bash
cd /Users/lukaszmarchlewicz/Desktop/Centrum_Operacyjne_Mieszkańca
source .venv/bin/activate
```

**Krok 2: Uruchom serwer FastAPI**
```bash
cd backend
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Serwer uruchomi się na: **http://localhost:8000**
- API będzie dostępne
- Scheduler automatycznie wystartuje (4 joby)
- Dokumentacja API: http://localhost:8000/docs

**Krok 3: Sprawdź czy działa**
```bash
# W nowym terminalu:
curl http://localhost:8000/health
# Powinno zwrócić: {"status":"ok"}
```

---

### 🧪 Testy i Skrypty

**1. Test AI Pipeline (kategoryzacja + wydarzenia):**
```bash
cd backend
python scripts/test_ai_pipeline.py
```

**2. Test wszystkich scraperów:**
```bash
cd backend
python scripts/test_article_job.py
```

**3. Test Daily Summaries:**
```bash
cd backend
python scripts/test_daily_summary.py
```

**4. Dodaj Facebook (opcjonalnie):**
```bash
# 1. Dodaj do .env:
APIFY_API_KEY=apify_api_twój_token

# 2. Aktywuj źródła FB:
cd backend
python scripts/add_facebook_sources.py
```

---

### 🌐 Test API Endpoints

**Wymaganie: Serwer musi być uruchomiony (krok powyżej)**

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Lista źródeł
curl http://localhost:8000/api/sources

# 3. Artykuły (50 najnowszych)
curl http://localhost:8000/api/articles?limit=50

# 4. Pogoda (wszystkie lokalizacje)
curl http://localhost:8000/api/weather

# 5. Pogoda dla Rybna
curl http://localhost:8000/api/weather/Rybno

# 6. Najnowsze podsumowanie dzienne
curl http://localhost:8000/api/summary/daily

# 7. Podsumowanie z konkretnej daty
curl http://localhost:8000/api/summary/daily/2026-01-08
```

**Lub otwórz w przeglądarce:**
- Dokumentacja interaktywna: http://localhost:8000/docs
- Alternatywna dokumentacja: http://localhost:8000/redoc

---

### 📋 Sprawdź Scheduler Logi

Po uruchomieniu serwera zobaczysz logi w terminalu:
- ✅ Weather update - co 15min
- ✅ Article scraping - co 6h (wszystkie źródła)
- ✅ AI processing - co 30min
- ✅ **Daily summary - codziennie o 6:00** ← NOWE!

Przykładowy output:
```
INFO:     Started server process
INFO:     Waiting for application startup.
Scheduler - INFO - Scheduler started with jobs:
Scheduler - INFO -   - Update weather data (weather_update): interval[0:15:00]
Scheduler - INFO -   - Update articles (article_update): interval[6:00:00]
Scheduler - INFO -   - AI article processing (ai_processing): interval[0:30:00]
Scheduler - INFO -   - Generate daily summary (daily_summary): cron[hour=6, minute=0]
INFO:     Application startup complete.
```

---

## Info
- **Lokalizacja**: Powiat Działdowski (60k), start Rybno (2.5k)
- **Stack**: Python/FastAPI + PostgreSQL + Pydantic AI + Apify + Next.js
- **AI Models**: GPT-4o-mini (kategoryzacja), GPT-4o (wydarzenia + podsumowania)
- **Scrapery**: 4 aktywne (Klikaj, Gmina Rybno, Moje Działdowo, Facebook/Apify)
- **Źródła**: 7 total (3 HTML active, 3 Facebook active, 1 legacy)
- **Artykuły**: ~81 w bazie (31 + 29 + 1 + 20 FB), 15 przetworzonych
- **Daily Summaries**: 1 wygenerowane (automatycznie codziennie o 6:00)
- **Scheduler Jobs**: 4 (weather 15min, articles 6h, AI 30min, summary 6:00)
- **API Endpoints**: 8 (health, sources, articles, weather×3, summary×2)
- **Koszty**: ~578 PLN/mies (infra 515 + AI 63 + Apify 0-200)
- **Cel**: Inteligentny agregator lokalnych wiadomości z AI

---
**Ostatnia aktualizacja**: 2026-01-11 (FAZA 3 KOMPLETNA - Daily Summaries!)
**Test pomyślny**: Daily Summary wygenerowane w 15s, 5 highlights, 5 kategorii, API działa ✓
