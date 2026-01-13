Oto pełny tekst artykułu ze strony **GammaVibe** w formacie Markdown, przygotowany zgodnie z Twoją prośbą.

---

# Architektura autonomicznego generatora pomysłów na startup (Python, Pydantic AI, Gemini, Postgres)

**Autor:** Mirko Froehlich

**Data:** 28 grudnia 2025 r.

**Czas czytania:** 11 min

*Zrzut ekranu terminala z działającym potokiem (widoczne kroki QA i Ghost Publish)*

Każdego ranka mój potok AI (pipeline) budzi się, przetwarza setki artykułów informacyjnych, identyfikuje okazje biznesowe ukryte w szumie informacyjnym i publikuje newsletter — bez jakiejkolwiek interwencji człowieka. Oto jak go zbudowałem.

## Co robi ten projekt

Gamma Vibe to codzienny newsletter, który syntetyzuje wiadomości w możliwe do zrealizowania okazje startupowe. Wyzwanie: wziąć natłok surowych informacji i przekształcić go w wyselekcjonowane, wysokiej jakości spostrzeżenia biznesowe, które czytelnicy faktycznie chcą czytać.

Potok obsługuje wszystko: pobieranie wiadomości, filtrowanie szumu, wyciąganie sygnałów biznesowych, syntezę tematów, generowanie wizualizacji, pisanie treści, kontrole jakości i publikację w systemie Ghost CMS. Dziesięć kroków, w pełni zautomatyzowanych, uruchamianych codziennie.

Możesz zobaczyć przykład wyniku tutaj: *Your AI’s Backdoor is Unlocked*.

## Architektura wysokiego poziomu

### Ewolucja od prototypu do produkcji

Szybko uruchomiłem początkowy potok, używając artefaktów JSON. Każdy krok odczytywał dane z pliku, wykonywał swoją pracę i zapisywał wynik do innego pliku. Było to idealne do prototypowania — mogłem skupić się na logice potoku, a nie na instalacji bazy danych.

Jednak to podejście miało ograniczenia. Potok był całkowicie liniowy: każde uruchomienie musiało pobierać wszystkie artykuły z poprzedniego dnia, przeprowadzać selekcję, ekstrakcję i tak dalej — nawet jeśli uruchomiłem potok kilka minut wcześniej.

Migracja do bazy danych jako "źródła prawdy" zmieniła wszystko:

* **Brak nadmiarowego przetwarzania:** Artykuły są dodawane (upsert) z unikalnym kluczem. Ponowne pobieranie nie przetwarza artykułów, które już widzieliśmy.
* **Ruchome okna:** Zamiast patrzeć tylko na dzisiejsze sygnały, synteza może analizować 4-dniowe okno spostrzeżeń, co pozwala na lepsze wykrywanie trendów.
* **Wznawialne wykonywanie:** Każdy krok odpytuje bazę o oczekujące zadania. Jeśli potok zawiedzie na kroku 7, wznowienie zaczyna dokładnie tam, gdzie przerwał.
* **Lepszy wybór kandydatów:** Zamiast "najlepszego pomysłu z dzisiejszego rynki", możemy rozważyć wszystkich kandydatów z ostatnich kilku dni.

### Projekt potoku oparty na stanach

Każdy z dziesięciu kroków następuje według tego samego wzorca:

1. Odpytaj bazę danych o elementy wymagające przetworzenia.
2. Wykonaj pracę (zazwyczaj obejmującą wywołanie LLM).
3. Zapisz wyniki z powrotem do bazy danych.

Żadne dane nie są przekazywane między krokami przez argumenty funkcji. Baza danych jest jedynym źródłem prawdy. Dzięki temu system jest niezwykle solidny.

## Dziesięć kroków potoku

1. **Fetch & Clean:** Pobieranie świeżych wiadomości z API EventRegistry, filtrowanie artykułów sponsorowanych, zapis do bazy.
2. **Triage:** Szybki filtr AI. Zachowanie artykułów o nowych technologiach, trendach konsumenckich, regulacjach. Odrzucanie giełdy, polityki, celebrytów.
3. **Extraction:** Dla zachowanych artykułów wyciągane są ustrukturyzowane sygnały biznesowe (punkty zapalne, zmiany konsumenckie) oraz fakty rynkowe.
4. **Synthesis:** Łączenie sygnałów z ostatnich 4 dni w tematy inwestycyjne. Generowane są trzy archetypy: Meta-Trend, Friction Point (uciążliwe problemy) i Rabbit Hole (niszowe tematy).
5. **Deep Dive:** Wybór zwycięskiego kandydata i rozwinięcie go w pełny model biznesowy (wartość, przychody, GTM, tech stack, nazwa).
6. **Visualizer:** Generowanie promptu do obrazu na podstawie archetypu kandydata.
7. **Image Generator:** Tworzenie nagłówka obrazu z promptu.
8. **Writer:** Przygotowanie finalnego newslettera w formacie Markdown z naturalnie wplecionymi linkami źródłowymi.
9. **Quality Assurance:** Persona „cynicznego redaktora” ocenia treść. Posty poniżej progu są odrzucane lub kierowane do przeglądu.
10. **Ghost Publisher:** Publikacja w Ghost CMS.

