"""
Test AI Processing Pipeline

Testuje:
1. ArticleProcessor - kategoryzacja artykułów
2. EventExtractor - ekstrakcja wydarzeń
3. Wyświetlanie wyników

Wymaga:
- Zainstalowane zależności (requirements.txt)
- Działającą bazę danych
- OPENAI_API_KEY w .env
"""
import asyncio
import sys
from pathlib import Path

# Dodaj backend do PYTHONPATH (żeby import src.* działał)
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.ai.article_processor import ArticleProcessor
from src.ai.event_extractor import EventExtractor
from src.database.schema import Article, Event


async def main():
    print("="*60)
    print("TEST: AI Processing Pipeline")
    print("="*60)

    # Sprawdź OPENAI_API_KEY
    if not settings.OPENAI_API_KEY:
        print("\n❌ ERROR: OPENAI_API_KEY not found in .env")
        print("Please add: OPENAI_API_KEY=sk-...")
        return

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Sprawdź czy są nieprzetwórzone artykuły
        unprocessed = await session.scalar(
            select(func.count(Article.id)).where(Article.processed == False)
        )

        if unprocessed == 0:
            print("\n⚠️  No unprocessed articles found")
            print("Run article scraping first or mark some articles as unprocessed")
            await engine.dispose()
            return

        print(f"\nFound {unprocessed} unprocessed articles")

        # Test 1: Przetwórz 5 artykułów
        print("\n" + "-"*60)
        print("[TEST 1] Article Processing - Kategoryzacja")
        print("-"*60)

        processor = ArticleProcessor()
        count = await processor.process_batch(session, batch_size=5, days_back=30)
        print(f"\n✓ Processed: {count} articles")

        # Sprawdź wyniki
        result = await session.execute(
            select(Article)
            .where(Article.processed == True)
            .order_by(Article.scraped_at.desc())
            .limit(5)
        )
        articles = result.scalars().all()

        print("\n" + "="*60)
        print("RESULTS - Przetwórzone artykuły:")
        print("="*60)
        for i, a in enumerate(articles, 1):
            print(f"\n[{i}] ID: {a.id}")
            print(f"    Title: {a.title[:80]}...")
            print(f"    Category: {a.category}")
            print(f"    Tags: {', '.join(a.tags) if a.tags else 'None'}")
            print(f"    Locations: {', '.join(a.location_mentioned) if a.location_mentioned else 'None'}")
            print(f"    Summary: {a.summary[:150]}...")

        # Test 2: Ekstrakcja wydarzeń
        print("\n" + "-"*60)
        print("[TEST 2] Event Extraction")
        print("-"*60)

        extractor = EventExtractor()
        event_count = await extractor.extract_from_recent(session, hours=168)  # Ostatni tydzień
        print(f"\n✓ Extracted: {event_count} events")

        if event_count > 0:
            # Pokaż wydarzenia
            events_result = await session.execute(
                select(Event)
                .order_by(Event.created_at.desc())
                .limit(3)
            )
            events = events_result.scalars().all()

            print("\n" + "="*60)
            print("RESULTS - Wyekstrahowane wydarzenia:")
            print("="*60)
            for i, e in enumerate(events, 1):
                print(f"\n[{i}] {e.title}")
                print(f"    Data: {e.event_date.strftime('%Y-%m-%d')} {e.event_time or ''}")
                print(f"    Lokalizacja: {e.location or 'Nie podano'}")
                print(f"    Opis: {e.short_description or 'Brak'}")
                print(f"    Źródło: {e.external_url}")

        # Statystyki końcowe
        total_articles = await session.scalar(select(func.count(Article.id)))
        processed_articles = await session.scalar(
            select(func.count(Article.id)).where(Article.processed == True)
        )
        total_events = await session.scalar(select(func.count(Event.id)))

        print("\n" + "="*60)
        print("STATISTICS")
        print("="*60)
        print(f"Total articles: {total_articles}")
        print(f"Processed articles: {processed_articles} ({processed_articles/total_articles*100:.1f}%)")
        print(f"Total events: {total_events}")
        print("="*60)

    await engine.dispose()
    print("\n✓ Test completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
