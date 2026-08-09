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

## Scheduler Timeline (13 jobów)
```
6:00  → Article Scraping
6:15  → AI Processing (batch=100, kategoryzacja)
6:20  → Embedding Job (RAG, text-embedding-3-small)
6:50  → Proactive Alerts (Premium: mróz, śmietnik)
7:00  → Daily Summary
Co 15 min → Alerty push o awariach (prąd, woda, pożar, wypadek)
Co 1h → Weather Update
Co 4h → Air Quality (Airly)
9/12/15/18/21:05 → Energa (wyłączenia prądu)
2/6/10/14/18/22h → Traffic Cache (Gemini)
13:00–13:45 → Popołudniowy przebieg (scraping → AI → summary → embedding)
8:00  → Cinema Repertoire
Niedz 3:00 → CEIDG Sync
Niedz 4:00 → Wiedza stała z BIP (statut, procedury, podatki, programy)
Sob 10:00 → Newsletter Weekly
Pn-Pt 7:15 → Newsletter Daily (Premium)
1.01/04/07/10 → GUS Statistics
```

## Alerty push (2026-07-28)
**Awaria nie czeka na okno pipeline'u.** `alert_push_job` chodzi co 15 min i wysyła
do WSZYSTKICH subskrybentów (kategoria `alerty` — plan Dla Każdego, nie Premium).
- `services/alert_policy.py` — trzy bramki: **rodzaj** (prąd/woda/pożar/wypadek/gaz —
  zamknięta lista wzorców, NIE kategoria z AI, bo ta powstaje o 6:15 i 13:15),
  **miejsce** (musi paść nazwa z gminy Rybno — feed Energi jest zawężony do całego
  powiatu, więc bez tego szło powiadomienie o Płośnicy), **czas** (36 h do przodu
  dla zdarzeń z terminem, 24 h wstecz dla reszty)
- `articles.alert_pushed_at` — Energa odświeża ten sam wpis co 3 h pod wspólnym
  `external_id`; bez znacznika jedno wyłączenie budziłoby telefon kilkanaście razy
- Limit 2 powiadomienia / przebieg (`MAX_ALERTS_PER_RUN`)
- `_flat()` podmienia `ł`→`l` ręcznie: to jedyna polska litera, która NIE rozkłada
  się w NFKD — bez tego wzorzec na „wyłączenie" nie trafiał w nic
- Test: `cd backend && python -m scripts.test_alert_policy [--db]`
- Zgoda na push: `AlertPushPrompt` w feedzie przy realnej awarii (nie tylko w profilu)

## Nagłówek briefingu (2026-07-29)
**Nagłówek wskazuje kod, nie model** (`_select_top_article`), AI dostaje go jako
„WYMAGANY ARTYKUŁ NAGŁÓWKA". Klucz: **lokalność → nie-powtórka → kategoria → bliskość w czasie**.
- **Awaria traci priorytet 0**, gdy nie jest sprawą najbliższych godzin — próg wspólny
  z feedem (`is_pinned_alert`). Bez tego zapowiedź wyłączenia żyła w materiale tygodniami
  i wygrywała nagłówek co dzień (28 i 29.07 briefing otwierał się wyłączeniem z 7 sierpnia)
- **Lokalność wpisu, nie tylko źródła** (`feed_policy.is_local_article`): dla `COUNTY_WIDE_SOURCES`
  (oba kanały Energi, zasięg = powiat) musi paść nazwa z gminy Rybno — listę sołectw
  trzyma `alert_policy.places_in`, jedna na projekt. Wcześniej wyłączenie w Płośnicy
  szło do briefingu jako lokalna awaria
- **Bliskość, nie „najdalej w przyszłość"**: `_time_distance_h` liczy odległość od teraz
  w obie strony — wyłączenie jutro bije wyłączenie za dziewięć dni
