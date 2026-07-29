"""
Traffic Cache Update Job - Database-First Architecture

Uruchamiany co 4 godziny (6:00, 10:00, 14:00, 18:00, 22:00, 2:00).
Pobiera aktualne dane o ruchu drogowym z Gemini Grounding API i zapisuje do cache.
Kosztowny API call - ograniczony do 6 razy dziennie.
"""
import asyncio
from datetime import datetime
from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.integrations.traffic_service import TrafficService
from src.services.road_context import fetch_road_context, format_road_context
from src.config import settings
from src.database.schema import TrafficCache
from src.utils.logger import setup_logger

logger = setup_logger("TrafficJob")


async def run_traffic_job_async():
    """
    Async version of traffic job - fetches fresh traffic data and saves to cache.
    """
    logger.info("=" * 80)
    logger.info("TRAFFIC CACHE UPDATE - Gemini Grounding API")
    logger.info("=" * 80)

    # Create fresh engine per run (avoids "attached to different loop" error)
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    service = TrafficService()

    try:
        # 1. Materiał źródłowy z własnego feedu — model ma pracować na naszych
        #    zweryfikowanych wpisach z datami, a nie rekonstruować stan dróg
        #    z przypadkowych wyników wyszukiwania.
        async with async_session() as session:
            road_items = await fetch_road_context(session)
        logger.info(f"Materiał źródłowy o drogach: {len(road_items)} wpisów lokalnych")
        for item in road_items[:5]:
            logger.info(f"    [{item['date']}] {item['title'][:70]}")

        # 2. Fetch fresh data from Gemini (kosztowne API call)
        logger.info("Fetching fresh traffic data from Gemini Grounding API...")
        traffic_data = await service.get_traffic_data(
            road_context=format_road_context(road_items)
        )

        if not traffic_data or not traffic_data.roads:
            logger.warning("  ⚠️  No roads data returned - using fallback")
            return

        # Atrapa (typowe czasy przejazdu) nie jest danymi — nie nadpisuj nią cache'u.
        # Stary, ale prawdziwy odczyt jest wart więcej niż świeży wpis "Brak danych",
        # a ERROR w logu sprawia, że awaria Gemini nie przeleży znowu trzech tygodni.
        if traffic_data.is_fallback:
            logger.error(
                "  ✗ Gemini nie zwrócił danych — zachowuję poprzedni wpis w cache. "
                "Sprawdź limity API (429) lub dostępność modelu."
            )
            return

        # 2. Save to database
        async with async_session() as session:
            # Mark all existing records as not current
            await session.execute(
                update(TrafficCache).values(is_current=False)
            )

            # Insert new cache record
            cache_entry = TrafficCache(
                data=traffic_data.dict(),  # Pydantic model → dict
                fetched_at=datetime.utcnow(),
                is_current=True,
                ttl_seconds=14400  # 4 hours
            )
            session.add(cache_entry)
            await session.commit()

            logger.info(f"  ✓ Saved traffic data to cache ({len(traffic_data.roads)} roads)")

        logger.info("=" * 80)
        logger.info(f"Traffic job finished - {len(traffic_data.roads)} roads cached")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"  ✗ Error in traffic job: {e}", exc_info=True)
    finally:
        await engine.dispose()


def run_traffic_job():
    """
    Wrapper synchroniczny dla async job.
    (APScheduler wymaga funkcji synchronicznej)
    """
    asyncio.run(run_traffic_job_async())


if __name__ == "__main__":
    # Test job ręcznie
    print("🧪 Test Traffic Cache Job...\n")
    run_traffic_job()
