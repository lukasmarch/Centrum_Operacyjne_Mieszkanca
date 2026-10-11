"""
Migration: próba ≠ sukces dla źródeł (2026-10-11)

Audyt 11.10.2026 (F-019): `sources.last_scraped` ustawiał się po KAŻDYM
przebiegu, także wtedy, gdy scraper połknął błąd i zwrócił pustą listę.
BIP miał „zeskanowane dziś” przy ostatnim artykule z 21.08 (od lipca 403),
a agent i raport źródeł nie miały jak tego odróżnić od ciszy.

Nowe kolumny (addytywne — stary kod ich nie zauważy, więc migracja idzie na
produkcję PRZED kodem, zgodnie z regułą wdrożeniową projektu):
  - `last_success_at` — ostatni przebieg, w którym źródło ODPOWIEDZIAŁO
    (także bez nowych wpisów: cisza profilu to poprawny stan, nie awaria)
  - `last_error`, `last_error_at` — ostatni błąd i kiedy

`last_scraped` zostaje: od teraz znaczy „ostatnia PRÓBA”.

Bez wypełniania wstecz: nie wiemy, które dawne `last_scraped` były sukcesem.
Pierwszy przebieg po wdrożeniu kodu ustawi stan każdego aktywnego źródła.

Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.add_source_freshness
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings

COLUMNS = (
    ("last_success_at", "TIMESTAMP"),
    ("last_error", "VARCHAR(300)"),
    ("last_error_at", "TIMESTAMP"),
)


async def migrate():
    print("=" * 60)
    print("Migration: sources.last_success_at / last_error / last_error_at")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        for name, sql_type in COLUMNS:
            await conn.execute(text(f"ALTER TABLE sources ADD COLUMN IF NOT EXISTS {name} {sql_type}"))
            print(f"✓ sources.{name} {sql_type}")
    await engine.dispose()
    print("\n✅ Migracja zakończona")


if __name__ == "__main__":
    asyncio.run(migrate())
