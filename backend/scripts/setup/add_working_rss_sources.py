"""
Dodaj działające RSS feeds do bazy danych
"""
import sys
import asyncio
from pathlib import Path

backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from src.database.connection import async_session
from src.database.schema import Source
from sqlmodel import select


async def add_rss_sources():
    """Dodaj Radio 7 i Gazetę Olsztyńską"""

    sources_to_add = [
        {
            "name": "Radio 7 Działdowo (RSS)",
            "type": "rss",
            "url": "https://radio7.pl/rss",
            "description": "Lokalne radio - wiadomości z Działdowa i powiatu"
        },
        {
            "name": "Gazeta Olsztyńska (RSS)",
            "type": "rss",
            "url": "https://gazetaolsztynska.pl/rss",
            "description": "Portal regionalny - sekcja Działdowo"
        }
    ]

    async with async_session() as session:
        added = []
        existing = []

        for source_data in sources_to_add:
            # Sprawdź czy istnieje
            result = await session.execute(
                select(Source).where(Source.name == source_data['name'])
            )
            source = result.scalar_one_or_none()

            if source:
                existing.append(source.name)
                continue

            # Dodaj nowe
            new_source = Source(
                name=source_data['name'],
                type=source_data['type'],
                url=source_data['url'],
                status="active",
                scraping_config={
                    "format": "rss",
                    "description": source_data['description'],
                    "scraper_class": "RSSFeedScraper"
                }
            )

            session.add(new_source)
            added.append(source_data['name'])

        if added:
            await session.commit()

        # Pokaż wyniki
        print("=" * 70)
        print("DODAWANIE ŹRÓDEŁ RSS")
        print("=" * 70)

        if added:
            print(f"\n✅ Dodano {len(added)} nowych źródeł:")
            for name in added:
                print(f"   - {name}")

        if existing:
            print(f"\n⏭️  Pominięto {len(existing)} istniejących źródeł:")
            for name in existing:
                print(f"   - {name}")

        # Pokaż wszystkie źródła RSS
        result = await session.execute(
            select(Source).where(Source.type == "rss")
        )
        all_rss = result.scalars().all()

        print(f"\n📊 Łącznie źródeł RSS w bazie: {len(all_rss)}")
        for source in all_rss:
            print(f"   [{source.id}] {source.name}")
            print(f"       URL: {source.url}")
            print(f"       Status: {source.status}")


if __name__ == "__main__":
    asyncio.run(add_rss_sources())
