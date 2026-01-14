"""
Remove duplicate events from database

Finds and removes duplicate events (same title + event_date + location),
keeping only the oldest entry (first created).

Run this BEFORE adding unique constraint if duplicates exist.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select, func
from src.config import settings
from src.database.schema import Event


async def remove_duplicates():
    """Find and remove duplicate events"""
    print("="*80)
    print("Finding and Removing Duplicate Events")
    print("="*80)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Find duplicates using SQL
        print("\n🔍 Searching for duplicate events...")

        result = await session.execute(text("""
            SELECT title, event_date, location, COUNT(*) as count
            FROM events
            GROUP BY title, event_date, location
            HAVING COUNT(*) > 1
        """))

        duplicates = result.all()

        if not duplicates:
            print("✓ No duplicate events found!")
            await engine.dispose()
            return

        print(f"\n⚠️  Found {len(duplicates)} groups of duplicate events:\n")

        total_removed = 0

        for title, event_date, location, count in duplicates:
            print(f"  • {title[:50]}... on {event_date.date()} at {location} ({count} copies)")

            # Get all events with this title + date + location
            result = await session.execute(
                select(Event)
                .where(
                    Event.title == title,
                    Event.event_date == event_date,
                    Event.location == location
                )
                .order_by(Event.created_at.asc())  # Keep oldest
            )
            events = result.scalars().all()

            # Keep first (oldest), delete rest
            to_delete = events[1:]

            for event in to_delete:
                await session.delete(event)
                total_removed += 1

        # Commit changes
        await session.commit()

        print(f"\n✅ Removed {total_removed} duplicate events!")
        print("✓ Kept oldest entry for each duplicate group")

    await engine.dispose()
    print("\n✓ Cleanup completed!")


if __name__ == "__main__":
    try:
        asyncio.run(remove_duplicates())
    except KeyboardInterrupt:
        print("\n\n⚠️  Cleanup interrupted by user")
    except Exception as e:
        print(f"\n❌ Cleanup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
