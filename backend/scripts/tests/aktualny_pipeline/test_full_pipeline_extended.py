#!/usr/bin/env python3
"""
Ręczny trigger pełnego pipeline — symuluje wszystkie joby schedulera w kolejności produkcyjnej.

Scheduler Timeline (produkcja):
    Interval  → Weather Update        (co 1h)
    Interval  → Air Quality (Airly)   (co 4h)
    Cron      → Traffic Cache         (2,6,10,14,18,22:00)
    06:00     → Article Scraping      (daily pipeline: krok 1)
    06:15     → AI Processing         (daily pipeline: krok 2)
    07:00     → Daily Summary         (daily pipeline: krok 3)
    07:15     → Newsletter Daily      (pon-pt, po summary)
    08:00     → Cinema Repertoire     (daily)
    Niedziela → CEIDG Business Sync   (weekly)
    Kwartalny → GUS Statistics        (quarterly)

UWAGA:
    - Newsletter, GUS i CEIDG są POMINIĘTE w tym teście (kosztowne / rzadkie)
    - Traffic job wymaga skonfigurowanego Gemini API (GOOGLE_API_KEY)
    - Air Quality wymaga skonfigurowanego AIRLY_API_KEY
    - Joby które mogą być skip'owane (brak API key) są oznaczone ⚠️

Uruchomienie:
    cd backend
    python scripts/tests/aktualny_pipeline/test_full_pipeline_extended.py

    # Pomiń konkretne joby:
    python scripts/tests/aktualny_pipeline/test_full_pipeline_extended.py --skip-traffic --skip-airly
"""
import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime

backend_path = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_path))

from src.scheduler.weather_job import update_weather_job
from src.scheduler.air_quality_job import update_air_quality
from src.scheduler.traffic_job import run_traffic_job_async
from src.scheduler.article_job import update_articles_job
from src.scheduler.ai_jobs import run_ai_processing
from src.scheduler.summary_job import run_daily_summary
from src.scheduler.cinema_job import run_cinema_job_async
from src.utils.logger import setup_logger

logger = setup_logger("FullPipelineExtended")


def parse_args():
    parser = argparse.ArgumentParser(description="Ręczny trigger pełnego pipeline")
    parser.add_argument("--skip-traffic", action="store_true", help="Pomiń Traffic Cache (Gemini API)")
    parser.add_argument("--skip-airly", action="store_true", help="Pomiń Air Quality (Airly API)")
    parser.add_argument("--skip-weather", action="store_true", help="Pomiń Weather Update")
    parser.add_argument("--skip-cinema", action="store_true", help="Pomiń Cinema Repertoire")
    parser.add_argument("--articles-only", action="store_true", help="Uruchom tylko daily pipeline (artykuły+AI+summary)")
    return parser.parse_args()


async def run_step(step_num: int, total: int, name: str, coro, skip: bool = False):
    """Uruchamia pojedynczy krok pipeline z logowaniem."""
    header = f"[{step_num}/{total}] {name}"

    if skip:
        logger.info(f"\n{'─' * 60}")
        logger.info(f"{header} — POMINIĘTY")
        logger.info(f"{'─' * 60}")
        return True

    logger.info(f"\n{'─' * 60}")
    logger.info(header)
    logger.info(f"{'─' * 60}")

    step_start = datetime.now()
    try:
        await coro
        elapsed = (datetime.now() - step_start).total_seconds()
        logger.info(f"✓ {name} — zakończony ({elapsed:.1f}s)\n")
        return True
    except Exception as e:
        elapsed = (datetime.now() - step_start).total_seconds()
        logger.error(f"✗ {name} — BŁĄD po {elapsed:.1f}s: {e}", exc_info=True)
        return False


async def main():
    args = parse_args()
    start = datetime.now()

    logger.info("=" * 60)
    logger.info("RĘCZNY TRIGGER — PEŁNY PIPELINE (EXTENDED)")
    logger.info(f"Start: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    results = {}

    if args.articles_only:
        # Tryb: tylko daily pipeline
        logger.info("Tryb: --articles-only (pomijam weather/airly/traffic/cinema)")
        steps = [
            ("Scraping artykułów",         update_articles_job(),   False),
            ("AI Processing (batch=100)",  run_ai_processing(),     False),
            ("Generowanie daily summary",  run_daily_summary(),     False),
        ]
        total = len(steps)
        for i, (name, coro, skip) in enumerate(steps, 1):
            results[name] = await run_step(i, total, name, coro, skip)
    else:
        # Pełny pipeline — kolejność jak w schedularze
        steps = [
            # (nazwa, korutyna, czy_pominąć)
            ("Weather Update",             update_weather_job(),    args.skip_weather),
            ("Air Quality / Airly",        update_air_quality(),    args.skip_airly),
            ("Traffic Cache / Gemini",     run_traffic_job_async(), args.skip_traffic),
            ("Scraping artykułów",         update_articles_job(),   False),
            ("AI Processing (batch=100)",  run_ai_processing(),     False),
            ("Generowanie daily summary",  run_daily_summary(),     False),
            ("Cinema Repertoire",          run_cinema_job_async(),  args.skip_cinema),
        ]
        total = len(steps)
        for i, (name, coro, skip) in enumerate(steps, 1):
            results[name] = await run_step(i, total, name, coro, skip)

    # --- Podsumowanie ---
    elapsed = (datetime.now() - start).total_seconds()
    ok = sum(1 for v in results.values() if v is True)
    skipped = sum(1 for v in results.values() if v is None or "POMINIĘTY" in str(v))
    failed = len(results) - ok

    logger.info("=" * 60)
    logger.info(f"PIPELINE GOTOWY — czas: {elapsed:.1f}s")
    logger.info(f"Wyniki: {ok} ok / {failed} błędów")
    logger.info("=" * 60)

    for name, result in results.items():
        status = "✓" if result else "✗"
        logger.info(f"  {status} {name}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nPrzerwane przez użytkownika")
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
