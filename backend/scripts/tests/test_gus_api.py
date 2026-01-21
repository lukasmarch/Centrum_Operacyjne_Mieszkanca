"""
Test GUS API Integration

Testuje:
1. Połączenie z API GUS (BDL)
2. Pobieranie statystyk demograficznych
3. Pobieranie statystyk rynku pracy
4. Wyszukiwanie zmiennych (eksploracja API)
5. Sprawdzanie Unit ID dla Powiatu Działdowskiego

Cel: Zweryfikować poprawność ID zmiennych i struktury danych
"""
import asyncio
import sys
from pathlib import Path

# Dodaj backend do PYTHONPATH
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from src.integrations.gus_api import GUSDataService


async def test_gus_api():
    """Test główny"""
    print("=" * 80)
    print("TEST GUS API - Bank Danych Lokalnych")
    print("=" * 80)
    print()

    service = GUSDataService()

    # Test 1: Sprawdź Unit Info
    print("🔍 Test 1: Sprawdzanie Unit ID dla Powiatu Działdowskiego...")
    print(f"   Unit ID: {service.UNIT_ID_DZIALDOWO}")
    try:
        unit_info = await service.get_unit_info()
        print(f"   ✓ Unit Name: {unit_info.get('name')}")
        print(f"   ✓ Level: {unit_info.get('level')}")
        print()
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print(f"   ⚠️  Unit ID może być niepoprawny!")
        print()

    # Test 2: Pobierz statystyki demograficzne
    print("📊 Test 2: Pobieranie statystyk demograficznych...")
    try:
        demographics = await service.get_population_stats()

        if demographics and demographics.get("total"):
            print(f"   ✓ Ludność ogółem: {demographics['total']}")
            print(f"   ✓ Zgony niemowląt/1000: {demographics.get('infant_mortality_rate', 'N/A')}")
            print(f"   ✓ Zgony/1000 urodzeń: {demographics.get('mortality_rate', 'N/A')}")
            print(f"   ✓ Rozwody: {demographics.get('divorces', 'N/A')}")
            print(f"   ✓ Rok danych: {demographics.get('year')}")
            print()
        else:
            print(f"   ⚠️  Brak danych demograficznych")
            print(f"   Response: {demographics}")
            print()

    except Exception as e:
        print(f"   ❌ Error: {e}")
        print(f"   ⚠️  Variable IDs mogą być niepoprawne!")
        print()

    # Test 3: Pobierz statystyki rynku pracy
    print("💼 Test 3: Pobieranie statystyk rynku pracy...")
    try:
        employment = await service.get_employment_stats()

        if employment and employment.get("unemployment_rate") is not None:
            print(f"   ✓ Stopa bezrobocia: {employment['unemployment_rate']}%")
            print(f"   ✓ Bezrobotni zarejestrowani: {employment.get('registered_unemployed', 'N/A')}")
            print(f"   ✓ Bezrobocie ogółem: {employment.get('unemployed_total', 'N/A')}")
            print(f"   ✓ Przeciętne wynagrodzenie: {employment.get('avg_salary', 'N/A')} PLN")
            print(f"   ✓ Rok danych: {employment.get('year')}")
            print()
        else:
            print(f"   ⚠️  Brak danych o rynku pracy")
            print(f"   Response: {employment}")
            print()

    except Exception as e:
        print(f"   ❌ Error: {e}")
        print(f"   ⚠️  Variable IDs mogą być niepoprawne!")
        print()

    # Test 3b: Pobierz statystyki transportowe
    print("🚗 Test 3b: Pobieranie statystyk transportowych...")
    try:
        transport = await service.get_transport_stats()

        if transport and transport.get("personal_cars") is not None:
            print(f"   ✓ Samochody osobowe: {transport['personal_cars']}")
            print(f"   ✓ Pojazdy ogółem: {transport.get('vehicles_total', 'N/A')}")
            print(f"   ✓ Pojazdy/1000 ludności: {transport.get('vehicles_per_1000', 'N/A')}")
            print(f"   ✓ Autobusy: {transport.get('buses', 'N/A')}")
            print(f"   ✓ Samochody ciężarowe: {transport.get('trucks', 'N/A')}")
            print(f"   ✓ Drogi twarde (km): {transport.get('paved_roads_km', 'N/A')}")
            print(f"   ✓ Drogi gruntowe (km): {transport.get('unpaved_roads_km', 'N/A')}")
            print(f"   ✓ Rok danych: {transport.get('year')}")
            print()
        else:
            print(f"   ⚠️  Brak danych transportowych")
            print()

    except Exception as e:
        print(f"   ❌ Error: {e}")
        print()

    # Test 3c: Pobierz statystyki infrastruktury
    print("🏗️ Test 3c: Pobieranie statystyk infrastruktury...")
    try:
        infrastructure = await service.get_infrastructure_stats()

        if infrastructure and infrastructure.get("road_spending") is not None:
            print(f"   ✓ Wydatki na drogi: {infrastructure['road_spending']:,.2f} PLN")
            print(f"   ✓ Wydatki na biblioteki: {infrastructure.get('library_spending', 'N/A')} PLN")
            print(f"   ✓ Wydatki domy pomocy: {infrastructure.get('social_care_spending', 'N/A'):,.2f} PLN")
            print(f"   ✓ Noclegi/10000 ludności: {infrastructure.get('accommodations_per_10000', 'N/A')}")
            print(f"   ✓ Rok danych: {infrastructure.get('year')}")
            print()
        else:
            print(f"   ⚠️  Brak danych infrastrukturalnych")
            print()

    except Exception as e:
        print(f"   ❌ Error: {e}")
        print()

    # Test 4: Wyszukaj zmienne (opcjonalnie - do debugowania)
    print("🔎 Test 4: Wyszukiwanie zmiennych GUS (przykład: 'ludność')...")
    try:
        variables = await service.search_variables(keyword="ludność")
        print(f"   ✓ Znaleziono {len(variables)} zmiennych")

        # Pokaż pierwsze 5
        for i, var in enumerate(variables[:5]):
            var_id = var.get("id")
            var_name = var.get("n1", "N/A")
            print(f"   - [{var_id}] {var_name}")

        if len(variables) > 5:
            print(f"   ... i {len(variables) - 5} więcej")
        print()

    except Exception as e:
        print(f"   ⚠️  Search failed: {e}")
        print()

    # Podsumowanie
    print("=" * 80)
    print("✅ TEST ZAKOŃCZONY")
    print("=" * 80)
    print()
    print("📝 Następne kroki:")
    print("   1. Jeśli Unit ID jest niepoprawny - zaktualizuj UNIT_ID_DZIALDOWO w gus_api.py")
    print("   2. Jeśli Variable IDs są niepoprawne - użyj Test 4 aby znaleźć właściwe ID")
    print("   3. Jeśli wszystko działa - uruchom: python scripts/tests/test_gus_job.py")
    print()


if __name__ == "__main__":
    try:
        asyncio.run(test_gus_api())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test przerwany przez użytkownika")
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
