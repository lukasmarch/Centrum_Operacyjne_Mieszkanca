"""
Places Cache Update Job — Gemini Maps grounding

Uruchamiany co tydzień (poniedziałek 5:00).
Pobiera dane o lokalnych miejscach z Gemini Maps API i zapisuje do local_places.
6 kategorii × 1 zapytanie = 6 API calls/tydzień (znikomy koszt).
"""
import asyncio
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from src.integrations.places_service import places_service, CATEGORY_PROMPTS
from src.config import settings
from src.utils.logger import setup_logger

logger = setup_logger("PlacesJob")


async def run_places_job_async():
    """Async version of places job — fetches all categories and upserts to DB."""
    logger.info("=" * 80)
    logger.info("LOCAL PLACES UPDATE — Gemini Maps grounding")
    logger.info("=" * 80)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    total_upserted = 0
    categories = list(CATEGORY_PROMPTS.keys())

    try:
        for i, category in enumerate(categories):
            logger.info(f"[{i+1}/{len(categories)}] Fetching: {category}")

            places = await places_service.fetch_places_for_category(category)

            if not places:
                logger.warning(f"  No places returned for {category}")
                if i < len(categories) - 1:
                    await asyncio.sleep(2)
                continue

            async with async_session_factory() as session:
                for place in places:
                    # Upsert by place_id
                    await session.execute(
                        text("""
                            INSERT INTO local_places (place_id, name, category, description, address, maps_uri, fetched_at, updated_at)
                            VALUES (:place_id, :name, :category, :description, :address, :maps_uri, :now, :now)
                            ON CONFLICT (place_id) DO UPDATE SET
                                name = EXCLUDED.name,
                                description = EXCLUDED.description,
                                address = EXCLUDED.address,
                                maps_uri = EXCLUDED.maps_uri,
                                updated_at = EXCLUDED.updated_at,
                                active = TRUE
                        """),
                        {
                            "place_id": place["place_id"],
                            "name": place["name"][:300],
                            "category": place["category"][:50],
                            "description": (place.get("description") or "")[:2000] or None,
                            "address": (place.get("address") or "")[:500] or None,
                            "maps_uri": (place.get("maps_uri") or "")[:500] or None,
                            "now": datetime.utcnow(),
                        }
                    )
                await session.commit()
                total_upserted += len(places)
                logger.info(f"  ✓ {len(places)} places upserted for {category}")

            # Rate limit between categories
            if i < len(categories) - 1:
                await asyncio.sleep(2)

        logger.info("=" * 80)
        logger.info(f"Places job finished — {total_upserted} total places upserted")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Error in places job: {e}", exc_info=True)
    finally:
        await engine.dispose()


def run_places_job():
    """Synchronous wrapper for APScheduler."""
    asyncio.run(run_places_job_async())


if __name__ == "__main__":
    print("Test Places Job...\n")
    run_places_job()
