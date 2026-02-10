"""
AI Processing Jobs dla schedulera

Automatyczne przetwarzanie artykułów przez AI:
1. Kategoryzacja artykułów (ArticleProcessor)
2. Ekstrakcja wydarzeń (EventExtractor)
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.ai.article_processor import ArticleProcessor
from src.ai.event_extractor import EventExtractor
from src.utils.logger import setup_logger

logger = setup_logger("AIScheduler")


async def run_ai_processing():
    """
    Główny pipeline AI - kategoryzacja + ekstrakcja wydarzeń

    Workflow:
    1. ArticleProcessor - przetwórz nieprzetwórzone artykuły (batch 100)
    2. EventExtractor - wyekstrahuj wydarzenia z ostatnich 6h

    Uruchamiany przez scheduler 1x dziennie o 6:15 AM
    """
    logger.info("="*60)
    logger.info("Starting AI processing job...")
    logger.info("="*60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        try:
            # Krok 1: Kategoryzacja artykułów
            logger.info("\n[1/2] Article Processing - Categorization")
            logger.info("-" * 60)

            processor = ArticleProcessor()
            processed_count = await processor.process_batch(
                session,
                batch_size=100  # Maksymalnie 100 artykułów na raz (~32 min dla 100 art)
            )

            logger.info(f"✓ Processed {processed_count} articles\n")

            # Krok 2: Ekstrakcja wydarzeń
            logger.info("[2/2] Event Extraction")
            logger.info("-" * 60)

            extractor = EventExtractor()
            event_count = await extractor.extract_from_recent(
                session,
                hours=6  # Sprawdź artykuły z ostatnich 6 godzin
            )

            logger.info(f"✓ Extracted {event_count} events\n")

            # Podsumowanie
            logger.info("="*60)
            logger.info("AI processing job completed successfully")
            logger.info(f"Summary: {processed_count} articles processed, {event_count} events extracted")
            logger.info("="*60)

        except Exception as e:
            logger.error(f"✗ AI processing job failed: {e}", exc_info=True)
            raise

    await engine.dispose()


def run_ai_job():
    """
    Sync wrapper dla schedulera

    Uruchamia async run_ai_processing() w synchronicznym kontekście
    wymaganym przez APScheduler
    """
    asyncio.run(run_ai_processing())
