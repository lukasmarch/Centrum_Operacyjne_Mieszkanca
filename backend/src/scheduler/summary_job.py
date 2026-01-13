"""
Daily Summary Job dla schedulera

Automatyczne generowanie dziennych podsumowań codziennie o 6:00 rano
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.ai.summary_generator import SummaryGenerator
from src.utils.logger import setup_logger

logger = setup_logger("SummaryScheduler")


async def run_daily_summary():
    """
    Generuj dzienne podsumowanie

    Workflow:
    1. Agreguj artykuły z ostatnich 24h
    2. Pobierz nadchodzące wydarzenia
    3. Pobierz pogodę
    4. Wygeneruj AI summary
    5. Zapisz do bazy

    Uruchamiany przez scheduler codziennie o 6:00
    """
    logger.info("="*60)
    logger.info("Starting daily summary generation...")
    logger.info("="*60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        try:
            generator = SummaryGenerator()

            # Generuj podsumowanie dla wczorajszego dnia
            summary = await generator.generate_daily_summary(session)

            if summary:
                logger.info(f"✓ Generated daily summary: {summary.headline}")
                logger.info(f"  Date: {summary.date.date()}")
                logger.info(f"  Generated at: {summary.generated_at}")
            else:
                logger.warning("No summary generated (may already exist or no data)")

            logger.info("="*60)
            logger.info("Daily summary job completed successfully")
            logger.info("="*60)

        except Exception as e:
            logger.error(f"✗ Daily summary job failed: {e}", exc_info=True)
            raise

    await engine.dispose()


def run_summary_job():
    """
    Sync wrapper dla schedulera

    Uruchamia async run_daily_summary() w synchronicznym kontekście
    wymaganym przez APScheduler
    """
    asyncio.run(run_daily_summary())
