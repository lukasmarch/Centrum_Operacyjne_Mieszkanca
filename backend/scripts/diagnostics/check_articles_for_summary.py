#!/usr/bin/env python3
"""
Articles Summary Diagnostics

Analizuje artykuły w bazie pod kątem generowania daily summary:
- Ile artykułów jest przetworzonych (processed=True)?
- Rozkład dat published_at vs scraped_at
- Czy są artykuły z wczoraj gotowe do summary?
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.database.schema import Article
from src.utils.logger import setup_logger

logger = setup_logger("ArticlesDiagnostics")


async def check_articles():
    """Analyze articles in database"""
    print("="*70)
    print("ARTICLES DIAGNOSTICS FOR DAILY SUMMARY")
    print("="*70)
    print()

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Total articles
        total_count = await session.scalar(select(func.count(Article.id)))
        print(f"Total articles in database: {total_count}")
        print()

        # Processed vs unprocessed
        processed_count = await session.scalar(
            select(func.count(Article.id)).where(Article.processed == True)
        )
        unprocessed_count = total_count - (processed_count or 0)

        print("PROCESSING STATUS:")
        print(f"  ✓ Processed (categorized): {processed_count or 0}")
        print(f"  ⚠ Unprocessed: {unprocessed_count}")
        print()

        # Articles from yesterday
        yesterday = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        yesterday_query = select(func.count(Article.id)).where(
            and_(
                Article.published_at >= yesterday,
                Article.published_at < today
            )
        )
        yesterday_count = await session.scalar(yesterday_query)

        yesterday_processed_query = select(func.count(Article.id)).where(
            and_(
                Article.published_at >= yesterday,
                Article.published_at < today,
                Article.processed == True
            )
        )
        yesterday_processed = await session.scalar(yesterday_processed_query)

        print(f"YESTERDAY'S ARTICLES ({yesterday.date()}):")
        print(f"  Total: {yesterday_count or 0}")
        print(f"  Processed: {yesterday_processed or 0}")
        print(f"  Unprocessed: {(yesterday_count or 0) - (yesterday_processed or 0)}")
        print()

        if yesterday_processed and yesterday_processed > 0:
            print("✓ READY FOR SUMMARY: Yes, processed articles from yesterday exist")
        else:
            print("✗ NOT READY: No processed articles from yesterday")
            print("  → Summary will return None (no data)")

        print()

        # Articles from today
        tomorrow = today + timedelta(days=1)
        today_query = select(func.count(Article.id)).where(
            and_(
                Article.published_at >= today,
                Article.published_at < tomorrow
            )
        )
        today_count = await session.scalar(today_query)

        today_processed_query = select(func.count(Article.id)).where(
            and_(
                Article.published_at >= today,
                Article.published_at < tomorrow,
                Article.processed == True
            )
        )
        today_processed = await session.scalar(today_processed_query)

        print(f"TODAY'S ARTICLES ({today.date()}):")
        print(f"  Total: {today_count or 0}")
        print(f"  Processed: {today_processed or 0}")
        print(f"  Unprocessed: {(today_count or 0) - (today_processed or 0)}")
        print()

        # Recent articles sample
        recent_articles_query = (
            select(Article)
            .order_by(Article.scraped_at.desc())
            .limit(5)
        )
        result = await session.execute(recent_articles_query)
        recent_articles = result.scalars().all()

        print("RECENT ARTICLES (last 5 scraped):")
        for article in recent_articles:
            processed_mark = "✓" if article.processed else "✗"
            category = article.category if article.category else "None"
            print(f"  {processed_mark} [{category:15}] {article.title[:50]}...")
            print(f"     Published: {article.published_at.strftime('%Y-%m-%d %H:%M') if article.published_at else 'N/A'}")
            print(f"     Scraped: {article.scraped_at.strftime('%Y-%m-%d %H:%M')}")
            print()

    await engine.dispose()

    print("="*70)
    print("DIAGNOSTICS COMPLETE")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(check_articles())
