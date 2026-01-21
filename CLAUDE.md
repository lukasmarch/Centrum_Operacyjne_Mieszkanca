# Centrum Operacyjne Mieszkańca - Status

## Aktualny stan
**Faza 4B** - Frontend Integration + Newsletter + Auth

## Ukończone funkcje

### Backend
- FastAPI + PostgreSQL + Redis
- 5 scraperów (HTML, RSS, Facebook/Apify)
- AI pipeline (GPT-4o-mini kategoryzacja, GPT-4o podsumowania)
- 10 źródeł danych, 174+ artykułów
- APScheduler (6 jobów automatycznych)
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
├── scheduler/    # 6 jobów
└── newsletter/   # Email

frontend/
├── components/   # React components
├── src/
│   ├── context/  # Auth, Cache
│   ├── hooks/    # useArticles, useWeather
│   └── pages/    # Login, Profile
```

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
*Ostatnia aktualizacja: 2026-01-21*
