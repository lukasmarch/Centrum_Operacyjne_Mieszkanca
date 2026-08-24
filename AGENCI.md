# Agenci AI — dlaczego narzędzia, a nie kolejny prompt

*Notatka z przebudowy 22.08.2026. Opisuje decyzję, powód i mechanizmy — żeby za
trzy miesiące dało się odtworzyć nie tylko CO zrobiliśmy, ale DLACZEGO tak.*

---

## 1. Od czego się zaczęło

Przez pięć dni (17–21.08) na produkcji padło 14 pytań. Cztery system przegrał —
i każde z innego powodu, co samo w sobie było ważną wskazówką.

| Pytanie | Odpowiedź | Prawdziwa przyczyna |
|---|---|---|
| „Jak pogoda będzie jutro" | „Nie mam tego w aktualnej bazie" | **Dane BYŁY.** `weather.forecast` miał 40 slotów prognozy 5-dniowej, odświeżanych co godzinę. Przewodnik czytał tylko pomiar bieżący i średnią z 7 dni **wstecz** |
| „Jakie są najnowsze uchwały?" | „W bazie BIP nie ma dokumentów" | **Danych NIE MA.** Uchwały leżą w module BIP `/akty/14/typ/`, poza `DEFAULT_SECTIONS` |
| „Jak pracuje gops", „Gops" | wiedza ogólna GPT | Godzin urzędu i GOPS nie było **nigdzie** w systemie |
| „Godziny pracy" | „Proszę o sprecyzowanie…" | Żadne słowo nie trafiło w słownik `INTENT_KEYWORDS` |

**Rzecz, która przesądziła o kierunku:** oba pierwsze pytania to **kliknięcia
w nasze własne podpowiedzi**. „Jak wyglądają warunki pogodowe?" i „Jakie są
najnowsze uchwały?" siedziały w `example_questions` i szły do `/api/chat/suggestions`.
Sami proponowaliśmy klikalnie to, czego nie dowoziliśmy.

---

## 2. Co było wcześniej

Każdy agent pobierał dane **przed** przeczytaniem pytania, na podstawie słów kluczowych:

```python
# organizator.py — tak to wyglądało
INTENT_KEYWORDS = {"waste": ["smieci","odpad",...], "cinema": [...], "clinics": [...]}
wanted = {k for k, kws in INTENT_KEYWORDS.items() if any(kw in msg_norm for kw in kws)}
waste = await self._fetch_waste(...) if "waste" in wanted else []
# → model dostawał gotowy tekst i JUŻ NIC nie mógł dobrać
```

Sześć takich heurystyk w pięciu plikach: `INTENT_KEYWORDS`, `PLACE_KEYWORDS`,
`_GENERIC_QUESTION`, `_is_place_query`, `_detect_place_category`, `_classify_gus_query`.

Trzy wady, wszystkie widoczne w logach:

1. **Decyzja zapadała przed zrozumieniem pytania.** „Godziny pracy" nie trafiło
   w żaden wzorzec, więc Organizator dostał komplet czterech sekcji naraz —
   i dopytał, zamiast odpowiedzieć.
2. **Decyzja była jednokrotna.** Model nie mógł zobaczyć wyniku i dobrać czegoś
   jeszcze. Pytanie wymagające dwóch źródeł było niewykonalne w każdej konfiguracji
   promptów.
3. **Model nie wiedział, co istnieje.** `_fetch_waste` nie miało opisu, więc
   z punktu widzenia modelu nie istniało.

Kluczowa obserwacja, od której wszystko ruszyło: **`_fetch_waste` było narzędziem
od zawsze.** Miało sygnaturę, argumenty i zwracało strukturę. Brakowało mu dwóch
rzeczy — opisu dla modelu i tego, żeby to **model** decydował o wywołaniu.

---

## 3. Dlaczego ta droga, a nie inne

### Odrzucone: „więcej promptów / kolejny agent"
Prompt nie tworzy danych. Gdyby dopisać Przewodnikowi akapit o prognozie, w kontekście
i tak by jej nie było — bo `_build_context` jej nie składał. Nowy agent oznaczałby
szóstą kopię heurystyki słów kluczowych.

### Odrzucone: OpenAI Assistants API
Sunset **26.08.2026** — cztery dni po tej decyzji.

### Odrzucone: OpenAI Agents SDK / LangGraph
To orkiestracja nad tym samym prymitywem (function calling). Naszą orkiestrację —
router + rejestr agentów — mamy w 155 liniach i ona działa. Dokładanie frameworka
nad działającym routerem to dług, nie oszczędność.

### Odrzucone: `pydantic-ai` w warstwie czatu
Jest w repo (0.4.3) i sprawdza się w pipeline offline (`article_processor`,
`summary_generator`, `event_extractor`, `council_summary`). Ale wersja jest
**przypięta konfliktem opentelemetry** (patrz komentarz w `requirements.txt`).
Wiązanie ścieżki live-czatu z biblioteką, której nie możemy podnieść, to dług.
Zostaje tam, gdzie jest.

