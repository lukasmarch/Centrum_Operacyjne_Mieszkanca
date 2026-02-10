#!/usr/bin/env python3
"""
Ręczny trigger TYLKO daily summary (bez scrapowania i bez AI)

Użyj gdy:
- Masz już artykuły przetworzone przez AI (processed=True)
- Chcesz TYLKO wygenerować summary dla wczorajszego dnia
- Uruchomiłeś już test_ai_only.py

UWAGA: Summary generuje się dla WCZORAJ (yesterday).
       Jeśli summary dla tej daty już istnieje, skrypt zwróci warning i nie nadpisze.

Wszystko zapisuje się do bazy danych.

Uruchomienie:
    cd backend
    python scripts/tests/aktualny_pipeline/test_summary_only.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

backend_path = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_path))

from src.scheduler.summary_job import run_daily_summary
from src.utils.logger import setup_logger

logger = setup_logger("TestSummaryOnly")


async def main():
    start = datetime.now()

    logger.info("=" * 60)
    logger.info("TEST — DAILY SUMMARY ONLY (bez scrapowania i bez AI)")
    logger.info(f"Start: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # --- Podsumowanie dnia ---
    logger.info("\nPODSUMOWANIE — generowanie daily summary")
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
