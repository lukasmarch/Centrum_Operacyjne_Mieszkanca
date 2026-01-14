import asyncio
import logging
from sqlalchemy.future import select
from sqlalchemy import desc
from src.database.connection import get_session
from src.database.schema import Article

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("DBCheck")

async def check_latest_articles():
    # await init_db() # Assuming DB exists
    
    async for session in get_session():
        logger.info("\n=== LATEST ARTICLES IN DATABASE ===")
        
        # Check for Source 1 (Gmina Rybno)
        stmt = select(Article).where(Article.source_id == 1).order_by(desc(Article.scraped_at)).limit(3)
        result = await session.execute(stmt)
        articles = result.scalars().all()
        
        logger.info(f"\n--- Source 1 (Gmina Rybno) [Found: {len(articles)}] ---")
        for a in articles:
            logger.info(f"[ID: {a.id}] Date: {a.published_at} | Title: {a.title} | Content Len: {len(a.content) if a.content else 0}")

        # Check for Source 2 (Moje Dzialdowo)
        stmt = select(Article).where(Article.source_id == 2).order_by(desc(Article.scraped_at)).limit(3)
        result = await session.execute(stmt)
        articles = result.scalars().all()
        
        logger.info(f"\n--- Source 2 (Moje Dzialdowo) [Found: {len(articles)}] ---")
        for a in articles:
             logger.info(f"[ID: {a.id}] Date: {a.published_at} | Title: {a.title} | Content Len: {len(a.content) if a.content else 0}")

        # Check for Source 3 (KlikajInfo)
        stmt = select(Article).where(Article.source_id == 3).order_by(desc(Article.scraped_at)).limit(3)
        result = await session.execute(stmt)
        articles = result.scalars().all()
        
        logger.info(f"\n--- Source 3 (KlikajInfo) [Found: {len(articles)}] ---")
        for a in articles:
             logger.info(f"[ID: {a.id}] Date: {a.published_at} | Title: {a.title} | Content Len: {len(a.content) if a.content else 0}")

if __name__ == "__main__":
    asyncio.run(check_latest_articles())
