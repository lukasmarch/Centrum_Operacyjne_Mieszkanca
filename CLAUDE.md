# Centrum Operacyjne Mieszkańca - Status

## Aktualny stan
**Faza 7 - PRODUKCJA LIVE** 🟢 https://rybnolive.pl

## Infrastruktura produkcyjna
- **Serwer**: Hetzner CX22, IP: `91.99.142.30` (Ubuntu 24.04)
- **Domena**: rybnolive.pl (DNS: Hostinger → 91.99.142.30)
- **Frontend**: https://rybnolive.pl (Caddy → Docker volume)
- **Backend API**: https://api.rybnolive.pl (Caddy → FastAPI :8000)
- **SSL**: Let's Encrypt via Caddy (auto-renewal)
- **Repo na serwerze**: `/opt/centrum` (branch: main)
- **Env sekrety**: `/opt/centrum/backend/.env.production` (nie w repo)
- **Docker env**: `/opt/centrum/.env` (DB_USER, DB_PASSWORD)

## Git Workflow (PRODUKCJA)
```
main   ← aktywna gałąź, zmiany idą tu bezpośrednio
        push → GitHub Actions → SSH deploy backend na VPS
        
Deploy frontendu (ręcznie):
  ./deploy-frontend.sh 91.99.142.30
```

## Komendy produkcyjne
```bash
# SSH na serwer
ssh root@91.99.142.30

# Status kontenerów
docker compose -f docker-compose.prod.yml ps

# Logi backendu
docker compose -f docker-compose.prod.yml logs backend --tail 50

# Restart backendu (po zmianach env)
docker compose -f docker-compose.prod.yml up -d backend

# Deploy frontendu (z MacBooka)
./deploy-frontend.sh 91.99.142.30
```

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
GET  /api/social/proposal?kind=text|photo   # gotowy post dla n8n (X-Social-Token)
GET  /api/social/campaign/due               # kalendarz kampanii
POST /api/social/media                      # grafika z URL → uploads/social/
```

## Newsletter — szata graficzna marki (2026-07-27)
- Szablony: `templates/_base.html` (nagłówek, CTA, stopka) + `daily.html` / `weekly.html` dziedziczą przez Jinja `{% extends %}`
- Ciemna paleta jak w serwisie (#020617 / #0d1117), font Outfit + monospace na liczbach, układ na `<table>` (Outlook), 600 px, ~25 KB
- Briefing: temat i nagłówek **składane w kodzie** (`Rybno, pon. 27 lipca · 18° · powietrze bardzo dobre`) — model potrafił wstawić złą datę; AI daje tylko `status_line` + `highlights` z polem `agent` (Redaktor/Urzędnik/Strażnik/Przewodnik/Organizator → kolor karty; walidacja w `email_service.AGENT_COLORS`, fallback Redaktor)
- Wypis działa: `GET /api/newsletter/unsubscribe?token=` (strona z przyciskiem, sam GET nic nie zmienia — skanery poczty odwiedzają linki) + `POST` (formularz, JSON, one-click). Mail wysyłany z nagłówkami `List-Unsubscribe` / `List-Unsubscribe-Post`
- Stopka: wydawca Lu-Mar-Go, Żabiny 96 + „serwis niezależny, nieprowadzony przez Urząd Gminy Rybno" (makieta miała adres urzędu)
- Sekcja „Polecane firmy" wyłączona flagą `NEWSLETTER_ADS_ENABLED=false` — wraca po pierwszej sprzedaży planu Firma lokalna
- Podgląd bez wysyłki: `python scripts/test_newsletter_send.py x@example.com --preview-dir /tmp/nl`

## Automatyzacja social media (2026-07-25, grafiki w każdym poście 2026-07-26)
**Backend robi treść, n8n tylko akceptuje i publikuje.**
- `services/social_content.py` — treść postów, prompt graficzny, klient kie.ai (`nano-banana-pro`), `CAMPAIGN_PLAN`
- `services/social_card.py` — **karta dnia**: grafika 1200×630 składana lokalnie (Pillow) z `headline`; 0 zł, ~0,1 s; font `backend/assets/fonts/Outfit.ttf` + kadr `backend/assets/social/orb.jpg` (`COPY assets/` w Dockerfile)
- **Oba rodzaje postów idą jako `/photos`** (nie `/feed`) — zdjęcie zamiast karty linku; `rybnolive.pl` zostaje w treści
- OG w `frontend/index.html`: domena `rybnolive.pl` + `og-image.jpg` 1200×630 (było `rybno.pl/icon-512.png` → pusty kwadrat pod postami)
- Grafiki: **jedno miejsce** `uploads/social/` → `api.rybnolive.pl/uploads/social/…` (wolumen `uploads`).
  Zlikwidowane duplikaty: `frontend/public/kampania/` i `/campaign/` na wolumenie frontendu
- n8n: 3 workflowy generowane z `automation/n8n/build_workflows.py` (W1 tekstowy 7:45, W2 graficzny wt+czw 17:00, W3 kampania)
- Akceptacja przez `$execution.resumeUrl` node'a Wait — jednorazowy, bez timeoutu (**fail-closed**: brak kliknięcia = brak publikacji)
- Sekrety: `automation/.env` (gitignore); w backendzie `SOCIAL_MEDIA_TOKEN`, `KIE_API_KEY`
- Klucz Public API n8n wygasa **2026-08-23**; po 10.08 **dezaktywuj W3**
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
| GUS-Analityk | ✅ działa | Direct SQL do gus_gmina_stats + gus_national_averages (zweryfikowane na prodzie 2026-07-19) |
| Organizator | ✅ działa | Direct SQL do waste_schedule |

## Ważne reguły techniczne
- `VITE_API_URL = http://localhost:8000/api` → hooki NIE dodają `/api/` prefixu
- Auth dependency: `get_optional_user` (nie `get_current_user_optional`)
- SSE split: po `\n` + `trim()` (nie `\n\n` - base_agent yield ma trailing `\n`)
- pgvector insert: `$emb$[...]$emb$::vector`, `$meta${json}$meta$::jsonb` (dollar-quoting)
- DB session w SSE generatorze: używaj `async_session()` z `database.connection`
- Frontend routing: `useState<AppSection>` w App.tsx (switch/case, brak react-router)
- Redis usunięty - cache w PostgreSQL

