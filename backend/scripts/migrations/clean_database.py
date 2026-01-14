"""
Clean Database - Usuń dane testowe

Usuwa: articles, events, daily_summaries
Zostawia: sources, weather (infrastruktura)
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.database.schema import Article, Event, DailySummary


async def main():
    print("="*80)
    print("DATABASE CLEANUP")
    print("="*80)
    print("\nThis will DELETE:")
    print("  - All articles")
    print("  - All events")
    print("  - All daily summaries")
    print("\nThis will KEEP:")
    print("  - Sources (configuration)")
    print("  - Weather data")
    print("\n" + "="*80)

    response = input("\nAre you sure? Type 'YES' to continue: ")
    if response != 'YES':
        print("Aborted.")
        return

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            print("\n1. Deleting daily_summaries...")
            result = await session.execute(delete(DailySummary))
            await session.commit()
            print(f"   ✓ Deleted {result.rowcount} daily summaries")

            print("\n2. Deleting events...")
            result = await session.execute(delete(Event))
            await session.commit()
            print(f"   ✓ Deleted {result.rowcount} events")

            print("\n3. Deleting articles...")
            result = await session.execute(delete(Article))
            await session.commit()
            print(f"   ✓ Deleted {result.rowcount} articles")

            print("\n" + "="*80)
            print("✓ Database cleaned successfully!")
            print("="*80)
            print("\nNext steps:")
            print("  1. Run scrapers: python scripts/test_article_job.py")
            print("  2. Run AI processing: python scripts/test_ai_pipeline.py")
            print("  3. Generate summary: python scripts/test_daily_summary.py")

        except Exception as e:
            print(f"\n✗ ERROR: {e}")
            await session.rollback()
            raise

    await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nAborted by user")
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
