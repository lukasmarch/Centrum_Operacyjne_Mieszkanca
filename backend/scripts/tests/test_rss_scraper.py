"""
Test RSS Scraper

Testuje pobieranie artykułów z kanału RSS Nasze Miasto Działdowo
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


async def test_rss_scraper():
    """Test RSS scraper"""

    async with async_session() as session:
        # Pobierz źródło RSS
        result = await session.execute(
            select(Source).where(Source.name == "Nasze Miasto Działdowo")
        )
        source = result.scalar_one_or_none()

        if not source:
            print("❌ Źródło 'Nasze Miasto Działdowo' nie istnieje w bazie!")
            print("   Uruchom: python scripts/add_rss_source.py")
            return

        print("=" * 60)
        print(f"Testing RSS Scraper: {source.name}")
        print(f"URL: {source.url}")
        print("=" * 60)

        # Inicjalizuj scraper
        scraper = RSSFeedScraper(source.id, source.scraping_config or {})

        # Scrape artykuły
        print("\n📡 Fetching RSS feed...")
        articles = await scraper.scrape_feed(source.url)

        if not articles:
            print("❌ No articles found!")
            return

        print(f"✅ Found {len(articles)} articles\n")

        # Pokaż przykładowe artykuły
        print("=" * 60)
        print("SAMPLE ARTICLES (first 3):")
        print("=" * 60)

        for i, article in enumerate(articles[:3], 1):
            print(f"\n[{i}] {article['title']}")
            print(f"    URL: {article['url']}")
            print(f"    Published: {article.get('published_at', 'N/A')}")
            print(f"    Author: {article.get('author', 'N/A')}")
            print(f"    Image: {article.get('image_url', 'N/A')}")
            if article.get('summary'):
                summary = article['summary'][:150]
                print(f"    Summary: {summary}...")

        # Zapisz do bazy (opcjonalnie)
        print("\n" + "=" * 60)
        save = input("Zapisać artykuły do bazy? (y/n): ").strip().lower()

        if save == 'y':
            saved_count = 0
            skipped_count = 0

            for article_data in articles:
                try:
                    # Sprawdź czy artykuł już istnieje (po URL)
                    result = await session.execute(
                        select(Article).where(Article.url == article_data['url'])
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        skipped_count += 1
                        continue

                    # Utwórz nowy artykuł
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
                    print(f"⚠️  Error saving article: {e}")

            await session.commit()

            print(f"\n✅ Zapisano {saved_count} nowych artykułów")
            print(f"⏭️  Pominięto {skipped_count} istniejących artykułów")

            # Pokaż statystyki
            result = await session.execute(
                select(Article).where(Article.source_id == source.id)
            )
            total = len(result.scalars().all())
            print(f"📊 Łącznie artykułów z tego źródła: {total}")

        else:
            print("⏭️  Pominięto zapisywanie do bazy")


if __name__ == "__main__":
    asyncio.run(test_rss_scraper())
