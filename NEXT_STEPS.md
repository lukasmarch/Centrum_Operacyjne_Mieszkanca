# Następne Kroki - Centrum Operacyjne Mieszkańca

**Ostatnia aktualizacja:** 2026-01-13
**Obecny stan:** FAZA 4A ukończona - RSS Feeds + AI Improvements ✅

---

## 🎯 PRIORYTETOWE OPCJE

### OPCJA A: Sprint 1 - Praca & Nieruchomości (Quick Win)
**Cel:** Zwiększyć % kategorii "Biznes" i "Nieruchomości" w Daily Summary

**Zadania:**
- [ ] PUP Działdowo Scraper (oferty pracy) - api/scraping
- [ ] OLX Praca Scraper (Działdowo + powiat)
- [ ] OLX Nieruchomości Scraper
- [ ] Otodom Scraper (opcjonalnie)
- [ ] Frontend: Job Widget + Real Estate Widget
- [ ] Test: Czy Daily Summary jest ciekawsze?

**Oczekiwany rezultat:**
- +20-30 artykułów dziennie kategorii "Biznes" i "Nieruchomości"
- Biznes: 6.9% → 15%+
- Nieruchomości: 1.7% → 5%+

**Czas:** 1-2 tygodnie
**Wartość dla użytkowników:** ⭐⭐⭐⭐⭐ (ludzie PŁACĄ za oferty pracy!)

---

### OPCJA B: Sprint 2 - Zdrowie & Transport
**Cel:** Dodać kategorie wysokiej wartości praktycznej

**Zadania:**
- [ ] NFZ Kolejki API (dostępne terminy do lekarzy)
- [ ] Apteka dyżurna (harmonogram + scraping)
- [ ] GIOŚ API (jakość powietrza PM2.5, PM10)
- [ ] PKP/PolRegio API (opóźnienia pociągów)
- [ ] e-petrol Scraper (ceny paliw)
- [ ] Frontend: Health Widget (rozszerzony)

**Oczekiwany rezultat:**
- +15-20 artykułów/update dziennie
- Zdrowie: 6.3% → 12%+
- Transport: 9.8% → 15%+

**Czas:** 1-2 tygodnie
**Wartość dla użytkowników:** ⭐⭐⭐⭐⭐ (praktyczne, codzienne potrzeby)

---

### OPCJA C: Sprint 3 - GUS Analytics (GAME CHANGER! B2B)
**Cel:** Stworzyć unikalny produkt B2B/Premium

**Zadania:**
- [ ] GUS API Integration (api.stat.gov.pl)
  - Demografia (ludność, wiek, przyrost naturalny)
  - Gospodarka (przedsiębiorstwa REGON, bezrobocie, wynagrodzenia)
  - Finanse (dochody/wydatki gminy, zadłużenie)
  - Infrastruktura (drogi, wodociągi, kanalizacja)
- [ ] Tabela `gus_statistics` + endpoint
- [ ] Frontend: GUS Dashboard (wykresy Recharts)
- [ ] Porównanie gmin (Rybno vs Działdowo vs Lidzbark)
- [ ] Export CSV/PDF (tylko Premium/Business)
- [ ] Marketing: Landing page dla B2B

**Oczekiwany rezultat:**
- Unikalny selling point (konkurencja tego nie ma!)
- Wartość dla przedsiębiorców (analiza rynku lokalnego)
- Wartość dla gmin (benchmarking)
- Potencjał B2B: 500-1500 PLN/mies per gmina

**Czas:** 2-3 tygodnie
**Wartość dla użytkowników:** ⭐⭐⭐⭐⭐ (B2B - wysokie marże!)

---

### OPCJA D: Sprint 4 - Więcej RSS Feeds
**Cel:** Szybko dodać więcej źródeł bez kosztów scraperów

**Zadania:**
- [ ] Fix Gazeta Olsztyńska encoding
- [ ] Dodać RSS-Bridge dla Facebooka (więcej kont)
- [ ] Szukać więcej lokalnych RSS feeds
- [ ] Google Alerts email parser (opcjonalnie)

**Oczekiwany rezultat:**
- +5-10 nowych źródeł RSS
- +50-100 artykułów dziennie
- 0 PLN kosztów (RSS jest darmowe)

**Czas:** 3-5 dni
**Wartość dla użytkowników:** ⭐⭐⭐ (więcej źródeł = lepsza pokrywa)

---

## 🚨 KRYTYCZNE POPRAWKI (Zrób przed następnym sprintem)

### 1. Fix `Article.locations` attribute error
**Problem:** `'Article' object has no attribute 'locations'`
**Rozwiązanie:**
```python
# backend/scripts/process_all_articles.py:
article.location_mentioned = result.locations  # ✓ POPRAWNE
# NIE: article.locations = result.locations
```

### 2. Fix Gazeta Olsztyńska RSS encoding
**Problem:** Feed nie parsuje się (encoding issue)
**Rozwiązanie:** Już użyto `response.content` zamiast `response.text` - do przetestowania

### 3. Napraw AI Event Extraction
**Problem:** 0 wydarzeń znalezionych w 89 artykułach
**Rozwiązanie:** Sprawdź `event_extractor.py` - może wymaga session parameter

---

## 📊 METRYKI SUKCESU (Cel dla kolejnych 2 tygodni)

**Daily Summary:**
- [ ] Min 5 kategorii w podsumowaniu (obecnie: 3)
- [ ] Min 10 artykułów z ostatnich 24h (obecnie: 8)
- [ ] Max 30% kategorii "Kultura" (obecnie: 38.5% - blisko!)
- [ ] Min 1 wydarzenie w highlights

**Artykuły:**
- [ ] Min 250 artykułów w bazie (obecnie: 174)
- [ ] Min 90% artykułów przetworzonych (obecnie: 100% ✓)
- [ ] Min 12 źródeł aktywnych (obecnie: 10)

**Kategorie (docelowy rozkład):**
- Kultura: 30% (obecnie: 38.5%)
- Urząd: 15% (obecnie: 16.1% ✓)
- Edukacja: 12% (obecnie: 14.9% ✓)
- **Biznes: 15%** (obecnie: 6.9%) ← PRIORYTET!
- Transport: 10% (obecnie: 9.8% ✓)
- **Zdrowie: 10%** (obecnie: 6.3%) ← PRIORYTET!
- Rekreacja: 5% (obecnie: 5.7% ✓)
- **Nieruchomości: 3%** (obecnie: 1.7%) ← PRIORYTET!

---

## 💡 REKOMENDACJA

**Polecam zacząć od:**
1. **OPCJA A (Sprint 1)** - Quick win, wysoka wartość dla użytkowników
2. **Potem OPCJA C (Sprint 3)** - Unikalny produkt B2B

**Dlaczego?**
- Sprint 1 doda konkretną wartość (oferty pracy = praktyka)
- Sprint 3 da unikalność (GUS Analytics = przewaga konkurencyjna)
- Razem = kompletny produkt Premium

**Alternatywnie:**
- Jeśli chcesz szybko - **OPCJA D** (RSS feeds w 3 dni)
- Jeśli chcesz B2B - od razu **OPCJA C** (GUS Analytics)

---

## 📁 Pliki do przeczytania przed rozpoczęciem:

- `DAILY_SUMMARY_COMPARISON.md` - analiza AI improvements
- `dzialowo-live-plan-biznesowy.md` - pełny business plan
- `PLAN_PROJEKTU.md` - techniczny roadmap
- `CLAUDE.md` - obecny status projektu

**Ready to start?** 🚀
