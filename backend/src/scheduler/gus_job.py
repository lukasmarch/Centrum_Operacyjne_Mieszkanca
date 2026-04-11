"""
GUS Job - Monthly Database Refresh (Database-First Architecture)

Uruchamiany raz w miesiącu (1. dnia o 4:00 AM) przez scheduler.
Odświeża dane dla wszystkich 88 zmiennych GUS w nowych tabelach:
- gus_gmina_stats (6 gmin + powiat)
- gus_national_averages (Polska + województwo)
- gus_data_refresh_log (tracking)

Pobiera tylko najnowszy dostępny rok (nie pełen historical).
"""
import asyncio
import aiohttp
from datetime import datetime
from typing import List, Tuple, Optional, Dict
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from src.core.config import settings
from src.database.schema import GUSGminaStats, GUSNationalAverages, GUSDataRefreshLog
from src.integrations.gus_variables import (
    get_all_variables,
    UNIT_IDS,
    UNIT_ID_POWIAT,
    UNIT_ID_POLSKA,
    UNIT_ID_WOJEWODZTWO,
    GUSVariable
)
from src.utils.logger import setup_logger

logger = setup_logger("GUSJob")

# API Config
BASE_URL = "https://bdl.stat.gov.pl/api/v1"
REQUEST_DELAY = 0.6  # Rate limit: ~100 req/15min
TIMEOUT = 30


