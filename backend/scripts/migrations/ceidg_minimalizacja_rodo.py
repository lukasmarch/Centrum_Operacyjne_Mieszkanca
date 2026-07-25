"""
Migration: minimalizacja danych CEIDG + flaga sprzeciwu (sprint A, 2026-07-12)

RODO art. 5 (minimalizacja) i art. 21 (sprzeciw) — warunek monetyzacji
katalogu firm (raport strategiczny 07.07.2026, rozdz. 3.3):
  - ceidg_businesses.opted_out BOOLEAN NOT NULL DEFAULT FALSE — sprzeciw
    wobec przetwarzania: karta ukryta publicznie, flaga przeżywa re-sync
  - czyszczenie kolumn wykraczających poza cel katalogu:
    raw_data, spolki, obywatelstwa, adres_korespondencyjny → NULL
    (scraper/job już ich nie zapisuje)

Kontakt rejestrowy (email/www/telefon) zostawał wtedy w bazie na potrzeby
kontaktu B2B — wycofane 2026-07-25, patrz ceidg_usun_kontakt_rejestrowy.py.

Migracja jest idempotentna — można uruchamiać wielokrotnie.

Użycie:
    cd backend && python -m scripts.migrations.ceidg_minimalizacja_rodo
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
    print("Migration: CEIDG minimalizacja + opted_out")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # 1. Kolumna opted_out
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'ceidg_businesses' AND column_name = 'opted_out'
        """))
        if result.fetchone():
            print("• ceidg_businesses.opted_out już istnieje — pomijam")
        else:
            await conn.execute(text("""
                ALTER TABLE ceidg_businesses
                ADD COLUMN opted_out BOOLEAN NOT NULL DEFAULT FALSE
            """))
            print("✓ Dodano kolumnę ceidg_businesses.opted_out")

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_ceidg_opted_out
            ON ceidg_businesses (opted_out)
        """))
        print("✓ Indeks idx_ceidg_opted_out")

        # 2. Czyszczenie danych nadmiarowych
        result = await conn.execute(text("""
            UPDATE ceidg_businesses
            SET raw_data = NULL,
                spolki = NULL,
                obywatelstwa = NULL,
                adres_korespondencyjny = NULL
            WHERE raw_data IS NOT NULL
               OR spolki IS NOT NULL
               OR obywatelstwa IS NOT NULL
               OR adres_korespondencyjny IS NOT NULL
        """))
        print(f"✓ Wyczyszczono dane nadmiarowe w {result.rowcount} rekordach")

    await engine.dispose()
    print("=" * 60)
    print("Migracja zakończona.")


if __name__ == "__main__":
    asyncio.run(migrate())
