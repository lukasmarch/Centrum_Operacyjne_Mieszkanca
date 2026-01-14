"""
Dodaj nowe źródło RSS do bazy danych

Usage:
    python scripts/add_rss_source.py
"""
import sys
import asyncio
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from src.database.connection import async_session
from src.database.schema import Source


async def add_rss_source():
    """Dodaj Nasze Miasto Działdowo RSS do bazy"""

    async with async_session() as session:
        # Sprawdź czy źródło już istnieje
        from sqlmodel import select
        result = await session.execute(
            select(Source).where(Source.name == "Nasze Miasto Działdowo")
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"✓ Źródło 'Nasze Miasto Działdowo' już istnieje (ID: {existing.id})")
            print(f"  URL: {existing.url}")
            print(f"  Status: {existing.status}")
            return

        # Dodaj nowe źródło
        source = Source(
            name="Nasze Miasto Działdowo",
            type="rss",
            url="https://dzialdowo.naszemiasto.pl/rss/",
            status="active",
            scraping_config={
                "format": "rss",
                "description": "Portal lokalny - wiadomości z Działdowa",
                "scraper_class": "RSSFeedScraper"
            }
        )

        session.add(source)
        await session.commit()
        await session.refresh(source)

        print("=" * 60)
        print("✅ Dodano nowe źródło RSS:")
        print(f"  ID: {source.id}")
        print(f"  Nazwa: {source.name}")
        print(f"  URL: {source.url}")
        print(f"  Type: {source.type}")
        print(f"  Status: {source.status}")
        print("=" * 60)
        print("\nKolejne kroki:")
        print("1. Zainstaluj feedparser: pip install feedparser")
        print("2. Przetestuj scraper: python scripts/test_rss_scraper.py")
        print("3. Uruchom scheduler lub ręczny scraping")


if __name__ == "__main__":
    asyncio.run(add_rss_source())
