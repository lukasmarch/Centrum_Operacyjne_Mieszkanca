# Instrukcja — Ręczne uruchomienie pipeline i dodawanie źródeł

## 1. Ręczny trigger dziennego pipeline (PEŁNY)

**Plik:** `scripts/tests/aktualny_pipeline/test_full_pipeline.py`

Symuluje dokładnie to, co scheduler robi automatycznie (patrz `scheduler.py`):

| Krok | Co się dzieje | Odpowiadający job |
|------|---------------|-------------------|
| 1 | Scraping wszystkich aktywnych źródeł | `article_job` (codziennie 6:00, 12:00) |
| 2 | Kategoryzacja artykułów przez AI (GPT) | `ai_jobs` — ArticleProcessor (co godzinę) |
| 3 | Ekstrakcja wydarzeń z artykułów | `ai_jobs` — EventExtractor (co godzinę) |
| 4 | Generowanie dziennego podsumowania | `summary_job` (codziennie 6:30, 12:30) |

Wszystko zapisuje się do bazy danych — artykuły, kategorie, wydarzenia i podsumowanie.

### Uruchomienie

```bash
cd backend
python scripts/tests/aktualny_pipeline/test_full_pipeline.py
```

### Wymogi przed uruchomieniem

- Baza danych działa (`docker-compose up -d`)
- W `.env` jest `DATABASE_URL` i `OPENAI_API_KEY`
- `.venv` aktywne (`source .venv/bin/activate`)
- **Backend nie musi być uruchomiony** — skrypt bezpośrednio importuje job-y ze scheduler i łączy się z bazą

### Kiedy tego użyć

- Scheduler czegoś nie goldnął (brak artykułów, brak podsumowania)
- Chcesz wymusić pipeline po ręcznym dodaniu nowego źródła
- Testujesz zmianę w scraperach lub AI
- **WYMAGA:** Apify API key dla Facebook scraperów

---

## 2. Ręczny trigger AI + Summary (BEZ scrapowania)

**Plik:** `scripts/tests/aktualny_pipeline/test_ai_and_summary.py`

**Robi TYLKO:**
1. Kategoryzacja artykułów przez AI (GPT-4o-mini)
2. Ekstrakcja wydarzeń z artykułów
3. Generowanie dziennego podsumowania

**Pomija:** Scraping (krok 1) — używa artykułów już w bazie.

### Uruchomienie

```bash
cd backend
python scripts/tests/aktualny_pipeline/test_ai_and_summary.py
```

### Kiedy tego użyć

- **Masz już artykuły w bazie** (po wcześniejszym scrapowaniu)
- Testujesz bez Apify (brak API key lub limit wyczerpany)
- Chcesz tylko przetworzyć istniejące artykuły przez AI
- Chcesz regenerować summary z tych samych artykułów
- **Szybsze testy** - pomija wolne scrapowanie Facebook/Apify

### Wymogi

- Baza danych z artykułami (`processed=False` dla kategoryzacji)
- `OPENAI_API_KEY` w `.env` (dla AI processing)
- **NIE wymaga:** Apify API key

### Przykładowy workflow

```bash
# Sprawdź ile nieprzetworzonych artykułów masz
psql $DATABASE_URL -c "SELECT COUNT(*) FROM articles WHERE processed=false;"

# Uruchom AI processing + summary
python scripts/tests/aktualny_pipeline/test_ai_and_summary.py
```

---

## 3. Dodawanie nowych źródeł Facebook / Apify

**Plik:** `scripts/setup/add_facebook_sources.py`

### Dodaj jedno nowe konto Facebook

```bash
cd backend
python scripts/setup/add_facebook_sources.py \
  --add "https://www.facebook.com/GminaRybno" "Gmina Rybno"
```

Jeśli `APIFY_API_KEY` jest w `.env`, źródło zostanie od razu ustawione jako `active` i scheduler go pobierze przy kolejnym uruchomieniu. Bez klucza — status `inactive`.

### Wyświetl wszystkie źródła Facebook w bazie

```bash
python scripts/setup/add_facebook_sources.py --list
```

Pokaże ID, URL, status i czy mamy API key dla każdego źródła.

### Dodaj predefiniowane źródła (Syla, Gmina Działdowo, Urząd Miasta)

```bash
python scripts/setup/add_facebook_sources.py
```

Bez argumentów dodaje listę predefiniowanych kont z kodu źródłowego.

### Wymogi

- `APIFY_API_KEY` w `.env` (konto: https://apify.com)
- Token z: https://console.apify.com/account/integrations

### Workflow — dodasz nowe źródło i chcesz od razu go pobrać

```bash
# 1. Dodaj źródło do bazy
python scripts/setup/add_facebook_sources.py \
  --add "https://www.facebook.com/NowaSzkolna" "Nowa Szkolna"

# 2. Uruchom PEŁNY pipeline (scraping + AI + summary)
python scripts/tests/aktualny_pipeline/test_full_pipeline.py

# LUB bez scrapowania (jeśli masz już artykuły):
python scripts/tests/aktualny_pipeline/test_ai_and_summary.py
```

---

## 4. Porównanie skryptów testowych

| Skrypt | Scraping | AI Processing | Summary | Wymaga Apify | Czas |
|--------|----------|--------------|---------|--------------|------|
| **test_full_pipeline.py** | ✅ Wszystkie źródła | ✅ | ✅ | ✅ TAK | ~5-10 min |
| **test_ai_and_summary.py** | ❌ Pomija | ✅ | ✅ | ❌ NIE | ~30-60s |

**Rekomendacja:**
- **Pełny test systemu** → `test_full_pipeline.py`
- **Szybkie testy AI/summary** → `test_ai_and_summary.py`
- **Production** → Scheduler automatyczny (6:00 AM codziennie)

---

## 5. Struktura scheduler-ów (dla odniesienia)

```
src/scheduler/
├── scheduler.py       ← Master — definiuje KIEDY co się uruchomia
├── article_job.py     ← Scraping (6:00, 12:00)
├── ai_jobs.py         ← Kategoryzacja + events (co godzinę)
├── summary_job.py     ← Daily summary (6:30, 12:30)
├── weather_job.py     ← Pogoda (co godzinę)
├── gus_job.py         ← Statystyki GUS (6:00)
├── cinema_job.py      ← Repertoire kina (8:00)
└── newsletter_job.py  ← Newsletter (sob 10:00 / pn-pt 6:30)
```
