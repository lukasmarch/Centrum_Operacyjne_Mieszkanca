# Harmonogram Jobów Schedulera

> Serwer działa lokalnie (macOS) — gdy laptop śpi, joby NIE są wykonywane.
> Na produkcji (Linux/Docker) problem nie wystąpi.

---

## Joby codzienne (CRON)

| Godzina | Job ID            | Opis                                      | Plik                     |
|---------|-------------------|-------------------------------------------|--------------------------|
| 06:00   | `article_update`  | Scrapowanie nowych artykułów              | scheduler/article_job.py |
| 06:15   | `ai_processing`   | Kategoryzacja artykułów (batch=100, ~32min) | scheduler/ai_jobs.py   |
| 07:00   | `daily_summary`   | Generowanie podsumowania AI (za wczoraj)  | scheduler/summary_job.py |
| 07:15   | `newsletter_daily`| Wysyłka newslettera Premium (Pn–Pt)       | scheduler/newsletter_job.py |
| 08:00   | `cinema_update`   | Repertuar kin (Działdowo, Lubawa)         | scheduler/cinema_job.py  |

## Pipeline dzienny (kolejność krytyczna)

```
06:00  → Scraping artykułów
06:15  → AI kategoryzacja (~32 min)
07:00  → Daily summary (wymaga skategoryzowanych artykułów)
07:15  → Newsletter (wymaga summary)
08:00  → Kino
```

---

## Joby cykliczne (INTERVAL)

| Interval | Job ID              | Opis                            | Plik                        |
|----------|---------------------|---------------------------------|-----------------------------|
| co 1h    | `weather_update`    | Pogoda (Rybno, Działdowo)       | scheduler/weather_job.py    |
| co 4h    | `air_quality_update`| Jakość powietrza Airly (Rybno)  | scheduler/air_quality_job.py|

> **Uwaga:** Joby interwałowe startują od momentu uruchomienia serwera.
> Jeśli serwer startuje o 09:02, weather bije co godzinę od 09:02 (09:02, 10:02, 11:02...).

---

## Joby cykliczne (CRON — stałe godziny)

| Godziny           | Job ID           | Opis                            | Plik                      |
|-------------------|------------------|---------------------------------|---------------------------|
| 02,06,10,14,18,22 | `traffic_update` | Cache danych drogowych (Gemini) | scheduler/traffic_job.py  |

---

## Joby tygodniowe / miesięczne

| Kiedy              | Job ID             | Opis                            |
|--------------------|--------------------|---------------------------------|
| Sobota 10:00       | `newsletter_weekly`| Newsletter tygodniowy           |
| Niedziela 03:00    | `ceidg_sync`       | Synchronizacja CEIDG            |
| 1 dzień (Sty/Kwi/Lip/Paź) 04:00 | `gus_update` | Statystyki GUS (kwartalnie) |

---

## Znane problemy

| Job               | Problem                                      | Status    |
|-------------------|----------------------------------------------|-----------|
| `air_quality_update` | `async def` bez wrappera → nigdy nie wykonywał się | **NAPRAWIONY** |
| `traffic_update`  | Event loop mismatch (shared asyncpg engine)  | **NAPRAWIONY** |
| Wszystkie joby    | macOS sleep → missed runs                    | Dev only  |

---

## Ręczne uruchomienie jobów

```bash
cd backend
source ../.venv/bin/activate

# Cinema (jeśli minął o 8:00)
python -c "from src.scheduler.cinema_job import run_cinema_job; run_cinema_job()"

# Airly
python -c "from src.scheduler.air_quality_job import run_air_quality_job; run_air_quality_job()"

# Pogoda
python -c "from src.scheduler.weather_job import run_weather_job; run_weather_job()"
```

---

*Ostatnia aktualizacja: 2026-02-19*
