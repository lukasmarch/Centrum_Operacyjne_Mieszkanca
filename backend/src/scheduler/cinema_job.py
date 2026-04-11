"""
Cinema Repertoire Update Job - Database-First Architecture

Uruchamiany codziennie o 8:00 AM.
Scrapuje repertuary kin i zapisuje do tabeli cinema_showtimes.
"""
import asyncio
from datetime import datetime
from typing import List
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.scrapers.cinema import CinemaScraper, CinemaRepertoire
from src.core.config import settings
from src.database.schema import CinemaShowtime
from src.utils.logger import setup_logger

logger = setup_logger("CinemaJob")


async def save_repertoire_to_db(repertoire: CinemaRepertoire, session: AsyncSession):
    """
    Zapisz repertuar kina do bazy danych.

    Args:
        repertoire: CinemaRepertoire object from scraper
        session: AsyncSession
    """
    cinema_name = repertoire.cinemaName
    date = repertoire.date

    # 1. Delete old entries for this cinema+date (replace strategy)
    await session.execute(
        delete(CinemaShowtime).where(
            CinemaShowtime.cinema_name == cinema_name,
            CinemaShowtime.date == date
        )
    )

    # 2. Insert new movies
    for movie in repertoire.movies:
        showtime = CinemaShowtime(
            cinema_name=cinema_name,
            date=date,
            title=movie.title,
            genre=movie.genre,
            showtimes=movie.time,  # List[str]
            poster_url=movie.posterUrl,
            rating=movie.rating,
            link=movie.link,
            fetched_at=datetime.utcnow()
        )
        session.add(showtime)

    await session.commit()
    logger.info(f"  ✓ Saved {len(repertoire.movies)} movies to database")


async def run_cinema_job_async():
    """
    Async version of cinema job - scrapes and saves to database.
    """
    logger.info("=" * 80)
    logger.info("CINEMA REPERTOIRE UPDATE - Database-First")
    logger.info("=" * 80)

    scraper = CinemaScraper()
    cities = ["Dzialdowo", "Lubawa"]
    total_movies = 0

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        for city in cities:
            try:
                logger.info(f"Processing {city}...")

                # Scrape fresh data (bypass cache)
                result = scraper.fetch_repertoire(city, force_update=True)

                if result and result.movies:
                    # Save to database
                    await save_repertoire_to_db(result, session)
                    total_movies += len(result.movies)
                    logger.info(f"  ✓ {city}: {len(result.movies)} movies")
                else:
                    logger.warning(f"  ⚠️  {city}: 0 movies found")

            except Exception as e:
                logger.error(f"  ✗ Error processing {city}: {e}", exc_info=True)

    await engine.dispose()
    logger.info("=" * 80)
    logger.info(f"Cinema job finished - Total movies: {total_movies}")
    logger.info("=" * 80)


def run_cinema_job():
    """
    Wrapper synchroniczny dla async job.
    (APScheduler wymaga funkcji synchronicznej)
    """
    asyncio.run(run_cinema_job_async())


if __name__ == "__main__":
    # Test job ręcznie
    print("🧪 Test Cinema Repertoire Job...\n")
    run_cinema_job()