## Stos technologiczny (Tech Stack)

* **Python 3.13 + uv:** Nowoczesne zarządzanie zależnościami.
* **Pydantic AI:** Strukturyzowane dane wyjściowe z LLM z zapewnieniem typów.
* **PostgreSQL + pgvector:** Baza danych z rozszerzeniem wektorowym do wyszukiwania podobieństw i deduplikacji pomysłów.
* **SQLModel:** Definicje modeli działające zarówno dla tabel bazy, jak i walidacji Pydantic.
* **SQLAdmin + FastAPI:** Wewnętrzny panel do inspekcji przebiegów potoku.
* **Alembic:** Migracje bazy danych.
* **Docker:** Konteneryzacja wdrożenia.

## Praca z modelami Gemini

### Wybór modelu do zadania

* **Gemini 2.5 Flash-Lite** do selekcji (triage): Duża objętość, proste decyzje, tanio i szybko.
* **Gemini 2.5 Flash** do ekstrakcji: Bardziej niuansowa identyfikacja sygnałów.
* **Gemini 2.5 Pro** do syntezy, pisania i QA: Wymaga rozumowania i kreatywności.

Używam również modeli specjalistycznych: **Gemini 3.0 Pro Image** (znany jako Nano Banana Pro) do obrazów oraz **gemini-embedding-001** do wektorów.

### Pydantic AI i Logfire

Pydantic AI zapewnia, że model zwraca dokładnie takie dane, jakich oczekuję (np. obiekt JSON zgodny ze schematem). Do monitorowania używam **Logfire**, który loguje każde wywołanie agenta, zużycie tokenów i opóźnienia.

## Rozwiązanie problemu „powtarzalności” (Sameness)

Bez odpowiednich mechanizmów AI produkuje powtarzalne treści. Wprowadziłem:

* **Strategia „Best of Buffer”:** Wybieram zwycięzcę z puli kandydatów z ostatnich 4 dni.
* **Mnożnik zmęczenia (Fatigue Multiplier):** Obniżanie oceny kandydatów o tym samym archetypie, co ostatni zwycięzcy (np. jeśli wczoraj był Meta-Trend, dziś ma mniejszą szansę).
* **Veto podobieństwa:** Używając wektorów, sprawdzam czy pomysł nie jest zbyt podobny do czegoś opublikowanego w ciągu ostatnich 60 dni.
* **Różnorodność wizualna:** Każdy archetyp ma przypisany styl (np. *Glassmorphism* dla Meta-Trendów, *Industrial Cyber-Structure* dla problemów technicznych).

## Dlaczego Ghost CMS i EventRegistry?

Wybrałem **Ghost**, ponieważ jest open-source, ma świetne API, wbudowane zarządzanie subskrypcjami (Stripe) i doskonałe dostarczanie e-maili przez Mailgun.

**EventRegistry** (newsapi.ai) wygrało dzięki hojnemu darmowemu planowi (pełna treść artykułów bez opóźnień) oraz możliwości definiowania stron tematycznych (Topic Pages), co pozwala stroić źródła bez zmiany kodu.

## Struktura kosztów

| Usługa | Koszt miesięczny |
| --- | --- |
| EventRegistry (News API) | Plan darmowy (później $90) |
| Ghost Pro | $35 |
| DigitalOcean (Droplet + Postgres) | $22 |
| Gemini API | ~$20 |
| **Suma** | **$77 (później $167)** |

## Lekcje i wnioski

1. **Od artefaktów do bazy danych:** Prototypuj na plikach JSON, ale migruj do bazy danych jak najszybciej.
2. **Inwestuj w obserwowalność:** Logfire był kluczowy. Musisz widzieć dokładnie, co wchodzi i wychodzi z LLM.
3. **Filozofia testowania:** Nie "mockuj" wywołań LLM. Testuj części deterministyczne, a zachowanie modelu monitoruj przez obserwowalność.
4. **Optymalizacja kosztów wymaga uwagi:** Model Flash jest świetny do masowej pracy, ale czasem "nudzi się" i ucina dane (np. UUID w JSON). Pro jest niezbędny do długich tekstów Markdown (>1000 słów).

## Co dalej

Skupiam się na jakości i różnorodności. Rozważam udostępnienie przeszukiwalnej bazy danych wygenerowanych pomysłów. Wkrótce pojawi się wideo z instrukcją systemu na YouTube.

---

### Pliki zdjęć (Linki bezpośrednie):

1. **Zdjęcie główne (Terminal):** `https://gammavibe.com/content/images/2025/12/terminal-screenshot.png`
2. **Diagram architektury:** `https://gammavibe.com/content/images/2025/12/architecture-diagram.png`