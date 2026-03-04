"""
Migration: Add anonymous_chat_usage table

Tworzy tabelę do śledzenia użycia chatu przez anonimowych użytkowników (po IP).
Używana do rate limitingu: 3 pytania/dzień dla niezalogowanych.

Użycie:
    cd backend && python -m scripts.migrations.add_anonymous_chat_usage
    lub:
    python backend/scripts/migrations/add_anonymous_chat_usage.py
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
    print("Migration: add anonymous_chat_usage table")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'anonymous_chat_usage'
        """))
        exists = result.fetchone()

        if not exists:
            print("Creating table: anonymous_chat_usage...")
            await conn.execute(text("""
                CREATE TABLE anonymous_chat_usage (
                    id SERIAL PRIMARY KEY,
                    ip_address TEXT NOT NULL,
                    usage_date DATE NOT NULL,
                    count INTEGER DEFAULT 0,
                    UNIQUE(ip_address, usage_date)
                )
            """))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_anon_ip_date ON anonymous_chat_usage(ip_address, usage_date)"
            ))
            print("✓ Table created")
        else:
            print("✓ Table 'anonymous_chat_usage' already exists")

    await engine.dispose()
    print("✅ Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