### Odrzucone (na teraz): migracja na Responses API
Chat Completions jest nadal wspierany. Responses to sensowny kierunek, ale to
osobna decyzja, nie warunek tej pracy.

### Wybrane: `chat.completions` + `tools` na `openai` SDK
Agenci już na nim stoją, SSE jest dopięte (`stream_options`, `sources`, `chart_data`).
Pętla narzędziowa to ~80 linii w jednym miejscu. Zero nowych zależności.

**Kryterium było jedno: rozwiązanie ma się obronić samo.** Nie „nowoczesne", tylko
takie, którego nie trzeba tłumaczyć przy każdym powrocie do kodu.

---

## 4. Co mamy teraz — mechanizmy

### 4.1 Rejestr narzędzi (`backend/src/ai/tools/__init__.py`)

Narzędzie = schemat JSON + funkcja + komunikat dla interfejsu.

```python
Tool(name, description, parameters, fn, status_message, short)
ToolContext(session, user, now)    # ← `now` WSTRZYKIWANE, nie z zegara
ToolResult(content, sources, charts, empty, error, summary)
```

Trzy rzeczy warte zapamiętania:

- **`ToolContext.now` jest wstrzykiwane.** Gdyby narzędzie brało czas z zegara,
  regresji z 7.08 (Strażnik gubiący wyłączenie prądu) nie dałoby się odtworzyć
  po fakcie. Walidator `replay-07-08` stoi wyłącznie na tym.
- **`ToolResult` rozdziela trzy warstwy.** `content` idzie do modelu; `sources`
  i `charts` idą **obok, prosto do interfejsu** — czego model nie musi przepisywać,
  tego nie może przekręcić.
- **`empty=True` to nie błąd.** „Szukałem i nie ma" jest odpowiedzią; „narzędzie
  padło" jest naszym problemem. Prompty traktują te przypadki inaczej, a narzędzia
  zwracają pole `co_powiedziec` z instrukcją, co zrobić zamiast zgadywania.

### 4.2 Pętla narzędziowa (`BaseAgent`)

```
strumień rusza OD RAZU z definicjami narzędzi
   ├─ model pisze tekst        → litery lecą do przeglądarki, ZERO dopłaty
   └─ model woła narzędzia     → status do UI → wykonanie → kolejna runda
```

- **`max_tool_rounds = 3`, ostatnia runda leci BEZ `tools`.** To jedyny hamulec:
  model nie ma wtedy wyjścia poza napisaniem odpowiedzi. Pętla zawsze się kończy.
- **Narzędzia wykonują się PO KOLEI, nie przez `asyncio.gather`.** Pierwsza wersja
  szła równolegle i padła na pierwszym teście z żywym modelem:
  `InvalidRequestError: This session is provisioning a new connection; concurrent
  operations are not permitted`. Wszystkie narzędzia dzielą sesję requestu.
  Koszt sekwencyjności to milisekundy — to zapytania do lokalnej bazy.
- **Błąd narzędzia nigdy nie wywraca rozmowy.** Wraca do modelu jako treść
  wiadomości `tool`, więc model może o nim powiedzieć. Limit czasu: 15 s.
- **`tools = []` → stara ścieżka RAG bez zmian.** Migracja idzie agentem po agencie,
  bo każdy niesie własne wnioski z awarii.

### 4.3 Świadomość własnego zasięgu

Blok generowany z rejestru, wstrzykiwany jak karta gminy:

```
TWOJE NARZĘDZIA (wołaj je zamiast zgadywać; wynik ma pierwszeństwo przed wiedzą ogólną):
- weather_forecast — prognoza na najbliższe dni (do 5), z szansą opadów i UV
- upcoming_events — kalendarz wydarzeń w gminie (do 60 dni w przód)
...
Jeśli pytanie wykracza poza to, co potrafisz sprawdzić — powiedz WPROST, czego nie
masz, i wskaż, gdzie mieszkaniec to znajdzie. Nie udawaj, że sprawdziłeś.
```

