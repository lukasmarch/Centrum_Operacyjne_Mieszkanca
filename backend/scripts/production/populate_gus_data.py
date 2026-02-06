#!/usr/bin/env python3
"""
GUS Data Population Script - Database-First Initialization

Jednorazowe zasilenie bazy danych GUS dla wszystkich 88 zmiennych.
Pobiera dane historyczne (10-22 lat) dla 8 jednostek:
- 6 gmin powiatu działdowskiego
- Powiat działdowski
- Polska (national averages)
- Województwo warmińsko-mazurskie

Wypełnia tabele:
- gus_gmina_stats (6 gmin + powiat)
- gus_national_averages (Polska + województwo)
- gus_data_refresh_log (tracking)

Usage:
    python populate_gus_data.py [--dry-run] [--verbose]
"""
import sys
import json
import time
import requests
import psycopg2
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from psycopg2.extras import execute_values

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from src.integrations.gus_variables import (
    get_all_variables,
    UNIT_IDS,
    UNIT_ID_POWIAT,
    UNIT_ID_POLSKA,
    UNIT_ID_WOJEWODZTWO,
    GUSVariable
)
from src.config import settings

# API Config
BASE_URL = "https://bdl.stat.gov.pl/api/v1"
REQUEST_DELAY = 0.6  # seconds between requests (~100 req/15min rate limit)
TIMEOUT = 30

# Database Config (convert asyncpg URL to psycopg2 format)
DATABASE_URL = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