- **Pamięć poprzedniego dnia**: `_previous_headline_id` odsuwa wczorajszy nagłówek na koniec
  jego grupy (nie wyklucza — przy chudym dniu wraca, bo to lepsze niż nagłówek regionalny).
  Refresh o 13:30 patrzy na dzień wcześniejszy, więc nagłówek jest stabilny w ciągu dnia
- Prompt: nagłówek awarii MUSI nazwać miejscowość — „AWARIA: wyłączenie w okolicy" nie mówi
  mieszkańcowi, czy chodzi o jego dom
- Test: `cd backend && python -m scripts.test_summary_headline [--db]`

## Strażnik: zdarzenie z terminem ≠ świeże ogłoszenie (2026-08-09)
**7.08 o 8:21 mieszkaniec pyta „czy dziś nie będzie prądu", Strażnik: „nie ma żadnych
zgłoszeń". Wyłączenie startowało o 9:00.** Wpis (art. 5060) był w bazie z `event_at`,
kategorią Awaria i osadzony w RAG — do kontekstu nie wszedł, bo zapytanie agenta
filtrowało po DACIE OGŁOSZENIA (`published_at >= now() - 7 dni`), a Energa ogłosiła
wyłączenie 28.07, dziesięć dni wcześniej. Feed i briefing dostały na to `event_at`
w lipcu (`_fetch_articles` w `summary_generator`), agent został z oknem publikacji.
- `straznik._fetch_alert_articles` ma teraz DWA okna: awaria bez terminu → 7 dni
  wstecz po publikacji; zdarzenie z `event_at` → od 6 h po zakończeniu do 72 h w przód,
  **bez względu na wiek ogłoszenia**. Kolejność: najbliżej zdarzenia, nie najświeżej
