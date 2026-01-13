# Pipeline Przepływ - Centrum Operacyjne Mieszkańca

**Data utworzenia**: 2026-01-12
**Wersja**: 1.0

---

## 📊 Pełny Flow: Scraping → Baza → AI Processing → Daily Summary

```
backend/src/
│
├── 🕷️  KROK 1: SCRAPOWANIE (co 6h)
│   └── scrapers/
│       ├── base.py                    ← Klasa bazowa (BaseScraper)
│       ├── registry.py                ← Rejestr wszystkich scraperów
│       ├── klikajinfo.py              ← Scraper #1: Klikaj.info
│       ├── gmina_rybno.py             ← Scraper #2: Gmina Rybno
│       ├── mojedzialdowo.py           ← Scraper #3: Moje Działdowo
│       └── apify_facebook.py          ← Scraper #4: Facebook (przez Apify)
│
├── 💾 KROK 2: ZAPIS DO BAZY
│   ├── database/
│   │   └── schema.py                  ← Tabele: Article, Event, DailySummary, Source, Weather
│   └── scheduler/
│       └── article_job.py             ← Job: scrapuje + zapisuje do DB (co 6h)
│
├── 🤖 KROK 3: AI PROCESSING (kolumna `summary` w Article)
│   ├── ai/
│   │   ├── article_processor.py      ← Kategoryzacja + generowanie SUMMARY dla pojedynczego artykułu
│   │   ├── event_extractor.py        ← Ekstrakcja wydarzeń z artykułów → tabela Events
│   │   ├── models.py                 ← Pydantic modele (ArticleCategory, ExtractedEvent, DailySummary)
│   │   └── prompts.py                ← Prompty systemowe dla AI
│   └── scheduler/
│       └── ai_jobs.py                ← Job: przetwarza artykuły AI (co 30min)
│
├── 📰 KROK 4: DAILY SUMMARY (tabela `daily_summaries`)
│   ├── ai/
│   │   └── summary_generator.py      ← Agreguje artykuły + generuje dzienne podsumowanie
│   └── scheduler/
│       └── summary_job.py            ← Job: generuje daily summary (codziennie 6:00)
│
├── ⏰ SCHEDULER (orkiestracja wszystkiego)
│   └── scheduler/
│       └── scheduler.py              ← APScheduler: 4 joby (weather, articles, AI, summary)
│
└── 🌐 API (dostęp do danych)
    └── api/
        └── main.py                   ← FastAPI endpoints (8 endpointów)
```

---

## 🔄 Szczegółowy Przepływ Danych

### 1️⃣ **Scrapowanie Artykułów** (co 6 godzin)

**Trigger**: `scheduler.py` → `article_job.py`

**Proces**:
```
1. article_job.py wczytuje scrapery z registry.py
2. Dla każdego aktywnego źródła:
   - Pobiera scraper (klikajinfo.py, gmina_rybno.py, mojedzialdowo.py, apify_facebook.py)
   - Scraper wykonuje request do źródła
   - Parsuje HTML/JSON
   - Ekstrahuje: title, content, url, published_at, external_id
3. Zapis do bazy danych (tabela: articles)
   - Deduplikacja po URL i external_id
   - Automatyczne timestamp: created_at
   - Kolumny: id, source_id, title, content, url, published_at, external_id, created_at
4. Update last_scraped w tabeli sources
```

**Pliki zaangażowane**:
- `backend/src/scheduler/article_job.py` - główna logika
- `backend/src/scrapers/registry.py` - zarządzanie scraperami
- `backend/src/scrapers/base.py` - BaseScraper (retry, rate limit)
- `backend/src/scrapers/klikajinfo.py`
- `backend/src/scrapers/gmina_rybno.py`
- `backend/src/scrapers/mojedzialdowo.py`
- `backend/src/scrapers/apify_facebook.py`
- `backend/src/database/schema.py` - model Article

**Output**: Nowe artykuły w tabeli `articles` (kolumna `processed=False`)

---

### 2️⃣ **AI Processing - Summary Pojedynczego Artykułu** (co 30 minut)

**Trigger**: `scheduler.py` → `ai_jobs.py`

