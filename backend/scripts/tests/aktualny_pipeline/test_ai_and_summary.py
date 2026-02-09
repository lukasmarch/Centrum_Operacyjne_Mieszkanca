#!/usr/bin/env python3
"""
Ręczny trigger AI processing + summary (BEZ scrapowania)

Użyj gdy:
- Masz już artykuły w bazie (po scrapowaniu)
- Chcesz tylko przetworzyć je przez AI + wygenerować summary
- Testujesz bez uruchamiania aktorów Apify

Kolejność:
    1. Kategoryzacja artykułów przez AI        (ai_jobs — ArticleProcessor)
    2. Ekstrakcja wydarzeń z artykułów         (ai_jobs — EventExtractor)
    3. Generowanie dziennego podsumowania      (summary_job)

Wszystko zapisuje się do bazy danych.

Uruchomienie:
    cd backend
    python scripts/tests/aktualny_pipeline/test_ai_and_summary.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

backend_path = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_path))

from src.scheduler.ai_jobs import run_ai_processing
from src.scheduler.summary_job import run_daily_summary
from src.utils.logger import setup_logger

logger = setup_logger("TestAISummary")


async def main():
    start = datetime.now()

    logger.info("=" * 60)
    logger.info("TEST — AI PROCESSING + SUMMARY (bez scrapowania)")
    logger.info(f"Start: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # --- 1. AI — kategoryzacja + wydarzenia ---
    logger.info("\n[1/2] AI PIPELINE — kategoryzacja + ekstrakcja wydarzeń")
    logger.info("-" * 60)
    await run_ai_processing()
    logger.info("✓ AI pipeline zakończony\n")

    # --- 2. Podsumowanie dnia ---
    logger.info("[2/2] PODSUMOWANIE — generowanie daily summary")
    logger.info("-" * 60)
    await run_daily_summary()
    logger.info("✓ Podsumowanie zakończone\n")

    elapsed = (datetime.now() - start).total_seconds()
    logger.info("=" * 60)
    logger.info(f"TEST GOTOWY — czas: {elapsed:.1f}s")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nPrzerwane przez użytkownika")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
