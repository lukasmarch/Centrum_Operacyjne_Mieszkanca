"""
Migration: Add local_places table for Gemini Maps grounding data

Tworzy tabelę local_places do przechowywania danych o lokalnych miejscach
(restauracje, kawiarnie, hotele, atrakcje) pobieranych z Gemini Maps API.

Użycie:
    cd backend && python -m scripts.migrations.add_local_places
    lub:
    python backend/scripts/migrations/add_local_places.py
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.config import settings


async def migrate():
    print("=" * 60)
    print("Migration: add local_places table")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # Check if table exists
        result = await conn.execute(text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'local_places'
        """))
        exists = result.fetchone()

        if not exists:
            print("Creating table: local_places...")
            await conn.execute(text("""
                CREATE TABLE local_places (
                    id SERIAL PRIMARY KEY,
                    place_id VARCHAR(200) NOT NULL UNIQUE,
                    name VARCHAR(300) NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    description VARCHAR(2000),
                    address VARCHAR(500),
                    maps_uri VARCHAR(500),
                    extra_data JSONB,
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    fetched_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            await conn.execute(text("CREATE INDEX idx_local_places_category ON local_places(category)"))
            await conn.execute(text("CREATE INDEX idx_local_places_fetched ON local_places(fetched_at)"))
            print("  ✓ Table created with indexes")
        else:
            print("  ✓ Table 'local_places' already exists")

    await engine.dispose()
    print("✅ Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
