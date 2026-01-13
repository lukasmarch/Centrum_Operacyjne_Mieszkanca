# PROJEKT: "Centrum Operacyjne Mieszkańca" - Działdowo Live

## 1. POZYCJONOWANIE PROJEKTU

**Obszar**: Powiat Działdowski (60k mieszkańców), start: Gmina Rybno (2.5k)

**Unikalna Wartość**:
- ❌ NIE jesteśmy kolejnym portalem informacyjnym
- ✅ Inteligentny agregator + analiza AI + dane publiczne (GUS, IMGW)
- ✅ Krótkie, przydatne wiadomości z 10+ źródeł
- ✅ Monitoring real-time: ruch, pogoda, jeziora

**Grupa docelowa**: Mieszkańcy powiatu, turyści, przedsiębiorcy, samorząd

---

## 2. ŹRÓDŁA DANYCH

### Media Lokalne
1. **Klikaj.info** (klikajinfo.pl) - scraping co 1h
2. **Moje Działdowo** (mojedzialdowo.pl) - scraping co 1h
3. **Syla** (facebook.com/serwis.informacyjny.syla) - Facebook Graph API co 30min

### Urzędy
4. **Gmina Rybno** (gminarybno.pl) - BIP scraping co 2h
5. **Miasto Działdowo** (dzialdowo.pl) - BIP scraping co 2h
6. **Powiat Działdowski** (powiatdzialdowo.pl) - BIP scraping co 2h

### APIs
7. **Pogoda** - OpenWeather API co 15min
8. **Jeziora** - IMGW (temperatura wody, poziom) co 6h
9. **Ruch drogowy** - Google Maps API co 15min (rush) / 1h (off-peak)
10. **GUS** - api.stat.gov.pl (ludność, budżety, bezrobocie) co 24h

---

## 3. ARCHITEKTURA SYSTEMU

```
DATA SOURCES → SCRAPERS (Celery) → AI PROCESSING (Pydantic AI)
→ PostgreSQL+PostGIS → FastAPI → Next.js Frontend
```

**Pipeline AI**:
- Kategoryzacja artykułów (GPT-4o-mini)
- Ekstrakcja wydarzeń (GPT-4o)
- Deduplikacja (similarity detection)
- Generowanie podsumowań dziennych (GPT-4o)

---

## 4. STACK TECHNOLOGICZNY

### Backend
- Python 3.13 + FastAPI
- PostgreSQL 16 + PostGIS
- SQLModel (ORM) + Pydantic v2
- Celery + Redis (task queue)
- Pydantic AI (structured LLM outputs)
- BeautifulSoup4, httpx, playwright (scraping)

### Frontend
- Next.js 14 (App Router)
- Tailwind CSS + shadcn/ui
- Leaflet/Mapbox (mapy)
- Recharts (wykresy GUS)

### Infrastructure
- Backend: Render (Docker)
- Frontend: Hostinger lub Vercel
- Database: Render PostgreSQL
- Redis: Upstash (free tier)
- CDN: Cloudflare

---

## 5. SCHEMAT BAZY DANYCH (Główne Tabele)

```sql
sources           - źródła danych
articles          - surowe artykuły + AI kategorie
events            - wydarzenia ekstrahowane
weather           - pogoda (aktualna + prognoza)
lakes_data        - jeziora (temperatura, poziom)
traffic           - ruch drogowy
gus_statistics    - dane GUS per gmina
users             - użytkownicy
subscriptions     - subskrypcje premium
newsletters       - wysłane newslettery
advertisements    - reklamy
analytics         - statystyki
```

---

## 6. FRONTEND - Główne Sekcje

```
/ (główna)
  ├── Podsumowanie AI (dzisiaj)
  ├── Pogoda + temperatura jezior
  ├── Status ruchu
  ├── Najważniejsze wiadomości (3-5)
  ├── Nadchodzące wydarzenia
  └── Newsletter CTA

/wydarzenia       - kalendarz + mapa + filtry
/pogoda          - prognoza + jeziora + alerty
/ruch-drogowy    - mapa tras + czasy przejazdu
/statystyki      - dashboard GUS + wykresy
/o-nas           - o projekcie
/premium         - zaawansowane funkcje
```

---

## 7. MONETYZACJA

### Strumienie Przychodów

**1. Reklamy Lokalne**
- Banner top: 1000 PLN/mies
- Sidebar: 500 PLN/mies
- Sponsored content: 800 PLN/artykuł
- Wydarzenie wyróżnione: 200 PLN/tydzień

**2. Subskrypcje**
- **Free**: wszystkie artykuły, newsletter 1x/tydzień, reklamy
- **Premium** (19 PLN/mies): newsletter codzienny, alerty SMS, brak reklam, statystyki zaawansowane
- **Business** (99 PLN/mies): API access, custom reports, dane historyczne

**3. Sponsored Newsletters**: 500 PLN/wysyłka

