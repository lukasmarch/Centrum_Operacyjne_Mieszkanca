"""
Migration: Disable legally risky / dead content sources (Etap 0 — plan z 29.06.2026)

Wyłącza źródła zgodnie z decyzją asymetryczną planu prawnego:
  - id 13: Facebook — Panorama Regionu  → wysokie ryzyko prawne (wizerunek ofiar,
           tragedie, zniesławienie), tylko 2% treści dotyczy Gminy Rybno
  - id 10: Gazeta Olsztyńska (RSS)      → źródło martwe od 04.2026 (błąd 403)

Źródła NIE są usuwane — istniejące artykuły pozostają w bazie, scraper
pomija źródła ze statusem 'disabled'. Skrypt jest idempotentny.

Użycie:
    cd backend && python -m scripts.migrations.disable_risky_sources
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.config import settings


# (id, oczekiwana nazwa — walidacja, żeby nie wyłączyć złego źródła)
SOURCES_TO_DISABLE = [
    (13, "Panorama"),
    (10, "Olszty"),
]


async def migrate():
    print("=" * 60)
    print("Migration: disable risky/dead sources (Panorama, Gazeta Olsztyńska)")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        for source_id, name_fragment in SOURCES_TO_DISABLE:
            result = await conn.execute(text(
                "SELECT id, name, status FROM sources WHERE id = :id"
            ), {"id": source_id})
            row = result.fetchone()

            if row is None:
                print(f"– Source id={source_id} not found (lokalna baza?) – skipping")
                continue

            if name_fragment.lower() not in row.name.lower():
                print(f"✗ Source id={source_id} is '{row.name}' — expected name containing "
                      f"'{name_fragment}'. NOT disabling (id mismatch safety check).")
                continue

            if row.status == "disabled":
                print(f"✓ '{row.name}' (id={source_id}) already disabled – skipping")
                continue

            await conn.execute(text(
                "UPDATE sources SET status = 'disabled' WHERE id = :id"
            ), {"id": source_id})
            print(f"✓ Disabled '{row.name}' (id={source_id}, was: {row.status})")

    await engine.dispose()
    print("=" * 60)
    print("Migration complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(migrate())
