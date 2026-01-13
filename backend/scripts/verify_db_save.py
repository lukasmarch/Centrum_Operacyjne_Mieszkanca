
import asyncio
import logging
from typing import List, Type
from datetime import datetime

from src.database.connection import get_session
from src.database.schema import Article
from src.scrapers.base import BaseScraper
from src.scrapers.gmina_rybno import GminaRybnoScraper
from src.scrapers.mojedzialdowo import MojeDzialdowoScraper
from src.scrapers.klikajinfo import KlikajInfoScraper
from sqlalchemy.future import select

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DBVerification")

async def verify_scraper_save(scraper_cls: Type[BaseScraper], source_id: int):
    logger.info(f"--- Verifying {scraper_cls.__name__} ---")
    scraper = scraper_cls(source_id=source_id)
    
    # 1. Fetch ONE article with deep scraping
    articles = []
    async with scraper:
        # Fetching main page logic depends on scraper implementation
        # Gmina Rybno and MojeDzialdowo have similar enough interface
        if scraper_cls == GminaRybnoScraper:
            url = "https://gminarybno.pl/aktualnosci"
        elif scraper_cls == MojeDzialdowoScraper:
            url = "https://mojedzialdowo.pl"
        elif scraper_cls == KlikajInfoScraper:
            url = "https://klikajinfo.pl"
            
        try:
            html = await scraper.fetch(url)
            # Fetch just a few to save time, we only need one for verification
            all_articles = await scraper.parse(html, url)
            
            if not all_articles:
                logger.error("No articles found!")
                return
            
            # Pick the first one
            article_to_save = all_articles[0]
            logger.info(f"Selected article for test: {article_to_save.get('title')} ({article_to_save.get('url')})")
            articles.append(article_to_save)

        except Exception as e:
            logger.error(f"Error scraping: {e}")
            return

    # 2. Save to DB (Upsert)
    async for session in get_session():
        # First ensure clean state or check existing? 
        # Actually checking UPSERT means we *want* to see it update if it exists or create if not.
        
        # Check if it exists and maybe print its current state
        existing = await session.execute(
            select(Article).where(Article.url == article_to_save['url'])
        )
        existing_article = existing.scalar_one_or_none()
        
        if existing_article:
            logger.info(f"Article exists. Current content length: {len(existing_article.content) if existing_article.content else 0}")
            logger.info(f"Current published_at: {existing_article.published_at}")
        else:
            logger.info("Article does not exist correctly.")

        # Perform Save
        await scraper.save_to_db(articles, session)
        
        # 3. Verify Data in DB
        # Re-fetch
        result = await session.execute(
            select(Article).where(Article.url == article_to_save['url'])
        )
        saved_article = result.scalar_one()
        
        logger.info(f"--- Verification Results for {scraper_cls.__name__} ---")
        logger.info(f"ID: {saved_article.id}")
        logger.info(f"Title: {saved_article.title}")
        logger.info(f"Content Length: {len(saved_article.content) if saved_article.content else 0}")
        logger.info(f"Published At: {saved_article.published_at}")
        
        if saved_article.content and len(saved_article.content) > 100:
             logger.info("SUCCESS: Content is present and populated.")
        else:
             logger.error("FAILURE: Content is missing or too short.")

        if saved_article.published_at:
             logger.info("SUCCESS: Published_at is set.")
        else:
             logger.error("FAILURE: Published_at is missing.")
             
        break

async def main():
    # await init_db() # Not present in connection.py, assuming DB already initialized or not needed for just generic verification if tables exist.
    # Actually, we rely on tables existing. If they don't script will fail. But we can't call missing function.
    pass
    
    # Run for all scrapers
    await verify_scraper_save(GminaRybnoScraper, 1)
    await verify_scraper_save(MojeDzialdowoScraper, 2)
    # Source ID 3 for KlikajInfo (assuming, check schema/seed if strict, but upsert creates if source_id is valid key)
    # Usually we should ensure source exists, but for now assuming 3 is fine or DB not strict on FK for verification if sources pre-seeded
    await verify_scraper_save(KlikajInfoScraper, 3)

if __name__ == "__main__":
    asyncio.run(main())
