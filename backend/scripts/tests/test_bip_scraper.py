"""
Test: BIP Gminy Rybno Scraper (Sprint 5D)

Uruchamia scraper BIP ręcznie i sprawdza wyniki.

Użycie:
    cd backend && python -u scripts/tests/test_bip_scraper.py
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from src.config import settings
from src.database.schema import Source, Article
from src.scrapers.bip_rybno import BipRybnoScraper


async def test_bip():
    print("=" * 60)
    print("Test: BIP Gminy Rybno Scraper")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Znajdź source BIP
        result = await session.execute(
            select(Source).where(Source.name == "BIP Gminy Rybno")
        )
        source = result.scalar_one_or_none()

        if not source:
            print("❌ Source 'BIP Gminy Rybno' not found in database!")
            print("Run setup script first: python scripts/setup/add_bip_source.py")
            return

        print(f"✓ Source found: id={source.id}, url={source.url}")
        print(f"  Config: {source.scraping_config}")
        print()

        # Uruchom scraper (tylko 1 strona dla testu)
        config = source.scraping_config or {}
        config["max_pages_per_run"] = 1  # Ogranicz do 1 strony podczas testu
        config["download_pdfs"] = False   # Pomiń PDF podczas testu

        scraper = BipRybnoScraper(source_id=source.id, config=config)

        print("Starting scraper (1 page, no PDFs)...")
        saved_ids = await scraper.scrape_bip(session)

        print(f"\n✓ Saved {len(saved_ids)} articles")

        if saved_ids:
            # Pokaż przykładowe artykuły
            result = await session.execute(
                select(Article)
                .where(Article.source_id == source.id)
                .order_by(Article.scraped_at.desc())
                .limit(5)
            )
            articles = result.scalars().all()

            print("\nRecent articles:")
            for art in articles:
                print(f"  - [{art.external_id}] {art.title[:60]}")
                print(f"    URL: {art.url}")
                print(f"    Published: {art.published_at}")
                print(f"    Content: {'YES (' + str(len(art.content)) + ' chars)' if art.content else 'NO'}")
                print()

        # Stats
        result = await session.execute(
            select(Article).where(Article.source_id == source.id)
        )
        total = len(result.scalars().all())
        print(f"Total BIP articles in DB: {total}")

    await engine.dispose()
    print("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(test_bip())
