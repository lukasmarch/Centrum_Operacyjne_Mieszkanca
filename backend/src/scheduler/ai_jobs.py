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


# Ile wpisów bierze lekki przebieg. Energa wypuszcza 1–3 komunikaty na okno;
# limit jest bezpiecznikiem rachunku, nie miarą oczekiwanego ruchu.
CATCHUP_BATCH = 10


async def run_categorization_catchup():
    """
    Sama kategoryzacja, bez wydarzeń — dla wpisów, które przyszły MIĘDZY
    pełnymi przebiegami (6:15 i 13:15).

    Do 3.09.2026 kategoryzacja chodziła wyłącznie o tych dwóch porach, a
    komunikaty Energi wpadają o 9:05, 12:05, 15:05, 18:05 i 21:05. Wpis
    z 9:05 czekał więc do 13:15, a wpis z 18:05 — do 6:15 NASTĘPNEGO DNIA.
    Przez cały ten czas nie miał ani jednego pola, które o nim decyduje:

      • `category`   → `is_pinned_alert` go nie przypnie, więc AWARIA nie
                       trafia na szczyt feedu (znane TODO)
      • `content_score` → `content_factor` daje neutralne 1,0, czyli WIĘCEJ
                       niż lokalna wiadomość oceniona na 2 — wpis stoi wyżej
                       przez to, że jest nieoceniony
      • `locality`   → ocena miejsca nie działa (`locality_factor`)
      • `display_title` → front pokazuje surowy tytuł RSS

    Pomiar 3.09.2026: art. 5784 („Wyłączenie planowane — Region Mława —
    Iłowo-Osada — Mławka") przyszedł o 9:05, o 9:30 wciąż miał
    `processed=false` i stał na CZWARTEJ pozycji feedu z wynikiem 0,701 —
    zapowiedź sprzed tygodnia z cudzej gminy nad wiadomościami z Rybna.

    Osobno od `run_ai_processing`, bo to nie jest ten sam przebieg:
    ekstrakcji wydarzeń tu NIE MA (`extract_from_recent` sięga 6 h wstecz
    i przy pięciu wywołaniach dziennie mieliłaby ten sam materiał po
    wielokroć), briefingu i newslettera też nie. Koszt okna to zwykle
    1–3 wpisy przez gpt-4o-mini.
    """
    logger.info("Kategoryzacja — przebieg uzupełniający (bez wydarzeń)")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            processor = ArticleProcessor()
            processed = await processor.process_batch(session, batch_size=CATCHUP_BATCH)
            logger.info(f"✓ Przebieg uzupełniający: {processed} wpisów")
        except Exception as e:
            logger.error(f"✗ Przebieg uzupełniający nie powiódł się: {e}", exc_info=True)
            raise

    await engine.dispose()


def run_ai_job():
    """
    Sync wrapper dla schedulera

    Uruchamia async run_ai_processing() w synchronicznym kontekście
    wymaganym przez APScheduler
    """
    asyncio.run(run_ai_processing())


def run_categorization_catchup_job():
    """Sync wrapper dla przebiegu uzupełniającego."""
    asyncio.run(run_categorization_catchup())