## Tier System (ceny od 2026-07-19)
- **Free (0 zł)**: 9 zmiennych GUS, 5 pytań AI/dzień (anonim: 3)
- **Premium (9,99 zł/mc · 84 zł/rok)**: 57 zmiennych GUS, AI bez limitu, newsletter daily, push, proaktywny asystent; **trial 30 dni bez karty** po rejestracji
- **Firma lokalna (tier `business`, 49 zł/mc · 490 zł/rok, B2B §11 regulaminu)**: 88 zmiennych GUS + wyróżniona wizytówka („Polecane w Rybnie", is_premium na business_profiles — auto-aktywacja po płatności P24)
- Płatności: Przelewy24 (`p24_service.py`); IPN → `API_URL/api/payments/webhook` (api.rybnolive.pl!); powrót → `APP_URL/payment/success` (PaymentReturnBanner.tsx); wygaszanie subskrypcji/trialu/wizytówek: trial_expiry_job (5:00)

## TODO (Kolejne priorytety)
- [ ] P24 go-live: rejestracja merchanta (Łukasz), wpis P24_* do .env.production, P24_SANDBOX=false, test end-to-end
- [ ] Przewodnik: dane pogodowe w embeddingach lub direct query
- [ ] Widget pogody → live API
- [ ] Filtrowanie artykułów po kategoriach
- [ ] Panel administracyjny
- [ ] Ogłoszenia firm w feedzie (2/mc dla planu Firma lokalna — obiecane w BusinessPage)

Uwaga: ~1065 historycznych artykułów poza RAG — **celowo** (decyzja 2026-07-19), embedded=True jako marker.

## Git Branches
```
main     # produkcja + aktywna praca (auto-deploy przez GitHub Actions)
develop  # nieaktywna
```

## Pliki pomocnicze
- `.git-rules.md` - zasady Git i workflow
- `backend/scripts/diagnostics/` - narzędzia diagnostyczne
- `backend/logs/scheduler.log` - logi schedulera (rotacja 10MB)

---
*Ostatnia aktualizacja: 2026-07-19*
