"""
Traffic Cache Update Job - Database-First Architecture

Uruchamiany co 4 godziny (6:00, 10:00, 14:00, 18:00, 22:00, 2:00).
Pobiera aktualne dane o ruchu drogowym z Gemini Grounding API i zapisuje do cache.
Kosztowny API call - ograniczony do 6 razy dziennie.
"""
import asyncio
from datetime import datetime
from sqlalchemy import update

from src.integrations.traffic_service import TrafficService
from src.database.connection import async_session
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

    service = TrafficService()

    try:
        # 1. Fetch fresh data from Gemini (kosztowne API call)
        logger.info("Fetching fresh traffic data from Gemini Grounding API...")
        traffic_data = await service.get_traffic_data()

        if not traffic_data or not traffic_data.roads:
            logger.warning("  ⚠️  No roads data returned - using fallback")
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


def run_traffic_job():
    """
    Wrapper synchroniczny dla async job.
    (APScheduler wymaga funkcji synchronicznej)
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running event loop - safe to use asyncio.run()
        asyncio.run(run_traffic_job_async())
    else:
        # Already in a running loop - create and run task
        loop.run_until_complete(run_traffic_job_async())


if __name__ == "__main__":
    # Test job ręcznie
    print("🧪 Test Traffic Cache Job...\n")
    run_traffic_job()
