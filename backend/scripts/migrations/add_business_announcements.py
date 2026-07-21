"""
Migration: Ogłoszenia firm (Radar Lokalnego Biznesu) + snapshot raportu miesięcznego

Tworzy tabelę business_announcements (ogłoszenia/okazje planu Firma lokalna)
i dodaje kolumnę views_last_report do business_profiles (delta wyświetleń
do raportu miesięcznego). Idempotentna — można uruchamiać wielokrotnie.

Użycie:
    cd backend && python -m scripts.migrations.add_business_announcements
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
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS business_announcements (
                id SERIAL PRIMARY KEY,
                business_id INTEGER NOT NULL REFERENCES ceidg_businesses(id),
                type VARCHAR(20) NOT NULL DEFAULT 'ogloszenie',
                title VARCHAR(120) NOT NULL,
                body VARCHAR(500) NOT NULL,
                valid_until TIMESTAMP NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_business_announcements_business_id "
            "ON business_announcements (business_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_business_announcements_active_valid "
            "ON business_announcements (is_active, valid_until)"
        ))
        await conn.execute(text(
            "ALTER TABLE business_profiles "
            "ADD COLUMN IF NOT EXISTS views_last_report INTEGER NOT NULL DEFAULT 0"
        ))
    await engine.dispose()
    print("✅ business_announcements + business_profiles.views_last_report gotowe")


if __name__ == "__main__":
    asyncio.run(migrate())
