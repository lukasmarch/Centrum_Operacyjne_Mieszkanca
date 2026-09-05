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
        (od 3.09: klucz deploy na serwerze, `set -e`, HEAD musi równać się github.sha,
         zdrowie = API przez Caddy; zielony job ZNACZY wdrożone)
        
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

## Scheduler Timeline (14 jobów)
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
Niedz 5:00 → Akty prawne z BIP (uchwały Rady, zarządzenia Wójta)
14:00 i 20:00 → Skróty sesji Rady (do akceptacji; obrady startują 10:00,
                20:00 to dogrywka — do 27.08 job chodził o 4:30)
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
- ⚠️ **Brak kierunku obraca się przeciw mieszkańcowi PO terminie** (26.08.2026): refresh
  o 13:30 otworzył briefing zdaniem „Posiedzenie Komisji Rozwoju Gospodarczego — już dziś
  o 12:00", bo posiedzenie sprzed półtorej godziny było najbliższym punktem w całym
  materiale — przy jutrzejszej sesji Rady w tym samym materiale. Bramka „czy to jeszcze
  sprawa najbliższych godzin" istniała **wyłącznie dla kategorii Awaria**; reszta nie miała
  żadnej. `_event_is_over` + druga oś klucza (zaraz po lokalności) spycha zdarzenie po
  terminie na koniec grupy — degradacja, nie wykluczenie: gdy przed nami nie ma nic, minione
  wraca. Awaria będąca sprawą TERAZ jest zwolniona, jak z reguły powtórki
- ⚠️ **Zapowiedź bez godziny stoi w bazie jako lokalna PÓŁNOC** (`event_at` 22:00 UTC dnia
  poprzedniego) i trwa do końca swojej doby — inaczej dożynki byłyby „po" o 00:01 w dniu
  dożynek. Termin z godziną, ale bez `event_until`, zamyka się ze startem: briefing z 13:30
  wisi na stronie do wieczora, więc nagłówkiem ma być rzecz, na którą da się jeszcze zdążyć
- `_time_label` mówi „— JUŻ PO": model dostawał samą datę i pisał o minionym terminie
  w czasie przyszłym
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

