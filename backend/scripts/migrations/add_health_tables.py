"""
Migration: Add clinic_schedules + pharmacy_duties tables

Tworzy tabele dla modulu zdrowotnego (harmonogram poradni + dyzury aptek).

Uzycie:
    cd backend && python -m scripts.migrations.add_health_tables
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
    print("Migration: add clinic_schedules + pharmacy_duties tables")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # 1. clinic_schedules
        result = await conn.execute(text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'clinic_schedules'
        """))
        if not result.fetchone():
            print("Creating table: clinic_schedules...")
            await conn.execute(text("""
                CREATE TABLE clinic_schedules (
                    id SERIAL PRIMARY KEY,
                    clinic_name VARCHAR(100) NOT NULL,
                    doctor_name VARCHAR(200),
                    doctor_role VARCHAR(100),
                    day_of_week INTEGER,
                    specific_date DATE,
                    hours_from VARCHAR(10) NOT NULL,
                    hours_to VARCHAR(10) NOT NULL,
                    notes VARCHAR(500),
                    source_url VARCHAR(500) NOT NULL,
                    fetched_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            await conn.execute(text("CREATE INDEX idx_clinic_name ON clinic_schedules(clinic_name)"))
            await conn.execute(text("CREATE INDEX idx_clinic_day ON clinic_schedules(clinic_name, day_of_week)"))
            print("  ✓ Table clinic_schedules created")
        else:
            print("  ✓ Table clinic_schedules already exists")

        # 2. pharmacy_duties
        result = await conn.execute(text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'pharmacy_duties'
        """))
        if not result.fetchone():
            print("Creating table: pharmacy_duties...")
            await conn.execute(text("""
                CREATE TABLE pharmacy_duties (
                    id SERIAL PRIMARY KEY,
                    pharmacy_name VARCHAR(200) NOT NULL,
                    address VARCHAR(300) NOT NULL,
                    phone VARCHAR(50),
                    duty_type VARCHAR(20) NOT NULL,
                    day_of_week INTEGER,
                    specific_dates VARCHAR[],
                    hours_from VARCHAR(10) NOT NULL,
                    hours_to VARCHAR(10) NOT NULL,
                    valid_year INTEGER NOT NULL,
                    notes VARCHAR(500),
                    fetched_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """))
            await conn.execute(text("CREATE INDEX idx_pharmacy_name ON pharmacy_duties(pharmacy_name)"))
            await conn.execute(text("CREATE INDEX idx_pharmacy_year ON pharmacy_duties(pharmacy_name, valid_year)"))
            print("  ✓ Table pharmacy_duties created")
        else:
            print("  ✓ Table pharmacy_duties already exists")

    await engine.dispose()
    print("\n✅ Migration complete!")


if __name__ == "__main__":
    asyncio.run(migrate())
