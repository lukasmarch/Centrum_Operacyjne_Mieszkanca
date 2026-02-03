# Centrum Operacyjne Mieszkańca - Status

## Aktualny stan
**Faza 4B** - Frontend Integration + Newsletter + Auth

## Ukończone funkcje

### Backend
- FastAPI + PostgreSQL + Redis
- 5 scraperów (HTML, RSS, Facebook/Apify)
- AI pipeline (GPT-4o-mini kategoryzacja, GPT-4o podsumowania)
- 10 źródeł danych, 620+ artykułów (441 przetworzonych)
- APScheduler (8 jobów, daily pipeline: 6:00→6:15→6:45)
- File logging (`logs/scheduler.log`, rotacja 10MB)
- Diagnostic tools (`scripts/diagnostics/`)
- Autentykacja JWT
- Newsletter (Resend)
- Integracja GUS

### Frontend
- React 19 + TypeScript + Vite
- Dashboard z widgetami
- Mapy (Leaflet) - tracker autobusów
- Logowanie/rejestracja
- Feed artykułów i wydarzeń

## Uruchomienie

### Backend
```bash
cd /Users/lukaszmarchlewicz/Desktop/Centrum_Operacyjne_Mieszkańca
source .venv/bin/activate
cd backend
uvicorn src.api.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm run dev
```

### Docker (baza danych)
```bash
docker-compose up -d
```

## Główne endpointy
- `GET /health` - status
- `GET /api/articles` - artykuły
- `GET /api/weather` - pogoda
- `GET /api/summary/daily` - podsumowanie AI
- `POST /api/auth/login` - logowanie
- Docs: http://localhost:8000/docs

## Struktura

```
backend/src/
├── ai/           # AI processing
├── api/          # FastAPI
├── auth/         # JWT auth
├── scrapers/     # 5 scraperów
├── scheduler/    # 8 jobów (daily pipeline: 6:00→6:15→6:45)
├── newsletter/   # Email
└── utils/        # Logger (file + console)

backend/scripts/
├── diagnostics/  # check_scheduler_health.py, check_articles_for_summary.py
├── production/   # regenerate_daily_summary.py, generate_daily_summary_test.py
└── tests/        # test_full_pipeline.py

backend/logs/
└── scheduler.log # APScheduler logs (rotacja 10MB)

frontend/
├── components/   # React components
├── src/
│   ├── context/  # Auth, Cache
│   ├── hooks/    # useArticles, useWeather
│   └── pages/    # Login, Profile
```

## Scheduler Timeline (Daily Pipeline)
```
6:00 AM → Article Scraping (scraping nowych artykułów)
6:15 AM → AI Processing (kategoryzacja artykułów)
6:45 AM → Daily Summary (generowanie podsumowania dla wczoraj)
Co 1h   → Weather Update
8:00 AM → Cinema Repertoire Update
```

## Ostatnio Ukończone (2026-02-02)
✅ **Daily Summary Scheduler - Naprawa Timing Issue**
- Problem: Summary nie generowało się (artykuły nieskategoryzowane)
- Fix: Zmiana kolejności jobów (AI processing przed summary)
- Nowy pipeline: 6:00 scraping → 6:15 AI → 6:45 summary (1x dziennie)
- Dodano file logging (`logs/scheduler.log`)
- Dodano diagnostic scripts (`scripts/diagnostics/`)
- Branch: `develop`

## W trakcie (Current Work)
**Branch:** `feature/frontent-witget-garbage`
- [ ] Widget śmieciowy (garbage collection) - frontend

## TODO (Faza 5)
- [ ] Widget pogody -> API
- [ ] Filtrowanie artykułów po kategoriach
- [ ] Panel administracyjny
- [ ] Powiadomienia push

## Git Branches
```
main                              # produkcja
develop                           # integracja
feature/frontent-witget-garbage   # aktywna praca
```

## Info
- **Lokalizacja:** Powiat Działdowski
- **Stack:** FastAPI + React 19 + PostgreSQL + OpenAI
- **Koszty:** ~580 PLN/mies

## Pliki kontekstowe
- `.claude-context.md` - szczegółowy kontekst techniczny projektu
- `.git-rules.md` - zasady Git i workflow

---
*Ostatnia aktualizacja: 2026-02-02*
