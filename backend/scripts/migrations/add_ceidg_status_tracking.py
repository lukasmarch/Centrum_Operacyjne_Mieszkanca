"""
Migration: śledzenie zmian statusu firm CEIDG

Dodaje do ceidg_businesses kolumny previous_status i status_changed_at —
bez nich nie da się powiedzieć, KIEDY firma została zawieszona lub wykreślona,
a to jest treść miesięcznego „Radaru rynku lokalnego" dla planu Firma lokalna.
Idempotentna — można uruchamiać wielokrotnie.

Użycie:
    cd backend && python -m scripts.migrations.add_ceidg_status_tracking
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
        await conn.execute(text(
            "ALTER TABLE ceidg_businesses "
            "ADD COLUMN IF NOT EXISTS previous_status VARCHAR(30) NULL"
        ))
        await conn.execute(text(
            "ALTER TABLE ceidg_businesses "
            "ADD COLUMN IF NOT EXISTS status_changed_at TIMESTAMP NULL"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_ceidg_status_changed_at "
            "ON ceidg_businesses (status_changed_at)"
        ))

        result = await conn.execute(text(
            "SELECT count(*) FROM ceidg_businesses"
        ))
        total = result.scalar() or 0

    await engine.dispose()
    print(f"✅ Migracja OK — ceidg_businesses: {total} firm, kolumny statusu gotowe")


if __name__ == "__main__":
    asyncio.run(migrate())
