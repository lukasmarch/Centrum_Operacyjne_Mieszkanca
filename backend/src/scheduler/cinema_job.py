from datetime import datetime
import logging
from src.scrapers.cinema import CinemaScraper

logger = logging.getLogger("Scheduler")

def run_cinema_job():
    """
    Job to update cinema repertoire (cache warming).
    Runs daily to ensure fresh data is available instantly for users.
    """
    logger.info("Starting cinema repertoire update job...")
    
    scraper = CinemaScraper()
    cities = ["Dzialdowo", "Lubawa"]
    
    for city in cities:
        try:
            logger.info(f"Updating cache for {city}...")
            # force_update=True ensures we scrape fresh data and update the cache file
            result = scraper.fetch_repertoire(city, force_update=True)
            if result and result.movies:
                logger.info(f"Successfully updated {city} - found {len(result.movies)} movies")
            else:
                logger.warning(f"Updated {city} but found 0 movies (or error)")
        except Exception as e:
            logger.error(f"Error executing cinema job for {city}: {e}")
            
    logger.info("Cinema repertoire update job finished")
