"""
Test Places Job — ręczne uruchomienie Gemini Maps grounding
Pobiera miejsca dla wszystkich 6 kategorii i zapisuje do local_places.

Użycie:
    cd backend && python -u scripts/tests/aktualny_pipeline/test_places_job.py
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_path))

from src.scheduler.places_job import run_places_job_async


async def main():
    print("=" * 60)
    print("TEST: Places Job (Gemini Maps grounding)")
    print("=" * 60)
    await run_places_job_async()

    # Verify: read back from DB
    print("\n" + "=" * 60)
    print("VERIFICATION: reading local_places from DB")
    print("=" * 60)

    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    from src.config import settings

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Count per category
        result = await session.execute(text("""
            SELECT category, COUNT(*) as cnt
            FROM local_places
            WHERE active = TRUE
            GROUP BY category
            ORDER BY category
        """))
        rows = result.fetchall()
        total = 0
        for row in rows:
            print(f"  {row[0]}: {row[1]} miejsc")
            total += row[1]
        print(f"\n  TOTAL: {total} miejsc w bazie")

        # Show sample places
        print("\n--- Przykładowe miejsca ---")
        result = await session.execute(text("""
            SELECT name, category, address, maps_uri
            FROM local_places
            WHERE active = TRUE
            ORDER BY category, name
            LIMIT 10
        """))
        for row in result:
            addr = f" | {row[2]}" if row[2] else ""
            maps = f" | {row[3]}" if row[3] else ""
            print(f"  [{row[1]}] {row[0]}{addr}{maps}")

    await engine.dispose()
    print("\n✅ Test complete!")


if __name__ == "__main__":
    asyncio.run(main())
