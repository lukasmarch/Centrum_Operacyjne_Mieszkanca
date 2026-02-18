"""
Scheduled job for article updates
Runs every 6 hours - scrapes all active sources
"""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update

from src.config import settings
from src.database.schema import Source
from src.scrapers.registry import get_scraper, list_scrapers
from src.scrapers.rss_scraper import RSSFeedScraper
from src.scrapers.bip_rybno import BipRybnoScraper
from src.utils.logger import setup_logger

logger = setup_logger("ArticleScheduler")


def filter_recent_articles(articles: list, days: int = 2) -> list:
    """
    Filter articles to only include recent ones (published within last N days)

    Args:
        articles: List of article dicts
        days: Number of days to look back (default: 2)

    Returns:
        Filtered list of articles
    """
    if not articles:
        return []

    cutoff_date = datetime.utcnow() - timedelta(days=days)
    filtered = []

    for article in articles:
        published_at = article.get('published_at')

        # Jeśli brak daty publikacji, przyjmij datę scrapowania (teraz)
        if published_at is None:
            # Artykuły bez daty publikacji są traktowane jako świeże
            filtered.append(article)
            continue

        # Jeśli data publikacji jest w przedziale, dodaj
        if published_at >= cutoff_date:
            filtered.append(article)
        else:
            logger.debug(f"Skipping old article: {article.get('title', 'Unknown')} (published: {published_at.date()})")

    if len(filtered) < len(articles):
        logger.info(f"Filtered out {len(articles) - len(filtered)} old articles (older than {days} days)")

    return filtered


async def update_articles_job():
    """Job to scrape and update articles from all active sources"""
    logger.info("=" * 60)
    logger.info("Starting article update job...")
    logger.info(f"Registered scrapers: {list_scrapers()}")
    logger.info("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    total_saved = 0
    total_sources = 0
    failed_sources = []

    async with async_session() as session:
        # Fetch all active sources and convert to dicts to avoid session issues
        result = await session.execute(
            select(Source).where(Source.status == "active")
        )
        sources_orm = result.scalars().all()

        # Convert to list of dicts to avoid lazy loading issues
        sources = [
            {
                "id": s.id,
                "name": s.name,
                "type": s.type,
                "url": s.url,
                "scraping_config": s.scraping_config
            }
            for s in sources_orm
        ]

        logger.info(f"Found {len(sources)} active sources to scrape")

        for source in sources:
            total_sources += 1

            # Extract source info from dict
            source_name = source["name"]
            source_id = source["id"]
            source_type = source["type"]
            source_url = source["url"]

            logger.info(f"\n{'─' * 60}")
            logger.info(f"Processing source: {source_name} (ID: {source_id})")
            logger.info(f"Type: {source_type} | URL: {source_url}")

            # Get scraper class from registry
            scraper_class = get_scraper(source_name)
            if not scraper_class:
                logger.warning(f"No scraper registered for '{source_name}' - skipping")
                failed_sources.append(f"{source_name} (no scraper)")
                continue

            # Initialize scraper with source config
            config = source["scraping_config"] or {}
            scraper = scraper_class(source_id=source_id, config=config)

            try:
                # Get URL to scrape (from source.url or config)
                scrape_url = source_url or config.get("base_url")
                if not scrape_url:
                    logger.error(f"No URL configured for source {source_name}")
                    failed_sources.append(f"{source_name} (no URL)")
                    continue

                logger.info(f"Scraping {scrape_url} with {scraper_class.__name__}...")

                async with scraper:
                    # BIP scrapers use scrape_bip() for multi-page + PDF extraction
                    if isinstance(scraper, BipRybnoScraper):
                        saved_ids = await scraper.scrape_bip(session)
                    # RSS scrapers use feedparser, not HTML parsing
                    elif isinstance(scraper, RSSFeedScraper):
                        articles = await scraper.scrape_feed(scrape_url)
                        # Filter articles by date (only last 2 days)
                        articles = filter_recent_articles(articles, days=2)
                        saved_ids = await scraper.save_to_db(articles, session)
                    else:
                        # Standard HTML scrapers
                        html = await scraper.fetch(scrape_url)
                        articles = await scraper.parse(html, scrape_url)
                        # Filter articles by date (only last 2 days)
                        articles = filter_recent_articles(articles, days=2)
                        saved_ids = await scraper.save_to_db(articles, session)

                logger.info(f"✓ {source_name}: {len(saved_ids)} new articles saved")
                total_saved += len(saved_ids)

                # Update last_scraped timestamp
                await session.execute(
                    update(Source)
                    .where(Source.id == source_id)
                    .values(last_scraped=datetime.utcnow())
                )
                await session.commit()

            except Exception as e:
                logger.error(f"✗ Failed to scrape {source_name}: {e}")
                failed_sources.append(f"{source_name} ({str(e)[:50]})")
                await session.rollback()

    await engine.dispose()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("ARTICLE UPDATE JOB SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total sources processed: {total_sources}")
    logger.info(f"Total new articles saved: {total_saved}")
    logger.info(f"Failed sources: {len(failed_sources)}")
    if failed_sources:
        for failed in failed_sources:
            logger.warning(f"  - {failed}")
    logger.info("=" * 60)


def run_article_job():
    """Sync wrapper for async job"""
    asyncio.run(update_articles_job())


if __name__ == "__main__":
    # Test run
    run_article_job()