**Proces**:
```
1. ai_jobs.py pobiera nieprzetworzony artykuł (processed=False)
2. Wywołuje article_processor.py:
   a) Kategoryzacja do 8 modułów (GPT-4o-mini):
      - Urząd, Zdrowie, Edukacja, Biznes, Transport, Kultura, Nieruchomości, Rekreacja
   b) Ekstrakcja metadanych:
      - summary (2-3 zdania)
      - tags (3-5 tagów)
      - location_mentioned (lokalizacje z Powiatu Działdowskiego)
      - key_entities
      - confidence (0-100%)
3. Wywołuje event_extractor.py:
   - Identyfikuje czy artykuł zawiera wydarzenie (GPT-4o)
   - Ekstrahuje: title, date, time, location, organizer, price, contact
   - Zapis do tabeli events (jeśli znaleziono wydarzenie)
4. Update artykułu w bazie:
   - summary ← "Krótkie 2-3 zdaniowe podsumowanie artykułu"
   - category ← "Transport" / "Kultura" / etc.
   - tags ← ["droga 538", "remont", "powiat działdowski"]
   - location_mentioned ← ["Rybno", "Działdowo"]
   - processed ← True
```

**Pliki zaangażowane**:
- `backend/src/scheduler/ai_jobs.py` - główna logika
- `backend/src/ai/article_processor.py` - **generowanie kolumny `summary`**
- `backend/src/ai/event_extractor.py` - ekstrakcja wydarzeń
- `backend/src/ai/models.py` - Pydantic modele (ArticleCategory, ExtractedEvent)
- `backend/src/ai/prompts.py` - system prompts (CATEGORIZATION_PROMPT, EVENT_EXTRACTION_PROMPT)
- `backend/src/database/schema.py` - model Article, Event

**Output**:
- Zaktualizowane artykuły w tabeli `articles` (kolumna `summary` + `category` + `tags` + `processed=True`)
- Nowe rekordy w tabeli `events` (jeśli znaleziono wydarzenia)

---

### 3️⃣ **Daily Summary - Podsumowanie Wszystkich Artykułów** (codziennie 6:00)

**Trigger**: `scheduler.py` → `summary_job.py`

**Proces**:
```
1. summary_job.py wywołuje summary_generator.py
2. summary_generator.py (GPT-4o):
   a) Pobiera artykuły z ostatnich 24h (processed=True)
   b) Pobiera nadchodzące wydarzenia (7 dni do przodu)
   c) Pobiera aktualną pogodę
   d) Grupuje artykuły po kategoriach (8 modułów)
   e) Generuje strukturę JSONB:
      {
        "headline": "Chwytliwy nagłówek dnia (max 200 znaków)",
        "highlights": [
          "Top 1 najważniejsza wiadomość",
          "Top 2 najważniejsza wiadomość",
          "Top 3-5 najważniejsze wiadomości"
        ],
        "summary_by_category": {
          "Urząd": "Zwięzły opis wydarzeń w kategorii (2-3 zdania)",
          "Transport": "...",
          "Kultura": "...",
          ...
        },
        "upcoming_events": [
          {
            "title": "Festyn w Rybnie",
            "date": "2026-01-15",
            "location": "Rynek"
          },
          ...
        ],
        "weather_summary": "Dziś -9°C, duże zachmurzenie, wiatr 4 m/s",
        "stats": {
          "total_articles": 15,
          "categories_count": 6,
          "events_count": 3
        }
      }
3. Zapis do tabeli daily_summaries:
   - date ← "2026-01-12"
   - headline ← "Droga 538 otwarta po remoncie..."
   - content ← JSONB (cała struktura powyżej)
   - created_at ← timestamp
```

**Pliki zaangażowane**:
- `backend/src/scheduler/summary_job.py` - główna logika (async wrapper)
- `backend/src/ai/summary_generator.py` - **generowanie daily summary**
- `backend/src/ai/prompts.py` - DAILY_SUMMARY_PROMPT
- `backend/src/ai/models.py` - DailySummary (Pydantic model)
- `backend/src/database/schema.py` - model DailySummary

**Output**: Nowy rekord w tabeli `daily_summaries` (jeden per dzień)

---

## 🗄️ Struktura Bazy Danych

### Tabela: `articles`
```sql
id (int, primary key)
source_id (int, foreign key → sources.id)
title (varchar) - tytuł artykułu
content (text) - pełna treść
url (varchar, unique) - link do artykułu
external_id (varchar) - ID ze źródła (deduplikacja)
published_at (datetime) - data publikacji
created_at (datetime) - data dodania do bazy
last_modified (datetime)

-- AI Processing (dodane przez article_processor.py):
summary (text) - 2-3 zdaniowe podsumowanie
category (varchar) - jedna z 8 kategorii
tags (JSONB) - array tagów
location_mentioned (JSONB) - array lokalizacji
processed (bool, default=False) - czy AI przetworzyło
```

