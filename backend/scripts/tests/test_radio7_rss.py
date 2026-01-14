"""
Test RSS Scraper z Radio 7 Działdowo
"""
import sys
import asyncio
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from src.database.connection import async_session
from src.database.schema import Source, Article
from src.scrapers.rss_scraper import RSSFeedScraper
from sqlmodel import select


async def test_radio7():
    """Test RSS scraper z Radio 7"""

    async with async_session() as session:
        # Pobierz źródło
        result = await session.execute(
            select(Source).where(Source.name == "Radio 7 Działdowo (RSS)")
        )
        source = result.scalar_one_or_none()

        if not source:
            print("❌ Źródło nie istnieje!")
            return

        print("=" * 70)
        print(f"TESTOWANIE: {source.name}")
        print(f"URL: {source.url}")
        print("=" * 70)

        # Scrape
        scraper = RSSFeedScraper(source.id, source.scraping_config or {})
        print("\n📡 Fetching RSS feed...")
        articles = await scraper.scrape_feed(source.url)

        if not articles:
            print("❌ No articles found!")
            return

        print(f"✅ Found {len(articles)} articles\n")

        # Pokaż przykłady
        print("=" * 70)
        print("PRZYKŁADOWE ARTYKUŁY:")
        print("=" * 70)

        for i, article in enumerate(articles[:3], 1):
            print(f"\n[{i}] {article['title']}")
            print(f"    URL: {article['url']}")
            print(f"    Published: {article.get('published_at', 'N/A')}")
            if article.get('summary'):
                summary = article['summary'][:100]
                print(f"    Summary: {summary}...")

        # Zapisz do bazy
        print("\n" + "=" * 70)
        print("ZAPISYWANIE DO BAZY...")
        print("=" * 70)

        saved_count = 0
        skipped_count = 0

        for article_data in articles:
            try:
                # Sprawdź czy istnieje
                result = await session.execute(
                    select(Article).where(Article.url == article_data['url'])
                )
                existing = result.scalar_one_or_none()

                if existing:
                    skipped_count += 1
                    continue

                # Zapisz nowy
                article = Article(
                    source_id=source.id,
                    title=article_data['title'],
                    url=article_data['url'],
                    summary=article_data.get('summary'),
                    content=article_data.get('content'),
                    author=article_data.get('author'),
                    published_at=article_data.get('published_at'),
                    image_url=article_data.get('image_url'),
                    external_id=article_data.get('external_id'),
                    processed=False
                )

                session.add(article)
                saved_count += 1

            except Exception as e:
                print(f"⚠️  Error: {e}")

        await session.commit()

        print(f"\n✅ Zapisano {saved_count} nowych artykułów")
        print(f"⏭️  Pominięto {skipped_count} istniejących")

        # Statystyki
        result = await session.execute(
            select(Article).where(Article.source_id == source.id)
        )
        total = len(result.scalars().all())
        print(f"📊 Łącznie artykułów z Radio 7: {total}")


if __name__ == "__main__":
    asyncio.run(test_radio7())