class GUSDataPopulator:
    """Populuje bazę danych GUS danymi historycznymi dla wszystkich zmiennych."""

    def __init__(self, dry_run: bool = False, verbose: bool = False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.conn = None
        self.cursor = None

        # Stats
        self.stats = {
            "started_at": datetime.now().isoformat(),
            "total_variables": 0,
            "successful_variables": 0,
            "failed_variables": 0,
            "total_api_calls": 0,
            "gmina_records_inserted": 0,
            "national_records_inserted": 0,
            "errors": []
        }

        # Unit mappings (unit_id -> name)
        self.unit_names = {
            **{uid: name for name, uid in UNIT_IDS.items()},
            UNIT_ID_POWIAT: "Powiat Działdowski",
            UNIT_ID_POLSKA: "Polska",
            UNIT_ID_WOJEWODZTWO: "Woj. Warmińsko-Mazurskie"
        }

    def connect_db(self):
        """Połącz z bazą danych."""
        if self.dry_run:
            print("🔍 DRY RUN mode - skipping database connection")
            return

        try:
            self.conn = psycopg2.connect(DATABASE_URL)
            self.cursor = self.conn.cursor()
            print("✓ Connected to database")
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            raise

    def close_db(self):
        """Zamknij połączenie z bazą."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("✓ Database connection closed")

    def fetch_unit_data(self, var: GUSVariable, unit_id: str) -> Optional[List[Tuple[int, float]]]:
        """
        Pobierz dane dla konkretnej jednostki i zmiennej.
        Używa endpoint /data/by-unit/{unit_id}?var-id={var_id}.

        Args:
            var: GUSVariable
            unit_id: ID jednostki GUS

        Returns:
            Lista (year, value) lub None jeśli błąd
        """
        endpoint = f"/data/by-unit/{unit_id}"
        url = f"{BASE_URL}{endpoint}"

        params = {
            "format": "json",
            "var-id": var.var_id,
            "page-size": 100
        }

        try:
            if self.verbose:
                unit_name = self.unit_names.get(unit_id, unit_id)
                print(f"      {unit_name}: GET {endpoint}?var-id={var.var_id}")

            response = requests.get(url, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()

            self.stats["total_api_calls"] += 1

            results = data.get("results", [])

            if not results:
                return []

            # Extract values from first result (should be only one for this unit)
            values_raw = results[0].get("values", [])
            data_points = []

            for v in values_raw:
                year = v.get("year")
                val = v.get("val")

                if year and val is not None:
                    try:
                        year_int = int(year)
                        val_float = float(val)
                        data_points.append((year_int, val_float))
                    except (ValueError, TypeError):
                        continue

            if self.verbose and data_points:
                print(f"        ✓ {len(data_points)} years")

            return data_points

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                # Variable not available for this unit - not an error
                return []
            elif e.response.status_code == 429:
                error = f"Rate limit exceeded (429) - increase delay"
                print(f"    ✗ {error}")
                self.stats["errors"].append({"var_key": var.key, "unit_id": unit_id, "error": error})
                return None
            else:
                if self.verbose:
                    print(f"        ✗ HTTP {e.response.status_code}")
                return []

        except requests.RequestException as e:
            if self.verbose:
                print(f"        ✗ Request error: {str(e)}")
            return []

    def filter_results_for_units(
        self,
        results: List[Dict],
        target_unit_ids: List[str]
    ) -> Dict[str, List[Tuple[int, float]]]:
        """
        Filtruj results do podanych jednostek.

        Args:
            results: Lista results z API
                     Format: [{"id": "042815403062", "name": "...", "values": [{"year": "2024", "val": 123}, ...]}, ...]
            target_unit_ids: Lista unit_ids do wyfiltrowania

        Returns:
            Dict {unit_id: [(year, value), ...]}
        """
        filtered = {uid: [] for uid in target_unit_ids}

        for result in results:
            unit_id = result.get("id")  # Already a string!

            if unit_id in target_unit_ids:
                values = result.get("values", [])

                for v in values:
                    year = v.get("year")
                    val = v.get("val")

                    if year and val is not None:
                        try:
                            year_int = int(year)
                            val_float = float(val)
                            filtered[unit_id].append((year_int, val_float))
                        except (ValueError, TypeError):
                            continue

        return filtered

    def upsert_gmina_stats(
        self,
        var: GUSVariable,
        unit_id: str,
        data_points: List[Tuple[int, float]]
    ):
        """
        Upsert danych do gus_gmina_stats (dla gmin + powiat).

        Args:
            var: GUSVariable
            unit_id: ID jednostki
            data_points: Lista (year, value)
        """
        if not data_points:
            return

        unit_name = self.unit_names.get(unit_id, f"Unit {unit_id}")

        # Prepare records for batch insert
        records = [
            (
                unit_id,
                unit_name,
                var.var_id,
                var.name_pl,
                year,
                value,
                var.category,
                datetime.utcnow()
            )
            for year, value in data_points
        ]

        if self.dry_run:
            print(f"    [DRY RUN] Would insert {len(records)} records for {unit_name}")
            self.stats["gmina_records_inserted"] += len(records)
            return

        # SQL upsert (INSERT ... ON CONFLICT DO UPDATE)
        sql = """
            INSERT INTO gus_gmina_stats
                (unit_id, unit_name, var_id, var_name, year, value, category, fetched_at)
            VALUES %s
            ON CONFLICT (unit_id, var_id, year)
            DO UPDATE SET
                value = EXCLUDED.value,
                fetched_at = EXCLUDED.fetched_at
        """

        try:
            execute_values(self.cursor, sql, records)
            self.stats["gmina_records_inserted"] += len(records)

            if self.verbose:
                print(f"    ✓ Inserted/updated {len(records)} records for {unit_name}")

        except Exception as e:
            print(f"    ✗ DB error for {unit_name}: {e}")
            self.stats["errors"].append({
                "var_key": var.key,
                "unit_id": unit_id,
                "error": str(e)
            })

    def upsert_national_averages(
        self,
        var: GUSVariable,
        unit_id: str,
        data_points: List[Tuple[int, float]]
    ):
        """
        Upsert danych do gus_national_averages (dla Polski i województwa).

        Args:
            var: GUSVariable
            unit_id: ID jednostki (POLSKA lub WOJEWODZTWO)
            data_points: Lista (year, value)
        """
        if not data_points:
            return

        # Determine level
        if unit_id == UNIT_ID_POLSKA:
            level = "national"
        elif unit_id == UNIT_ID_WOJEWODZTWO:
            level = "voivodeship"
        else:
            print(f"    ⚠️  Unknown unit_id for national averages: {unit_id}")
            return

        # Prepare records
        records = [
            (
                var.var_id,
                var.key,
                year,
                level,
                value,
                datetime.utcnow()
            )
            for year, value in data_points
        ]

        if self.dry_run:
            print(f"    [DRY RUN] Would insert {len(records)} {level} averages")
            self.stats["national_records_inserted"] += len(records)
            return

        # SQL upsert
        sql = """
            INSERT INTO gus_national_averages
                (var_id, var_key, year, level, value, fetched_at)
            VALUES %s
            ON CONFLICT (var_id, year, level)
            DO UPDATE SET
                value = EXCLUDED.value,
                fetched_at = EXCLUDED.fetched_at
        """

        try:
            execute_values(self.cursor, sql, records)
            self.stats["national_records_inserted"] += len(records)

            if self.verbose:
                print(f"    ✓ Inserted/updated {len(records)} {level} averages")

        except Exception as e:
            print(f"    ✗ DB error for {level} averages: {e}")
            self.stats["errors"].append({
                "var_key": var.key,
                "level": level,
                "error": str(e)
            })

    def update_refresh_log(self, var: GUSVariable, records_count: int, status: str, error: Optional[str] = None):
        """
        Update gus_data_refresh_log dla zmiennej.

        Args:
            var: GUSVariable
            records_count: Liczba zaktualizowanych rekordów
            status: "success" | "failed"
            error: Error message jeśli failed
        """
        if self.dry_run:
            print(f"    [DRY RUN] Would update refresh log: {var.key} -> {status}")
            return

        sql = """
            INSERT INTO gus_data_refresh_log
                (var_key, var_id, last_refresh, records_updated, status, error_message, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (var_key)
            DO UPDATE SET
                last_refresh = EXCLUDED.last_refresh,
                records_updated = EXCLUDED.records_updated,
                status = EXCLUDED.status,
                error_message = EXCLUDED.error_message,
                updated_at = EXCLUDED.updated_at
        """

        try:
            now = datetime.utcnow()
            self.cursor.execute(sql, (
                var.key,
                var.var_id,
                now,
                records_count,
                status,
                error,
                now,
                now
            ))

            if self.verbose:
                print(f"    ✓ Updated refresh log: {status}")

        except Exception as e:
            print(f"    ✗ Failed to update refresh log: {e}")

    def process_variable(self, var: GUSVariable) -> bool:
        """
        Przetwarza pojedynczą zmienną - pobiera dane i zapisuje do DB.

        Returns:
            True jeśli sukces, False jeśli błąd
        """
        # Define units to fetch
        gmina_units = list(UNIT_IDS.values()) + [UNIT_ID_POWIAT]  # 6 gmin + powiat
        national_units = [UNIT_ID_POLSKA, UNIT_ID_WOJEWODZTWO]   # Polska + województwo
        all_units = gmina_units + national_units  # 8 total

        total_records = 0
        failed_units = 0

        # 1. Fetch data for each unit
        for unit_id in all_units:
            data_points = self.fetch_unit_data(var, unit_id)

            if data_points is None:
                # Fatal error (rate limit, etc.)
                failed_units += 1
                continue

            if not data_points:
                # No data for this unit (e.g., 404) - not an error
                continue

            # 2. Upsert to appropriate table
            if unit_id in gmina_units:
                self.upsert_gmina_stats(var, unit_id, data_points)
            else:
                self.upsert_national_averages(var, unit_id, data_points)

            total_records += len(data_points)

            # Rate limiting between units (only if more units to fetch)
            if unit_id != all_units[-1]:  # Not the last unit
                time.sleep(REQUEST_DELAY)

        # 3. Update refresh log
        if failed_units > 0:
            status = "failed"
            error_msg = f"{failed_units}/{len(all_units)} units failed (rate limit or network error)"
        elif total_records == 0:
            status = "failed"
            error_msg = "No data found for any unit"
        else:
            status = "success"
            error_msg = None

        self.update_refresh_log(var, total_records, status, error_msg)

        return total_records > 0

    def populate_all(self):
        """Populuje bazę danych dla wszystkich 88 zmiennych."""
        variables = get_all_variables()
        self.stats["total_variables"] = len(variables)

        print(f"\n{'='*80}")
        print(f"GUS Data Population - Database-First Initialization")
        print(f"{'='*80}")
        print(f"Total variables: {len(variables)}")
        print(f"Units to fetch per variable: 8")
        print(f"  - 6 gmin: {', '.join(UNIT_IDS.keys())}")
        print(f"  - Powiat Działdowski")
        print(f"  - Polska (national average)")
        print(f"  - Województwo warmińsko-mazurskie")
        print(f"\nTotal API calls: {len(variables)} vars × 8 units = {len(variables) * 8}")
        print(f"Rate limit delay: {REQUEST_DELAY}s between requests")
        print(f"Estimated time: ~{len(variables) * 8 * REQUEST_DELAY / 60:.1f} minutes")

        if self.dry_run:
            print(f"\n🔍 DRY RUN MODE - No database changes will be made")

        print(f"\n{'='*80}\n")

        # Connect to DB
        self.connect_db()

        # Process each variable
        for i, var in enumerate(variables, 1):
            print(f"[{i}/{len(variables)}] {var.key}")
            print(f"  var_id={var.var_id} | {var.name_pl}")
            print(f"  category={var.category} | tier={var.tier} | level={var.level}")

            success = self.process_variable(var)

            if success:
                self.stats["successful_variables"] += 1
                print(f"  ✓ SUCCESS")
            else:
                self.stats["failed_variables"] += 1
                print(f"  ✗ FAILED")

            # Commit after each variable (in case of crash)
            if not self.dry_run and self.conn:
                self.conn.commit()

            print()  # Newline between variables

        # Final commit
        if not self.dry_run and self.conn:
            self.conn.commit()
            print("✓ Final commit")

        # Close DB
        self.close_db()

    def print_summary(self):
        """Wyświetla podsumowanie populacji."""
        self.stats["finished_at"] = datetime.now().isoformat()

        # Calculate duration
        start = datetime.fromisoformat(self.stats["started_at"])
        end = datetime.fromisoformat(self.stats["finished_at"])
        duration = (end - start).total_seconds()

        print(f"\n{'='*80}")
        print(f"Population Summary")
        print(f"{'='*80}")
        print(f"Duration: {duration/60:.1f} minutes ({duration:.0f}s)")
        print(f"\nVariables:")
        print(f"  Total: {self.stats['total_variables']}")
        print(f"  ✓ Successful: {self.stats['successful_variables']} ({self.stats['successful_variables']/self.stats['total_variables']*100:.1f}%)")
        print(f"  ✗ Failed: {self.stats['failed_variables']} ({self.stats['failed_variables']/self.stats['total_variables']*100:.1f}%)")

        print(f"\nAPI Calls: {self.stats['total_api_calls']}")

        print(f"\nRecords Inserted/Updated:")
        print(f"  Gmina stats: {self.stats['gmina_records_inserted']}")
        print(f"  National averages: {self.stats['national_records_inserted']}")
        print(f"  Total: {self.stats['gmina_records_inserted'] + self.stats['national_records_inserted']}")

        if self.stats["errors"]:
            print(f"\nErrors ({len(self.stats['errors'])}):")
            for err in self.stats["errors"][:10]:  # Show max 10
                print(f"  - {err.get('var_key', 'unknown')}: {err.get('error', 'unknown error')}")

            if len(self.stats["errors"]) > 10:
                print(f"  ... and {len(self.stats['errors']) - 10} more")

    def save_results(self, output_file: str):
        """Zapisuje statystyki do pliku JSON."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Results saved to: {output_path}")


def main():
    """Main entry point."""
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    populator = GUSDataPopulator(dry_run=dry_run, verbose=verbose)

    try:
        populator.populate_all()
        populator.print_summary()

        # Save results
        output_file = backend_dir / "scripts" / "production" / "populate_gus_data_results.json"
        populator.save_results(output_file)

        # Exit code
        if populator.stats["failed_variables"] > 0:
            print(f"\n⚠️  {populator.stats['failed_variables']} variables failed")
            sys.exit(1)
        else:
            print(f"\n✓ All {populator.stats['successful_variables']} variables populated successfully!")
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  Population interrupted by user")

        # Try to close DB gracefully
        if populator.conn:
            populator.conn.rollback()
            populator.close_db()

        sys.exit(130)

    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()

        # Try to close DB gracefully
        if populator.conn:
            populator.conn.rollback()
            populator.close_db()

        sys.exit(1)


if __name__ == "__main__":
    main()
