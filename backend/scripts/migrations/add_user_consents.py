"""
Migration: Add RODO consent columns to users table (Etap 0 — zgodność prawna)

Dodaje kolumny rozliczalności zgód (RODO art. 7):
  - consent_terms_at        TIMESTAMP  — kiedy zaakceptowano regulamin + politykę prywatności
  - consent_marketing       BOOLEAN    — zgoda marketingowa (newsletter, oferty)
  - consent_privacy_version VARCHAR(20) — wersja zaakceptowanych dokumentów

Migracja jest idempotentna — można uruchamiać wielokrotnie.

Użycie:
    cd backend && python -m scripts.migrations.add_user_consents
    lub:
    python backend/scripts/migrations/add_user_consents.py
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.config import settings


COLUMNS = [
    ("consent_terms_at", "TIMESTAMP"),
    ("consent_marketing", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("consent_privacy_version", "VARCHAR(20)"),
]


async def migrate():
    print("=" * 60)
    print("Migration: add RODO consent columns to users")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        for name, ddl in COLUMNS:
            result = await conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'users' AND column_name = :col
            """), {"col": name})
            if result.fetchone():
                print(f"✓ Column 'users.{name}' already exists – skipping")
            else:
                print(f"Adding column: users.{name}...")
                await conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {ddl}"))
                print(f"✓ Added users.{name}")

    await engine.dispose()
    print("=" * 60)
    print("Migration complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(migrate())
