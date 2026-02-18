"""
Migration: Add push_subscriptions table (Sprint 5C)

Tworzy tabelę push_subscriptions dla Web Push Notifications.
Uruchom raz po aktualizacji schema.py.

Użycie:
    cd backend && python -m scripts.migrations.add_push_subscriptions
    lub:
    python backend/scripts/migrations/add_push_subscriptions.py
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
    print("Migration: add push_subscriptions table")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # Sprawdź czy tabela już istnieje
        result = await conn.execute(text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'push_subscriptions'
        """))
        exists = result.fetchone()

        if exists:
            print("✓ Table 'push_subscriptions' already exists – skipping")
        else:
            print("Creating table: push_subscriptions...")
            await conn.execute(text("""
                CREATE TABLE push_subscriptions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    email VARCHAR(255),
                    endpoint VARCHAR(1000) NOT NULL UNIQUE,
                    p256dh VARCHAR(200) NOT NULL,
                    auth VARCHAR(100) NOT NULL,
                    categories JSONB NOT NULL DEFAULT '[]',
                    user_agent VARCHAR(500),
                    active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    last_used_at TIMESTAMP
                )
            """))
            await conn.execute(text("""
                CREATE INDEX idx_push_subscriptions_user_id ON push_subscriptions(user_id)
            """))
            await conn.execute(text("""
                CREATE INDEX idx_push_subscriptions_endpoint ON push_subscriptions(endpoint)
            """))
            await conn.execute(text("""
                CREATE INDEX idx_push_subscriptions_active ON push_subscriptions(active)
            """))
            print("✓ Table 'push_subscriptions' created")

    await engine.dispose()
    print("\n✅ Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
