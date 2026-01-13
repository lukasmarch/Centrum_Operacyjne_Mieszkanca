# Quick Start Guide - Centrum Operacyjne Mieszkańca

## 🚀 Uruchom Backend w 3 krokach

### 1. Aktywuj środowisko
```bash
cd /Users/lukaszmarchlewicz/Desktop/Centrum_Operacyjne_Mieszkańca
source .venv/bin/activate
```

### 2. Uruchom serwer
```bash
cd backend
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Sprawdź czy działa
Otwórz w przeglądarce: **http://localhost:8000/docs**

---

## 📡 Dostępne API Endpoints

Po uruchomieniu serwera możesz użyć:

| Endpoint | Opis | Przykład |
|----------|------|----------|
| `GET /health` | Health check | `curl http://localhost:8000/health` |
| `GET /api/sources` | Lista źródeł | `curl http://localhost:8000/api/sources` |
| `GET /api/articles` | Artykuły (50 najnowszych) | `curl http://localhost:8000/api/articles?limit=50` |
| `GET /api/weather` | Pogoda wszystkie lokalizacje | `curl http://localhost:8000/api/weather` |
| `GET /api/weather/{location}` | Pogoda dla lokalizacji | `curl http://localhost:8000/api/weather/Rybno` |
| `GET /api/summary/daily` | Najnowsze podsumowanie | `curl http://localhost:8000/api/summary/daily` |
| `GET /api/summary/daily/{date}` | Podsumowanie z daty | `curl http://localhost:8000/api/summary/daily/2026-01-08` |

---

## 🧪 Testy

```bash
# Test AI Pipeline
cd backend
python scripts/test_ai_pipeline.py

# Test Scrapers
python scripts/test_article_job.py

# Test Daily Summaries
python scripts/test_daily_summary.py
```

---

## 🤖 Scheduler Jobs (automatyczne)

Po uruchomieniu serwera działają:
- ⏰ **Weather update** - co 15min
- ⏰ **Article scraping** - co 6h
- ⏰ **AI processing** - co 30min
- ⏰ **Daily summary** - codziennie o 6:00

---

## 📚 Pełna dokumentacja

Zobacz: `CLAUDE.md` - pełny status projektu i szczegóły implementacji
