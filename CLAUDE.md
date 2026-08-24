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
- **AI**: GPT-4o-mini (routing/kategoryzacja), GPT-4o (summary/GUS), text-embedding-3-small (RAG)
- **Lokalizacja**: Gmina Rybno, Powiat Działdowski
- Wersje bibliotek: `frontend/package.json`, `backend/requirements.txt` (nie duplikujemy ich tutaj — notatka się rozjeżdżała)

## Uruchomienie

```bash
# Backend
source .venv/bin/activate && cd backend && uvicorn src.api.main:app --reload --port 8000

# Frontend — MUSI być z katalogu frontend, tam leży vite.config.ts
cd frontend && npm run dev   # port 3001

# Docker (PostgreSQL + pgvector) — plik compose leży w backend/, NIE w korzeniu
cd backend && docker compose up -d
```
Lokalna baza: kontener `backend-postgres-1` (:5432), Adminer :8080.
CORS backendu dopuszcza `localhost:3001/3002/5173` — podgląd na innym porcie
nie dogada się z API.

## WYRÓWNANIE BAZ — testujemy lokalnie, nie na produkcji (2026-08-18)

**Kod ma się pokrywać, różnić mają się tylko rekordy.** 18.08 okazało się, że
lokalna baza była o **3 tabele i 7 kolumn** za produkcją — stąd odruch
sprawdzania rzeczy „na żywym", bo lokalnie kod po prostu nie działał.

**Przyczyna, którą trzeba znać:** `alembic_version` pokazuje **tę samą wersję
`22fbd3a7c45e` w obu bazach**, a schematy się różnią. Każda zmiana schematu idzie
ręcznym skryptem z `backend/scripts/migrations/` (**34 sztuki**) i **żaden nie
dopisuje nic do `alembic_version`**. Nie ma więc licznika, który powie, czego
brakuje — rozjazd narasta po cichu.

**Sprawdzenie rozjazdu (rób to przed każdą dłuższą pracą na bazie):**
```bash
Q="select table_name||'.'||column_name from information_schema.columns where table_schema='public' order by 1"
docker exec backend-postgres-1 sh -c "psql -U \$POSTGRES_USER -d centrum_operacyjne -tAc \"$Q\"" | sort > /tmp/local.txt
ssh root@91.99.142.30 "docker exec centrum-db-1 sh -c \"psql -U \\\$POSTGRES_USER -d centrum_operacyjne -tAc \\\"$Q\\\"\"" | sort > /tmp/prod.txt
comm -13 /tmp/local.txt /tmp/prod.txt   # czego brakuje LOKALNIE
comm -23 /tmp/local.txt /tmp/prod.txt   # co mamy ponad produkcję
```

**Wyrównanie lokalnej bazy** — uruchom brakujące migracje (są idempotentne):
```bash
cd backend && python -m scripts.migrations.<nazwa>
```
⚠️ **NIE odpalać wszystkich 34 hurtem** — część to operacje na DANYCH, nie na
schemacie: `clean_database.py`, `remove_duplicate_events.py`,
`disable_risky_sources.py`, `normalize_ceidg_casing.py`, `ceidg_minimalizacja_rodo.py`.

**Kierunek rozjazdu ma znaczenie:**
- **Produkcja z przodu** = błąd. Kodu nie da się uruchomić u siebie, więc testuje
  się na żywym. Wyrównaj natychmiast.
- **Lokalnie z przodu** = stan normalny. Kolumna jest u nas, bo TU testujemy kod,
  który dopiero czeka na wdrożenie.

**Reguła wdrożeniowa: migracja idzie na produkcję PRZED kodem, nigdy odwrotnie.**
Kolumna, której stary kod nie używa, nie szkodzi nikomu — kod bez kolumny to 500
na każdym zapytaniu. GitHub Actions **nie uruchamia migracji**: robi tylko
`git pull && build && up -d`.

