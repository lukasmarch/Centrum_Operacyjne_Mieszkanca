"""
Add unique constraint to events table to prevent duplicate events

This script adds a composite unique index on (title, event_date, location)
to prevent duplicate event entries.

Run this ONCE after updating schema.py
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.config import settings


async def add_unique_constraint():
    """Add unique constraint to events table"""
    print("="*80)
    print("Adding unique constraint to events table")
    print("="*80)

    engine = create_async_engine(settings.DATABASE_URL, echo=True)

    async with engine.begin() as conn:
        # Check if index already exists
        result = await conn.execute(text("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'events' AND indexname = 'idx_event_unique'
        """))
        existing = result.first()

        if existing:
            print("\n✓ Index 'idx_event_unique' already exists - skipping")
            await engine.dispose()
            return

        print("\n📝 Creating unique index on (title, event_date, location)...")

        try:
            # Create unique index
            await conn.execute(text("""
                CREATE UNIQUE INDEX idx_event_unique
                ON events (title, event_date, location)
            """))

            print("✅ SUCCESS - Unique constraint added!")
            print("\nThe events table now prevents duplicate entries with:")
            print("  - Same title")
            print("  - Same event_date")
            print("  - Same location")

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            print("\nPossible causes:")
            print("  - Duplicate events already exist in the database")
            print("  - Database connection issues")
            print("\nTo fix duplicates, run:")
            print("  python scripts/remove_duplicate_events.py")
            raise

    await engine.dispose()
    print("\n✓ Migration completed!")


if __name__ == "__main__":
    try:
        asyncio.run(add_unique_constraint())
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
