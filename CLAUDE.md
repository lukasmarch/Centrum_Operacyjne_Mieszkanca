# Centrum Operacyjne Mieszkańca - Status

## Aktualny stan
**Faza 6 - Multi-Agent AI System + RAG + Chat UI**

## Stack
- **Backend**: FastAPI + PostgreSQL + pgvector + OpenAI
- **Frontend**: React 19 + TypeScript + Vite + TailwindCSS
- **AI**: GPT-4o-mini (routing/kategoryzacja), GPT-4o (summary/GUS), text-embedding-3-small (RAG)
- **Scheduler**: APScheduler (12 jobów)
- **Auth**: JWT (tier: free/premium/business)
- **Lokalizacja**: Gmina Rybno, Powiat Działdowski

## Uruchomienie

```bash
# Backend
source .venv/bin/activate && cd backend && uvicorn src.api.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev   # port 3001

# Docker (PostgreSQL + pgvector)
docker-compose up -d
```

## Scheduler Timeline (12 jobów)
```
6:00  → Article Scraping
6:15  → AI Processing (batch=100, kategoryzacja)
6:20  → Embedding Job (RAG, text-embedding-3-small)
7:00  → Daily Summary
Co 1h → Weather Update
Co 4h → Air Quality (Airly)
2/6/10/14/18/22h → Traffic Cache (Gemini)
8:00  → Cinema Repertoire
Niedz 3:00 → CEIDG Sync
Sob 10:00 → Newsletter Weekly
Pn-Pt 7:15 → Newsletter Daily (Premium)
1.01/04/07/10 → GUS Statistics
```

## Struktura Backend

```
backend/src/
├── ai/
│   ├── agents/         # 5 agentów AI + orchestrator
│   │   ├── orchestrator.py   # routing GPT-4o-mini
│   │   ├── base_agent.py     # RAG + streaming (SSE)
│   │   ├── redaktor.py       # wiadomości lokalne
│   │   ├── urzednik.py       # BIP, przetargi
│   │   ├── gus_analityk.py   # statystyki (❌ wymaga SQL)
│   │   ├── przewodnik.py     # wydarzenia, pogoda
│   │   └── straznik.py       # awarie, bezpieczeństwo
│   ├── embeddings.py   # EmbeddingService (pgvector)
│   ├── chunker.py      # tekst → chunki
│   └── ...             # kategoryzacja, summary
├── api/endpoints/
│   ├── chat.py         # POST /api/chat/message (SSE), GET /history /suggestions /agents
│   ├── articles.py
│   ├── weather.py
│   ├── summary.py
│   ├── gus.py          # tier-based stats
│   └── ...
├── database/
│   ├── schema.py       # modele (Article, Event, User, GUSGminaStats...)
│   ├── vectors.py      # Conversation, ChatMessage, DocumentEmbedding
│   └── connection.py   # async_session()
├── scheduler/
│   ├── embedding_job.py  # RAG embeddings
│   └── ...
└── integrations/
    └── gus_variables.py  # 88 zmiennych, 10 kategorii, 3 tiery
```

## Struktura Frontend

```
frontend/
├── App.tsx                    # routing (useState<AppSection>)
├── components/
│   ├── ChatInterface.tsx      # chat UI + wybór agenta
│   ├── ChatMessage.tsx        # bąbelki wiadomości
│   ├── SourceChip.tsx         # chip z linkiem do źródła
│   ├── PromptBar.tsx          # hero input (Dashboard)
│   ├── BentoGrid/Tile         # dashboard layout
│   ├── AIBriefingTile.tsx     # daily summary tile
│   ├── WeatherTile.tsx
│   ├── NewsTile.tsx
│   ├── EventsTile.tsx
│   └── gus/                  # GUS components (dark mode ✅)
└── src/
    ├── hooks/
    │   ├── useChat.ts         # SSE streaming hook
    │   ├── useArticles.ts
    │   ├── useWeather.ts
    │   └── useGUSStats.ts
    ├── pages/
    │   ├── AssistantPage.tsx  # Asystent AI
    │   ├── GUSPage.tsx
    │   ├── WeatherPage.tsx
    │   └── ...
    └── context/
        ├── AuthContext.tsx
        └── DataCacheContext.tsx
```

## Główne endpointy API
```
GET  /health
GET  /api/articles
GET  /api/weather
GET  /api/summary/daily
POST /api/auth/login
GET  /api/chat/agents
GET  /api/chat/suggestions
GET  /api/chat/history
POST /api/chat/message          # SSE streaming
GET  /api/stats/variables/list  # GUS tier-based
GET  /api/stats/variable/{key}
GET  /api/stats/multi-metric    # Business tier
```
Docs: http://localhost:8000/docs

## Stan RAG / Embeddings
- **Osadzone**: 100 artykułów, 50 eventów → 170 chunków w `document_embeddings`
- **Nieosadzone**: ~1065 artykułów (uruchomić embedding_job)
- **Model**: text-embedding-3-small (1536 dim)
- **Tabela**: `document_embeddings` (pgvector 0.8.1)

## Stan Agentów AI
| Agent | Status | Dane |
|-------|--------|------|
| Redaktor | ✅ działa | RAG artykuły |
| Urzędnik | ✅ działa | RAG artykuły |
| Strażnik | ✅ działa | RAG artykuły |
| Przewodnik | ⚠️ częściowo | RAG eventy/artykuły, pogoda/śmieci brak |
| GUS-Analityk | ❌ wymaga naprawy | Potrzeba SQL do gus_gmina_stats |

## Ważne reguły techniczne
- `VITE_API_URL = http://localhost:8000/api` → hooki NIE dodają `/api/` prefixu
- Auth dependency: `get_optional_user` (nie `get_current_user_optional`)
- SSE split: po `\n` + `trim()` (nie `\n\n` - base_agent yield ma trailing `\n`)
- pgvector insert: `$emb$[...]$emb$::vector`, `$meta${json}$meta$::jsonb` (dollar-quoting)
- DB session w SSE generatorze: używaj `async_session()` z `database.connection`
- Frontend routing: `useState<AppSection>` w App.tsx (switch/case, brak react-router)
- Redis usunięty - cache w PostgreSQL

## Tier System
- **Free**: 5 zmiennych GUS, 10 pytań/dzień do AI
- **Premium**: 21 zmiennych GUS, newsletter daily, push notifications
- **Business**: 88 zmiennych GUS, multi-metric, dostęp do API

## TODO (Kolejne priorytety)
- [ ] GUS-Analityk: SQL queries do `gus_gmina_stats` (zamiast RAG)
- [ ] Więcej embeddingów: osadzić pozostałe ~1065 artykułów
- [ ] Przewodnik: dane pogodowe w embeddingach lub direct query
- [ ] Widget pogody → live API
- [ ] Filtrowanie artykułów po kategoriach
- [ ] Panel administracyjny

## Git Branches
```
main     # produkcja
develop  # integracja (aktywna)
```

## Pliki pomocnicze
- `.git-rules.md` - zasady Git i workflow
- `backend/scripts/diagnostics/` - narzędzia diagnostyczne
- `backend/logs/scheduler.log` - logi schedulera (rotacja 10MB)

---
*Ostatnia aktualizacja: 2026-02-23*
