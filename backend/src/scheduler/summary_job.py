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

    Uruchamiany przez scheduler codziennie o 6:45 (po AI processing)
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
                logger.info(f"✓ SUCCESS: Generated daily summary")
                logger.info(f"  ID: {summary.id}")
                logger.info(f"  Headline: {summary.headline}")
                logger.info(f"  Date: {summary.date.date()}")
                logger.info(f"  Generated at: {summary.generated_at}")
                logger.info(f"  Articles count: {len(summary.headline.split())}")  # Approximate

                # Trigger push notification for daily summary
                try:
                    from src.services.push_service import push_service
                    sent = await push_service.send_daily_summary_push(session, summary.headline)
                    logger.info(f"Push sent to {sent} subscribers (daily summary)")
                except Exception as push_err:
                    logger.error(f"Daily summary push failed: {push_err}")
            else:
                logger.warning("⚠ SUMMARY IS NONE - Possible reasons:")
                logger.warning("  1. Summary for this date already exists in database")
                logger.warning("  2. No processed articles found for target date")
                logger.warning("  3. Articles exist but are not categorized (processed=False)")
                logger.warning("  → Check database: SELECT * FROM daily_summaries ORDER BY date DESC LIMIT 3")
                logger.warning("  → Check articles: SELECT COUNT(*) FROM articles WHERE processed=True")

            logger.info("="*60)
            logger.info("Daily summary job completed")
            logger.info("="*60)

            return summary

        except Exception as e:
            logger.error("="*60)
            logger.error(f"✗ CRITICAL ERROR in daily summary job")
            logger.error(f"Exception type: {type(e).__name__}")
            logger.error(f"Exception message: {str(e)}")
            logger.error("="*60)
            logger.error("Full traceback:", exc_info=True)
            raise

    await engine.dispose()


def run_summary_job():
    """
    Sync wrapper dla schedulera

    Uruchamia async run_daily_summary() w synchronicznym kontekście
    wymaganym przez APScheduler
    """
    asyncio.run(run_daily_summary())
