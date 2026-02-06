#!/usr/bin/env python3
"""
GUS Variables Verification Script

Testuje wszystkie 88 zmiennych z rejestru gus_variables.py przeciwko GUS BDL API.
Sprawdza dostępność danych na poziomie gminy i powiatu.
Raportuje które zmienne mają dane i za jakie lata.

Usage:
    python verify_gus_variables.py [--verbose]
"""
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from src.integrations.gus_variables import (
    get_all_variables,
    UNIT_IDS,
    UNIT_ID_POWIAT,
    UNIT_ID_POLSKA,
    GUSVariable
)

# API Config
BASE_URL = "https://bdl.stat.gov.pl/api/v1"
REQUEST_DELAY = 0.6  # seconds between requests (rate limit ~100 req/15min)
TIMEOUT = 30


class VariableVerifier:
    """Weryfikator zmiennych GUS"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = {
            "verified_at": datetime.now().isoformat(),
            "total_variables": 0,
            "successful": 0,
            "failed": 0,
            "variables": {}
        }

    def verify_variable(self, var: GUSVariable) -> Dict:
        """
        Weryfikuje pojedynczą zmienną poprzez request do API.
        Używa endpoint /data/by-variable/{var_id} który zwraca dane dla wszystkich jednostek.
        """
        endpoint = f"/data/by-variable/{var.var_id}"
        url = f"{BASE_URL}{endpoint}"

        params = {
            "format": "json",
            "page-size": 100
        }

        try:
            if self.verbose:
                print(f"  Testing: {url}")

            response = requests.get(url, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])

            if not results:
                return {
                    "status": "no_data",
                    "error": "Empty results array",
                    "years": [],
                    "units_count": 0
                }

            # Extract years and units
            years = sorted(list(set([r.get("year") for r in results if r.get("year")])))
            units_count = len(set([r.get("id") for r in results if r.get("id")]))

            # Check if our units have data
            our_units = list(UNIT_IDS.values()) + [UNIT_ID_POWIAT]
            has_rybno = any(r.get("id") == int(UNIT_IDS["Rybno"]) for r in results)
            has_powiat = any(r.get("id") == int(UNIT_ID_POWIAT) for r in results)

            # Get latest value for Rybno or Powiat
            latest_value = None
            latest_year = None

            target_unit_id = UNIT_IDS["Rybno"] if var.level == "gmina" else UNIT_ID_POWIAT
            target_records = [r for r in results if str(r.get("id")) == target_unit_id]

            if target_records:
                # Sort by year desc
                target_records.sort(key=lambda x: x.get("year", 0), reverse=True)
                latest_record = target_records[0]
                latest_value = latest_record.get("val")
                latest_year = latest_record.get("year")

            return {
                "status": "success",
                "years": years,
                "year_range": f"{years[0]}-{years[-1]}" if years else "N/A",
                "units_count": units_count,
                "has_rybno": has_rybno,
                "has_powiat": has_powiat,
                "latest_value": latest_value,
                "latest_year": latest_year,
                "total_records": len(results)
            }

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return {
                    "status": "not_found",
                    "error": f"Variable ID not found in BDL API (404)"
                }
            elif e.response.status_code == 429:
                return {
                    "status": "rate_limited",
                    "error": "Rate limit exceeded (429)"
                }
            else:
                return {
                    "status": "http_error",
                    "error": f"HTTP {e.response.status_code}: {str(e)}"
                }
        except requests.RequestException as e:
            return {
                "status": "request_error",
                "error": str(e)
            }

    def verify_all(self) -> Dict:
        """Weryfikuje wszystkie zmienne z rejestru."""
        variables = get_all_variables()
        self.results["total_variables"] = len(variables)

        print(f"\n{'='*80}")
        print(f"GUS Variables Verification")
        print(f"{'='*80}")
        print(f"Total variables to verify: {len(variables)}")
        print(f"Rate limit delay: {REQUEST_DELAY}s between requests")
        print(f"Estimated time: ~{len(variables) * REQUEST_DELAY / 60:.1f} minutes\n")

        for i, var in enumerate(variables, 1):
            print(f"[{i}/{len(variables)}] {var.key} (var_id={var.var_id}, level={var.level}, tier={var.tier})")

            result = self.verify_variable(var)

            # Store result
            self.results["variables"][var.key] = {
                "var_id": var.var_id,
                "name_pl": var.name_pl,
                "unit": var.unit,
                "category": var.category,
                "tier": var.tier,
                "level": var.level,
                "verification": result
            }

            # Update counters
            if result["status"] == "success":
                self.results["successful"] += 1
                status_icon = "✓"
                status_msg = f"OK - {result['year_range']}, {result['units_count']} units"
                if result.get("latest_value"):
                    status_msg += f", latest: {result['latest_value']} ({result['latest_year']})"
            else:
                self.results["failed"] += 1
                status_icon = "✗"
                status_msg = f"{result['status'].upper()}: {result.get('error', 'Unknown error')}"

            print(f"  {status_icon} {status_msg}")

            # Rate limiting (skip on last iteration)
            if i < len(variables):
                time.sleep(REQUEST_DELAY)

        return self.results

    def print_summary(self):
        """Wyświetla podsumowanie weryfikacji."""
        print(f"\n{'='*80}")
        print(f"Verification Summary")
        print(f"{'='*80}")
        print(f"Total: {self.results['total_variables']}")
        print(f"✓ Successful: {self.results['successful']} ({self.results['successful']/self.results['total_variables']*100:.1f}%)")
        print(f"✗ Failed: {self.results['failed']} ({self.results['failed']/self.results['total_variables']*100:.1f}%)")

        # Group by status
        by_status = {}
        for var_key, var_data in self.results["variables"].items():
            status = var_data["verification"]["status"]
            by_status.setdefault(status, []).append(var_key)

        print(f"\nBreakdown by status:")
        for status, var_keys in sorted(by_status.items()):
            print(f"  {status}: {len(var_keys)}")

        # Show failed variables
        if self.results["failed"] > 0:
            print(f"\nFailed variables:")
            for var_key, var_data in self.results["variables"].items():
                if var_data["verification"]["status"] != "success":
                    print(f"  - {var_key} (var_id={var_data['var_id']}): {var_data['verification']['status']}")

        # Tier breakdown
        by_tier = {"free": [], "premium": [], "business": []}
        for var_key, var_data in self.results["variables"].items():
            if var_data["verification"]["status"] == "success":
                by_tier[var_data["tier"]].append(var_key)

        print(f"\nSuccessful by tier:")
        for tier in ["free", "premium", "business"]:
            print(f"  {tier}: {len(by_tier[tier])}")

        # Level breakdown
        by_level = {"gmina": 0, "powiat": 0}
        for var_key, var_data in self.results["variables"].items():
            if var_data["verification"]["status"] == "success":
                by_level[var_data["level"]] += 1

        print(f"\nSuccessful by level:")
        print(f"  gmina: {by_level['gmina']}")
        print(f"  powiat: {by_level['powiat']}")

    def save_results(self, output_file: str):
        """Zapisuje wyniki do pliku JSON."""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Results saved to: {output_path}")


def main():
    """Main entry point."""
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    verifier = VariableVerifier(verbose=verbose)

    try:
        results = verifier.verify_all()
        verifier.print_summary()

        # Save results
        output_file = backend_dir / "scripts" / "production" / "gus_variables_verification.json"
        verifier.save_results(output_file)

        # Exit code based on results
        if results["failed"] > 0:
            print(f"\n⚠️  {results['failed']} variables failed verification")
            sys.exit(1)
        else:
            print(f"\n✓ All {results['successful']} variables verified successfully!")
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  Verification interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
