"""
Migration: wizytówki firm — tabela business_profiles (sprint B, 2026-07-12)

Model 3 poziomów wizytówki (scenariusz biznesowy z 12.07.2026):
  rejestrowa (brak profilu) → przejęta (claim_status=verified, kontakt od firmy
  = zgoda) → Firma lokalna (is_premium, 49 zł/mc, w MVP włączane przez admina).

Migracja jest idempotentna — można uruchamiać wielokrotnie.

Użycie:
    cd backend && python -m scripts.migrations.add_business_profiles
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
    print("Migration: business_profiles (wizytówki)")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS business_profiles (
                id SERIAL PRIMARY KEY,
                business_id INTEGER NOT NULL UNIQUE REFERENCES ceidg_businesses(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                claim_status VARCHAR(20) NOT NULL DEFAULT 'pending',
                claim_note VARCHAR(500),
                description VARCHAR(600),
                telefon VARCHAR(50),
                email VARCHAR(255),
                www VARCHAR(500),
                godziny VARCHAR(200),
                logo_url VARCHAR(500),
                is_premium BOOLEAN NOT NULL DEFAULT FALSE,
                premium_until TIMESTAMP,
                views_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                verified_at TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        print("✓ Tabela business_profiles")

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_bprofiles_user ON business_profiles (user_id)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_bprofiles_premium ON business_profiles (is_premium)
        """))
        print("✓ Indeksy")

    await engine.dispose()
    print("=" * 60)
    print("Migracja zakończona.")


if __name__ == "__main__":
    asyncio.run(migrate())