### Projekcja Przychodów (rok 1, realistyczna)
```
Reklamy display:        1500 PLN/mies × 12 = 18 000 PLN
Subskrypcje Premium:    4000 PLN/mies × 12 = 48 000 PLN
Subskrypcje Business:   3000 PLN/mies × 12 = 36 000 PLN
Sponsored content:      1000 PLN/mies × 12 = 12 000 PLN
Newsletter sponsoring:   800 PLN/mies × 12 =  9 600 PLN
───────────────────────────────────────────────────
RAZEM ROK 1:                            123 600 PLN
```

---

## 8. KOSZTY OPERACYJNE

### Miesięcznie
```
Render (backend + DB):       100 PLN
Hostinger (frontend):         15 PLN
OpenAI API:                  200 PLN
Google Maps API:             100 PLN
Email delivery:               50 PLN
SMS gateway (premium):       100 PLN
Analytics:                    45 PLN
Domena:                        4 PLN
────────────────────────────────────
RAZEM:                       515 PLN/mies (~6200 PLN/rok)
```

**Breakeven**: 30-40 subskrybentów premium

---

## 9. ROADMAP IMPLEMENTACJI (18 tygodni)

### FAZA 0: Przygotowanie (Tydzień 1)
- Setup środowiska (Python, PostgreSQL, Redis)
- Rejestracja API keys
- Docker Compose
- Decyzje (nazwa domeny, logo)

### FAZA 1: MVP Backend (Tygodnie 2-4)
**Tydzień 2**: Database + FastAPI skeleton
**Tydzień 3**: Scrapers (Klikaj, Moje Działdowo, BIP Rybno)
**Tydzień 4**: AI Processing (kategoryzacja, ekstrakcja wydarzeń)

### FAZA 2: MVP Frontend (Tygodnie 5-6)
**Tydzień 5**: Next.js + główna strona + artykuły
**Tydzień 6**: Strona wydarzeń + kalendarz + mapa

### FAZA 3: Więcej Źródeł (Tydzień 7)
- Facebook API (Syla)
- OpenWeather API
- Widget pogody

### FAZA 4: Deployment Beta (Tydzień 8)
- Docker + Render deploy
- Frontend deploy
- Soft launch (50-100 osób)

### FAZA 5: Newsletter (Tydzień 9-10)
- Mailgun/SendGrid integration
- AI generator newslettera
- Automatyczna wysyłka (piątki 17:00)

### FAZA 6: Dane GUS (Tydzień 11-12)
- GUS API integration
- Dashboard statystyk + wykresy
- Export CSV/PDF

### FAZA 7: Jeziora & Ruch (Tydzień 13-14)
- IMGW API (temperatura wody, poziomy)
- Google Maps (ruch drogowy)
- Strony dedykowane

### FAZA 8: Premium (Tydzień 15-16)
- System użytkowników (auth)
- Płatności (Stripe/Przelewy24)
- Gated content

### FAZA 9: Reklamy (Tydzień 17)
- System banerów
- Tracking impressions/clicks
- Admin panel

### FAZA 10: Optymalizacja (Tydzień 18+)
- Caching (Redis)
- SEO (sitemap, schema.org)
- Performance tuning

---

## 10. METRYKI SUKCESU (KPIs)

### Miesiąc 1-3 (Beta)
- 500+ użytkowników/mies
- 100+ subskrybentów newslettera
- 5000+ wyświetleń/mies
- 50+ artykułów/dzień

### Miesiąc 4-6
- 2000+ użytkowników/mies
- 500+ subskrybentów newslettera
- 20 000+ wyświetleń/mies
- 10+ subskrybentów premium

### Miesiąc 7-12
- 5000+ użytkowników/mies
- 1500+ subskrybentów newslettera
- 50+ subskrybentów premium
- 10+ aktywnych reklamodawców
- **Breakeven** (przychody > koszty)

---

## 11. RYZYKA & MITIGATION

**Ryzyko 1: Brak zainteresowania**
→ Marketing lokalny (Facebook groups), współpraca z influencerami

**Ryzyko 2: Problemy prawne (scraping)**
→ Robots.txt, rate limiting, linki do źródeł, kontakt z portalami

**Ryzyko 3: Koszty AI**
→ GPT-4o-mini, caching, batch processing, rozważyć Llama 3.1

**Ryzyko 4: Konkurencja**
→ Unikalna wartość (agregacja+AI+GUS), lepsze UX, community

---

## 12. NASTĘPNE KROKI

### Rekomendacja: Zacznij od Pierwszego Modułu

**Cel**: Działający prototyp end-to-end

```
Klikajinfo.pl Scraper → AI Kategoryzacja → PostgreSQL → FastAPI Endpoint
```

**Deliverables**:
1. Scraper pobierający artykuły z Klikaj.info
2. Pydantic AI kategoryzujący treści
3. Zapisywanie do PostgreSQL
4. Celery task (automatyzacja co 1h)
5. FastAPI endpoint zwracający artykuły

**Następnie**: Powielenie dla innych źródeł + dodanie frontendu

---

**Autor**: Claude Sonnet 4.5
**Data utworzenia**: 2026-01-07
**Status**: Plan koncepcyjny - gotowy do implementacji