- Kontekst pokazuje TERMIN („ZDARZENIE dziś 09:00–14:00 — TRWA TERAZ"), datę ogłoszenia
  tylko w nawiasie, oraz zasięg (`gmina Rybno` / `poza gminą` przez `is_local_article`)
- Prompt: mając w kontekście zdarzenie zapowiedziane, agent NIE MOŻE odpowiedzieć
  „brak awarii" bez jego wymienienia — na pytanie ogólne gubił je nawet z poprawnym kontekstem
- ⚠️ Strażnik **nie używa RAG** (`source_types = []`) — obecność wpisu w `document_embeddings`
  nic tu nie gwarantuje. To zapytanie SQL jest jedynym źródłem jego wiedzy o awariach

## Redaktor: świeżość to nie zadanie dla wyszukiwarki (2026-08-09)
**„Co nowego w gminie?" → „nie mam aktualnych artykułów" przy 16 wpisach z 3 dni.**
RAG był świeży (każdy wpis z ostatnich 36 h ma chunki, ostatni zapis 13:45) — zawiódł
retrieval: pytanie ogólne nie ma słów wyróżniających, więc sąsiadami wektora były chunki
ze słowami „nowe" i „gmina" (Działdowo 2.08, Płośnica 25.02, Lubowidz 19.03, Stawiguda 31.03).
`rag_recency_boost=0.25` tego nie przebija. Model **poprawnie** nie podał tego jako nowin.
- `BaseAgent.extra_context(session, msg, retrieved_ids)` — hak na materiał, którego
  wyszukiwarka z definicji nie znajdzie. Domyślnie `None`, więc reszta agentów nie płaci nic
- `RedaktorAgent.extra_context` → blok **ŚWIEŻY FEED** (48 h, 8 wpisów, `feed_policy`:
  publishable + `article_score` + `collapse_duplicates`), z etykietą `[gmina Rybno]`/`[okolice]`
  i znacznikiem czasu; wpisy już wzięte przez RAG są pomijane (`retrieved_ids`)
- ⚠️ Blok to ~1,5 kB, czyli tyle co cały kontekst RAG → **bramka**: wchodzi tylko przy pytaniu
  ogólnym (`_GENERIC_QUESTION`) albo gdy retrieval dał < 3 trafienia. Przy „kiedy gra Delfin"
  nie wchodzi wcale — ten sam argument, przez który karta gminy ma limit 2 kB
- `feed_policy.time_label()` — jedno miejsce na znacznik „dziś 09:00–14:00 — TRWA TERAZ",
  używa go Strażnik i Redaktor. ⚠️ `summary_generator._time_label` to nadal osobna kopia;
  scalenie wymaga przebiegu `test_summary_headline`

## Kto czyta RAG (stan 2026-08-09)
| Agent | Wiedza | Uwagi |
|---|---|---|
| Redaktor | RAG `["article"]` + blok świeżego feedu | top_k 8, próg 0.35, recency 0.25 |
| Urzędnik | RAG `["bip_static","bip","article"]` | top_k 6, próg 0.40 |
| Strażnik / Organizator / Przewodnik / GUS | **własny SQL, zero RAG** | osadzenie wpisu nic tu nie gwarantuje |

Przebieg: scraping 6:00/13:00 → AI 6:15/13:15 (`processed`) → embedding 6:50/13:45 →
`document_embeddings`. Zapytanie: przepisanie pytania → synonimy → hybrid_search (wektor+BM25,
próg, recency) → rerank gpt-4o-mini → KONTEKST + karta gminy. Opóźnienie publikacja→RAG:
max ~7 h rano, ~45 min po południu (wieczorne posty FB czekają do rana).
⚠️ **1095 chunków `event` nie czyta żaden agent** — Przewodnik bierze wydarzenia SQL-em.

## Walidator odpowiedzi agentów (2026-08-09)
`backend/scripts/test_agent_answers.py` — 11 pytań mieszkańca sprawdzanych **kontra stan bazy**.
Oczekiwania liczy wyrocznia (własne zapytanie SQL, niezależne od kodu agenta), nie sztywna
lista odpowiedzi: „czy dziś nie będzie prądu" jest poprawne albo błędne wyłącznie względem
tego, co w bazie stoi na dziś.
- Dwa etapy: **KONTEKST** (czy fakt dotarł do materiału agenta — błąd zapytania/retrievalu)
  i **ODPOWIEDŹ** (czy model go powiedział — błąd promptu). Bez tego każdy czerwony wynik
  to śledztwo od zera
- `replay-07-08` odtwarza chwilę awarii (`_fetch_alert_articles(now=...)`) — jedyny przypadek
  z datą na sztywno, bo dotyczy zdarzenia, które już było
- Użycie: `python -m scripts.test_agent_answers [--dry] [--no-route] [--only id1,id2] [--list]`.
  `--dry` = same wyrocznie i kontekst, bez kosztów modelu. Kod wyjścia 1 przy błędzie
- Stan 9.08.2026 po naprawach Strażnika i Redaktora: **11/11 zielonych** na danych produkcyjnych
- Uruchamianie na prodzie z MacBooka: `ssh -f -N -L 55432:<IP kontenera db>:5432 root@91.99.142.30`,
  potem `DATABASE_URL=…@localhost:55432/centrum_operacyjne`. Lokalna baza jest z kwietnia
  i nie ma nawet kolumny `event_at`

## Wiedza agentów o gminie (2026-08-03)
**Dwie warstwy, bo to dwa różne rodzaje wiedzy.** Pytanie „ile gmina ma sołectw"
dostawało odpowiedź „nie posiadam danych, skontaktuj się z urzędem" + wykres ludności.
- **Karta gminy** (`services/gmina_facts.py`) — fakty fundamentalne (20 sołectw, wójt,
  15 radnych, jednostki, adres urzędu) wstrzykiwane **bezwarunkowo do KAŻDEGO agenta**
  przez `base_agent.base_context_messages()`. NIE przez RAG: odpowiedź na takie pytanie
  nie może zależeć od progu podobieństwa. Limit 2 kB pilnuje `scripts/test_gmina_facts.py`
  — rozdęta karta konkuruje o uwagę modelu z materiałem źródłowym.
  ⚠️ `alert_policy.GMINA_RYBNO_PLACES` (22 nazwy) to MIEJSCOWOŚCI, nie sołectwa (20) —
  nie podstawiać jednej listy pod drugą
- **`bip_documents` + `source_type="bip_static"`** — stałe działy BIP (statut, procedury,
  podatki, ochrona środowiska/azbest, gospodarka odpadami, fundusz sołecki).
  Osobna tabela, NIE `articles`: BIP jest w `feed_policy.LOCAL_SOURCES`, więc statut
  z 2016 r. wjechałby na Dashboard jako świeża wiadomość
- `scrapers/bip_knowledge.py` — bez cutoff dat, bez limitu 1000 zn., **wszystkie**
  załączniki PDF (scraper aktualności bierze `pdf_links[0]` i gubi resztę — konkrety
  programu dotacyjnego siedzą we wniosku i regulaminie, nie w ogłoszeniu).
  Zakres to jawna lista `DEFAULT_SECTIONS`, nie pełzanie po drzewie
- `content_hash` decyduje o ponownym osadzeniu — BIP odświeża strony bez zmiany treści
- Pierwsze napełnienie: `python -m scripts.migrations.add_bip_documents`, potem
  `python -m scripts.run_bip_knowledge` (`--dry` = podgląd bez kosztów).
  Cały korpus ~600 tys. znaków ≈ $0,003
- Routing: `gus_analityk` = WYŁĄCZNIE szeregi czasowe BDL; ustrój gminy → `urzednik`.
  Klasyfikator kategorii GUS zwraca `NO_CATEGORY` zamiast domyślnej „demografii" —
  to ona doklejała wykres ludności do niepowiązanych odpowiedzi
- **Synonimy** (`services/search_synonyms.py`) — mowa potoczna → język urzędowy, dopisywane
  do zapytania PRZED retrievalem (`base_agent`). Pomiar: „azbest" trafiał w dokument BIP
  z podobieństwem 0,674, „eternit" nie trafiał wcale. Termin jest dopisywany, nie
  podmieniany (oryginał pracuje w gałęzi BM25). Słownik ma zostać krótki
- Testy: `python -m scripts.test_gmina_facts`, `python -m scripts.test_bip_knowledge [--live]`
- ⚠️ **BIP /112/ milczy od 16.07.2026** — to NIE awaria scrapera (sprawdzone: parsuje
  10 pozycji, najwyższe ID 3713 = to w bazie). Gmina publikuje na FB i gminarybno.pl,
  sam BIP nie wydał obwieszczenia. Uboczne: scraper próbuje paginacji `?start=N`,
  a BIP używa `/112/2/` — czyta więc tylko pierwszą stronę (bez znaczenia przy cutoff 2 dni)

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
- **Obsada grafik W2 (2026-08-03)**: trzy powracające postacie — **Kuba** (urząd, dane, ciekawostki),
  **Ola** (wydarzenia, weekend, ludzie), **Bartek** (awarie, drogi, odpady, pogoda). Postać do zdarzenia
  wybiera gpt-4o (`cast` w JSON-ie), wygląd trzyma arkusz referencyjny `backend/assets/social/cast/<id>.jpg`
  podawany kie.ai w polu **`image_input`** (NIE `image_urls` — to inny model i zostałoby zignorowane bez błędu).
  Endpoint kopiuje arkusz do `uploads/social/cast/`, bo tylko ten katalog jest publiczny.
  Styl: naklejka komiksowa, gruby biały kontur, pociągnięcia pędzla; granat #05080f i błękit #3a81f6
  marki + żółć/magenta/fiolet. Prompt pilnuje **nowoczesnej** wsi (bez chałup z bali) i ubrań bez cudzych logo.
  Arkusze: `python -m scripts.build_social_cast [--only ola] [--force]`;
  podgląd posta bez publikacji: `python -m scripts.test_social_photo [--db] [--reference URL]`
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