class GUSMonthlyRefresh:
    """Monthly refresh job for GUS database-first architecture."""

    def __init__(self):
        self.stats = {
            "started_at": datetime.utcnow(),
            "total_variables": 0,
            "successful": 0,
            "failed": 0,
            "gmina_records": 0,
            "national_records": 0,
            "errors": []
        }

        # Unit mappings (unit_id -> name)
        self.unit_names = {
            **{uid: name for name, uid in UNIT_IDS.items()},
            UNIT_ID_POWIAT: "Powiat Działdowski",
            UNIT_ID_POLSKA: "Polska",
            UNIT_ID_WOJEWODZTWO: "Woj. Warmińsko-Mazurskie"
        }

    async def fetch_unit_latest(
        self,
        session: aiohttp.ClientSession,
        var: GUSVariable,
        unit_id: str
    ) -> Optional[Tuple[int, float]]:
        """
        Pobierz najnowszą wartość dla jednostki i zmiennej.

        Args:
            session: aiohttp ClientSession
            var: GUSVariable
            unit_id: ID jednostki GUS

        Returns:
            (year, value) lub None jeśli błąd
        """
        endpoint = f"/data/by-unit/{unit_id}"
        url = f"{BASE_URL}{endpoint}"

        params = {
            "format": "json",
            "var-id": var.var_id,
            "page-size": 100
        }

        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as response:
                response.raise_for_status()
                data = await response.json()

                results = data.get("results", [])

                if not results:
                    return None

                # Extract latest value (last year in array)
                values_raw = results[0].get("values", [])

                if not values_raw:
                    return None

                # Get last (most recent) value
                latest = values_raw[-1]
                year = latest.get("year")
                val = latest.get("val")

                if year and val is not None:
                    try:
                        return (int(year), float(val))
                    except (ValueError, TypeError):
                        return None

                return None

        except aiohttp.ClientError as e:
            if hasattr(e, 'status') and e.status == 404:
                # Variable not available for this unit - not an error
                return None
            else:
                logger.warning(f"    ✗ API error for {unit_id}/{var.var_id}: {e}")
                return None

        except Exception as e:
            logger.warning(f"    ✗ Unexpected error for {unit_id}/{var.var_id}: {e}")
            return None

    async def upsert_gmina_stats(
        self,
        db_session: AsyncSession,
        var: GUSVariable,
        unit_id: str,
        year: int,
        value: float
    ):
        """
        Upsert pojedynczego rekordu do gus_gmina_stats.

        Args:
            db_session: AsyncSession
            var: GUSVariable
            unit_id: ID jednostki
            year: Rok danych
            value: Wartość
        """
        unit_name = self.unit_names.get(unit_id, f"Unit {unit_id}")

        # Check if record exists
        result = await db_session.execute(
            select(GUSGminaStats).where(
                GUSGminaStats.unit_id == unit_id,
                GUSGminaStats.var_id == var.var_id,
                GUSGminaStats.year == year
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing record
            existing.value = value
            existing.fetched_at = datetime.utcnow()
            logger.debug(f"      Updated {unit_name} ({year}): {value}")
        else:
            # Insert new record
            new_record = GUSGminaStats(
                unit_id=unit_id,
                unit_name=unit_name,
                var_id=var.var_id,
                var_name=var.name_pl,
                year=year,
                value=value,
                category=var.category,
                fetched_at=datetime.utcnow()
            )
            db_session.add(new_record)
            logger.debug(f"      Inserted {unit_name} ({year}): {value}")

        self.stats["gmina_records"] += 1

    async def upsert_national_averages(
        self,
        db_session: AsyncSession,
        var: GUSVariable,
        unit_id: str,
        year: int,
        value: float
    ):
        """
        Upsert pojedynczego rekordu do gus_national_averages.

        Args:
            db_session: AsyncSession
            var: GUSVariable
            unit_id: ID jednostki (POLSKA lub WOJEWODZTWO)
            year: Rok danych
            value: Wartość
        """
        # Determine level
        if unit_id == UNIT_ID_POLSKA:
            level = "national"
        elif unit_id == UNIT_ID_WOJEWODZTWO:
            level = "voivodeship"
        else:
            logger.warning(f"    ⚠️  Unknown unit_id for national averages: {unit_id}")
            return

        # Check if record exists
        result = await db_session.execute(
            select(GUSNationalAverages).where(
                GUSNationalAverages.var_id == var.var_id,
                GUSNationalAverages.year == year,
                GUSNationalAverages.level == level
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing record
            existing.value = value
            existing.fetched_at = datetime.utcnow()
            logger.debug(f"      Updated {level} avg ({year}): {value}")
        else:
            # Insert new record
            new_record = GUSNationalAverages(
                var_id=var.var_id,
                var_key=var.key,
                year=year,
                level=level,
                value=value,
                fetched_at=datetime.utcnow()
            )
            db_session.add(new_record)
            logger.debug(f"      Inserted {level} avg ({year}): {value}")

        self.stats["national_records"] += 1

    async def update_refresh_log(
        self,
        db_session: AsyncSession,
        var: GUSVariable,
        records_count: int,
        status: str,
        error: Optional[str] = None
    ):
        """
        Update gus_data_refresh_log dla zmiennej.

        Args:
            db_session: AsyncSession
            var: GUSVariable
            records_count: Liczba zaktualizowanych rekordów
            status: "success" | "failed"
            error: Error message jeśli failed
        """
        # Check if log entry exists
        result = await db_session.execute(
            select(GUSDataRefreshLog).where(
                GUSDataRefreshLog.var_key == var.key
            )
        )
        existing = result.scalar_one_or_none()

        now = datetime.utcnow()

        if existing:
            # Update existing log
            existing.last_refresh = now
            existing.records_updated = records_count
            existing.status = status
            existing.error_message = error
            existing.updated_at = now
        else:
            # Insert new log
            new_log = GUSDataRefreshLog(
                var_key=var.key,
                var_id=var.var_id,
                last_refresh=now,
                records_updated=records_count,
                status=status,
                error_message=error,
                created_at=now,
                updated_at=now
            )
            db_session.add(new_log)

    async def process_variable(
        self,
        http_session: aiohttp.ClientSession,
        db_session: AsyncSession,
        var: GUSVariable
    ) -> bool:
        """
        Przetwarza pojedynczą zmienną - pobiera najnowsze dane i zapisuje do DB.

        Args:
            http_session: aiohttp ClientSession
            db_session: AsyncSession
            var: GUSVariable

        Returns:
            True jeśli sukces, False jeśli błąd
        """
        logger.info(f"  [{var.key}] {var.name_pl} (tier={var.tier}, level={var.level})")

        # Define units to fetch
        gmina_units = list(UNIT_IDS.values()) + [UNIT_ID_POWIAT]  # 7 units
        national_units = [UNIT_ID_POLSKA, UNIT_ID_WOJEWODZTWO]   # 2 units
        all_units = gmina_units + national_units  # 9 total

        total_records = 0
        failed_units = 0

        # 1. Fetch latest data for each unit
        for unit_id in all_units:
            data_point = await self.fetch_unit_latest(http_session, var, unit_id)

            if data_point is None:
                # No data or error - skip this unit
                continue

            year, value = data_point

            # 2. Upsert to appropriate table
            try:
                if unit_id in gmina_units:
                    await self.upsert_gmina_stats(db_session, var, unit_id, year, value)
                else:
                    await self.upsert_national_averages(db_session, var, unit_id, year, value)

                total_records += 1

            except Exception as e:
                logger.error(f"    ✗ DB error for {unit_id}: {e}")
                failed_units += 1

            # Rate limiting between units
            if unit_id != all_units[-1]:  # Not the last unit
                await asyncio.sleep(REQUEST_DELAY)

        # 3. Update refresh log
        if failed_units > 0:
            status = "failed"
            error_msg = f"{failed_units}/{len(all_units)} units failed"
        elif total_records == 0:
            status = "failed"
            error_msg = "No data found for any unit"
        else:
            status = "success"
            error_msg = None

        await self.update_refresh_log(db_session, var, total_records, status, error_msg)

        # 4. Commit after each variable (incremental saves)
        await db_session.commit()

        if total_records > 0:
            logger.info(f"    ✓ {total_records} records updated")
            return True
        else:
            logger.warning(f"    ✗ No data found")
            return False

    async def run_refresh(self):
        """Wykonaj monthly refresh dla wszystkich zmiennych."""
        variables = get_all_variables()
        self.stats["total_variables"] = len(variables)

        logger.info("=" * 80)
        logger.info("GUS MONTHLY REFRESH - Database-First Architecture")
        logger.info("=" * 80)
        logger.info(f"Variables to refresh: {len(variables)}")
        logger.info(f"Units per variable: 9 (6 gmin + powiat + Polska + województwo)")
        logger.info(f"Rate limit delay: {REQUEST_DELAY}s between requests")
        logger.info(f"Estimated time: ~{len(variables) * 9 * REQUEST_DELAY / 60:.1f} minutes")
        logger.info("=" * 80)

        # Create HTTP session
        timeout = aiohttp.ClientTimeout(total=TIMEOUT)
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with aiohttp.ClientSession(timeout=timeout) as http_session:
            # Create DB session
            async with async_session() as db_session:
                try:
                    # Process each variable
                    for i, var in enumerate(variables, 1):
                        logger.info(f"[{i}/{len(variables)}] {var.category}")

                        success = await self.process_variable(http_session, db_session, var)

                        if success:
                            self.stats["successful"] += 1
                        else:
                            self.stats["failed"] += 1

                except Exception as e:
                    logger.error(f"❌ Refresh failed: {e}")
                    await db_session.rollback()
                    raise

        await engine.dispose()

        # Summary
        self.stats["finished_at"] = datetime.utcnow()
        duration = (self.stats["finished_at"] - self.stats["started_at"]).total_seconds()

        logger.info("=" * 80)
        logger.info("GUS MONTHLY REFRESH - SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Duration: {duration/60:.1f} minutes ({duration:.0f}s)")
        logger.info(f"Variables:")
        logger.info(f"  ✓ Successful: {self.stats['successful']}/{self.stats['total_variables']}")
        logger.info(f"  ✗ Failed: {self.stats['failed']}/{self.stats['total_variables']}")
        logger.info(f"Records Updated:")
        logger.info(f"  Gmina stats: {self.stats['gmina_records']}")
        logger.info(f"  National averages: {self.stats['national_records']}")
        logger.info(f"  Total: {self.stats['gmina_records'] + self.stats['national_records']}")
        logger.info("=" * 80)


async def run_gus_job_async():
    """
    Async version for calling from within existing event loop.
    Use this when you're already inside an async context (e.g., in tests).
    """
    refresh = GUSMonthlyRefresh()
    await refresh.run_refresh()


def run_gus_job():
    """
    Wrapper synchroniczny dla async job.
    (APScheduler wymaga funkcji synchronicznej)

    Obsługuje zarówno wywołanie z istniejącego event loop jak i bez:
    - Jeśli NIE ma running loop: używa asyncio.run()
    - Jeśli JEST running loop: tworzy task
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running event loop - safe to use asyncio.run()
        asyncio.run(run_gus_job_async())
    else:
        # Already in a running loop - create and run task
        loop.run_until_complete(run_gus_job_async())


if __name__ == "__main__":
    # Test job ręcznie
    print("🧪 Test GUS Monthly Refresh Job...\n")
    run_gus_job()
