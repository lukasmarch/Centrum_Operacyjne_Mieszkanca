#!/usr/bin/env python3
"""
Ręczny trigger pełnego pipeline — symuluje wszystkie joby schedulera w kolejności produkcyjnej.

Scheduler Timeline (produkcja, Europe/Warsaw):
    Interval  → Weather Update        (co 1h)
    Interval  → Air Quality (Airly)   (co 4h)
    Cron      → Traffic Cache         (2,6,10,14,18,22:00)
    06:00     → Article Scraping      (daily pipeline: krok 1)
    06:15     → AI Processing         (daily pipeline: krok 2)
    06:50     → Embedding Job         (RAG)
    07:00     → Daily Summary         (daily pipeline: krok 3)
    07:15     → Newsletter Daily      (pon-pt, po summary)
    08:00     → Cinema Repertoire     (daily)
    Poniedziałek → Health Job         (harmonogramy SPGZOZ + dyżury aptek)
    Niedziela → CEIDG Business Sync   (weekly)
    Kwartalny → GUS Statistics        (quarterly)

UWAGA:
    - Newsletter, GUS i CEIDG są POMINIĘTE (kosztowne / rzadkie)
    - Traffic job wymaga skonfigurowanego GOOGLE_API_KEY
    - Air Quality wymaga skonfigurowanego AIRLY_API_KEY
    - Health job cotygodniowy — domyślnie włączony, użyj --skip-health by pominąć

Uruchomienie (na serwerze):
    docker exec centrum-backend-1 python scripts/production/run_pipeline.py
    docker exec centrum-backend-1 python scripts/production/run_pipeline.py --articles-only
    docker exec centrum-backend-1 python scripts/production/run_pipeline.py --skip-traffic --skip-airly --skip-health
"""
import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime

backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from src.scheduler.weather_job import update_weather_job
from src.scheduler.air_quality_job import update_air_quality
from src.scheduler.traffic_job import run_traffic_job_async
from src.scheduler.article_job import update_articles_job
from src.scheduler.ai_jobs import run_ai_processing
from src.scheduler.embedding_job import run_embedding_job_async
from src.scheduler.summary_job import run_daily_summary
from src.scheduler.cinema_job import run_cinema_job_async
from src.scheduler.health_job import run_health_job_async
from src.utils.logger import setup_logger

logger = setup_logger("RunPipeline")


def parse_args():
    parser = argparse.ArgumentParser(description="Ręczny trigger pełnego pipeline")
    parser.add_argument("--skip-traffic", action="store_true", help="Pomiń Traffic Cache (Gemini API)")
    parser.add_argument("--skip-airly", action="store_true", help="Pomiń Air Quality (Airly API)")
    parser.add_argument("--skip-weather", action="store_true", help="Pomiń Weather Update")
    parser.add_argument("--skip-cinema", action="store_true", help="Pomiń Cinema Repertoire")
    parser.add_argument("--skip-health", action="store_true", help="Pomiń Health Job (cotygodniowy)")
    parser.add_argument("--articles-only", action="store_true", help="Tylko daily pipeline: artykuły+AI+embedding+summary")
    return parser.parse_args()


async def run_step(step_num: int, total: int, name: str, coro, skip: bool = False):
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
    logger.info("RĘCZNY TRIGGER — PEŁNY PIPELINE")
    logger.info(f"Start: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    results = {}

    if args.articles_only:
        logger.info("Tryb: --articles-only")
        steps = [
            ("Scraping artykułów",              update_articles_job(),     False),
            ("AI Processing (batch=100)",        run_ai_processing(),       False),
            ("Embedding Job (RAG)",              run_embedding_job_async(), False),
            ("Generowanie daily summary",        run_daily_summary(),       False),
        ]
    else:
        steps = [
            ("Weather Update",                   update_weather_job(),      args.skip_weather),
            ("Air Quality / Airly",              update_air_quality(),      args.skip_airly),
            ("Traffic Cache / Gemini",           run_traffic_job_async(),   args.skip_traffic),
            ("Scraping artykułów",               update_articles_job(),     False),
            ("AI Processing (batch=100)",        run_ai_processing(),       False),
            ("Embedding Job (RAG)",              run_embedding_job_async(), False),
            ("Generowanie daily summary",        run_daily_summary(),       False),
            ("Cinema Repertoire",                run_cinema_job_async(),    args.skip_cinema),
            ("Health Job (SPGZOZ + apteki)",     run_health_job_async(),    args.skip_health),
        ]

    total = len(steps)
    for i, (name, coro, skip) in enumerate(steps, 1):
        results[name] = await run_step(i, total, name, coro, skip)

    elapsed = (datetime.now() - start).total_seconds()
    ok = sum(1 for v in results.values() if v is True)
    failed = len(results) - ok

    logger.info("=" * 60)
    logger.info(f"PIPELINE GOTOWY — czas: {elapsed:.1f}s")
    logger.info(f"Wyniki: {ok} ok / {failed} błędów")
    logger.info("=" * 60)
    for name, result in results.items():
        logger.info(f"  {'✓' if result else '✗'} {name}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPrzerwane przez użytkownika")
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
