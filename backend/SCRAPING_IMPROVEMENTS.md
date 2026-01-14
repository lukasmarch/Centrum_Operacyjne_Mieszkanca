# Ulepszenia Scrapowania - 2026-01-14

## 🎯 Rozwiązane Problemy

### 1. RSS Scrapery nie działały ❌ → ✅
**Problem:** RSS scrapery (Radio 7, Gazeta Olsztyńska) rzucały błąd:
```
RSS scraper uses feedparser, not HTML parsing
```

**Przyczyna:** `article_job.py` wywoływał standardowe `fetch()` + `parse()`, ale RSS używa `scrape_feed()` z feedparser.

**Rozwiązanie:** Dodano wykrywanie typu scrapera w `article_job.py`:
```python
if isinstance(scraper, RSSFeedScraper):
    articles = await scraper.scrape_feed(scrape_url)
else:
    html = await scraper.fetch(scrape_url)
    articles = await scraper.parse(html, scrape_url)
```

---

### 2. Stare artykuły (sprzed miesięcy/lat) ❌ → ✅
**Problem:** Skrapowanie pobierało wszystkie artykuły z archiwum stron (setki starych artykułów).

**Rozwiązanie:** Dodano filtrowanie po dacie publikacji:
```python
def filter_recent_articles(articles: list, days: int = 30) -> list:
    """Zwraca tylko artykuły z ostatnich 30 dni"""
```

**Parametr:** `days=30` (można zmienić w `article_job.py` linia 99)

---

### 3. Duplikaty Event ❌ → ✅
**Problem:** Brak zabezpieczenia przed duplikatami wydarzeń w bazie.

**Rozwiązanie:**
1. **Schema.py** - dodano unique constraint:
   ```python
   __table_args__ = (
       Index('idx_event_unique', 'title', 'event_date', 'location', unique=True),
   )
   ```

2. **event_extractor.py** - zaktualizowano check duplikatów:
   ```python
   # Sprawdza: title + event_date + location
   ```

**Zabezpieczenia Article (już były):**
- `url` - unique ✅
- `external_id` - unique ✅

**Zabezpieczenia DailySummary (już były):**
- `date` - unique ✅

---

## 📊 Nowy Harmonogram Schedulera

**Zmieniono w:** `/backend/src/scheduler/scheduler.py`

| Job | Poprzednio | Teraz | Częstotliwość |
|-----|-----------|-------|---------------|
| Weather update | Co 15 min | Co 1h | 24× dziennie |
| Article scraping | Co 6h | 6:00 + 12:00 | 2× dziennie |
| AI processing | Co 30 min | Co 1h | 24× dziennie |
| Daily summary | 6:00 | 6:30 + 12:30 | 2× dziennie |

**Uzasadnienie:**
- **Scraping 2× dziennie** = oszczędność $20/miesiąc na Apify (180 zamiast 360 wywołań)
- **Summary 30 min po scraping** = daje czas na AI processing przed generowaniem
- **Weather co 1h** = oszczędność API calls, 1h jest wystarczające dla pogody

---

## 🚀 Jak zastosować zmiany

### Krok 1: Usuń duplikaty (jeśli istnieją)
```bash
cd backend
python scripts/remove_duplicate_events.py
```

### Krok 2: Dodaj unique constraint do bazy
```bash
python scripts/add_event_unique_constraint.py
```

### Krok 3: Restart serwera
```bash
# Zatrzymaj serwer (Ctrl+C)
# Uruchom ponownie:
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Krok 4: Test scrapowania
```bash
# W nowym terminalu:
python scripts/test_article_job.py
```

**Oczekiwany wynik:**
- ✅ RSS scrapery działają (Radio 7, Gazeta Olsztyńska)
- ✅ Tylko świeże artykuły (ostatnie 30 dni)
- ✅ Brak duplikatów wydarzeń

---

## 📝 Zmienione pliki

### Backend Core:
- `src/scheduler/scheduler.py` - nowy harmonogram (2× dziennie)
- `src/scheduler/article_job.py` - obsługa RSS + filtrowanie dat
- `src/database/schema.py` - unique constraint dla Event
- `src/ai/event_extractor.py` - check duplikatów (title+date+location)

### Nowe skrypty:
- `scripts/add_event_unique_constraint.py` - migracja bazy
- `scripts/remove_duplicate_events.py` - cleanup duplikatów

### Dokumentacja:
- `SCRAPING_IMPROVEMENTS.md` - ten dokument

---

## 💰 Oszczędności kosztów

### Apify Facebook Scraping:
- **Poprzednio:** 4× dziennie = 360 wywołań/miesiąc ≈ $40/miesiąc
- **Teraz:** 2× dziennie = 180 wywołań/miesiąc ≈ **$20/miesiąc**
- **Oszczędność:** $20/miesiąc (50%)

### OpenWeatherMap:
- **Poprzednio:** Co 15 min = 2880 wywołań/miesiąc
- **Teraz:** Co 1h = 720 wywołań/miesiąc
- **W granicach free tier:** 1000 wywołań/dzień = FREE ✅

---

## 🔧 Parametry do dostosowania

### Filtrowanie po dacie (`article_job.py` linia 99):
```python
articles = filter_recent_articles(articles, days=30)  # ← Zmień 30 na inną wartość
```

**Przykłady:**
- `days=7` - tylko ostatni tydzień
- `days=60` - ostatnie 2 miesiące
- `days=90` - ostatni kwartał

### Harmonogram (`scheduler.py`):
```python
# Scraping 3× dziennie (6:00, 12:00, 18:00)
trigger=CronTrigger(hour='6,12,18', minute=0)

# AI co 2 godziny
trigger=IntervalTrigger(hours=2)

# Summary tylko raz dziennie (18:00)
trigger=CronTrigger(hour=18, minute=0)
```

---

## ✅ Checklist wdrożenia

- [ ] Uruchomiono `remove_duplicate_events.py`
- [ ] Uruchomiono `add_event_unique_constraint.py`
- [ ] Zrestartowano serwer backend
- [ ] Przetestowano `test_article_job.py`
- [ ] Sprawdzono logi schedulera (RSS działa?)
- [ ] Zweryfikowano że tylko świeże artykuły są zapisywane
- [ ] Sprawdzono że duplikaty event są blokowane

---

## 📞 Wsparcie

Jeśli masz problemy z migracją:

1. **Duplikaty blokują dodanie constraint:**
   ```bash
   python scripts/remove_duplicate_events.py
   ```

2. **RSS nadal nie działa:**
   - Sprawdź logi serwera
   - Upewnij się że `feedparser>=6.0.10` jest zainstalowany
   - Sprawdź czy źródła RSS mają `type="rss"` w bazie

3. **Za dużo/za mało artykułów:**
   - Dostosuj `days=30` w `article_job.py`
   - Zmień harmonogram w `scheduler.py`

---

**Ostatnia aktualizacja:** 2026-01-14
**Status:** ✅ Gotowe do wdrożenia
