"""
GUS Job - Pobieranie statystyk z API GUS (BDL)

Uruchamiany codziennie o 6:00 AM przez scheduler.
Pobiera:
- Statystyki demograficzne (ludność, przyrost, gęstość)
- Statystyki rynku pracy (bezrobocie, zatrudnienie, wynagrodzenia)
"""
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database.connection import async_session
from src.database.schema import GUSStatistic
from src.integrations.gus_api import GUSDataService
from src.utils.logger import setup_logger

logger = setup_logger("GUSJob")


async def run_gus_job_async():
    """
    Async version for calling from within existing event loop.
    Use this when you're already inside an async context (e.g., in tests).
    """
    await fetch_gus_statistics()


def run_gus_job():
    """
    Wrapper synchroniczny dla async job
    (APScheduler wymaga funkcji synchronicznej)
    
    Obsługuje zarówno wywołanie z istniejącego event loop jak i bez:
    - Jeśli NIE ma running loop: używa asyncio.run()
    - Jeśli JEST running loop: tworzy task
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running event loop - safe to use asyncio.run()
        asyncio.run(fetch_gus_statistics())
    else:
        # Already in a running loop - create and run task
        # This handles cases like being called from within a test
        loop.run_until_complete(fetch_gus_statistics())


async def fetch_gus_statistics():
    """
    Pobierz statystyki GUS i zapisz do bazy danych

    Proces:
    1. Połącz z API GUS
    2. Pobierz statystyki demograficzne
    3. Pobierz statystyki rynku pracy
    4. Zapisz do tabeli gus_statistics (upsert)
    """
    logger.info("=" * 80)
    logger.info("GUS JOB - Pobieranie statystyk z API GUS")
    logger.info("=" * 80)

    service = GUSDataService()

    async with async_session() as session:
        try:
            # 1. Pobierz statystyki demograficzne
            logger.info("📊 Pobieranie statystyk demograficznych...")
            demographics = await service.get_population_stats()

            if not demographics or not demographics.get("total"):
                logger.warning("⚠️  Brak danych demograficznych z API")
                return

            # 2. Pobierz statystyki rynku pracy
            logger.info("💼 Pobieranie statystyk rynku pracy...")
            employment = await service.get_employment_stats()

            if not employment or employment.get("unemployment_rate") is None:
                logger.warning("⚠️  Brak danych o rynku pracy z API")
                return

            current_year = datetime.now().year

            # 3. Upsert demographics do bazy
            # Konwersja year na int (API GUS zwraca string)
            demo_year = int(demographics.get('year', current_year))
            logger.info(f"💾 Zapisywanie statystyk demograficznych (rok: {demo_year})...")

            result = await session.execute(
                select(GUSStatistic)
                .where(
                    GUSStatistic.category == "demographics",
                    GUSStatistic.year == demo_year
                )
            )
            demo_stat = result.scalar_one_or_none()

            if demo_stat:
                # Update istniejącego rekordu
                demo_stat.data = demographics
                demo_stat.updated_at = datetime.utcnow()
                demo_stat.population_total = demographics.get("total")
                logger.info(f"  ✓ Zaktualizowano demografia (ID: {demo_stat.id})")
            else:
                # Insert nowego rekordu
                demo_stat = GUSStatistic(
                    category="demographics",
                    year=demo_year,
                    data=demographics,
                    population_total=demographics.get("total")
                )
                session.add(demo_stat)
                logger.info(f"  ✓ Dodano nową demografię")

            # 4. Upsert employment do bazy
            # Konwersja year na int (API GUS zwraca string)
            emp_year = int(employment.get('year', current_year))
            logger.info(f"💾 Zapisywanie statystyk rynku pracy (rok: {emp_year})...")

            result = await session.execute(
                select(GUSStatistic)
                .where(
                    GUSStatistic.category == "employment",
                    GUSStatistic.year == emp_year
                )
            )
            emp_stat = result.scalar_one_or_none()

            if emp_stat:
                # Update istniejącego rekordu
                emp_stat.data = employment
                emp_stat.updated_at = datetime.utcnow()
                emp_stat.unemployment_rate = employment.get("unemployment_rate")
                logger.info(f"  ✓ Zaktualizowano employment (ID: {emp_stat.id})")
            else:
                # Insert nowego rekordu
                emp_stat = GUSStatistic(
                    category="employment",
                    year=emp_year,
                    data=employment,
                    unemployment_rate=employment.get("unemployment_rate")
                )
                session.add(emp_stat)
                logger.info(f"  ✓ Dodano nowy employment")

            # 5. Pobierz i zapisz dane transportowe
            logger.info("🚗 Pobieranie statystyk transportowych...")
            try:
                transport = await service.get_transport_stats()
                if transport and transport.get("year"):
                    transport_year = int(transport.get("year", current_year))
                    result = await session.execute(
                        select(GUSStatistic)
                        .where(
                            GUSStatistic.category == "transport",
                            GUSStatistic.year == transport_year
                        )
                    )
                    transport_stat = result.scalar_one_or_none()

                    if transport_stat:
                        transport_stat.data = transport
                        transport_stat.updated_at = datetime.utcnow()
                        logger.info(f"  ✓ Zaktualizowano transport (ID: {transport_stat.id})")
                    else:
                        transport_stat = GUSStatistic(
                            category="transport",
                            year=transport_year,
                            data=transport
                        )
                        session.add(transport_stat)
                        logger.info(f"  ✓ Dodano nowy transport")
                else:
                    logger.info("  ⚠️ Brak danych transportowych")
            except Exception as e:
                logger.warning(f"  ⚠️ Transport stats failed (non-critical): {e}")

            # 6. Pobierz i zapisz dane infrastruktury/finansów
            logger.info("🏗️ Pobieranie statystyk infrastruktury...")
            try:
                infrastructure = await service.get_infrastructure_stats()
                if infrastructure and infrastructure.get("year"):
                    infra_year = int(infrastructure.get("year", current_year))
                    result = await session.execute(
                        select(GUSStatistic)
                        .where(
                            GUSStatistic.category == "infrastructure",
                            GUSStatistic.year == infra_year
                        )
                    )
                    infra_stat = result.scalar_one_or_none()

                    if infra_stat:
                        infra_stat.data = infrastructure
                        infra_stat.updated_at = datetime.utcnow()
                        logger.info(f"  ✓ Zaktualizowano infrastructure (ID: {infra_stat.id})")
                    else:
                        infra_stat = GUSStatistic(
                            category="infrastructure",
                            year=infra_year,
                            data=infrastructure
                        )
                        session.add(infra_stat)
                        logger.info(f"  ✓ Dodano nową infrastructure")
                else:
                    logger.info("  ⚠️ Brak danych infrastrukturalnych")
            except Exception as e:
                logger.warning(f"  ⚠️ Infrastructure stats failed (non-critical): {e}")

            # 7. Commit
            await session.commit()

            # 8. Podsumowanie
            logger.info("=" * 80)
            logger.info("✅ GUS JOB ZAKOŃCZONY POMYŚLNIE!")
            logger.info("=" * 80)
            logger.info(f"📊 Demografia:")
            logger.info(f"   - Ludność: {demographics.get('total')}")
            logger.info(f"   - Zgony niemowląt/1000: {demographics.get('infant_mortality_rate')}")
            logger.info(f"   - Rok: {demographics.get('year')}")
            logger.info(f"💼 Rynek pracy:")
            logger.info(f"   - Stopa bezrobocia: {employment.get('unemployment_rate')}%")
            logger.info(f"   - Bezrobotni zarejestrowani: {employment.get('registered_unemployed')}")
            logger.info(f"   - Wynagrodzenie: {employment.get('avg_salary')} PLN")
            logger.info(f"   - Rok: {employment.get('year')}")

        except Exception as e:
            logger.error(f"❌ GUS Job failed: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    # Test job ręcznie
    print("🧪 Test GUS Job...\n")
    run_gus_job()
