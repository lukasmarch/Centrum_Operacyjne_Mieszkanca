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

## 5. Kto ma jakie narzędzia (stan 22.08.2026)

| Agent | Narzędzia | Uwagi |
|---|---|---|
| **Przewodnik** | `weather_forecast`, `current_weather`, `air_quality`, `upcoming_events`, `local_places` | pierwszy przeniesiony; zniknęły `PLACE_KEYWORDS`, `_is_place_query`, `_detect_place_category` |
| **Organizator** | `waste_schedule`, `cinema_repertoire`, `clinic_schedule`, `pharmacy_duty`, `office_hours` | zniknął `INTENT_KEYWORDS`; `office_hours` to **nowe dane**, nie było ich nigdzie |
| **Strażnik** | `active_alerts`, `citizen_reports` | ⚠️ `active_alerts` to **jedyne** źródło jego wiedzy o awariach — nie używa RAG |
| Redaktor | — (RAG `["article"]` + blok świeżego feedu) | Etap 3 |
| Urzędnik | — (RAG `["bip_static","bip","article"]`) | Etap 3 |
| GUS-Analityk | — (własny SQL + `chart_data`) | Etap 3 |

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

- **Etap 3** — RAG jako narzędzie (`search_knowledge_base`) dla Redaktora
  i Urzędnika. ⚠️ Bramka `_GENERIC_QUESTION` została kupiona porażką z 9.08
  („co nowego" → „nie mam artykułów" przy 16 świeżych wpisach). Zdejmować tylko
  z zielonym `test_agent_answers`.
- **Etap 4 — uchwały.** Moduł BIP `/akty/14/typ/` (**inny** niż `DEFAULT_SECTIONS`),
  286 stron, pola: data podjęcia, grupa tematyczna, tytuł, nr aktu, status.
  Zakres **2024–2026** (decyzja Łukasza; zakres tłumaczymy użytkownikowi).
  Metadane SQL-em (`search_legal_acts`) — „jakie są najnowsze uchwały" to zwykły
  `ORDER BY date DESC`, nie zadanie dla wyszukiwarki wektorowej. Treść do RAG.
- **Etap 5 — sesje rady.** 6 rekordów w statusie `new`, `transcript_chars = 0`.
  Pipeline gotowy (`council_job`, 4:30), bramka akceptacji przez człowieka zostaje.
  Do tego miejsce na froncie.
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
