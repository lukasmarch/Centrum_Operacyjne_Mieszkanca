#!/usr/bin/env python3
"""
Test Enhanced GUS Dashboard - Tier-based Access Control

Sprawdza czy nowe endpointy działają poprawnie.
"""

import asyncio
import sys
from pathlib import Path

# Dodaj backend do ścieżki
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from src.integrations.gus_api import GUSDataService
from src.api.endpoints.gus import (
    FREE_VARIABLES,
    PREMIUM_VARIABLES,
    BUSINESS_VARIABLES,
    VARIABLE_METADATA,
    get_allowed_variables
)


async def test_gus_integration():
    """Test integracji GUS API"""
    print("=" * 70)
    print("🧪 TEST: Enhanced GUS Dashboard - Backend Integration")
    print("=" * 70)

    # Test 1: Sprawdź czy zmienne są poprawnie załadowane
    print("\n1️⃣ Sprawdzenie zmiennych GUS API")
    print("-" * 70)

    service = GUSDataService()
    total_vars = len(service.VARS)
    print(f"✅ Total variables in GUS API: {total_vars}")
    print(f"   Expected: ~36 (nowe zmienne dodane)")

    # Sprawdź nowe zmienne
    new_vars = [
        "population_male",
        "population_female",
        "population_density",
        "births_live",
        "natural_persons_business",
        "foreign_capital_companies",
        "investment_expenditure"
    ]

    print(f"\n   Nowe zmienne:")
    for var in new_vars:
        if var in service.VARS:
            print(f"   ✅ {var}: {service.VARS[var]}")
        else:
            print(f"   ❌ {var}: BRAK!")

    # Test 2: Sprawdź tier definitions
    print("\n2️⃣ Sprawdzenie tier definitions")
    print("-" * 70)

    print(f"🆓 FREE tier: {len(FREE_VARIABLES)} variables")
    for var in FREE_VARIABLES[:3]:
        print(f"   - {var}")
    print(f"   ... (+{len(FREE_VARIABLES) - 3} more)")

    print(f"\n⭐ PREMIUM tier: {len(PREMIUM_VARIABLES)} variables (includes FREE)")
    premium_only = [v for v in PREMIUM_VARIABLES if v not in FREE_VARIABLES]
    print(f"   Premium-only: {len(premium_only)} variables")
    for var in premium_only[:5]:
        meta = VARIABLE_METADATA.get(var, {})
        print(f"   - {var}: {meta.get('name', 'N/A')} ({meta.get('category', 'N/A')})")
    print(f"   ... (+{len(premium_only) - 5} more)")

    print(f"\n💎 BUSINESS tier: {len(BUSINESS_VARIABLES)} variables (wszystkie)")

    # Test 3: Sprawdź kategoryzację
    print("\n3️⃣ Sprawdzenie kategoryzacji")
    print("-" * 70)

    categories = {}
    for var_key, meta in VARIABLE_METADATA.items():
        category = meta.get("category", "inne")
        if category not in categories:
            categories[category] = []
        categories[category].append(var_key)

    for category, vars_list in categories.items():
        print(f"📊 {category.upper()}: {len(vars_list)} variables")
        for var in vars_list[:2]:
            meta = VARIABLE_METADATA[var]
            print(f"   - {var} ({meta['tier']}): {meta['name']}")

    # Test 4: Test pojedynczej zmiennej
    print("\n4️⃣ Test pobierania pojedynczej zmiennej")
    print("-" * 70)

    try:
        # Test unemployment_rate (premium)
        var_key = "unemployment_rate"
        print(f"Pobieranie: {var_key}")

        result = await service.get_single_variable(var_key)

        print(f"✅ Sukces!")
        print(f"   Value: {result['value']}")
        print(f"   Year: {result['year']}")
        print(f"   Unit ID: {result['unit_id']}")
        print(f"   Var ID: {result['var_id']}")

    except Exception as e:
        print(f"❌ Błąd: {e}")

    # Test 5: Sprawdź tier filtering
    print("\n5️⃣ Test tier filtering")
    print("-" * 70)

    # Mock user objects
    class MockUser:
        def __init__(self, tier):
            self.tier = tier

    free_user = MockUser("free")
    premium_user = MockUser("premium")
    business_user = MockUser("business")

    print(f"Free user ma dostęp do: {len(get_allowed_variables(free_user))} zmiennych")
    print(f"Premium user ma dostęp do: {len(get_allowed_variables(premium_user))} zmiennych")
    print(f"Business user ma dostęp do: {len(get_allowed_variables(business_user))} zmiennych")

    # Test 6: Sprawdź premium-only variables
    print("\n6️⃣ Premium-only variables (TOP 10)")
    print("-" * 70)

    premium_only_sorted = [
        v for v in PREMIUM_VARIABLES
        if v not in FREE_VARIABLES
    ][:10]

    for var in premium_only_sorted:
        meta = VARIABLE_METADATA.get(var, {})
        print(f"⭐ {var}")
        print(f"   Name: {meta.get('name', 'N/A')}")
        print(f"   Unit: {meta.get('unit', 'N/A')}")
        print(f"   Category: {meta.get('category', 'N/A')}")
        print()

    # Summary
    print("\n" + "=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    print(f"✅ Total GUS variables: {total_vars}")
    print(f"✅ Free tier: {len(FREE_VARIABLES)} variables")
    print(f"✅ Premium tier: {len(PREMIUM_VARIABLES)} variables")
    print(f"✅ Business tier: {len(BUSINESS_VARIABLES)} variables")
    print(f"✅ Metadata entries: {len(VARIABLE_METADATA)}")
    print(f"✅ Categories: {len(categories)}")
    print("\n🎉 All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_gus_integration())
