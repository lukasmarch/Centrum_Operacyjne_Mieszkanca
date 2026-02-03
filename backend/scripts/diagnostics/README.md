# Diagnostic Scripts

Skrypty diagnostyczne do sprawdzania stanu schedulera i danych.

## Skrypty

### check_scheduler_health.py
Sprawdza status schedulera i listę zarejestrowanych jobów.

**Użycie:**
```bash
cd backend
python scripts/diagnostics/check_scheduler_health.py
```

**Co sprawdza:**
- Czy scheduler jest uruchomiony
- Lista wszystkich jobów (ID, nazwa, trigger, next run time)
- Liczba zarejestrowanych jobów

---

### check_articles_for_summary.py
Analizuje artykuły w bazie pod kątem generowania daily summary.

**Użycie:**
```bash
cd backend
python scripts/diagnostics/check_articles_for_summary.py
```

**Co sprawdza:**
- Całkowita liczba artykułów
- Ile artykułów jest przetworzonych (processed=True)
- Artykuły z wczoraj (gotowe do summary?)
- Artykuły z dzisiaj
- Ostatnie 5 artykułów (sample)

**Przykładowy output:**
```
ARTICLES DIAGNOSTICS FOR DAILY SUMMARY
======================================================================

Total articles in database: 174

PROCESSING STATUS:
  ✓ Processed (categorized): 168
  ⚠ Unprocessed: 6

YESTERDAY'S ARTICLES (2026-01-20):
  Total: 12
  Processed: 12
  Unprocessed: 0

✓ READY FOR SUMMARY: Yes, processed articles from yesterday exist
```

---

## Debugging Daily Summary

Jeśli daily summary zwraca None, uruchom te skrypty:

1. **Sprawdź scheduler:**
   ```bash
   python scripts/diagnostics/check_scheduler_health.py
   ```
   - Czy job 'daily_summary' jest zarejestrowany?
   - Kiedy ma się następne uruchomienie?

2. **Sprawdź artykuły:**
   ```bash
   python scripts/diagnostics/check_articles_for_summary.py
   ```
   - Czy są artykuły z wczoraj?
   - Czy są przetworzone (processed=True)?

3. **Sprawdź logi:**
   ```bash
   tail -f logs/scheduler.log | grep "SummaryScheduler"
   ```
   - Czy job się uruchomił?
   - Jaki jest powód None?

4. **Sprawdź bazę danych:**
   ```sql
   -- Sprawdź istniejące summaries
   SELECT date, headline, generated_at FROM daily_summaries ORDER BY date DESC LIMIT 5;

   -- Sprawdź artykuły z wczoraj
   SELECT COUNT(*), processed FROM articles
   WHERE published_at >= CURRENT_DATE - INTERVAL '1 day'
   AND published_at < CURRENT_DATE
   GROUP BY processed;
   ```

---

## Timeline Schedulera (po naprawie)

```
6:00 AM → Article Scraping (article_update)
6:15 AM → AI Processing (ai_processing) - kategoryzacja artykułów
6:45 AM → Daily Summary (daily_summary) - generuje summary dla wczoraj

Co 1h → Weather Update (weather_update)
```

**Klucz:** Summary uruchamia się **po** AI processing, więc artykuły są gotowe (processed=True).