Dzięki temu na pytanie spoza zakresu („uchwała z 2019") agent powie, gdzie kończy
się jego wiedza, zamiast zgadywać albo milczeć. Limit: blok ma zostać krótki —
rozdęty konkuruje o uwagę modelu z materiałem źródłowym (ten sam argument, przez
który karta gminy ma limit 2 kB).

### 4.4 Widoczna praca agenta (front)

Pod pytaniem, na żywo:

```
ⓘ Analizuję pytanie i wybieram agenta…
✓ Pobieram prognozę pogody… · Rybno · 3 dni  → prognoza Rybno: 3 dni (14-14°C dziś)
🔍 Przeglądam kalendarz wydarzeń… · 7 dni     → kalendarz pusty w oknie 7 dni   [żółty]
```

- **Argumenty (`· Rybno · 3 dni`) to nie ozdoba ładowania.** To moment, w którym
  mieszkaniec widzi, że został źle zrozumiany („Szukam miejsc · Działdowo" przy
  pytaniu o Rybno) — i poprawia pytanie, zamiast czytać odpowiedź nie na temat.
- **Trzy stany, bo dla czytającego to trzy różne wiadomości:** znalazłem (można
  ufać) / nie ma tego w danych (odpowiedź będzie ostrożna — i wiadomo dlaczego) /
  narzędzie zawiodło (to nasz problem, nie brak danych).
- **Gdy wszystkie narzędzia wrócą puste**, dochodzi osobne ostrzeżenie przed
  odpowiedzią.
- Kod: `useChat.ts` (typ `AgentStep`, scalanie kroku „w toku" z jego wynikiem),
  `ChatMessage.tsx` (`AgentStepRow`).

### 4.5 Widget prognozy

`chart_type: "forecast"` → `ForecastStrip` w `ChatMessage.tsx`. Liczby idą do
interfejsu **obok** tekstu modelu, tą samą drogą co wykresy GUS (`trend`, `kpi`).

---

### 4.6 Pomiar wywołań (etap 6, 24.08.2026)

O dziurze z prognozą dowiedzieliśmy się dlatego, że ktoś przypadkiem kliknął
podpowiedź. Po przejściu na narzędzia ta sama dziura ma **stały kształt** —
narzędzie zawołane, `ToolResult.empty = True` — więc daje się policzyć zamiast
zauważyć.

Jeden wiersz w `agent_tool_calls` na jedno wywołanie: agent, narzędzie, stan,
rodzaj błędu, argumenty, czas, skrót pytania. Zbiera `_call_tool` — jedyne
przewężenie, przez które przechodzą obie ścieżki (strumień i non-stream)
i **wszystkie** gałęzie błędów.

Trzy rzeczy, które warto wiedzieć, zanim się to ruszy:

* **`empty` ≠ `error`, i nie wolno ich zlewać.** „Nie ma dziś awarii" to
  poprawna odpowiedź na poprawne wywołanie; naprawia się ją w ŹRÓDLE danych
  albo wcale. `timeout` czy `bad_arguments` to nasz kod. Wrzucone do jednej
  kolumny przestają się różnić — a to dwie różne naprawy;
* **zapis idzie OSOBNĄ sesją i po każdej rundzie.** Osobną, bo sesja requestu
  należy w tym momencie do pętli (`AsyncSession` nie znosi współbieżności —
  ta sama pułapka co `gather`), a `commit()` na niej zatwierdziłby cudzą
  transakcję. Po rundzie, a nie na końcu odpowiedzi, bo strumień kończy się też
  przez rozłączenie przeglądarki, a `finally` generatora asynchronicznego nie
  może wtedy bezpiecznie czekać na `await`;
* **telemetria nie ma prawa wywrócić odpowiedzi.** `flush()` nigdy nie rzuca —
  najgorsze, co się może stać, to brak wiersza w tabeli diagnostycznej.

```bash
cd backend && python -m scripts.tool_usage_report [--days 7] [--agent nazwa]
```

Raport ma cztery warstwy, bo to cztery różne naprawy: **użycie** (narzędzie
z zerem wywołań = zły `description`, nie zły kod), **pustka** (brak danych —
i tylko powtarzalna pustka na to samo pytanie coś znaczy), **awarie**
(`bad_arguments` mówi o opisie parametru, nie o bazie) oraz **argumenty**,
bo wywołanie `days=1` na pytanie o jutro wygląda w statystykach dokładnie
jak poprawne.

⚠️ **Czego ten pomiar NIE widzi:** pytań, przy których model nie zawołał
żadnego narzędzia. Wiersz powstaje dopiero przy wywołaniu, więc „Przewodnik
nie sprawdził pogody, choć powinien" nie zostawia tu śladu. To pomiar
narzędzi, nie pomiar trafności routingu.

**RODO:** `question` (200 zn.) i `user_id` znikają po 30 dniach, wiersz po 180
(`scheduler/retention_job.py`, 3:30). Liczniki zostają — do analityki wystarczy
nazwa narzędzia i stan. Pełna treść pytania i tak leży w `chat_messages`,
więc druga kopia żyje tylko tyle, ile trwa jej użyteczność.

---

### 4.7 Wyszukiwarka jako narzędzie (etap 3, 24.08.2026)

Retrieval był **podatkiem**: każde pytanie do Redaktora i Urzędnika płaciło za
przepisanie zapytania, wyszukiwanie hybrydowe i rerank, ZANIM ktokolwiek
wiedział, czy materiał z bazy jest potrzebny. „Kto jest wójtem" przechodziło
przez pełny retrieval, żeby odpowiedź i tak wzięła się z karty gminy.

Trzy narzędzia w `ai/tools/knowledge.py`. Podział na `search_news`
i `search_documents` zamiast jednego `search_knowledge_base` z parametrem, bo
progi (0,35/0,90/recency 0,25 kontra 0,40/0,55/0,0) kalibrowano osobno na
osobnych korpusach — jedno narzędzie musiałoby wybrać jeden zestaw i popsuć drugi.
Dodatkowo model MUSI wiedzieć, w czym szuka; sama nazwa mu to mówi.

**Najważniejsze: `latest_local_news` to nie wyszukiwarka.** Świeżość jest
zapytaniem po dacie, nie zadaniem dla podobieństwa wektorów — patrz porażka
z 9.08 w rozdziale 1. Do 24.08 wybierał między nimi regex `_GENERIC_QUESTION`,
który działał, ale tylko dla sformułowań przewidzianych przez autora („a co tam
u was ostatnio?" nie trafiało w żaden wzorzec). Dziś wybiera model, a reguła
przeniosła się z kodu do OPISU narzędzia — czyli tam, gdzie czyta ją ten, kto
podejmuje decyzję. Sprawdzone na żywym modelu (`test_agent_tools --live`).

**Co zniknęło:** przepisywanie pytania (`_rewrite_query`). Jego zadaniem było
zrobić z „a w zeszłym roku?" samodzielne zapytanie — a tutaj zapytanie układa
model, który historię rozmowy ma przed sobą. Jedno wywołanie gpt-4o-mini mniej
na każde pytanie.

**Co zostało:** rerank i synonimy. Oba kupione pomiarem i oba przeniesione
do narzędzia.

**Klasyczna ścieżka RAG w `BaseAgent` została USUNIĘTA.** Po przeniesieniu
Redaktora i Urzędnika nie miała ani jednego użytkownika — a wyglądała na żywą,
więc następna osoba naprawiałaby kod, którego nikt nie wywołuje i którego nic
nie sprawdza. `respond()` bez `tools` rzuca teraz `NotImplementedError` z
podpowiedzią. `_stream` zostaje: używa go GUS-Analityk.

⚠️ **Sondy w bramce trzeba było przepisać razem z agentem.** `test_agent_answers`
powtarzał retrieval Urzędnika ręcznie (`hybrid_search` z jego progami) i po
migracji mierzyłby coś, czego agent już nie robi — świecąc na zielono, bo
atrybuty `rag_*` dalej stały w klasie. Dokładnie ten sam błąd, przez który
22.08 sondy Strażnika przechodziły na usuniętej metodzie. Dziś obie sondy idą
przez narzędzia, a `co-nowego` dostał etap KONTEKST, którego nigdy nie miał.

---

### 4.8 Rejestr aktów prawnych (etap 4, 24.08.2026)

Moduł BIP `/akty/14/` — **inny niż `DEFAULT_SECTIONS`** wiedzy stałej: własna
paginacja, własna tabela metadanych, inna strona szczegółowa. Stąd osobny
scraper, nie parametr w tamtym.

Zakres **2024–2026**: 430 aktów (200 uchwał Rady, 230 zarządzeń Wójta),
2844 chunki w RAG, 14 minut pełnego przebiegu.

**Dlaczego osobna tabela, a nie `bip_documents`.** Akt ma NUMER, DATĘ PODJĘCIA,
STATUS i GRUPĘ — a najczęstsze pytanie („jakie są najnowsze uchwały") to
`ORDER BY adopted_at DESC`. Wyszukiwarka podobieństwa nie umie tego z tego
samego powodu, dla którego nie umiała „co nowego" (9.08): pytanie nie ma słów
wyróżniających, więc podobieństwo losuje.

**Trzy pułapki, każda kosztowała przebieg:**

* **lista NIE jest sortowana po dacie podjęcia**, tylko kolejnością wprowadzenia
  do BIP. Wśród aktów z kwietnia 2025 siedzi zarządzenie z listopada 2023
  (wprowadzone z opóźnieniem). Pierwsza wersja przerywała skan na pierwszym
  akcie sprzed progu i przez ten jeden wpis wciągnęła 229 aktów zamiast 430.
  Dziś przerywa po dwóch stronach POD RZĄD bez trafienia;
* **komórki tabeli niosą etykietę w treści** („Data podjęcia 2026-06-24") —
  układ responsywny, nie błąd parsowania. Bez obcięcia data nie parsuje się
  wcale, a akt wypada z „najnowszych";
* **`ORDER BY adopted_at` przy remisie losuje.** Jedna sesja podejmuje kilkanaście
  uchwał tego samego dnia (24.06.2026 — osiem), więc „najnowsze uchwały" nie
  były powtarzalne między dwoma wywołaniami. Druga oś: `bip_id DESC`.

**Treść aktu jest w PDF-ie** (`/system/pobierz.php?plik=…`) i ma warstwę
tekstową. 31 aktów na 430 to skany bez tekstu — ich metadane i tak odpowiadają
na pytanie „jakie są najnowsze". Eksport „Pobierz dane XML" jest ślepy: zwraca
stronę główną.

**Nagłówek chunku niesie NUMER i DATĘ** (`chunk_legal_act`), bo model cytuje to,
co widzi obok tekstu. Zły numer uchwały to nie nieścisłość — mieszkaniec pójdzie
z nim do urzędu.

⚠️ **Zakres mówimy WPROST.** Pusty wynik tłumaczy, że rejestr obejmuje akty od
2024 r. — inaczej „nie ma takiej uchwały" brzmi jak sąd o całym prawie gminy.

---

### 4.9 Skróty obrad Rady (etap 5, 24.08.2026)

**Diagnoza: nic nie było zepsute.** Sześć sesji stało w stanie `new` z zerem
prób, bo funkcja weszła na produkcję **12.08**, a najnowsza sesja (XXIII) była
z **24.06** — czyli 49 dni wcześniej, przy progu świeżości 45 dni
(`MAX_SESSION_AGE_DAYS`, bezpiecznik rachunku: Whisper to ~$0,59 za sesję).
Job utworzył wiersze i poprawnie pominął wszystkie. Funkcja wdrożyła się cztery
dni za późno, żeby złapać ostatnie obrady, a nowej sesji od tego czasu nie było
(przerwa wakacyjna).

**Bramka akceptacji obowiązuje także agenta.** `council_sessions` czyta
WYŁĄCZNIE `published`. Skrót w stanie `pending` nie istnieje dla czatu tak samo,
jak nie istnieje dla strony — bo cytat da się sprawdzić twardo, a `description`
punktu już nie (na sesji pilotażowej model dopisał tam cel zagospodarowania
działki, którego nikt nie wypowiedział). Wpuszczenie `pending` do rozmowy
obeszłoby jedyne zabezpieczenie tej funkcji, i to po cichu.

**Numery uchwał doklejamy z rejestru.** Model streszczający obrady zapisuje
`resolutions[].number = null` — na sesji XXIII wszystkie siedem. Nic dziwnego:
przewodniczący czyta tytuł uchwały, bo numer nadaje się po głosowaniu.
`legal_acts` zna numer i datę podjęcia, a ta jest równa dacie sesji — jedno
zapytanie zamienia „przyjęto uchwałę o kredycie dla OSP" w „XXIII/176/2026".

To jest ta klasa odpowiedzi, dla której powstały narzędzia: żadna heurystyka
słów kluczowych nie połączyłaby nagrania z rejestrem aktów, bo musiałaby z góry
wiedzieć, że pytanie o obrady potrzebuje numerów uchwał.

---

### 4.10 Pętla orkiestracji: agent może zmienić zdanie (etap 7, 24.08.2026)

**Skąd.** Pytanie „czy jesteś w stanie sprawdzić kondycję Rybna, podsumować
mocne i słabe strony, masz informacje bieżące i historyczne" dostało odpowiedź
*„Nie mam możliwości przeszukiwania historycznych danych ani analizy kondycji
gminy"* — przy 9123 rekordach GUS, 430 uchwałach i świeżym feedzie w bazie.

Nikt tu nie zawinił po stronie promptu. Router (`route()`) wybiera JEDNEGO
agenta, raz, na podstawie samego brzmienia pytania, zanim ktokolwiek zajrzy
do danych — a pytanie wielodziedzinowe z definicji nie mieści się w jednej
dziedzinie. Wybrał Redaktora, bo „bieżące" brzmi najgłośniej. Redaktor ma dwa
narzędzia i blok świadomości, który każe mu przyznać się do granic (4.3).
Zrobił dokładnie to. **Decyzja o agencie była nieodwoływalna — to był ten błąd.**

**Trzy elementy.**

1. **`przekaz_dalej`** (`tools/handoff.py`) — rezygnacja jako sygnał
   strukturalny. Agent bez zasięgu woła narzędzie z `czego_brakuje`
   i `sugerowany_agent`, zamiast pisać odmowę. Nie klasyfikator odmowy nad
   gotowym tekstem: wyrzuciliśmy sześć heurystyk słownych i nie wracamy po
   siódmą — tym razem na własnym tekście, gdzie „nie mam danych o Płośnicy,
   ale mam o Rybnie" jest odpowiedzią, nie odmową. Skutek uboczny, cenny:
   klasa porażki „agent poddał się, nie zawoławszy NICZEGO" była dla
   telemetrii **niewidzialna** (wiersz powstaje w `_call_tool`, a wywołania
   nie było). Teraz rezygnacja JEST wywołaniem i widać ją w raporcie.

2. **`Orchestrator.run()`** — pętla nad agentem. `MAX_HANDOFFS = 2`,
   a `_next_agent` nie wraca do agenta, który już odpowiadał: odbicie „to nie
   ja" ↔ „ja też nie" kończy się samo, niezależnie od tego, co wymyśli model.
   Ślepy zaułek pisze KOD, nie model (`_dead_end_message`) — model bez
   materiału wyprodukowałby dokładnie tę odmowę, od której zaczęliśmy.

3. **Koordynator** (`agents/koordynator.py`) — agent, którego narzędziami są
   inni agenci (`tools/delegation.py`). Nowej pętli nie budowaliśmy: to
   `max_tool_rounds`, które działa od 22.08, podniesione do 5. Router dostał
   siódmą opcję dla pytań wielodziedzinowych.

**Dlaczego delegacja woła AGENTA, a nie jego narzędzia.** Kusiło, żeby dać
koordynatorowi wszystkie 17 naraz. Przepadłaby wiedza z promptów specjalistów —
okna czasowe Strażnika, zakaz „nie mam wiadomości" u Redaktora, numery uchwał
u Urzędnika. To wnioski z awarii 7.08, 9.08 i 24.08, nie da się ich przenieść
do opisu narzędzia. Do tego GUS jako zbiór narzędzi nie istnieje w ogóle.

**Głębokość jeden, dwa zamki**: koordynatora nie ma wśród celów delegacji,
a delegowany agent dostaje `allow_handoff=False`.

⚠️ **Blok świadomości zmienił zakończenie** (4.3). Do etapu 7 brzmiało
bezwarunkowo „powiedz WPROST, czego nie masz" — i działało za dobrze. Gdy agent
ma `przekaz_dalej`, uczciwym wyjściem jest przekazanie, a odmowa staje się
szkodą. Agent bez handoffu ma stare brzmienie.

⚠️ **Timeout narzędzia to nie timeout delegacji.** Wspólne `TOOL_TIMEOUT_S = 15`
jest skalibrowane dla zapytania do bazy. Delegacja uruchamia całą pętlę innego
agenta z jego wywołaniami gpt-4o — pierwszy przebieg 24.08 uciął Urzędnika po
15 s i koordynator napisał o kondycji gminy **bez ani jednego zdania
o finansach**. Stąd `Tool.timeout_s` i 45 s dla delegacji (pomiar: 6–20 s).

⚠️ **Etykieta zasięgu ginie w syntezie.** Pierwszy przebieg podał piknik
w Żurominie i blok w Działdowie jako *mocne strony gminy Rybno*. Redaktor
oznaczał je poprawnie (`article_scope`) — to koordynator zgubił rozróżnienie
przy sklejaniu. Reguła jest dziś w jego prompcie; to ta sama pułapka, co przy
`is_local_article` (4.7).

⚠️ **GUS-Analityk nie umie przekazać pytania** — nie ma pętli narzędziowej,
więc odsyła słowami („skontaktuj się z Organizatorem"). Zniknie razem
z `_classify_gus_query`. Dotyczy tylko ręcznego wyboru GUS-a na froncie; router
kieruje takie pytania poprawnie.

**Koszt.** Pytanie bez handoffu kosztuje tyle co wcześniej — pętla nie ma się
od czego uruchomić. Jedyny stały wzrost to definicja `przekaz_dalej` w każdym
wywołaniu (~80 tokenów). Pomiar 24.08 na żywej bazie: pełna analiza kondycji
gminy = 8949 tokenów i 37,6 s (trzy delegacje), handoff przy prostym pytaniu =
4,2 s.

**Front**: zdarzenie kroku pracy niesie `handoff: true` i `discard_text` —
przeglądarka ma skasować tekst porzuconego agenta. Backend robi to samo dla
zapisu w bazie (`chat.py`), inaczej w historii rozmowy zostałaby odmowa
sklejona z odpowiedzią.

---

### 4.11 Dane jednostek z bazy, nie ze stałej (etap 7 pkt 5, 24.08.2026)

**Stała w kodzie nie ma jak zdezaktualizować się głośno.** `OFFICE_HOURS`
w `ai/tools/daily.py` niosła dwie instytucje i obie miały błędy:

| | w kodzie | naprawdę |
|---|---|---|
| Urząd Gminy | 7:15–15:15 | **8:00–16:00** (gminarybno.pl) |
| GOPS | ul. Lubawska 15, tel. 696 60 55 | **ul. Zajeziorna 58, tel. 696 63 39** |

Adres i telefon GOPS to były dane Urzędu Gminy. Agent podawał je płynnie
i z przekonaniem — mieszkaniec pojechałby pod zły adres, a pod urząd trafiłby
godzinę przed otwarciem.

Dziś: tabela `gmina_institutions` (12 jednostek), scraper
`scrapers/bip_institutions.py`, narzędzie `institution_info`. `office_hours`
usunięte, nie zostawione obok.

**Dlaczego nie do karty gminy** — pytanie wracało kilka razy, więc na piśmie:
karta ma limit 2 kB pilnowany testem, bo wchodzi do promptu KAŻDEGO agenta przy
KAŻDYM pytaniu; dwanaście adresów zjadłoby ją w całości, a płaciłby też ktoś
pytający o śmieci. Do tego wiedza w prompcie **nie zostawia śladu** — nie
wiadomo, czy model jej użył. Odczyt narzędziem zapisuje wiersz
w `agent_tool_calls`, więc widać, o co ludzie pytają i czego brakuje.

⚠️ **`hours` puste dla 11 z 12 jednostek i to jest stan poprawny** — BIP
publikuje godziny tylko dla urzędu. Narzędzie mówi wprost „NIE MAMY tej
informacji — podaj telefon". To pola RĘCZNE: scraper ich nie nadpisuje, więc
uzupełnienie przeżywa niedzielny przebieg. Zmyślona godzina otwarcia szkoły
byłaby gorsza od jej braku.

⚠️ Scraper **musi chodzić lokalnie** — serwerownia dostaje z BIP 403 (6.4).

---

## 5. Kto ma jakie narzędzia (stan 24.08.2026)

| Agent | Narzędzia | Uwagi |
|---|---|---|
| **Przewodnik** | `weather_forecast`, `current_weather`, `air_quality`, `upcoming_events`, `local_places` | pierwszy przeniesiony; zniknęły `PLACE_KEYWORDS`, `_is_place_query`, `_detect_place_category` |
| **Organizator** | `waste_schedule`, `cinema_repertoire`, `clinic_schedule`, `pharmacy_duty`, `institution_info` | zniknął `INTENT_KEYWORDS`; `office_hours` **zastąpione** przez `institution_info` (4.11) |
| **Strażnik** | `active_alerts`, `citizen_reports` | ⚠️ `active_alerts` to **jedyne** źródło jego wiedzy o awariach — nie używa RAG |
| **Redaktor** | `latest_local_news`, `search_news` | zniknął regex `_GENERIC_QUESTION` i blok „ŚWIEŻY FEED" z `extra_context` |
| **Urzędnik** | `search_legal_acts`, `council_sessions`, `search_documents` | zniknął retrieval przed każdym pytaniem; cztery poziomy odpowiedzi zostają |
| GUS-Analityk | — (własny SQL + `chart_data`) | `_classify_gus_query` czeka na swoją kolej; **jedyny bez `przekaz_dalej`** |
| **Koordynator** | `zapytaj_*` × 6 (etap 7) | narzędziami są inni agenci; `can_handoff = False`, nie jest celem delegacji |

Do tego **każdy agent poza GUS-em i Koordynatorem** dostaje `przekaz_dalej` — dopisywane
w `_effective_tools`, nie w `tools` klasy, żeby nie pilnować sześciu list (4.10).

---

## 6. Pułapki, które już nas kosztowały

- **`AsyncSession` nie znosi współbieżności** — narzędzia PO KOLEI (patrz 4.2).
- **Świeżość danych to część odpowiedzi.** `weather_forecast` odrzuca sloty
  z przeszłości i oznacza nieświeży pomiar (`uwaga_swiezosc`). Bez tego stojący
  `weather_job` oznaczałby prognozę sprzed trzech dni podaną jako jutrzejsza —
  cicho i z pełnym przekonaniem. Ta sama pułapka co utrudnienie drogowe sprzed
  dwóch dni wiszące w widgecie ruchu.
- **Opis parametru to treść promptu, nie metadana.** Model prosił o `days=1`
  sądząc, że „jutro" to jeden dzień, i opisywał resztkę dzisiejszego wieczoru
  jako jutro. Opis mówi teraz wprost: dziś liczy się jako dzień pierwszy.
- **Szablon w prompcie potrafi produkować bzdury przy pustych danych.** Strażnik
  miał kazane mówić „teraz nic nie trwa, ale zapowiedziano *<co>*" — przy pustej
  bazie wychodziło „zapowiedziano brak przerw w dostawie prądu". Zdanie
  o zapowiedziach obowiązuje teraz tylko wtedy, gdy coś w wyniku jest.
- **Testy z atrapą nie zastąpią jednego przebiegu z żywym modelem.** Błąd
  z `gather` i błąd z `days=1` wyszły dopiero na `--live`.
- **Agent wołający narzędzia na wszystko jest tak samo zepsuty jak ten, który nie
  woła wcale — tylko drożej.** Stąd przypadek kontrolny w testach: „kto jest
  wójtem" musi wrócić **bez** wywołania narzędzia (odpowiedź jest w karcie gminy).
- **Etykieta miejsca to nie to samo co bramka rankingu.** `is_local_article`
  mówi „czy to nasz region" i jest celowo szeroka (lepiej pokazać sąsiednią
  gminę niż zgubić naszą sprawę). Użyta jako ETYKIETA kłamie: 24.08 Redaktor
  podał „budowa bloku komunalnego w Działdowie (**gmina Rybno**)", bo całe
  źródło „Powiat Działdowski (RSS)" przechodzi przez tę funkcję bez patrzenia
  na treść. Stąd `feed_policy.article_scope` — osobna funkcja na osobne pytanie.
- **Test, który losowo świeci na czerwono, uczy ignorowania czerwonego.**
  Wzorzec zakazany w bramce zawierał „skontaktuj się z urzędem", a prompt
  Urzędnika WYMAGA podania konkretnego następnego kroku. Ta sama, dobra
  odpowiedź o azbeście raz przechodziła, raz nie — zależnie od tego, jak model
  zakończył zdanie. Sprzeczność między promptem a wyrocznią rozstrzyga się
  na rzecz produktu, nie testu.
- **Data wpisana w test na sztywno to bomba zegarowa.** `test_agent_tools --live`
  wymagał, żeby odpowiedź o jutrzejszej pogodzie zawierała „23" — jutro z dnia
  pisania testu. 24.08 test świecił na czerwono przy odpowiedzi **poprawnej**.
  Test psujący się od upływu czasu uczy ignorowania czerwonego wyniku, czyli
  jest gorszy niż jego brak. Dziś data liczy się z zegara (dzień + miesiąc
  słownie — sam numer trafiłby przypadkiem w stopień Celsjusza).

---

## 7. Jak dodać nowe narzędzie

1. Funkcja `async def nazwa(ctx: ToolContext, **args) -> ToolResult` w module
   w `backend/src/ai/tools/`.
2. `register(Tool(...))` na dole modułu — `description` mówi modelowi **KIEDY**
   użyć (nie tylko co robi), `short` to jedno zdanie do bloku świadomości,
   `status_message` widzi użytkownik.
3. Import modułu na dole `tools/__init__.py`.
4. Nazwa narzędzia na liście `tools` agenta.
5. Pusty wynik: `empty=True` + pole `co_powiedziec` w treści.
6. `summary` — jedno zdanie dla człowieka („6 terminów wywozu", „kalendarz pusty").

Trzymaj listę per agent wąską (3–5). Definicje wchodzą do **każdego** wywołania
(~80 tokenów sztuka), a Urzędnik i GUS chodzą na gpt-4o.

---

## 8. Testy

```bash
cd backend
python -m scripts.test_agent_tools            # rejestr, pętla, składanie prognozy (atrapa, 0 zł)
python -m scripts.test_agent_tools --db       # + narzędzia na żywej bazie
python -m scripts.test_agent_tools --live     # + prawdziwy model: czy woła WŁAŚCIWE narzędzia (~1 grosz)
python -m scripts.test_agent_answers          # 11 pytań mieszkańca kontra stan bazy
python -m scripts.tool_usage_report --days 7  # co narzędzia zastały (nie test — raport)
```

`test_agent_answers` sonduje Strażnika przez narzędzia (`active_alerts`,
`citizen_reports`), nie przez metody agenta — bo od 22.08 agent ich nie ma.

---

## 9. Co zostało

- ~~**Etap 3** — RAG jako narzędzie.~~ ✅ **24.08.2026** — `search_news`,
  `search_documents`, `latest_local_news`; Redaktor i Urzędnik przeniesieni,
  klasyczna ścieżka RAG usunięta (patrz 4.7). Zostaje `_classify_gus_query`
  w GUS-Analityku.
- ~~**Etap 4 — uchwały.**~~ ✅ **24.08.2026** — 430 aktów 2024–2026,
  `search_legal_acts` + treść w RAG (patrz 4.8).
- **Etap 5 — sesje rady.** ✅ diagnoza (funkcja weszła 4 dni za późno, nic nie
  jest zepsute) + narzędzie `council_sessions` z bramką akceptacji (patrz 4.9).
  ⏳ **Zostaje**: miejsce na froncie oraz DECYZJA Łukasza — czy przepisać sesję
  XXIII ręcznie na produkcji (`run_council_session --url … --save`, ~$0,59)
  i zaakceptować skrót. Bez tego rejestr obrad jest pusty i front pokazywałby
  pustkę.
- ~~**Etap 6** — log wywołań narzędzi i raport pustych wyników.~~ ✅ **24.08.2026**
  — `agent_tool_calls` + `scripts/tool_usage_report.py`, patrz 4.6.

---

## 10. Stan wdrożenia

🟢 **Produkcja, 22.08.2026 wieczorem.** Front `5cde9e1` wdrożony ręcznie,
backend wypchnięty (GitHub Actions 19 s). Zweryfikowane na żywym API:

```
"Kiedy wywoz smieci w Hartowcu?"
  status · waste_schedule · running · detail: "Hartowiec"
  status · waste_schedule · done    · "Hartowiec: najbliższy wywóz 25.08.2026"
```

Uwaga na przyszłość: tym razem front poszedł **przed** backendem i nic się nie
zepsuło (front bez `state` pokazuje krok jako neutralny wiersz). Ale gdy w grę
wchodzi migracja bazy, kolejność jest nienegocjowalna — **migracja przed kodem**.

*Commity: `7799a3c` (fundament + pogoda + Przewodnik), `5cde9e1` (Organizator,
Strażnik, widoczna praca agenta).*
