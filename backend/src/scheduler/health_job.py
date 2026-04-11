"""
Health Schedule Update Job - Database-First Architecture

Uruchamiany co poniedziałek o 6:30 AM.
Scrapuje harmonogramy poradni SPGZOZ Rybno i dyżury aptek,
zapisuje do tabel clinic_schedules i pharmacy_duties.
"""
import asyncio
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.integrations.health_scraper import HealthScraper
from src.utils.logger import setup_logger

logger = setup_logger("HealthJob")


async def run_health_job_async():
    """Async version - scrape clinics + pharmacies, full replace in DB."""
    logger.info("=" * 80)
    logger.info("HEALTH SCHEDULE UPDATE - Database-First")
    logger.info("=" * 80)

    scraper = HealthScraper()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        clinics, pharmacies = await scraper.scrape_all()

        async with async_session() as session:
            # 1. Replace clinic_schedules (DELETE ALL + INSERT)
            await session.execute(text("DELETE FROM clinic_schedules"))
            clinic_count = 0
            for entry in clinics:
                # Truncate fields to fit DB constraints
                if entry.get("doctor_name") and len(entry["doctor_name"]) > 200:
                    entry["doctor_name"] = entry["doctor_name"][:200]
                if entry.get("doctor_role") and len(entry["doctor_role"]) > 100:
                    # Move overflow to notes
                    overflow = entry["doctor_role"]
                    entry["doctor_role"] = overflow[:100]
                    if not entry.get("notes"):
                        entry["notes"] = overflow
                if entry.get("notes") and len(entry["notes"]) > 500:
                    entry["notes"] = entry["notes"][:500]

                await session.execute(
                    text("""
                        INSERT INTO clinic_schedules
                            (clinic_name, doctor_name, doctor_role, day_of_week,
                             specific_date, hours_from, hours_to, notes, source_url, fetched_at)
                        VALUES
                            (:clinic_name, :doctor_name, :doctor_role, :day_of_week,
                             :specific_date, :hours_from, :hours_to, :notes, :source_url, :fetched_at)
                    """),
                    {
                        **entry,
                        "fetched_at": datetime.utcnow(),
                    }
                )
                clinic_count += 1

            # 2. Replace pharmacy_duties (DELETE ALL + INSERT)
            await session.execute(text("DELETE FROM pharmacy_duties"))
            pharmacy_count = 0
            for entry in pharmacies:
                await session.execute(
                    text("""
                        INSERT INTO pharmacy_duties
                            (pharmacy_name, address, phone, duty_type, day_of_week,
                             specific_dates, hours_from, hours_to, valid_year, notes, fetched_at)
                        VALUES
                            (:pharmacy_name, :address, :phone, :duty_type, :day_of_week,
                             :specific_dates, :hours_from, :hours_to, :valid_year, :notes, :fetched_at)
                    """),
                    {
                        **entry,
                        "fetched_at": datetime.utcnow(),
                    }
                )
                pharmacy_count += 1

            await session.commit()

        logger.info(f"  ✓ Clinics: {clinic_count} entries saved")
        logger.info(f"  ✓ Pharmacies: {pharmacy_count} entries saved")

    except Exception as e:
        logger.error(f"  ✗ Health job error: {e}", exc_info=True)
    finally:
        await scraper.close()
        await engine.dispose()

    logger.info("=" * 80)
    logger.info("Health job finished")
    logger.info("=" * 80)


def run_health_job():
    """Synchronous wrapper for APScheduler."""
    asyncio.run(run_health_job_async())


if __name__ == "__main__":
    print("🧪 Test Health Schedule Job...\n")
    run_health_job()
