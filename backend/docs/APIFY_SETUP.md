# Apify Setup - Facebook Scraping

## Czym jest Apify?

Apify to platforma do web scrapingu oferująca gotowe "actory" (narzędzia do scrapowania). Używamy actora `apify/facebook-posts-scraper` do pobierania postów z Facebooka.

---

## Krok 1: Rejestracja konta Apify

1. Wejdź na https://apify.com
2. Kliknij "Sign up" (możesz użyć GitHub/Google)
3. Wybierz plan:
   - **Free tier**: $5 kredytów/miesiąc (wystarczy na ~1000 postów)
   - **Starter**: $49/miesiąc (jeśli potrzebujesz więcej)

---

## Krok 2: Pobranie API Token

1. Zaloguj się do Apify
2. Przejdź do: https://console.apify.com/account/integrations
3. Sekcja "Personal API tokens"
4. Skopiuj swój token (format: `apify_api_***************`)

---

## Krok 3: Konfiguracja w projekcie

### 3.1 Dodaj do `.env`

```bash
cd backend
nano .env  # lub vim .env
```

Dodaj linię:
```
APIFY_API_KEY=apify_api_twój_token_tutaj
```

### 3.2 Aktywuj źródła Facebook w bazie

**Opcja A: Automatyczna (zalecana)**

Uruchom ponownie script:
```bash
python scripts/add_facebook_sources.py
```

Script wykryje `APIFY_API_KEY` w `.env` i automatycznie:
- Zaktualizuje wszystkie źródła FB
- Ustawi `status='active'`
- Doda API key do `scraping_config`

**Opcja B: Ręczna (przez SQL)**

```sql
-- Aktywuj źródło Syla
UPDATE sources
SET
    status = 'active',
    scraping_config = jsonb_set(
        scraping_config,
        '{apify_api_key}',
        '"apify_api_twój_token"'
    )
WHERE name = 'Facebook - Syla';

-- Aktywuj wszystkie źródła Facebook
UPDATE sources
SET status = 'active'
WHERE type = 'social_media' AND name LIKE 'Facebook -%';
```

---

## Krok 4: Test scrapera

```bash
cd backend
python scripts/test_facebook_scraper.py
```

Oczekiwany output:
```
✓ Facebook - Syla: 20 postów scraped
✓ Kategorie: Urząd (5), Transport (3), Kultura (2), ...
✓ Saved to database
```

**Uwaga:** Pierwszy run może zająć 1-3 minuty (Apify musi uruchomić actor).

---

## Krok 5: Dodawanie kolejnych źródeł Facebook

Edytuj: `backend/scripts/add_facebook_sources.py`

```python
FACEBOOK_SOURCES = [
    {
        "name": "Facebook - Syla",
        "display_name": "Serwis Informacyjny Syla",
        "url": "https://www.facebook.com/serwis.informacyjny.syla",
        "description": "Lokalne wiadomości",
        "status": "inactive",
    },
    # Dodaj nowe źródło:
    {
        "name": "Facebook - Twoja Strona",
        "display_name": "Pełna nazwa strony",
        "url": "https://www.facebook.com/username",
        "description": "Opis strony",
        "status": "inactive",  # Zmieni się na 'active' jeśli APIFY_API_KEY w .env
    },
]
```

Uruchom ponownie:
```bash
python scripts/add_facebook_sources.py
```

---

## Konfiguracja Actora

### Domyślne ustawienia (w `scraping_config`):

```json
{
  "actor_id": "apify/facebook-posts-scraper",
  "results_limit": 20,
  "caption_text": false,
  "facebook_page_url": "https://www.facebook.com/...",
  "apify_api_key": "apify_api_***"
}
```

### Zmiana ustawień:

**Zwiększ liczbę postów:**
```sql
UPDATE sources
SET scraping_config = jsonb_set(scraping_config, '{results_limit}', '50')
WHERE name = 'Facebook - Syla';
```

**Włącz tekst z obrazków:**
```sql
UPDATE sources
SET scraping_config = jsonb_set(scraping_config, '{caption_text}', 'true')
WHERE name = 'Facebook - Syla';
```

---

## Koszty Apify

### Pricing (stan: styczeń 2026)