## Pustka narzędzia nie kończy pracy agenta (2026-08-25)
**„Kiedy w gminie Rybno posiedzenie rady i komisji?" → „skrótów obrad jeszcze nie
opublikowano". Cztery razy, mimo próśb „poszukaj w RAG" i „nie pytam o streszczenie
tylko datę".** Termin XXIV sesji (27.08, 10:00) leżał w bazie w DWÓCH miejscach:
w kalendarzu i w ogłoszeniu BIP w RAG (`search_documents` zwracał salę, godzinę
i porządek obrad).
- **Winne było pole `co_powiedziec`** w pustym wyniku `council_sessions`: kończyło
  się zdaniem „NIE streszczaj obrad z pamięci ani z innych źródeł". Reguła ogólna:
  **wynik narzędzia jest ostatnią rzeczą, jaką model czyta przed pisaniem, więc bije
  prompt agenta.** Pustka ma kończyć się KIERUNKIEM („szukaj dalej narzędziem X"),
  nie zamknięciem — zawsze, gdy nie jest jeszcze odpowiedzią na pytanie. Ten sam
  wzorzec porażki co odmowa Redaktora 24.08, przesunięty o poziom: tym razem sprawę
  zamknęło NARZĘDZIE, nie prompt
- Zakaz zawężony do tego, co chronił: nie wolno **streszczać PRZEBIEGU**
  niezatwierdzonej sesji (bramka akceptacji). Podanie **terminu z ogłoszenia** nigdy
  nie było tym samym
- `council_sessions` w opisie mówi teraz wprost: obrady, które **JUŻ SIĘ ODBYŁY**.
  Prompt Urzędnika rozdziela „co ustalono" od „kiedy się zbiera"
- **Urzędnik dostał `upcoming_events`** (narzędzie Przewodnika — terminy posiedzeń
  Rady to sprawa urzędowa). Kalendarz daje etykietę liczoną od TERAZ („jutro 14:00")
- ⚠️ **„Zawołaj jeszcze raz z innym sformułowaniem" wymaga narzędzia z pytaniem.**
  `council_sessions` ma jedyny parametr `limit`, więc druga próba modelu wyglądała
  tak: `limit=2` → `limit=5`. Prompt mówi teraz, że wtedy zmienia się NARZĘDZIE
  albo woła `przekaz_dalej`
- ⚠️ Router kierował to pytanie raz do Urzędnika, raz do Redaktora — `ROUTING_PROMPT`
  ma teraz zdanie o pracy Rady (posiedzenie to nie impreza ani wiadomość z mediów)
- Test: `python -m scripts.test_agent_answers --only kiedy-sesja`

## Dedup wydarzeń: weto organu, nie próg (2026-08-25)
**Kalendarz stracił XXIV sesję Rady** — dedup uznał ją za powtórkę Komisji Budżetu
(obie 27.08, ta sama sala). Zniknęła z kalendarza, briefingu, newslettera
i `upcoming_events` na dwa dni przed terminem; razem z nią Komisja Zdrowia.
- **Progu tu NIE MA.** Pomiar 25.08 na 8 parach z produkcji: „XXIV sesja" vs
  „Komisja Budżetu" (różne) = **0,909**, „Msza dziękczynna" vs „Pożegnanie księdza"
  (jedno) = **0,790**, „MTB Etap 6" vs „Zarybinek MTB" (jedno) = **0,846**. Dwa różne
  posiedzenia są sobie BLIŻSZE niż dwa opisy tej samej imprezy — embedding mierzy
  temat, a temat mają identyczny
- `event_extractor._organ_key` + weto w `same_event`: **sesja ≠ komisja X ≠ komisja Y**,
  niezależnie od podobieństwa. ⚠️ W odróżnieniu od weta miejsca pewność semantyczna
  go NIE znosi — wysokie podobieństwo jest tu regułą, nie wyjątkiem
- Klucz = pierwsze słowo po „Komisji" obcięte do 6 znaków (`rewizy|budzet|skarg|
  zdrowi|rozwoj`), więc odmiana nie tworzy drugiego organu. **Zamkniętej listy nazw
  celowo nie ma** — nowa komisja dostanie klucz sama
- ⚠️ **Weto godziny ODRZUCONE po pomiarze**, choć było w planie: rozbijało trafne
  scalenie MTB (09:20 vs 08:00) i nie łapało nic ponad weto organu
- ⚠️ **Powtórki nie mają embeddingu**, więc przegląd tego, co już scalone, jest
  TEKSTOWY i darmowy: `python -u -m scripts.production.unmerge_wrong_organ_events
  [--apply]` (518 par na prodzie → 1 do rozscalenia). Rozscalony wpis dostaje
  `embedded=False`, bo bez chunku jest niewidzialny dla RAG i przyszłego dedupu
- ⚠️ **Jedno ogłoszenie z SERIĄ terminów wciąż gubi wszystkie poza pierwszym**:
  art. 5342 zapowiadał konsultacje w Rumianie (25.08) i w Naguszewie (26.08),
  a częściowy unikat na `source_article_id` przepuścił jeden — drugi wpisano ręcznie.
  Osobna praca, patrz TODO
- Test: `python -m scripts.test_event_dedup` (sekcje 5 i 6, podobieństwa ZMIERZONE)

## Godziny wydarzeń: kalendarz spóźniał się o dwie godziny (2026-08-25)
**Cały projekt trzyma naiwny UTC, `EventExtractor` jako jedyny zapisywał czas LOKALNY.**
Ten sam termin z tego samego ogłoszenia stał w bazie dwa razy: `articles.event_at`
= 27.08 08:00 (UTC, dobrze), `events.event_date` = 27.08 10:00 (lokalny). XXIV sesja
Rady o 10:00 pokazywała się jako 12:00, dożynki o 11:00 jako 13:00.
- **Wynik `upcoming_events` niósł DWIE sprzeczne godziny naraz**: `data` z surowego
  `strftime` i `kiedy` z `time_label` (który konwertuje). Model wybierał losowo —
  obie muszą być lokalne (`to_local`), bo model przepisuje jedną z nich
- ⚠️ **Front nie był winny i pokazywał dobrze**: `/api/events` oddawało datę BEZ
  znacznika strefy, a `new Date("2026-08-27T10:00:00")` czyta ją jako lokalną —
  czyli przypadkiem zgodnie z bazą. Dlatego sama poprawka zapisu ZEPSUŁABY stronę.
  API mówi teraz wprost `…Z`; front mapuje `event_date` w jednym miejscu
  (`useEvents.ts`) i nie wymagał wdrożenia
- ⚠️ **Kolejność odwrotna niż przy migracjach: KOD PRZED DANYMI.** Backfill przed
  deployem pokazałby godziny o 2 h za wcześnie
- **Dedup liczy dobę LOKALNĄ** — wpis całodniowy to w UTC 22:00 dnia poprzedniego,
  więc `date(event_date)` odsunęłoby go od posiedzenia o 10:00 tego samego dnia
- Backfill: `python -u -m scripts.production.backfill_event_timezone [--apply]`
  (✅ wykonany na prodzie 25.08, 1165 wierszy). ⚠️ Ma **bezpiecznik**: gdy ≥50 %
  par zgadza się z `articles.event_at` bez konwersji, odmawia — `created_at` nie
  wystarcza, bo stare wpisy mają je zawsze przed granicą i drugi przebieg cofnąłby
  wszystko o kolejne 2 h. Pomiar: przed backfillem 0/33 zgodnych, po nim 27/33

## Narzędzia wiedzy przegrywały z polską odmianą (2026-08-25)
**Dwa narzędzia, ten sam błąd, obie odpowiedzi FAŁSZYWE i brzmiące kompetentnie.**
- **`search_legal_acts`**: „plan ogólny" nie trafiało w tytuł „przystąpienia do
  sporządzenia planu **ogólnego**" — `ILIKE '%ogólny%'` nie widzi formy „ogólnego".
  Zwracało JEDNĄ uchwałę: o Strategii Rozwoju (ma „ogólny" gdzieś w treści), a agent
  wiernie o niej opowiadał, cytując prawdziwy numer NIE TEGO dokumentu
- **`upcoming_events`**: filtr szukał całej FRAZY jako podłańcucha, więc „spotkanie
  z mieszkańcami" nie trafiało w „Spotkanie w sprawie Planu Ogólnego". Pusty wynik
  wracał do pełnej listy (`narrowed or rows`) i limit ucinał 10 NAJBLIŻSZYCH —
  właściwe spotkanie stało trzynaste. Agent odpowiedział, że takich spotkań nie ma
- **`feed_policy.word_stem`** — jedno miejsce na obcięcie końcówki (≥5 znaków → −2):
  „ogólny"→„ogóln", „uchwały"→„uchwał". Ten sam zabieg co `_places_re` w testach
  i `_organ_key` w dedupie. ⚠️ Krótszy rdzeń przepuszcza szum — to świadomy wybór
- ⚠️ **Samo dopasowanie nie wystarcza, bo LIMIT ukrywa właściwą pozycję.**
  Po naprawie rdzenia rejestr zwracał 5 aktów i nadal bez tego właściwego:
  III/20/2024 jest NAJSTARSZA, a sortowanie szło po dacie. Przy podanym `query`
  pierwsza oś to teraz **liczba trafień w TYTULE** (akt z tematem w tytule jest
  o tym temacie; akt ze słowem w uzasadnieniu wspomina mimochodem).
  Analogicznie `upcoming_events` przy `query` bierze 8× większą pulę kandydatów

## Kto czyta RAG (stan 2026-08-24)
**Wyszukiwarka jest NARZĘDZIEM, nie podatkiem doliczanym do każdego pytania.**
| Agent | Wiedza | Uwagi |
|---|---|---|
| Redaktor | `latest_local_news` + `search_news` | świeżość = zapytanie po dacie, NIE wektory |
| Urzędnik | `search_legal_acts`, `council_sessions`, `search_documents` | korpus: `bip_static`,`bip`,`legal_act`,`article` |
| Strażnik / Organizator / Przewodnik | **własny SQL przez narzędzia** | osadzenie wpisu nic tu nie gwarantuje |
| GUS-Analityk | własny SQL + `chart_data` | jedyny z własnym `respond()`; jedyny bez `przekaz_dalej` |
| Koordynator | **inni agenci** (`zapytaj_*`) | pytania wielodziedzinowe; nie deleguje do siebie |

⚠️ **Klasyczna ścieżka RAG w `BaseAgent` NIE ISTNIEJE od 24.08.2026** — po
przeniesieniu Redaktora i Urzędnika nie miała ani jednego użytkownika.
`respond()` bez `tools` rzuca `NotImplementedError`. Zniknęło też
`_rewrite_query` (zapytanie układa model, który ma historię rozmowy).
⚠️ **Etykieta miejsca: `feed_policy.article_scope`, NIE `is_local_article`.**
Ta druga steruje rankingiem i jest celowo szeroka — przepuszcza całe źródło
„Powiat Działdowski (RSS)" jako nasze, więc jako etykieta kłamie („budowa bloku
w Działdowie (gmina Rybno)", 24.08). Nie podmieniać jednej pod drugą:
`is_local_article` wchodzi w `article_score`, nagłówek briefingu i newsletter.

Przebieg: scraping 6:00/13:00 → AI 6:15/13:15 (`processed`) → embedding 6:50/13:45 →
`document_embeddings`. Zapytanie: przepisanie pytania → synonimy → hybrid_search (wektor+BM25,
próg, recency) → rerank gpt-4o-mini → KONTEKST + karta gminy. Opóźnienie publikacja→RAG:
max ~7 h rano, ~45 min po południu (wieczorne posty FB czekają do rana).
⚠️ **1095 chunków `event` nie czyta żaden agent** — Przewodnik bierze wydarzenia SQL-em.

## Pętla orkiestracji: decyzja o agencie jest odwoływalna (2026-08-24)
**„Sprawdź kondycję Rybna, mocne i słabe strony" → „nie mam możliwości"** przy
9123 rekordach GUS, 430 uchwałach i świeżym feedzie. Router wybiera JEDNEGO
agenta, raz, zanim ktokolwiek zajrzy do danych — pytanie wielodziedzinowe nie
mieści się w tym z definicji. Redaktor odmówił zgodnie z instrukcją bloku
świadomości; błędem była nieodwoływalność wyboru.
- **`przekaz_dalej`** (`ai/tools/handoff.py`) — agent bez zasięgu woła narzędzie
  zamiast pisać odmowę. NIE klasyfikator odmowy nad gotowym tekstem: siódma
  heurystyka słowna po sześciu wyrzuconych, tyle że na własnym tekście.
  Skutek uboczny: porażka „poddał się, nie zawoławszy niczego" była dla
  telemetrii **niewidzialna** — teraz jest wywołaniem i widać ją w raporcie
- **`Orchestrator.run()`** zastąpił `handle()` w `chat.py`. `MAX_HANDOFFS = 2`,
  a `_next_agent` NIE wraca do agenta, który już odpowiadał — odbicie kończy
  się samo. Ślepy zaułek pisze KOD (`_dead_end_message`), nie model: model bez
  materiału wyprodukuje tę samą odmowę, od której zaczęliśmy
- **Koordynator** (`ai/agents/koordynator.py`) — narzędziami są inni agenci
  (`ai/tools/delegation.py`). Nowej pętli nie ma: to `max_tool_rounds` = 5.
  Router ma siódmą opcję. Delegacja woła AGENTA, nie jego narzędzia — inaczej
  przepada wiedza z promptów specjalistów (okna Strażnika, numery uchwał)
- ⚠️ **Głębokość jeden, dwa zamki**: koordynatora nie ma wśród celów delegacji,
  a delegowany agent dostaje `allow_handoff=False`
- ⚠️ **`Tool.timeout_s`** — wspólne 15 s to limit dla zapytania do bazy.
  Delegacja uruchamia pętlę innego agenta z gpt-4o: pierwszy przebieg uciął
  Urzędnika i koordynator napisał o kondycji gminy bez zdania o finansach.
  Delegacje mają 45 s (pomiar: 6–20 s)
- ⚠️ **Zasięg ginie w syntezie** — pierwszy przebieg podał piknik w Żurominie
  jako mocną stronę gminy Rybno. Redaktor oznaczał go poprawnie; zgubił to
  koordynator. Reguła jest w jego prompcie
- ⚠️ **GUS-Analityk jako jedyny nie przekaże pytania** (brak pętli narzędziowej)
  — odsyła słowami. Zniknie z `_classify_gus_query`
- Koszt: pytanie bez handoffu = tyle co wcześniej. Pomiar 24.08: pełna analiza
  kondycji 8949 tok. / 37,6 s (3 delegacje), handoff prosty 4,2 s
- Front: krok pracy niesie `handoff` + `discard_text` (skasuj tekst porzuconego
  agenta). Backend robi to samo przy zapisie do bazy
- Test: `python -m scripts.test_agent_tools` (sekcja „Pętla orkiestracji")

## Dane jednostek: stała w kodzie kłamała (2026-08-24)
**`OFFICE_HOURS` w `ai/tools/daily.py` miała dwie instytucje i BŁĘDY W OBU.**
Urząd: 7:15–15:15 w kodzie, **8:00–16:00** naprawdę. GOPS: adres i telefon
**Urzędu Gminy** zamiast własnych (naprawdę ul. Zajeziorna 58, tel. 23 696 63 39).
Agent podawał to płynnie — ręcznie wpisana stała nie ma jak zestarzeć się głośno.
- `gmina_institutions` (migracja `add_gmina_institutions`) — 12 jednostek:
  urząd, GOPS, ZOZ, biblioteka, OSiR, 5 szkół, przedszkole, żłobek
- `scrapers/bip_institutions.py` + `python -m scripts.run_bip_institutions [--dry]`
- `ai/tools/institutions.py::institution_info` — **zastąpiło `office_hours`**
  (usunięte, nie zostawione obok). Ma je Organizator
- ⚠️ **`hours` i `scope` są RĘCZNE** — scraper ich nie nadpisuje. BIP publikuje
  godziny tylko dla urzędu; dla 11 jednostek narzędzie mówi wprost, że ich nie ma
- ⚠️ **Scraper tylko LOKALNIE** — serwer dostaje z BIP 403
- ⚠️ Nie przenosić tych danych do karty gminy: limit 2 kB, a wiedza w prompcie
  nie zostawia śladu w `agent_tool_calls`
- Test: `test_agent_answers`, przypadek `gops-godziny` (sprawdza POPRAWNOŚĆ
  adresu, nie samo udzielenie odpowiedzi)

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
| Organizator | ✅ działa | Direct SQL do waste_schedule + `institution_info` |
| Koordynator | ✅ działa | narzędziami są inni agenci (etap 7) |

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

## Rejestr aktów prawnych i skróty obrad (2026-08-24)
**430 aktów 2024–2026** (200 uchwał Rady, 230 zarządzeń Wójta) z modułu BIP
`/akty/14/` — INNY moduł niż `DEFAULT_SECTIONS` wiedzy stałej.
- `legal_acts` (migracja `add_legal_acts`) + `scrapers/legal_acts.py` +
  `legal_acts_job` (**niedziela 5:00**, godzinę po wiedzy stałej — ten sam serwer)
- Napełnienie: `python -m scripts.run_legal_acts [--dry] [--since RRRR-MM-DD]`
- `search_legal_acts` — metadane SQL-em. „Jakie są najnowsze uchwały" to
  `ORDER BY adopted_at DESC`, NIE zadanie dla wyszukiwarki wektorowej
- ⚠️ **Lista BIP nie jest sortowana po dacie podjęcia**, tylko kolejnością
  wprowadzenia — wśród aktów z IV 2025 siedzi zarządzenie z XI 2023. Przerwanie
  skanu na pierwszym starym akcie dało 229 zamiast 430. Dziś: 2 strony pod rząd
  bez trafienia
- ⚠️ **Komórki tabeli niosą etykietę w treści** („Data podjęcia 2026-06-24") —
  układ responsywny. Bez obcięcia data nie parsuje się wcale
- ⚠️ **`ORDER BY adopted_at` przy remisie losuje** — jedna sesja to kilkanaście
  uchwał tego samego dnia. Druga oś: `bip_id DESC`
- Treść w PDF (`/system/pobierz.php`), ma warstwę tekstową; 31/430 to skany.
  Eksport „Pobierz dane XML" jest ślepy — zwraca stronę główną
- **Sesje rady**: `council_sessions` czyta WYŁĄCZNIE `published` — bramka
  akceptacji obowiązuje też agenta. Numery uchwał doklejane z rejestru po dacie
  sesji (z nagrania nie padają — numer nadaje się po głosowaniu)
- ⚠️ **6 sesji stoi w `new` NIE z powodu awarii**: funkcja weszła 12.08, a sesja
  XXIII jest z 24.06 — 49 dni przy progu 45 (`MAX_SESSION_AGE_DAYS`, bezpiecznik
  rachunku). Nadrobienie ręczne: `run_council_session --url … --save` (~$0,59)
- Testy: `python -m scripts.test_legal_acts [--db] [--live]`

## Pomiar strony: log serwera widzi tylko pierwsze żądanie (2026-08-30)
**24 132 zasięgu na FB, 138 urządzeń na stronie w tygodniu, ZERO nowych kont i ZERO
zgód push — i żadnego źródła odpowiedzi „gdzie się odbili".** Front to SPA bez
react-routera (nawigacja przez `history.pushState` w `frontend/App.tsx`), więc log
Caddy widzi wyłącznie pierwsze żądanie HTML; do tego przewija się po **168 h**
(`roll_keep_for`), więc fala 18–22.08 już nie istnieje.
- **`site_events`** (migracja `add_site_events`) + `POST /api/events`
  (`api/endpoints/analytics.py`). Front: `frontend/src/services/analytics.ts`,
  wysyłka `navigator.sendBeacon` przy chowaniu karty
- ⚠️ **Zamknięta lista `ALLOWED_EVENTS`** — endpoint jest publiczny i bez
  uwierzytelnienia, więc bez białej listy to otwarty zapis do bazy. Nowe zdarzenie
  dodaje się w **backendzie**, nie we froncie. `register_done` dopisuje SERWER
  (`auth/routes.py`) — z przeglądarki przyszłoby też od kogoś bez konta
- ⚠️ **Jedno miejsce podpięcia**: efekt na `activeSection` w `App.tsx` łapie wejście,
  kliknięcie w menu i przycisk wstecz naraz. `activeSection` jest źródłem prawdy
- **RODO**: brak IP i User-Agenta w bazie (z nagłówka zostaje samo `mobile`/`desktop`),
  `rl_sid` w **sessionStorage** (ginie z kartą, nie łączy wizyt między dniami →
  bez banera zgody), `rl_acq` w localStorage trzyma źródło PIERWSZEJ wizyty.
  Retencja: `session_id`/`user_id` → NULL po 90 dniach, wiersz po 180
- ⚠️ **`captureAcquisition()` woła się w `index.tsx` PRZED montowaniem Reacta** —
  `syncUrl` przepisuje adres przy pierwszej nawigacji i gubi wtedy `?utm_...`
- ⚠️ **`Acquisition.strip_timezone`**: przeglądarka wysyła `toISOString()` ze strefą,
  cały projekt trzyma naiwny UTC → bez walidatora rejestracja kończyła się **500 przy
  KAŻDYM koncie**. Złapane testem end-to-end, nie w przeglądzie kodu
- ⚠️ **`React.StrictMode` podwaja zdarzenia w trybie deweloperskim.** Na buildzie
  produkcyjnym `view` strzela raz — sprawdzone. Nie „naprawiać" tego dedupem
- Atrybucja: `users.acq_*` (denormalizacja celowa — `site_events` kasuje retencja,
  a skąd wziął się klient ma przeżyć dłużej niż log), `push_subscriptions.acq_session_id`
  (5 z 9 subskrypcji nie ma `user_id`)
- Raport: `python -u -m scripts.site_report [--days 7]`. ⚠️ Okna: `site_events` żyje
  180 dni, log Caddy 7 — przy `--days` > 7 liczby z obu raportów są nieporównywalne

## Newsletter: kolumny bez mechanizmu (2026-08-30)
**`newsletter_logs.opened_at` i `clicked_at` istniały od początku projektu i NIC
w całym repozytorium do nich nie pisało** — 91 wysyłek, 0 otwarć. To nie był wynik,
to był brak mechanizmu; nie dało się powiedzieć, czy Premium dostaje to, za co zapłacił.
- `newsletter_logs.provider_message_id` ← `result["id"]` z Resend (zwracany od zawsze
  przez `email_service.send_email`, tylko wyrzucany). Zapis w `newsletter_job.py`, 2 miejsca
- `api/endpoints/newsletter_webhook.py` — `POST /api/newsletter/webhook/resend`,
  zdarzenia `email.opened` i `email.clicked`
- ⚠️ **Podpis Svix liczony ręcznie**, bez paczki `svix`: 189 z 202 zależności nie ma
  przypiętej wersji, więc nowy pakiet = świeży resolve przy przebudowie obrazu, co już
  raz położyło produkcję na 20 min
- ⚠️ **Odpowiedź zawsze 200** — Resend, jak P24, ponawia webhooka przy każdym innym kodzie
- ⚠️ Wymaga ręcznej konfiguracji: adres w panelu Resend + `RESEND_WEBHOOK_SECRET`
  w `.env.production` + `up -d --force-recreate backend`

## Link ma prowadzić tam, co obiecał post (2026-08-30)
**`social_content.tracked_url()` prowadził ZAWSZE na stronę główną**, więc kto kliknął
po informację o wyłączeniu prądu, lądował na ogólnym pulpicie i szukał jej sam.
- Pomiar kampanii „sesja XXIV" (log Caddy, 24–30.08): post ze zdjęciem i deep linkiem
  na `/sesje` → **2,48% i 3,86%** zasięgu jako wejścia, rolka na tę samą stronę **0,84%**,
  automat na stronę główną — zero
- Sekcja liczona z **PRAWDZIWEJ kategorii** artykułu nagłówka (`articles.category`
  przez `cited_articles[0].id` w `_latest_summary`), nie ze słów w tytule — ta sama
  zasada co `ground_categorization`
- ⚠️ `CATEGORY_TO_PATH` to **trzecia kopia** listy ścieżek (obok `SECTION_TO_PATH`
  w `frontend/App.tsx` i `STATIC_PAGES` w `api/endpoints/seo.py`). Rozjazd wyłapuje
  `_assert_paths()` — link donikąd byłby widoczny dopiero w statystykach, tydzień po fakcie
- `utm_content` niesie identyfikator kreacji; `scripts/traffic_report.py` przestał go ignorować

## Układ trzech bramek: pustka nie jest neutralna (2026-09-03)
**Cały wybór treści — feed, briefing, newsletter, kafel — stoi na czterech polach
z kategoryzacji: `category`, `locality`, `content_score`, `event_at`. Każde bywa
puste, a system traktował pustkę jako neutralną albo KORZYSTNĄ.** 3.09 briefing
otworzył dzień poborem krwi za 13 dni (brak `event_at`), feed miał na szczycie
podatek za psa w Działdowie (0,792 — najwyższy wynik, `locality=2` ignorowane),
kafel pokazał wyłączenie w Mławce za tydzień, a 5 skrzynek Premium dostało
o 7:15 wczorajszą awarię jako „dzisiejszą" (mail = kopia briefingu z 5:00).

**Wzorzec, który powielamy, to `alert_policy` dla pusha: RODZAJ → MIEJSCE → CZAS.**
Feed i briefing zadawały te same pytania własnymi, niepełnymi kopiami.
| | Push (wzorzec) | Feed | Briefing |
|---|---|---|---|
| Rodzaj | `incident_of` z TEKSTU | `category` z AI | `CATEGORY_PRIORITY` |
| Miejsce | `places_in` — nieomijalne | `locality_factor` | `_mark_local_articles` |
| Czas | `is_timely` + `span_from_text` | `is_pinned_alert` + `span_from_text` | `_alert_still_running` |

- **`locality` rozstrzyga w OBIE strony** (`MIN_ARTICLE_LOCALITY = 3`), pierwsze przed
  źródłem. Obawę „model bywa skąpy" zmierzono: źródła gminne dają 3 w **30/35**
  (Gmina Rybno 5/5, FB Rybno 9/10, BIP 11/13, ZGK 5/7). ⚠️ To NIE `MIN_EVENT_LOCALITY`(2):
  tamten o widoczności wydarzeń, ten o kolejności wiadomości
- **Briefing ma tę samą regułę w JEDNYM miejscu** (`_mark_local_articles`) — pierwszy
  przebieg po naprawie feedu wybrał „akcję zdrowotną w LUBAWIE" (`locality=1`), bo
  `_local_article_ids` było osobną kopią. ⚠️ `test_summary_headline` trzymał TRZECIĄ
  kopię pod komentarzem „to samo, co briefing robi" — test woła teraz metodę produkcyjną
- **Awaria bez godzin**: `AWARIA_PIN_HOURS` 24 → 12; zwolnienie z reguły powtórki nagłówka
  wymaga DOWODU trwania (`ONGOING_ALERT_H = 12`) — wcześniej 5 z 6 briefingów zaczynało
  się „AWARIA", a 2 i 3.09 to była ta sama awaria wody. ZGK nie publikuje „już działa"
- **Etykieta niesie SKUTEK, nie tylko datę**: model dostał poprawne `[wczoraj 11:07]`
  i napisał „**Dziś** spadek ciśnienia". Z etykietą „— AWARIA SPRZED DOBY, MOGŁA JUŻ
  ZOSTAĆ USUNIĘTA" napisał „mogła już zostać usunięta". Ta sama zasada co „JUŻ PO"
- **Wpis spoza gminy nie ma „drugiego życia" zapowiedzi** — dla `locality_factor < 1`
  świeżość liczy się od TERMINU (Mławka za 7 dni nie jest wiadomością dnia)
- **Data wprost w tekście jest zadaniem dla kodu** (`time_span.parse_date_span`): ten sam
  post „📅 16 września 2026 r. ⏰ godz. 8:00–11:30" puszczony przez model 3× dał termin
  w 2/3, godzinę końca w 0/3, kategorię raz Społeczność, raz Edukacja. W bazie
  **27/104** wpisów z datą we własnym tytule nie miało `event_at`. Kod UZUPEŁNIA model
  (bramka „data ≥ dzień publikacji" chroni relacje). ⚠️ Nowa linia ≠ koniec zdania —
  FB łamie wiersz między datą a godziną. Backfill: `backfill_event_dates` (✅ prod, 30)
- **`same_incident` zamiast równości sygnatur push**: przedruk Syli był urwany przez
  scraper (3 wsie zamiast 8) i DOKŁADAŁ „Rybno" z nazwy nadawcy → drugi push o 6:03 dobę
  po awarii. Reguła: odjąć nazwę gminy, gdy padła obok innych wsi, potem ZAWIERANIE.
  ⚠️ Nie przecięcie — test pokazał, że każdy komunikat Energi niesie „Rybno gmina
  wiejska" i przecięcie scaliłoby Koszelewy z Rybnem
- **Kategoryzacja uzupełniająca** o :15 po każdym oknie Energi (9/12/15/18/21) —
  `run_categorization_catchup`, sama kategoryzacja, batch 10. Wpis z 18:05 czekał do
  6:15 rana bez pól, które o nim decydują; nieoceniony dostawał `content_factor` 1,0
  = tyle co ocena 3/6
- **Front**: `firstSentences` łamało briefing na skrócie „m.in." — lista skrótów, bez
  lookbehind (Safari < 16.4)
- **Zakończona zapowiedź ZNIKA** (`ENDED_EVENT_GRACE_H = 24` w `publishable_conditions`):
  ranking dawał wpisowi po terminie ×0,25, czyli spychał niżej zamiast usunąć — przy
  4–9 lokalnych wpisach dziennie „niżej" i tak znaczyło pierwszą stronę. Doba karencji,
  bo wczorajsza impreza czyta się jako relacja. Pomiar: wypada 6 wpisów z 70
- **`idx_event_unique` usunięty** — dedup semantyczny (`canonical_id`) jest jedynym
  sędzią powtórek; stary indeks tekstowy blokował zapis rozpoznanej powtórki i wywracał
  całą pętlę (`PendingRollbackError` w następnej iteracji, trzeci nawrót tego wzorca)
- **Bramka WEJŚCIOWA ekstrakcji wydarzeń ma być HOJNA** — nazwa miejscowości w tekście
  przebija niską `articles.locality`. Odsiewała 96 wpisów na 14 dni, w tym „VI Leśny
  Nocny Bieg w KOPANIARZACH" z oceną 0. Ostra jest bramka WYJŚCIOWA, która ocenia SAMO
  WYDARZENIE. ⚠️ Spadek wydarzeń 39→4/tydz. to jednak głównie sezon i naprawiony dedup
- **Wiadomości w sekcjach po ZASIĘGU** (`scope` w `/api/articles`: gmina/okolice/region
  z `locality`, fallback `article_scope`). Grupowanie po dacie unieważniało ranking:
  lokalne posty wchodzą rano z WCZORAJSZĄ datą (Apify raz o 6:00), więc „Dzisiaj (3)"
  otwierały zawsze RSS-y z powiatu stojące w rankingu na 5., 11. i 15. miejscu
- ⚠️ **Zielony job Actions ≠ wdrożenie.** GitHub TRWALE limituje anonimowe pobrania
  z IP serwera (3 próby, ten sam błąd), `git pull` pada, obraz buduje się z cache,
  health „OK". Obejście: `git bundle create d.bundle main --not <SHA>` → scp → fetch
  z pliku → `merge --ff-only` → build. Trwała naprawa (deploy key + `set -e`) NIEZROBIONA
- Testy: `test_summary_headline` 36, `test_alert_policy` 46, `test_content_score` 17,
  `test_event_terms` 27 (sekcja 4 nowa)

## Warstwa czasu: doba lokalna i wpis całodniowy (2026-09-05)
**Jeden rekord, dwa przeciwne objawy, dwa dni z rzędu.** „VI Leśny Nocny Bieg",
sobota 5.09, ogłoszony bez godziny (post urwał się na „⏰ Godzina…"), więc w bazie
stoi jako `2026-09-04 22:00` — **lokalna północ**. W piątek briefing napisał
„**Dziś** odbędzie się", w sobotę — w dniu biegu — wpis **zniknął z kalendarza**.
Model nie zawinił: blok „NADCHODZĄCE WYDARZENIA" podał mu `Data: 2026-09-04`
surowym `strftime` na UTC, a obok, w bloku SPORT, ten sam bieg miał poprawne
„[ZDARZENIE jutro]" — materiał był **wewnętrznie sprzeczny**.

**Cała wiedza o czasie mieszka w `services/time_span.py`** — było pięć kopii
`_local` i sześć własnych sposobów na „dzisiejszą dobę":
- `local_day_bounds(day, now, days)` — granice doby LOKALNEJ w naiwnym UTC.
  ⚠️ Koniec liczony z lokalnej północy, **nie** przez `+timedelta` do granicy UTC:
  w noc zmiany czasu (26.10) doba ma 23 albo 25 godzin
- `is_all_day(start, end)` — lokalna 00:00 bez końca. Ta sama reguła co
  `frontend/src/utils/eventTime.ts::isAllDay` i `summary._event_is_over`
- `when_label(start, end, now, all_day=True)` — RDZEŃ „kiedy": „jutro (cały dzień)",
  „dziś 09:00–14:00", „16.09 08:00". Ozdobniki („TRWA TERAZ", „JUŻ PO", „AWARIA
  SPRZED DOBY") dokłada wołający — `feed_policy.time_label` i `summary._time_label`
  stoją na tym samym rdzeniu, każdy w swoim brzmieniu.
  ⚠️ `all_day=False` dla PUBLIKACJI: wpis wydany o lokalnej północy ukazał się
  o 00:00, a nie „przez cały dzień"

**Trzy postacie tego samego błędu** — trzecią znalazł dopiero strażnik:
| Wzorzec | Skutek |
|---|---|
| `event_date.strftime(...)` bez konwersji | briefing „dziś" o jutrzejszym biegu; plakietka „4 wrz" w mailu |
| `utcnow().replace(hour=0)` | kalendarz gubił wpis w dniu wydarzenia; mail „Dziś w okolicy" o jutrzejszym |
| `event_date >= now` | zapowiedź całodniowa istniała **jedną minutę** — `upcoming_events`, świeży feed Redaktora, tygodnik |

- **Strażnik: `python -m scripts.test_timezone_guard`** — skanuje `src/` na te trzy
  wzorce. Wyjątek zapisuje się dopiskiem **`# tz-ok: <powód>`** przy linii (albo
  w komentarzu nad nią), NIE listą w teście — lista rozjeżdża się przy pierwszym
  przeniesieniu kodu. Cztery takie miejsca: data przed `to_utc` w ekstraktorze,
  klucz dnia w `daily_summaries` (×2), log diagnostyczny
- ⚠️ **Data kalendarzowa ≠ moment**: `session_date` sesji Rady i `DailySummary.date`
  to identyfikatory DNIA, nie chwile — konwersja by je zepsuła. Poza zakresem strażnika
- ⚠️ Karencja `event_at >= now - timedelta(days=1)` w `publishable_conditions` jest
  **poprawna** — strażnik celuje w GOŁE „teraz" (lookahead na działanie za `now`)
- **Kontener ma `TZ=Europe/Warsaw`**, więc `datetime.now()` (waste, proactive, agenci)
  jest lokalne i poprawne. Pułapką jest wyłącznie `utcnow()` z bazy
- Przy okazji, ta sama klasa: godzina pomiaru powietrza podawana agentowi jako UTC
  (widget obok pokazywał inną liczbę), godzina zgłoszenia w mailu do redakcji, data
  publikacji skrótu sesji, data repertuaru. Limit pytań AI liczył **anonimowych po
  dacie lokalnej, a zalogowanych po dobie UTC** — między północą a 2:00 jedni mieli
  nowy dzień, drudzy stary
- **Czwarta postać, znaleziona przy okazji: `date_start` briefingu pełnił DWIE
  role** — klucz dnia w `daily_summaries` I granicę okna materiału. Klucz jest
  poprawny jako północ UTC (etykieta dnia jak `session_date`; wisi na nim unikat
  kolumny rozstrzygający, czy przebieg z 13:30 NADPISUJE poranny wiersz, oraz
  `strptime` w `/api/summary/daily/{date}` i 186 wierszy) — **nie ruszać**.
  Zepsuty był drugi użytek: `_fetch_articles` filtruje `event_at >= window_start`,
  więc artykuł zapowiadający DZISIEJSZE wydarzenie całodniowe wypadał z materiału.
  Okno wydzielone do `_material_window` (doba lokalna, przycięta do „teraz").
  ⚠️ Pomiar 5.09: fallback chudego dnia (<10 artykułów) maskował to losowo —
  19 dni na 30 miało taki wpis, **17 z nich było zbyt obfitych, by fallback pomógł**
- Testy: `test_timezone_guard`, `test_event_terms` sekcja 5 (16 sprawdzeń na
  prawdziwym rekordzie biegu), `test_summary_headline` 36 + 9 (okno vs klucz)

## Wyszukiwarka pokazywała 1% bazy — i nikt tego nie widział (2026-09-05)
**Mieszkaniec pyta o nocny bieg, który odbywa się TEGO DNIA w Kopaniarzach.
Agent podaje „Leśny zryw" ze Starych Jabłonek — cudzy bieg sprzed pół roku.**
To nie była halucynacja: model dostał ten artykuł jako NAJLEPSZE trafienie.

**`idx_embeddings_vector` był indeksem ivfflat ze 100 listami, a `ivfflat.probes`
nikt nigdy nie ustawił.** Wartość domyślna to **1** — jedna lista, ~1% korpusu.
| pomiar (12 pytań, prod) | recall@12 | właściwy #1 |
|---|---|---|
| przed (probes=1) | **38%** | 8/12 |
| po (HNSW) | **100%** | 12/12 |
Zerową trafność miały „podatek od nieruchomości stawki" i „GOPS zasiłek rodzinny".

- ⚠️ **To nie jest awaria widoczna w logu.** Zapytanie kończy się sukcesem, zwraca
  wyniki, a rerank i progi pracują na materiale bez właściwej odpowiedzi. Część
  wcześniejszych porażek retrievalu przypisywanych progom mogła mieć TĘ przyczynę
- ✅ prod: `swap_vector_index_to_hnsw` (HNSW m=16, `CONCURRENTLY` — o 6:50/13:45
  chodzi job osadzania; budowa 5,8 s, 74 MB). ivfflat był przy tym **wolniejszy
  od skanu dokładnego** (85 vs 36 ms na 9540 wektorach) — płaciliśmy za gorsze wyniki
- ⚠️ **`hnsw.ef_search` MUSI być ≥ LIMIT zapytania** — HNSW zwraca najwyżej
  `ef_search` wierszy, więc niższa wartość obcina wynik PO CICHU. Ustawia to
  `embeddings._widen_index_scan` (`SET LOCAL`, bo sesje są z puli); ustawiamy oba
  GUC-i, bo lokalna baza może stać na innym indeksie
- Test: `python -m scripts.test_rag_recall` — prawdę liczy **skan dokładny**, więc
  test nie zależy od tego, jaki indeks stoi w bazie. Sprawdzony na stanie sprzed
  naprawy: czerwony (to jedyny dowód, że strażnik działa)

**Kalendarz i ogłoszenie to jedna sprawa, agent widział je osobno.** Termin stoi
w `events`, a nazwa wsi, godzina i trasa — w artykule, z którego je wyłuskaliśmy.
- `upcoming_events` dokłada fragment ogłoszenia (`source_article_id`, jedno
  zapytanie na listę) + `miejscowosc` liczoną KODEM (`alert_policy.places_in`;
  pole `miejsce` mówiło „Gmina Rybno", a bieg był w Kopaniarzach)
- `days_back` (0–365): kalendarz był ślepy na własną przeszłość — z 1180 wydarzeń
  agent widział **7**. „Kiedy był ten bieg" nie miało ŻADNEGO narzędzia
- Przewodnik dostał `search_news`; miał wcześniej tylko `search_documents`
  (wyszukiwarkę strojoną pod BIP)

**Pierwszy niepusty wynik kończył pracę — dołożenie narzędzia tego NIE naprawia.**
Pomiar: to samo pytanie w czterech konfiguracjach; dwie miały komplet narzędzi
i użyły wyłącznie pierwszego. Pętla kończy się, gdy model przestaje wołać
narzędzia, a nie gdy odpowiedź pokrywa pytanie.
- `base_agent.COMPLETENESS` — reguła w kontekście bazowym KAŻDEGO agenta (+671 B).
  ⚠️ Nie w bloku „TWOJE NARZĘDZIA": tamten ma twardy limit 2 kB i jest go 1976 B
- `tools.EMPTY_RESULT_RULE` — **trzeci nawrót** wzorca z 25.08: pustka „nie ma
  awarii" JEST odpowiedzią, pustka „nie znalazłem" nie jest. `co_powiedziec`
  w `upcoming_events`, `_search`, `latest_local_news`, `local_places` wskazuje
  NASTĘPNY KROK zamiast zamykać wątek
- Fragmenty wyszukiwarki niosą `zasieg` (`article_scope`, NIE `is_local_article`)
  i `trafione_slowa` — ile słów z pytania faktycznie pada w tekście. Zero we
  wszystkich fragmentach → `uwaga_dopasowanie`: to podobny TEMAT, nie ta sprawa
- ⚠️ `active_alerts` i `latest_local_news` wołały `publishable_conditions` **bez
  `now`**, więc mieszały czas wstrzyknięty z zegarem — odtworzenie awarii z 7.08
  przestało widzieć wyłączenie, którego dotyczy. Wstrzykiwany czas jest wart tyle,
  ile najsłabsze ogniwo, które go pomija

**Czego NIE DA SIĘ zdobyć — sprawdzone, nie założone.** Post gminy urywa się na
„⏰ Godzina…" (limit 300 zn., `make_social_snippet` — decyzja prawna). Facebook
oddaje serwerowi 338 kB skorupy BEZ treści posta; ta sama impreza na
powiatdzialdowski.pl to 480 znaków i żaden konkret. Dociągnięcie źródła NIE
odpowiedziałoby na to pytanie.
- `feed_policy.is_truncated` + pola `ogloszenie_urwane` / `urwany`: model ma
  WIEDZIEĆ, że czyta wypis, i powiedzieć mieszkańcowi, że reszta jest u źródła
- ⚠️ Podniesienie limitu 300 znaków to decyzja **prawna**, nie techniczna —
  najkrótsza droga do lepszych odpowiedzi o lokalnych wydarzeniach, ale wymaga
  świadomej zgody. Urwanych jest 193/246 wpisów Syli i 11/12 wpisów gminy
- ⚠️ **Radio 7 (234 wpisy) i KPP (156) nie mają `content` WCALE** — sam tytuł
  i streszczenie RSS. Ich strony są osiągalne z serwera (200), więc to do
  odzyskania; BIP nadal oddaje serwerowi 403

## TODO (Kolejne priorytety)
- [x] ~~Usunąć `idx_event_unique`~~ ✅ 3.09 `drop_event_text_unique` (prod). Był reliktem
      sprzed dedupu semantycznego i wywracał przebieg ekstrakcji. Pomiar: 521 powtórek
      z `canonical_id`, 86 o identycznym tytule — indeks blokował podzbiór tego, co
      `find_duplicate` łapie embeddingiem. Zostaje `idx_event_one_per_article`
- [x] ~~Deploy: deploy key + `set -e` + weryfikacja SHA~~ ✅ 3.09 `6e9ecde`, sprawdzone
      pierwszym prawdziwym deployem. Front nadal ręcznie: `yes TAK | ./deploy-frontend.sh`
- [ ] **Wolumen treści** (pomiar 3.09, 14 dni): 4–9 wpisów o gminie dziennie, 76% z jednego
      profilu (Syla); oficjalne kanały gminy prawie milczą (Gmina Rybno 2, FB Rybno 8).
      Radio 7 + KPP = 91 wpisów, 2 lokalne. Wzbogacenie = nowe profile FB przez Apify
      (limit FREE $5/mies., każdy profil to osobny run) — decyzja produktowa
- [ ] Waga `Facebook - Syla` = 0,85 (najniższa) przy 66 wpisach `locality=3` na 140 —
      główne źródło wiadomości o gminie ma najniższą wagę; po 3.09 lokalność rozstrzyga
      `locality`, więc waga gra mniejszą rolę, ale tabela wciąż mówi co innego niż dane
- [ ] Kategoria skacze między przebiegami (Społeczność/Edukacja dla tego samego tekstu)
      — `CATEGORY_PRIORITY` nagłówka opiera się na niedeterministycznej etykiecie
- [x] ~~Migracja `add_site_events` na produkcji~~ ✅ 30.08 (schemat zweryfikowany)
- [x] ~~Backend na produkcji~~ ✅ 30.08, `818a497` — `/api/events` i webhook odpowiadają,
      rejestracja zgodna wstecz (front bez `acq` przechodzi), zero błędów w logu
- [x] ~~Front na produkcji~~ ✅ 30.08, `5831478` — beacon łapie realny ruch
- [x] ~~Webhook Resend~~ ✅ 30.08 — podpis zweryfikowany NA PRODUKCJI wierszem
      kontrolnym: podrobiony odrzucony, prawidłowy zapisał `opened_at` i `clicked_at`
- [ ] **Pierwszy odczyt `site_events` po tygodniu** (`python -u -m scripts.site_report
      --days 7`), potem dopiero decyzja o GA4
- [ ] Cztery sierpniowe konta (id 8–11) zadały łącznie **1 pytanie** agentowi i żadne
      nie ma zgody push. To retencja, nie pozyskanie — ale co naprawiać, powie dopiero pomiar
- [x] ~~`date_start` w briefingu pełnił DWIE role naraz~~ ✅ 5.09 `0594e43` (prod).
      Klucz dnia ZOSTAJE północą UTC (etykieta dnia, unikat kolumny, `strptime`
      w `/api/summary/daily/{date}`); okno materiału wydzielone do
      `_material_window` i liczone `local_day_bounds`. Weryfikacja produkcyjnym
      kodem na produkcyjnej bazie: okno stare 7 artykułów, nowe 9 — doszedł
      art. 5618 (zapowiedź biegu NA DZIŚ) i 5826
- [ ] Przewodnik: dane pogodowe w embeddingach lub direct query
- [ ] Widget pogody → live API
- [ ] Filtrowanie artykułów po kategoriach
- [ ] Panel administracyjny
- [ ] Wybór rejonu wywozu dla kont z zapisem „Rybno” (dziś dostają oba terminy)
- [ ] `is_pinned_alert` bez czekania na kategorię — od 3.09 czeka najwyżej do :15
      po oknie Energi (kategoryzacja uzupełniająca); pełne rozwiązanie = czytać
      `incident_of` z treści, jak push i ostrzeżenia meteo
- [ ] **Nagłówek briefingu nie zna rangi organu**: 26.08 jutrzejsze posiedzenia
      stały tak — Komisja Zdrowia 08:30, Komisja Budżetu 08:45, **XXIV sesja Rady
      10:00**. Wszystkie lokalne, wszystkie „Urząd", więc rozstrzygnął dystans
      i sesja Rady przegrała o półtorej godziny z komisją. `event_extractor._organ_key`
      już odróżnia sesję od komisji (weto dedupu) — brakuje osi w `_select_top_article`
- [ ] Zgłoszenia 24: przypomnienie o sprawach stojących > 24 h w jednym statusie,
      starzenie kart awaryjnych, przycisk „już działa" dla mieszkańców (odłożone 24.08)
- [ ] Widget ruchu: zdarzenie chwilowe (spadłe bele, kolizja) musi WYGASAĆ — 21.08 trasa
      do Iławy pokazywała utrudnienie z 19.08; `road_context` nie odróżnia incydentu od prac
- [ ] Uruchomić `add_locality_and_event_dedup` + `dedupe_events --apply` (prod i lokalnie)
- [ ] **Jedno ogłoszenie = wiele terminów**: `events` ma częściowy unikat na
      `source_article_id`, więc ogłoszenie z serią spotkań daje JEDNO wydarzenie
      (konsultacje 25.08 Rumian + 26.08 Naguszewo — drugie wpisane ręcznie).
      Ekstraktor musi zwracać listę, unikat przejść na `(source_article_id,
      event_date)`, a ochronę przed re-scrapingiem przejąć znacznik na artykule
- [ ] Wydarzenia z `locality IS NULL` (4 z 15 przyszłych) — ocena lokalności
      istnieje od 21.08, starsze wpisy jej nie mają. `visible_event_conditions`
      je przepuszcza (świadomie), ale nie da się ich odróżnić od lokalnych
- [ ] Strażnik nazywa DZISIEJSZE wyłączenie „wczorajszym" (`test_agent_answers`:
      `prad-dzis`, `prad-planowane`, `awarie` — 3 czerwone 25.08, **stan zastany**,
      sprawdzone na czystym `HEAD`). Do rozstrzygnięcia też, czy wyłączenie
      zakończone dwie godziny temu ma jeszcze być „awarią" dla wyroczni
- [ ] Sesje rady: miejsce na froncie + decyzja, czy przepisać sesję XXIII na
      produkcji (~$0,59) — bez tego rejestr obrad jest pusty
- [ ] GUS-Analityk: `_classify_gus_query` → narzędzie `gus_series` (ostatnia heurystyka);
      przy okazji dostanie `przekaz_dalej` — dziś jako jedyny odsyła słowami
- [ ] Front: obsłużyć `discard_text` w kroku pracy (kasowanie tekstu porzuconego
      agenta) — bez tego przy handoffie mignie początek odmowy
- [ ] Uruchomić na PRODUKCJI: `add_gmina_institutions` + `run_bip_institutions`
      (migracja PRZED kodem!). Scraper tylko lokalnie — serwer dostaje z BIP 403
- [ ] Uzupełnić `gmina_institutions.hours` dla 11 jednostek (BIP ich nie ma):
      biblioteka, OSiR, szkoły, przedszkole, żłobek, GOPS, ZOZ

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
*Ostatnia aktualizacja: 2026-09-05*