## Scheduler Timeline (13 jobów)
```
6:00  → Article Scraping
6:15  → AI Processing (batch=100, kategoryzacja)
6:20  → Embedding Job (RAG, text-embedding-3-small)
18:00 → Wieczorne przypomnienia push (Premium: wywóz JUTRO, mróz tej nocy)
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

## Podział gałęzi (2026-08-18)
- **`strona-glowna-etap0`** — praca przenikająca front i backend (przebudowa strony
  głównej, wątek firm, kino, Zgłoszenia 24). Zostaje na gałęzi **aż wdrożymy
  całość**, sprawdzana **lokalnie**. Wyciąganie z niej samego backendu zostawia
  funkcję bez interfejsu i wymusza rozcinanie commitów, których nie da się rozciąć.
- **`main`** — bieżące poprawki, kampania, materiały social. Wypychane od razu
  (push → GitHub Actions → deploy backendu; **front zawsze ręcznie**).

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

## Kalendarz wydarzeń: lokalność i powtórki (2026-08-21)
**Mail z 21.08 wysłał „Dziś w okolicy: III Ciechanowski Festiwal" — dwa razy — i dwa
Posiedzenia tej samej Komisji.** Ekstrakcja wydarzeń nie miała ANI bramki miejsca,
ANI działającej deduplikacji: 129 wydarzeń z 30 dni pochodziło z 90 artykułów,
a ~74 na 130 dotyczyło Sierpca, Ciechanowa, Mławy czy Warszawy.

- **`articles.locality` / `events.locality`** (migracja `add_locality_and_event_dedup`) —
  ocena 0–3 z kategoryzacji BYŁA liczona i wyrzucana: `article_processor` dodawał ją do
  użyteczności i zapisywał wyłącznie sumę `content_score`. Wpis z Ciechanowa użyteczny
  (0+3) miał ten sam wynik co lokalna ciekawostka (3+0), więc każde miejsce, które
  potrzebowało lokalności, budowało własną heurystykę — a newsletter miał **czwartą kopię
  listy miejscowości** (12 nazw, z „wymój", bez Tuczek). Dziś: jedna liczba w bazie
- **`feed_policy.visible_event_conditions(Event)`** — jeden warunek widoczności dla
  kalendarza, briefingu, newslettera i Przewodnika: `canonical_id IS NULL` + próg
  `MIN_EVENT_LOCALITY = 2` (gmina + sąsiednie gminy powiatu; Sierpc i Ciechanów odpadają)
- **`is_pinned_alert` ma wreszcie bramkę miejsca.** Push miał ją od początku
  (`alert_policy.evaluate`), feed nie miał wcale — stąd przypięte „wyłączenie prądu
  w Iłowie-Osadzie" (art. 5322). Ostrzeżenia meteo są z niej wyłączone: IMGW ostrzega
  dla powiatu i nazwa gminy w komunikacie nie pada
- **Reguły w Pydantic, nie w prompcie**: `ExtractedEvent` dostał `is_upcoming` i `locality`,
  a `event_extractor.ground_event` (output_validator) przycina odpowiedź do tekstu —
  ten sam wzorzec co `ground_categorization`. Relacja z dożynek nie jest już zapowiedzią
- **Deduplikacja wydarzeń — embedding, nie tekst.** Pomiar 21.08 na `document_embeddings`
  (typ `event`, 40 par): duplikaty 0,66–0,98, różne wydarzenia ≤ 0,54 → próg **0,60**
  wewnątrz jednego DNIA. Tekst tego nie umie i nie da się go dostroić: „Pożegnanie księdza
  Tomasza" vs „Msza Święta dziękczynna w Rybnie" = zawieranie rdzeni **0,00** (to samo
  wydarzenie), „Komisja Skarg" vs „Komisja Rewizyjna" = **0,50** (dwa różne).
  ⚠️ Te 1156 chunków `event` leżało w bazie nieużywane — semantyka była już opłacona
- **Embedding wydarzenia liczy EKSTRAKTOR**, nie `embedding_job` o 6:50: wpisy z jednego
  przebiegu muszą się widzieć nawzajem. Job został siatką bezpieczeństwa (`embedded=False`)
- **Jeden artykuł = jedno wydarzenie** (częściowy unikat na `source_article_id`). Powtórki
  brały się z tego, że okno liczy się od `scraped_at`, który re-scrape NADPISUJE — ten sam
  post szedł do gpt-4o przy obu przebiegach dnia i za każdym razem dostawał inny tytuł
- Scalanie, nie kasowanie: `events.canonical_id`. Sprzątanie bazy:
  `python -m scripts.dedupe_events [--apply] [--days N]` (na prodzie 21.08: **84 rekordy
  ze 167 do scalenia**). ⚠️ `scripts/migrations/remove_duplicate_events.py` jest martwy —
  szuka po `(title, event_date, location)`, czyli po kluczu, który tych powtórek nie widzi
- Test: `python -m scripts.test_event_dedup [--db]` (14 sprawdzeń + stan bazy)

## Newsletter jest obrazem feedu (2026-08-21)
**Mail miał własne zapytania SQL i własne listy — więc pokazywał to, czego na stronie nie
było.** Teraz `NewsletterGenerator` woła te same funkcje polityki co feed:
`publishable_conditions` + `article_score` + `collapse_duplicates` (turniej w Tuczkach
opisało 20.08 sześć postów i wszystkie sześć szło do modelu jako osobne wiadomości)
oraz `visible_event_conditions` dla wydarzeń.
- **Czas gramatyczny rozstrzyga kod, nie model**: prompt dostaje DWA bloki — „JUŻ SIĘ
  WYDARZYŁO (relacje — czas przeszły)" i „DZIŚ I PRZED NAMI" — a każdy wpis ma etykietę
  z `feed_policy.time_label()` (`[wczoraj 14:45]`, `[ZDARZENIE dziś 09:00–14:00 — TRWA
  TERAZ]`). Do 21.08 model dostawał `{"title", "category"}` — **ani jednej daty** — i sam
  zgadywał, co się dopiero wydarzy
- „Dziś w okolicy" ma okno **jednodniowe**; wcześniej dwudniowe, więc jutrzejszy festyn
  czytało się jako dzisiejszy

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
- ⚠️ `vite.config.ts` ma `envDir: ../backend`, więc **`frontend/.env` NIE jest wczytywany**.
  Lokalnie zmienna jest pusta i działa fallback w kodzie (od 21.08 poprawny, z `/api`);
  produkcja stoi na tym, że `deploy-frontend.sh` podaje `VITE_API_URL=…` w linii poleceń.
  Zwykłe `npm run build` z ręki daje bundle z `localhost:8000` — nie wgrywaj takiego `dist/`
- Auth dependency: `get_optional_user` (nie `get_current_user_optional`)
- SSE split: po `\n` + `trim()` (nie `\n\n` - base_agent yield ma trailing `\n`)
- pgvector insert: `$emb$[...]$emb$::vector`, `$meta${json}$meta$::jsonb` (dollar-quoting)
- DB session w SSE generatorze: używaj `async_session()` z `database.connection`
- Frontend routing: `useState<AppSection>` w App.tsx (switch/case, brak react-router)
- Redis usunięty - cache w PostgreSQL

## Tier System (ceny od 2026-07-19)
- **Free (0 zł)**: **8** zmiennych GUS, 5 pytań AI/dzień (anonim: 3)
- **Premium (9,99 zł/mc · 84 zł/rok)**: **37** zmiennych GUS, AI bez limitu, newsletter daily, push, proaktywny asystent; **trial 30 dni bez karty** po rejestracji
- ⚠️ **Rejestr ≠ oferta**: `gus_variables.py` ma 9/57/88 pozycji, ale endpointy oddają
  `get_gmina_variables_for_tier` (odrzuca zmienne z danymi tylko dla powiatu) → realnie **8/37/53**.
  Do 21.08.2026 cennik i mail obiecywały liczby z rejestru. Dane powiatowe istnieją, ale wyłącznie
  jako **porównanie** przy zmiennej gminnej
- **Firma lokalna (tier `business`, 49 zł/mc · 490 zł/rok, B2B §11 regulaminu)**: **53** zmienne GUS + wyróżniona wizytówka („Polecane w Rybnie", is_premium na business_profiles — auto-aktywacja po płatności P24)
- Płatności: Przelewy24 (`p24_service.py`); IPN → `API_URL/api/payments/webhook` (api.rybnolive.pl!); powrót → `APP_URL/payment/success` (PaymentReturnBanner.tsx); wygaszanie subskrypcji/trialu/wizytówek: trial_expiry_job (5:00)

## Obietnice oferty a kod (audyt 2026-08-20, naprawa 21.08)
**Mail powitalny wymienia pięć rzeczy — dwie z nich nie docierały do nikogo.** Każda pozycja
listy `perks` w `email_service.send_welcome_email` musi mieć pokrycie w kodzie; zmieniając
ofertę, sprawdź, czym ją dowozimy.

| Obietnica | Czym dowozimy | Pułapka |
|---|---|---|
| Briefing pon.–pt. 7:15 | `newsletter_daily` (7:15 **Europe/Warsaw**) | cennik pisał 6:30 — nieprawda |
| Asystent bez limitu | `DAILY_LIMITS["premium"] = None` | — |
| Powiadomienia o awariach | `alert_push_job` co 15 min | **tylko push**; plan Dla Każdego, nie Premium |
| Wywóz odpadów wieczorem | `proactive_alerts_job` **18:00** + blok w briefingu | patrz niżej |
| Wskaźniki GUS | `get_gmina_variables_for_tier` | 37, nie 57 |

- **Odpady, dwa kanały**: `services/waste_policy.py` to jedyne miejsce łączące lokalizację konta
  z rejonem wywozu. Rano briefing pisze „dziś/jutro", wieczorem o 18:00 idzie push „wystaw pojemnik".
  Do 20.08 push chodził o 6:50 (po przejeździe śmieciarki) i **wykluczał** posiadaczy newslettera
  dziennego z adnotacją „dostaną w mailu" — czego briefing nigdy nie robił. Newsletter dzienny jest
  dla Premium domyślny, więc wykluczenie obejmowało dokładnie wszystkich adresatów obietnicy
- ⚠️ **Rybno ma dwa rejony** (`Rybno R1`/`Rybno R2`) różniące się o tydzień. Dawne dopasowanie
  `town in location` wysyłało oba naraz. `match_towns` robi trafienie dokładne, potem przedrostek,
  bez „zawiera"; konta sprzed 20.08 z zapisem „Rybno" dostają oba terminy **z adnotacją**
- **Push wymaga zgody w przeglądarce**, a prośbę o nią pokazywał tylko feed w dniu realnej awarii.
  Świeże konto zostawało z obietnicą bez włącznika → `RegisterPage` stawia `rl_registered_at`,
  a `AlertPushPrompt` czyta ten znacznik przez 7 dni (`fresh`). Mail powitalny mówi o tym wprost
- **Pogoda**: pomiar istnieje tylko dla `Rybno` i `Działdowo`, a konto wybiera jedną z 24 wsi →
  `NewsletterGenerator._weather_for` ma fallback na Rybno (mieszkaniec Dębienia dostawał briefing
  bez pogody — zapytanie o jego lokalizację nie miało prawa niczego znaleźć)
- **„Brak reklam" w Premium**: blok „Polecane firmy" zależał WYŁĄCZNIE od zgody marketingowej.
  Teraz `_marketing_consent` wymaga też `tier == free`, a briefing dzienny nie dostaje promo wcale
- Testy: `python -m scripts.test_waste_reminder` (20 sprawdzeń), `python -m scripts.test_trial_lifecycle` (8 scenariuszy)

## Koniec planu płatnego = mail, nie cisza (2026-08-21)
**Plan nie odnawia się automatycznie (regulamin §6.5), więc przypomnienie jest jedyną drogą do
przedłużenia.** Przypomnienia zbudowane 20.08 patrzyły wyłącznie na `users.trial_ends_at`, a zakup
Premium czyści to pole → klient, który ZAPŁACIŁ, tracił dostęp bez ostrzeżenia.
- `subscriptions.reminder_stage` / `reminder_sent_at` (migracja `add_subscription_reminder`) —
  znacznik na SUBSKRYPCJI, nie na koncie: kolejny zakup zaczyna cykl od zera
- `trial_expiry_job._send_paid_reminders` — −7 dni, −1 dzień; `ended` przy wygaszaniu. Obejmuje też
  `cancelled` (dostęp trwa do końca opłaconego okresu)
- **Potwierdzenie zakupu** (`send_purchase_confirmation`, szablon `purchase.html`) — regulamin §6.4
  obiecuje je wprost, a pierwsza prawdziwa płatność (20.08) nie wywołała żadnego maila. Wysyłka jest
  owinięta w `try` — IPN nie może paść przez pocztę, bo P24 ponawia webhooka
- `_close_abandoned_payments` — wpis `pending` starszy niż **doba** → `expired`. Rekord powstaje przy
  `/create-transaction`, więc każda porzucona płatność zostawiała sierotę. Doba, nie godzina: BLIK
  i przelew bywają wolniejsze niż sesja w przeglądarce
- Kasowanie kont testowych: `python -m scripts.cleanup_test_accounts --emails a@x.pl [--apply]`
  (bez `--apply` tylko podgląd; `conversations`/`subscriptions` mają `NO ACTION`, więc samo
  `DELETE FROM users` nie przejdzie, a `business_profiles` ma CASCADE i zabiera wizytówkę)

## Pomiar narzędzi agentów (2026-08-24)
**O dziurze w danych dowiadywaliśmy się przypadkiem** — 21.08 Przewodnik powiedział
„nie mam prognozy", mając ją w bazie od godziny. Po przejściu agentów na narzędzia
dziura ma stały kształt (`ToolResult.empty`), więc daje się policzyć.
- `agent_tool_calls` (migracja `add_agent_tool_calls`) — wiersz na wywołanie:
  agent, narzędzie, stan, rodzaj błędu, argumenty, czas, skrót pytania
- Zbiera `base_agent._call_tool` — jedyne przewężenie obu ścieżek (strumień
  i non-stream) i wszystkich gałęzi błędów. Bufor `services/tool_telemetry.py`
- ⚠️ **zapis OSOBNĄ sesją, po każdej rundzie.** Osobną, bo sesja requestu należy
  wtedy do pętli (`AsyncSession` nie znosi współbieżności — ta sama pułapka co
  `gather` 22.08). Po rundzie, bo strumień kończy się też przez rozłączenie
  przeglądarki, a `finally` generatora asynchronicznego nie poczeka wtedy na `await`
- ⚠️ **`empty` ≠ `error`.** Pustka naprawia się w ŹRÓDLE danych, awaria w kodzie —
  w jednej kolumnie przestają się różnić
- ⚠️ **nie widzi pytań, przy których model NIE zawołał narzędzia** — wiersz powstaje
  dopiero przy wywołaniu. To pomiar narzędzi, nie trafności routingu
- Raport: `python -m scripts.tool_usage_report [--days 7] [--agent nazwa]`
- RODO: `question`+`user_id` → NULL po 30 dniach, wiersz kasowany po 180
  (`retention_job`, 3:30). Liczniki zostają
- Pełny opis: `AGENCI.md` §4.6

## Push: termin zdarzenia rozstrzyga treść (2026-08-24)
**24.08 o 6:08 push wysłał alarm o wyłączeniu prądu, które skończyło się poprzedniego
dnia o 19:00 — i wysłał go dwa razy.** Bramka „po zdarzeniu" (`is_timely`) istniała od
początku; brakowało jej `event_until`. Post ZGK mówił „W godzinach 16.00 - 19.00", ale
bez daty, więc model nie zaryzykował `event_at` i polityka mierzyła wiek od publikacji.
- **`services/time_span.py`** — parser godzin wyjęty z `weather_alert`. Ten sam zapis
  potrzebny jest awariom i nie jest sprawą pogody; `parse_validity` deleguje, API bez zmian.
  ⚠️ Dwie luki wzorca, odziedziczone: godzina z **kropką** („16.00") i **spacja po myślniku**
- **Liczone w dwóch miejscach**, jak dla ostrzeżeń meteo: `alert_policy.span_from_text`
  w locie (działa dla wpisów już w bazie, bez czekania na kategoryzację o 13:15) oraz
  `article_processor` zapisem do bazy (dla feedu, briefingu i agentów)
- ⚠️ **Tylko dla awarii** (`incident_of` — zamknięta lista, ta sama co push): „w godzinach
  8:00–16:00" bywa godzinami urzędowania, a jako `event_at` przestawia wpis w rankingu feedu
  i w kalendarzu. Drugi bezpiecznik: zakres kończący się PRZED publikacją odrzucamy
- **`alert_policy.signature` (rodzaj + miejsca + termin)** zwija przedruki. Zwijanie po
  tekście tej pary NIE łączy — kategoryzacja napisała „Wyłączenie prądu w Rybnie" i „Przerwa
  w dostawie prądu w Rybnie", czyli podobieństwo **0,43** przy progu 0,72. Progów feedu nie
  naginamy pod push. Pominięty przedruk i tak dostaje `alert_pushed_at`, inaczej wracałby
  do oceny co kwadrans; pamięć wysłanych sygnatur: `RECENT_PUSH_MEMORY_H = 24`
- **Push trafia do wsi, której dotyczy** (24.08): `push_subscriptions.location` +
  `places` w `send_to_category`. ⚠️ Miejscowość na **subskrypcji, nie na koncie** —
  z 6 aktywnych subskrypcji 5 nie ma `user_id` (zgody wydane w przeglądarce bez
  rejestracji), więc filtr po `users.location` objąłby jedną osobę. Puste = cała
  gmina. Przy okazji: dla kategorii `alerty` nie działał nawet filtr kategorii
  wybranych przez użytkownika. Lista wsi dla frontu: **`/api/business/gmina-localities`**
  (istniejący endpoint — nie budować drugiego)
- **Sygnatura liczy dobę LOKALNĄ**, nie minutę: Energa zapowiada jeden dzień kilkoma
  wpisami (23.08 dwa powiadomienia o wyłączeniach 25.08 w Rybnie, 09:30 i 10:00).
  Miejscowości zostają w kluczu. ⚠️ Cena: awaria poranna i wieczorna w tej samej wsi
  mają jeden klucz
- Test: `python -m scripts.test_alert_policy [--db]` (18 + 9 + 4 sprawdzenia).
  Backfill: `python -u -m scripts.production.backfill_incident_spans [--days 14] [--apply]`
- ⚠️ **`is_pinned_alert` wciąż wymaga kategorii z „awari"**, a ta powstaje 6:15/13:15 —
  art. 5572 (awaria 08:12–12:15) dostał push o 9:08, a na stronie stanął dopiero o 13:15,
  godzinę po końcu wyłączenia. Dla ostrzeżeń meteo rozwiązano to czytaniem treści

## TODO (Kolejne priorytety)
- [ ] Przewodnik: dane pogodowe w embeddingach lub direct query
- [ ] Widget pogody → live API
- [ ] Filtrowanie artykułów po kategoriach
- [ ] Panel administracyjny
- [ ] Wybór rejonu wywozu dla kont z zapisem „Rybno” (dziś dostają oba terminy)
- [ ] `is_pinned_alert` bez czekania na kategorię — awaria ma trafiać na szczyt feedu
      od razu po scrapingu, tak jak ostrzeżenia meteo (dziś czeka na 6:15/13:15)
- [ ] Zgłoszenia 24: przypomnienie o sprawach stojących > 24 h w jednym statusie,
      starzenie kart awaryjnych, przycisk „już działa" dla mieszkańców (odłożone 24.08)
- [ ] Widget ruchu: zdarzenie chwilowe (spadłe bele, kolizja) musi WYGASAĆ — 21.08 trasa
      do Iławy pokazywała utrudnienie z 19.08; `road_context` nie odróżnia incydentu od prac
- [ ] Uruchomić `add_locality_and_event_dedup` + `dedupe_events --apply` (prod i lokalnie)

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
- Swagger: http://localhost:8000/docs

---
*Ostatnia aktualizacja: 2026-08-24*
