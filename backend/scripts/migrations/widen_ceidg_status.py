"""
Migration: status firmy CEIDG nie mieści się w 30 znakach (2026-09-14)

13.09.2026 `ceidg_sync` padł na wpisie „RADOSŁAW DEPTUŁA DACHY":

    value too long for type character varying(30)
    ... 'OCZEKUJE_NA_ROZPOCZECIE_DZIALANOSCI'  ← 35 znaków

Kolumna została skrojona pod TRZY wartości, które akurat znaliśmy w dniu jej
powstania (komentarz przy `CEIDGBusiness.status` do dziś wymienia „AKTYWNY,
ZAWIESZONY, WYKRESLONY"). Słownik statusów rejestru jest jednak OTWARTY —
w bazie stoi już czwarta wartość, `WYLACZNIE_W_FORMIE_SPOLKI` (25 znaków),
która zmieściła się wyłącznie przypadkiem.

⚠️ Skutek był szerszy niż jeden pominięty wiersz: `ceidg_job` zapisuje cały
przebieg w JEDNEJ transakcji, więc pojedynczy felerny rekord wycofał komplet —
nowe firmy, zmiany statusu i wykreślenia. `ceidg_sync_stats.sync_status`
stanął na `failed`, a sync padał CO NIEDZIELĘ, dopóki ta firma jest w rejestrze.
Ta sama lekcja co przy kategoryzacji 2.09: felerny rekord nie może zabierać
całego przebiegu.

60 znaków, nie 36: najdłuższa znana wartość ma 35, a celem nie jest zmieszczenie
DZISIEJSZEGO słownika, tylko przestanie traktować cudzy rejestr jak stałą w kodzie.

Rozszerzenie kolumny jest zgodne wstecz (stary kod nie zauważy), więc migracja
może iść na produkcję przed kodem — zgodnie z regułą wdrożeniową projektu.

Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.widen_ceidg_status
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings

NEW_LENGTH = 60


async def migrate():
    print("=" * 60)
    print("Migration: ceidg_businesses.status → VARCHAR(60)")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        for column in ("status", "previous_status"):
            current = await conn.scalar(text("""
                SELECT character_maximum_length
                FROM information_schema.columns
                WHERE table_name = 'ceidg_businesses' AND column_name = :col
            """), {"col": column})

            if current is None:
                print(f"⚠️  Kolumny {column} nie ma — pomijam")
                continue
            if current >= NEW_LENGTH:
                print(f"✓ {column}: już VARCHAR({current}) — bez zmian")
                continue

            await conn.execute(text(
                f"ALTER TABLE ceidg_businesses "
                f"ALTER COLUMN {column} TYPE VARCHAR({NEW_LENGTH})"
            ))
            print(f"✓ {column}: VARCHAR({current}) → VARCHAR({NEW_LENGTH})")

        rows = await conn.execute(text("""
            SELECT status, count(*) FROM ceidg_businesses
            GROUP BY status ORDER BY 2 DESC
        """))
        print("\nStatusy w bazie:")
        for status, count in rows:
            print(f"  {len(status or ''):>3} zn.  {status:<40} {count}")

    await engine.dispose()
    print("\n✅ Migracja zakończona")


if __name__ == "__main__":
    asyncio.run(migrate())
