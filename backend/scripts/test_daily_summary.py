"""
Test Daily Summary Generator

Testuje:
1. SummaryGenerator - generowanie dziennego podsumowania
2. Wyświetlanie wyników

Wymaga:
- Zainstalowane zależności (requirements.txt)
- Działającą bazę danych z przetworzonymi artykułami
- OPENAI_API_KEY w .env
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Dodaj backend do PYTHONPATH
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.ai.summary_generator import SummaryGenerator
from src.database.schema import Article, Event, DailySummary, Weather


async def main():
    print("="*80)
    print("TEST: Daily Summary Generator")
    print("="*80)

    # Sprawdź OPENAI_API_KEY
    if not settings.OPENAI_API_KEY:
        print("\n❌ ERROR: OPENAI_API_KEY not found in .env")
        print("Please add: OPENAI_API_KEY=sk-...")
        return

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Sprawdź dane w bazie
        print("\n" + "-"*80)
        print("Database Status Check")
        print("-"*80)

        total_articles = await session.scalar(select(func.count(Article.id)))
        processed_articles = await session.scalar(
            select(func.count(Article.id)).where(Article.processed == True)
        )
        total_events = await session.scalar(select(func.count(Event.id)))
        weather_count = await session.scalar(select(func.count(Weather.id)))

        print(f"Total articles: {total_articles}")
        print(f"Processed articles: {processed_articles}")
        print(f"Total events: {total_events}")
        print(f"Weather records: {weather_count}")

        if processed_articles == 0:
            print("\n⚠️  No processed articles found")
            print("Run AI pipeline first: python scripts/test_ai_pipeline.py")
            await engine.dispose()
            return

        # Find the most recent date with processed articles
        print("\n" + "-"*80)
        print("Finding most recent processed articles...")
        print("-"*80)

        result = await session.execute(
            select(Article.scraped_at)
            .where(Article.processed == True)
            .order_by(Article.scraped_at.desc())
            .limit(1)
        )
        latest_article = result.scalar_one_or_none()

        if not latest_article:
            print("\n⚠️  No processed articles found")
            await engine.dispose()
            return

        # Use the date of the latest processed article
        target_date = latest_article.replace(hour=0, minute=0, second=0, microsecond=0)
        print(f"Latest article scraped: {latest_article}")
        print(f"Using target date: {target_date.date()}")

        # Test: Wygeneruj podsumowanie
        print("\n" + "-"*80)
        print("[TEST] Generating Daily Summary")
        print("-"*80)

        generator = SummaryGenerator()

        print(f"\nTarget date: {target_date.date()}")
        print("Generating summary (this may take 20-30 seconds)...\n")

        try:
            summary = await generator.generate_daily_summary(session, target_date)

            if summary:
                print("="*80)
                print("SUCCESS - Daily Summary Generated!")
                print("="*80)
                print(f"\nID: {summary.id}")
                print(f"Date: {summary.date.date()}")
                print(f"Generated at: {summary.generated_at}")
                print(f"\nHeadline:")
                print(f"  {summary.headline}")
                print(f"\nContent Preview:")

                # Display highlights
                highlights = summary.content.get('highlights', [])
                if highlights:
                    print(f"\nHighlights ({len(highlights)}):")
                    for i, h in enumerate(highlights, 1):
                        print(f"  {i}. {h}")

                # Display categories
                summary_by_cat = summary.content.get('summary_by_category', {})
                if summary_by_cat:
                    print(f"\nSummaries by Category ({len(summary_by_cat)}):")
                    for cat, text in summary_by_cat.items():
                        print(f"\n  [{cat}]")
                        print(f"  {text}")

                # Display events
                upcoming = summary.content.get('upcoming_events', [])
                if upcoming:
                    print(f"\nUpcoming Events ({len(upcoming)}):")
                    for event in upcoming[:5]:
                        print(f"  • {event}")

                # Display weather
                weather_summary = summary.content.get('weather_summary')
                if weather_summary:
                    print(f"\nWeather Summary:")
                    print(f"  {weather_summary}")

                # Display stats
                stats = summary.content.get('stats', {})
                if stats:
                    print(f"\nStatistics:")
                    print(f"  Articles processed: {stats.get('total_articles', 0)}")
                    print(f"  Categories: {stats.get('categories_count', 0)}")
                    print(f"  Events: {stats.get('events_count', 0)}")

            else:
                print("\n⚠️  No summary generated")
                print("Possible reasons:")
                print("  - Summary for this date already exists")
                print("  - No processed articles found for target date")

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

        # Check all summaries in DB
        print("\n" + "-"*80)
        print("All Summaries in Database")
        print("-"*80)

        result = await session.execute(
            select(DailySummary)
            .order_by(DailySummary.date.desc())
        )
        all_summaries = result.scalars().all()

        if all_summaries:
            print(f"\nTotal summaries: {len(all_summaries)}\n")
            for s in all_summaries:
                print(f"  • {s.date.date()} - {s.headline[:60]}...")
        else:
            print("\nNo summaries in database yet")

        print("\n" + "="*80)

    await engine.dispose()
    print("\n✓ Test completed!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
