"""
Scheduled job for weather updates
Runs every 15 minutes
"""
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.integrations.weather import WeatherService
from src.utils.logger import setup_logger

logger = setup_logger("WeatherScheduler")


async def update_weather_job():
    """Job to update weather data for all locations"""
    logger.info("Starting weather update job...")

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        weather_service = WeatherService()

        try:
            results = await weather_service.update_all_locations(session)
            logger.info(f"Weather updated: {len(results)} locations")

        except Exception as e:
            logger.error(f"Weather update failed: {e}")

    await engine.dispose()


def run_weather_job():
    """Sync wrapper for async job"""
    asyncio.run(update_weather_job())


if __name__ == "__main__":
    # Test run
    run_weather_job()
