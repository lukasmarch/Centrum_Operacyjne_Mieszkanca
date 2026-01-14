# Changelog - Centrum Operacyjne Mieszkańca

## [2026-01-13] - FAZA 4A: RSS Feeds + AI Improvements

### ✅ Dodano
- **Universal RSS Scraper** (`backend/src/scrapers/rss_scraper.py`)
  - Obsługa RSS 2.0 i Atom
  - Automatyczna ekstrakcja metadanych (tytuł, autor, data, obrazy)
  - Obsługa Cloudflare (custom headers)
  - Integracja z registry pattern

- **Nowe źródła RSS:**
  - Radio 7 Działdowo (radio7.pl/rss) - 10 artykułów
  - Gazeta Olsztyńska (gazetaolsztynska.pl/rss) - ready to use

- **Nowe skrypty:**
  - `process_all_articles.py` - batch AI processing
  - `regenerate_daily_summary.py` - regeneracja podsumowań
  - `view_daily_summary.py` - podgląd podsumowań
  - `find_rss_feeds.py` - automatyczne szukanie RSS feeds
  - `add_working_rss_sources.py` - dodawanie źródeł RSS
  - `test_radio7_rss.py` - test RSS scrapera

- **Dokumentacja:**
  - `DAILY_SUMMARY_COMPARISON.md` - raport porównawczy AI improvements

### 🔧 Zmieniono
- **AI Prompt Engineering** (`backend/src/ai/prompts.py`)
  - Zaktualizowano `DAILY_SUMMARY_PROMPT`
  - Nowa priorytetyzacja: PILNE → PRAKTYCZNE → NICE-TO-KNOW
  - Kultura/rozrywka jako dodatek, nie główny temat
  - Headline musi być o czymś WAŻNYM lub NOWYM

- **Scraper Registry** (`backend/src/scrapers/registry.py`)
  - Dodano pattern matching dla RSS (wszystkie "*RSS" używają RSSFeedScraper)
  - Zaktualizowano `get_scraper()` function

### 📊 Wyniki
- **AI Processing:**
  - 89 nieprzetworzonych artykułów → 100% (174/174)
  - Czas: ~7 minut (GPT-4o-mini)

- **Rozkład kategorii (poprawiony):**
  - Kultura: 45.9% → 38.5% (spadek -7.4pp)
  - Transport: 4.7% → 9.8% (wzrost +5.1pp)
  - Edukacja: 11.8% → 14.9% (wzrost +3.1pp)
  - Zdrowie: 4.7% → 6.3% (wzrost +1.6pp)

- **Daily Summary (ID: 8):**
  - 8 artykułów (było 3) - +167%
  - 5 highlights (było 3)
  - 3 kategorie (było 2)
  - Większa różnorodność, lepszy rozkład

### 🐛 Znane problemy
- `Article.locations` attribute error (kosmetyczny - nie wpływa na kategoryzację)
- Gazeta Olsztyńska RSS wymaga encoding fix
- Nasze Miasto Działdowo - Cloudflare blocking

---

## [2026-01-11] - FAZA 3: Daily Summaries

### ✅ Dodano
- `SummaryGenerator` class
- Daily summary scheduler (6:00 AM)
- API endpoints: `/api/summary/daily`, `/api/summary/daily/{date}`
- Tabela `daily_summaries` w bazie

### 📊 Wyniki
- Automatyczne podsumowania codziennie o 6:00
- 10-15s czas generowania
- Koszty AI: ~$0.02 per podsumowanie

---

## [2026-01-08] - FAZA 2: Rozbudowa Scraperów

### ✅ Dodano
- Scraper Registry Pattern
- `MojeDzialdowoScraper` (HTML)
- `GminaRybnoScraper` (BIP)
- `ApifyFacebookScraper` (Facebook posts)
- Dokumentacja: `APIFY_SETUP.md`, `NEW_SCRAPERS.md`

### 📊 Wyniki
- 3 nowe źródła HTML
- 3 konta Facebook (gotowe po dodaniu API key)
- ~61 artykułów w bazie

---

## [2026-01-07] - FAZA 1: AI Processing Pipeline

### ✅ Dodano
- `ArticleProcessor` (GPT-4o-mini)
- `EventExtractor` (GPT-4o)
- AI Scheduler (co 30 min)
- Pydantic AI models + prompts

### 📊 Wyniki
- 15/31 artykułów przetworzonych (48.4%)
- Confidence: 90%
- ~6s per artykuł

---

## [2026-01-07] - FAZA 1: Setup Backend + First Scraper

### ✅ Dodano
- Backend: Python/FastAPI + PostgreSQL + Redis
- Database: SQLModel + Alembic
- `BaseScraper` class
- `KlikajInfoScraper` (pierwszy scraper)
- `OpenWeatherMap` integration
- APScheduler (3 jobs)

### 📊 Wyniki
- 31 artykułów z Klikaj.info
- Weather API działa (15min updates)
- Scheduler uruchomiony