- **Free tier**: $5 kredytów/miesiąc
  - ~1000 postów FB miesięcznie
  - Wystarczy dla testów i małych projektów

- **Starter**: $49/miesiąc
  - $49 kredytów (~10 000 postów)
  - Dla 10 źródeł × 20 postów/dzień = ~6000 postów/mies

### Optymalizacja kosztów:

1. **results_limit**: Ustaw 10-20 zamiast 50 (mniej postów = niższy koszt)
2. **caption_text: false**: OCR tekstu z obrazków kosztuje więcej
3. **Scraping frequency**: Co 6h zamiast co 1h (w `scheduler.py`)
4. **Wybiórcze źródła**: Aktywuj tylko najważniejsze konta FB

---

## Monitoring

### Sprawdź zużycie kredytów Apify:

https://console.apify.com/billing/usage

### Logi w aplikacji:

```bash
# Backend logs
tail -f logs/article_scheduler.log

# Filtruj tylko Facebook
grep "Facebook" logs/article_scheduler.log
```

### Sprawdź ostatnio zscrapowane posty:

```sql
SELECT
    s.name,
    COUNT(*) as posts_count,
    MAX(a.scraped_at) as last_scraped
FROM articles a
JOIN sources s ON a.source_id = s.id
WHERE s.type = 'social_media'
GROUP BY s.name;
```

---

## Troubleshooting

### Problem: "Missing apify_api_key"

**Przyczyna:** API key nie jest w config źródła.

**Rozwiązanie:**
```bash
python scripts/add_facebook_sources.py
```
Lub dodaj ręcznie przez SQL (patrz Krok 3.2).

---

### Problem: "Actor run failed with status: FAILED"

**Przyczyny:**
1. Facebook zablokował Apify IP
2. Strona FB nie istnieje / jest prywatna
3. Przekroczono rate limit

**Rozwiązanie:**
1. Sprawdź URL strony FB (musi być publiczna)
2. Zmniejsz `results_limit` do 10
3. Poczekaj 1h i spróbuj ponownie
4. Sprawdź logi Apify: https://console.apify.com/actors/runs

---

### Problem: Wysokie koszty

**Rozwiązanie:**
```python
# backend/src/scheduler/scheduler.py

# Zmniejsz częstotliwość dla FB (było co 6h)
scheduler.add_job(
    run_article_job,
    'interval',
    hours=12,  # Facebook tylko 2x dziennie
    id='article_scraping'
)
```

Lub:
```sql
-- Dezaktywuj mniej ważne źródła
UPDATE sources
SET status = 'inactive'
WHERE name = 'Facebook - Mniej Ważne Konto';
```

---

## Przykładowe źródła Facebook dla Działdowa

Gotowe konta do dodania (edytuj `add_facebook_sources.py`):

```python
{
    "name": "Facebook - Starostwo Działdowo",
    "url": "https://www.facebook.com/starostwo.dzialdowo",
    "description": "Starostwo Powiatowe w Działdowie",
},
{
    "name": "Facebook - Biblioteka Działdowo",
    "url": "https://www.facebook.com/biblioteka.dzialdowo",
    "description": "Miejska Biblioteka Publiczna",
},
{
    "name": "Facebook - MDK Działdowo",
    "url": "https://www.facebook.com/mdk.dzialdowo",
    "description": "Miejski Dom Kultury",
},
{
    "name": "Facebook - Welham Działdowo",
    "url": "https://www.facebook.com/welham.dzialdowo",
    "description": "Klub sportowy Welham",
},
```

---

## Następne kroki

Po skonfigurowaniu Apify:

1. **Sprawdź czy działa:**
   ```bash
   python scripts/test_article_job.py
   ```

2. **Uruchom backend:**
   ```bash
   uvicorn src.api.main:app --reload
   ```

3. **Sprawdź API endpoint:**
   ```bash
   curl http://localhost:8000/api/articles?source_id=5
   ```

4. **Zintegruj z frontendem** (Next.js)

---

**Pytania? Problemy?**
- Apify Docs: https://docs.apify.com
- Facebook Posts Scraper: https://apify.com/apify/facebook-posts-scraper
- GitHub Issues: https://github.com/anthropics/claude-code/issues