### Tabela: `events`
```sql
id (int, primary key)
article_id (int, foreign key → articles.id)
title (varchar) - nazwa wydarzenia
date (date) - data wydarzenia
time (time) - godzina
location (varchar) - miejsce
organizer (varchar) - organizator
price (varchar) - cena (może być "bezpłatnie")
contact (varchar) - dane kontaktowe
description (text)
created_at (datetime)
```

### Tabela: `daily_summaries`
```sql
id (int, primary key)
date (date, unique) - data podsumowania
headline (varchar) - nagłówek dnia
content (JSONB) - pełne podsumowanie (struktura jak wyżej)
created_at (datetime)
```

---

## ⏰ Scheduler Jobs (APScheduler)

**Plik**: `backend/src/scheduler/scheduler.py`

| Job | Częstotliwość | Plik | Funkcja |
|-----|---------------|------|---------|
| **Weather Update** | co 15 minut | `weather_job.py` | Aktualizacja pogody (OpenWeatherMap) |
| **Article Scraping** | co 6 godzin | `article_job.py` | Scrapowanie artykułów ze wszystkich źródeł |
| **AI Processing** | co 30 minut | `ai_jobs.py` | Kategoryzacja + ekstrakcja wydarzeń |
| **Daily Summary** | codziennie 6:00 | `summary_job.py` | Generowanie dziennego podsumowania |

---

## 🌐 API Endpoints

**Plik**: `backend/src/api/main.py`

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/health` | GET | Health check |
| `/api/sources` | GET | Lista źródeł (7 sources) |
| `/api/articles` | GET | Lista artykułów (limit, offset, category filter) |
| `/api/weather` | GET | Pogoda dla wszystkich lokalizacji |
| `/api/weather/{location}` | GET | Pogoda dla konkretnej lokalizacji |
| `/api/summary/daily` | GET | Najnowsze daily summary |
| `/api/summary/daily/{date}` | GET | Daily summary z konkretnej daty (YYYY-MM-DD) |
| `/api/events` | GET | Lista nadchodzących wydarzeń |

---

## 🔑 Różnice Kluczowe

### `Article.summary` vs `DailySummary.content`

| Aspekt | Article.summary | DailySummary.content |
|--------|-----------------|----------------------|
| **Plik** | `article_processor.py` | `summary_generator.py` |
| **Model AI** | GPT-4o-mini | GPT-4o |
| **Zakres** | Pojedynczy artykuł | Wszystkie artykuły z dnia |
| **Długość** | 2-3 zdania | Headline + highlights + podsumowania per kategoria |
| **Częstotliwość** | Co 30min (batch 20 artykułów) | Raz dziennie o 6:00 |
| **Tabela** | `articles.summary` (kolumna text) | `daily_summaries.content` (kolumna JSONB) |
| **Przykład** | "Droga 538 została otwarta po remoncie trwającym 3 miesiące. Inwestycja poprawia połączenie między Działdowem a Rybniem." | Pełna struktura z headline, highlights, 8 kategorii, wydarzenia, pogoda |

---

## 📈 Statystyki (stan na 2026-01-11)

- **Total Articles**: 138 (5 przetworzonych przez AI)
- **Sources**: 7 (5 aktywnych)
- **Events**: 1 wyekstrahowane
- **Daily Summaries**: 1 wygenerowane
- **Weather Records**: 16

### Performance:
- Scraping (6 źródeł, 132 artykuły): ~90s
- AI Kategoryzacja (5 artykułów): ~20s
- Event Extraction: ~5s
- Daily Summary: ~11s

### Koszty AI:
- Kategoryzacja (GPT-4o-mini): ~6s/artykuł, ~60 PLN/miesiąc
- Daily Summary (GPT-4o): ~$0.02/podsumowanie, ~2.50 PLN/miesiąc

---

## 🚀 Jak Uruchomić Pipeline

### 1. Start Backend (automatycznie uruchamia scheduler):
```bash
cd backend
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Manualne Testy:
```bash
# Test scrapingu
python backend/scripts/test_article_job.py

# Test AI processing
python backend/scripts/test_ai_pipeline.py

# Test daily summary
python backend/scripts/test_daily_summary.py
```

---

## 📚 Powiązane Dokumenty

- **CLAUDE.md** - Status projektu + historia zmian
- **PIPELINE_TEST_REPORT.md** - Raport testowy pipeline'u
- **backend/docs/APIFY_SETUP.md** - Setup Apify Facebook
- **backend/docs/NEW_SCRAPERS.md** - Dokumentacja scraperów

---

**Ostatnia aktualizacja**: 2026-01-12
**Autor**: Claude Code
**Wersja Backend**: v1.0 (Faza 3 Complete)
