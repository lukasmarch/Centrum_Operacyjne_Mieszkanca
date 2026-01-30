#!/usr/bin/env python3
"""
Ręczny trigger dziennego pipeline — simuluje to, co robi scheduler automatycznie.

Kolejność (identyczna jak w scheduler.py):
    1. Scraping wszystkich aktywnych źródeł  (article_job)
    2. Kategoryzacja artykułów przez AI        (ai_jobs — ArticleProcessor)
    3. Ekstrakcja wydarzeń z artykułów         (ai_jobs — EventExtractor)
    4. Generowanie dziennego podsumowania      (summary_job)

Wszystko zapisuje się do bazy danych.

Uruchomienie:
    cd backend
    python scripts/tests/test_full_pipeline.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from src.scheduler.article_job import update_articles_job
from src.scheduler.ai_jobs import run_ai_processing
from src.scheduler.summary_job import run_daily_summary
from src.utils.logger import setup_logger

logger = setup_logger("ManualPipeline")


async def main():
    start = datetime.now()

    logger.info("=" * 60)
    logger.info("RĘCZNY TRIGGER — DZIENNI PIPELINE")
    logger.info(f"Start: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # --- 1. Scraping ---
    logger.info("\n[1/4] SCRAPING — pobieranie artykułów ze źródeł")
    logger.info("-" * 60)
    await update_articles_job()
    logger.info("✓ Scraping zakończony\n")

    # --- 2. AI — kategoryzacja ---
    logger.info("[2-3/4] AI PIPELINE — kategoryzacja + ekstrakcja wydarzeń")
    logger.info("-" * 60)
    await run_ai_processing()
    logger.info("✓ AI pipeline zakończony\n")

    # --- 3. Podsumowanie dnia ---
    logger.info("[4/4] PODSUMOWANIE — generowanie daily summary")
    logger.info("-" * 60)
    await run_daily_summary()
    logger.info("✓ Podsumowanie zakończone\n")

    elapsed = (datetime.now() - start).total_seconds()
    logger.info("=" * 60)
    logger.info(f"PIPELINE GOTOWY — czas: {elapsed:.1f}s")
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
