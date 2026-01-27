from datetime import datetime
import logging
import asyncio
from src.scrapers.cinema import CinemaScraper

logger = logging.getLogger("Scheduler")

async def run_cinema_job_async():
    """
    Async job to update cinema repertoire (cache warming).
    Runs daily to ensure fresh data is available instantly for users.
    """
    logger.info("Starting cinema repertoire update job...")

    scraper = CinemaScraper()
    cities = ["Dzialdowo", "Lubawa"]

    for city in cities:
        try:
            logger.info(f"Updating cache for {city}...")
            # force_update=True ensures we scrape fresh data and update the cache file
            result = await scraper.fetch_repertoire(city, force_update=True)
            if result and result.movies:
                logger.info(f"Successfully updated {city} - found {len(result.movies)} movies")
            else:
                logger.warning(f"Updated {city} but found 0 movies (or error)")
        except Exception as e:
            logger.error(f"Error executing cinema job for {city}: {e}")

    logger.info("Cinema repertoire update job finished")

def run_cinema_job():
    """
    Wrapper function for scheduler compatibility.
    Runs the async cinema job in the event loop.
    """
    asyncio.run(run_cinema_job_async())
