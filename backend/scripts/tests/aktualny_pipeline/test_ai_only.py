#!/usr/bin/env python3
"""
Ręczny trigger TYLKO AI processing (bez scrapowania i bez summary)

Użyj gdy:
- Masz już artykuły w bazie (po scrapowaniu)
- Chcesz TYLKO przetworzyć je przez AI (kategoryzacja + wydarzenia)
- Nie chcesz jeszcze generować summary

Kolejność:
    1. Kategoryzacja artykułów przez AI        (ai_jobs — ArticleProcessor, batch=100)
    2. Ekstrakcja wydarzeń z artykułów         (ai_jobs — EventExtractor)

UWAGA: AI processing przetwarza tylko artykuły z processed=False (nie duplikuje pracy).
       Batch size: 100 artykułów, czas wykonania: ~32 minuty dla pełnego batcha.

Jeśli masz więcej niż 100 nieprzetworzonych artykułów, uruchom skrypt kilka razy.

Po zakończeniu uruchom test_summary_only.py aby wygenerować summary.

Wszystko zapisuje się do bazy danych.

Uruchomienie:
    cd backend
    python scripts/tests/aktualny_pipeline/test_ai_only.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

backend_path = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_path))

from src.scheduler.ai_jobs import run_ai_processing
from src.utils.logger import setup_logger

logger = setup_logger("TestAIOnly")


async def main():
    start = datetime.now()

    logger.info("=" * 60)
    logger.info("TEST — AI PROCESSING ONLY (bez scrapowania i bez summary)")
    logger.info(f"Start: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # --- AI — kategoryzacja + wydarzenia ---
    logger.info("\nAI PIPELINE — kategoryzacja + ekstrakcja wydarzeń (batch=100)")
    logger.info("-" * 60)
    await run_ai_processing()
    logger.info("✓ AI pipeline zakończony\n")

    elapsed = (datetime.now() - start).total_seconds()
    logger.info("=" * 60)
    logger.info(f"TEST GOTOWY — czas: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    logger.info("=" * 60)
    logger.info("\n💡 Następny krok: uruchom test_summary_only.py aby wygenerować summary")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nPrzerwane przez użytkownika")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
