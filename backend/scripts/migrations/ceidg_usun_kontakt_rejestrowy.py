"""
Migration: usunięcie kontaktu rejestrowego z CEIDG (2026-07-25)

Audyt minimalizacji wykazał, że kolumny email/telefon/www w ceidg_businesses
nie były odczytywane przez żaden fragment aplikacji — kontakt w katalogu
pochodzi wyłącznie z business_profiles, czyli od firmy, która przejęła
wizytówkę (zgoda). Przechowywanie 99 adresów e-mail i 103 telefonów bez
realizowanego celu jest niezgodne z RODO art. 5 ust. 1 lit. c, a marketing
B2B na tych danych i tak wymagałby zgody (art. 10 uśude, art. 172 PT).

Decyzja: kolumny czyścimy i przestajemy zapisywać (extract_business_data).
Same kolumny zostają w schemacie — puste — żeby nie przepisywać modelu.

Migracja jest idempotentna — można uruchamiać wielokrotnie.

Użycie:
    cd backend && python -m scripts.migrations.ceidg_usun_kontakt_rejestrowy
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
    print("Migration: CEIDG — usunięcie kontaktu rejestrowego")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        result = await conn.execute(text("""
            UPDATE ceidg_businesses
            SET email = NULL,
                telefon = NULL,
                www = NULL
            WHERE email IS NOT NULL
               OR telefon IS NOT NULL
               OR www IS NOT NULL
        """))
        print(f"✓ Wyczyszczono kontakt rejestrowy w {result.rowcount} rekordach")

        check = await conn.execute(text("""
            SELECT count(email) AS email, count(telefon) AS telefon, count(www) AS www
            FROM ceidg_businesses
        """))
        row = check.fetchone()
        print(f"✓ Pozostało: email={row[0]}, telefon={row[1]}, www={row[2]}")

    await engine.dispose()
    print("=" * 60)
    print("Migracja zakończona.")


if __name__ == "__main__":
    asyncio.run(migrate())
