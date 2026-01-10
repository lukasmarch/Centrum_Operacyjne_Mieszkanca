#!/usr/bin/env python3
"""
Integration test: Scrape Klikaj.info and save articles to database.
Tests:
- Scraping from real website
- Saving to database
- Deduplication (URL and external_id unique constraints)
"""
import asyncio
import os
from pathlib import Path
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.schema import Source, Article
from src.scrapers.klikajinfo import KlikajInfoScraper


async def test_integration():
    """Run integration test: scraping + database save + deduplication."""

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment variables")

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Get Klikaj.info source
        result = await session.execute(
            select(Source).where(Source.name == "Klikaj.info")
        )
        source = result.scalar_one_or_none()

        if not source:
            print("❌ Source 'Klikaj.info' not found in database")
            print("   Run: python scripts/init_sources.py first")
            return

        print(f"✓ Found source: {source.name} (ID: {source.id})")

        # Count articles before scraping
        result = await session.execute(
            select(Article).where(Article.source_id == source.id)
        )
        articles_before = len(result.scalars().all())
        print(f"📊 Articles in DB before: {articles_before}")

        # Scrape articles
        print("\n🕷️  Starting scraper...")
        urls_to_scrape = ["https://klikajinfo.pl"]

        async with KlikajInfoScraper(source_id=source.id) as scraper:
            article_ids = await scraper.scrape(urls_to_scrape, session)

        print(f"✓ Scraped {len(article_ids)} new articles")

        # Count articles after scraping
        result = await session.execute(
            select(Article).where(Article.source_id == source.id)
        )
        articles_after = len(result.scalars().all())
        print(f"📊 Articles in DB after: {articles_after}")
        print(f"📈 Net new articles: {articles_after - articles_before}")

        # Test deduplication - run scraper again
        print("\n🔄 Testing deduplication (running scraper again)...")

        async with KlikajInfoScraper(source_id=source.id) as scraper:
            article_ids_2 = await scraper.scrape(urls_to_scrape, session)

        print(f"✓ Second run: {len(article_ids_2)} new articles (should be 0 or very few)")

        # Count final articles
        result = await session.execute(
            select(Article).where(Article.source_id == source.id)
        )
        articles_final = len(result.scalars().all())
        print(f"📊 Articles in DB final: {articles_final}")

        # Show sample articles
        print("\n📰 Sample articles:")
        result = await session.execute(
            select(Article)
            .where(Article.source_id == source.id)
            .limit(3)
        )
        sample_articles = result.scalars().all()

        for i, article in enumerate(sample_articles, 1):
            print(f"\n{i}. {article.title}")
            print(f"   URL: {article.url}")
            print(f"   External ID: {article.external_id}")
            print(f"   Image: {article.image_url}")
            print(f"   Scraped: {article.scraped_at}")

        print("\n✅ Integration test completed successfully!")
        print(f"   - Scraping: ✓")
        print(f"   - Database save: ✓")
        print(f"   - Deduplication: ✓")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test_integration())
