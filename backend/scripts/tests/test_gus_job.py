"""
Test GUS Job - Pełny test z zapisem do bazy

Testuje:
1. Uruchomienie GUS job
2. Pobieranie danych z API GUS
3. Zapis do tabeli gus_statistics
4. Weryfikacja danych w bazie

Wymaga:
- Działającą bazę danych PostgreSQL
- Tabela gus_statistics musi istnieć (uruchom migrację)
"""
import asyncio
import sys
from pathlib import Path

# Dodaj backend do PYTHONPATH
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from src.scheduler.gus_job import run_gus_job_async, fetch_gus_statistics
from src.database.connection import async_session
from src.database.schema import GUSStatistic
from sqlmodel import select


async def verify_database():
    """Sprawdź czy dane zostały zapisane do bazy"""
    print("\n" + "=" * 80)
    print("WERYFIKACJA DANYCH W BAZIE")
    print("=" * 80)

    async with async_session() as session:
        # Sprawdź demographics
        result = await session.execute(
            select(GUSStatistic)
            .where(GUSStatistic.category == "demographics")
            .order_by(GUSStatistic.year.desc())
            .limit(1)
        )
        demo = result.scalar_one_or_none()

        if demo:
            print(f"\n✓ Demografia (ID: {demo.id}):")
            print(f"  - Rok: {demo.year}")
            print(f"  - Ludność: {demo.population_total}")
            print(f"  - Gęstość: {demo.data.get('density')} os/km²")
            print(f"  - Fetched at: {demo.fetched_at}")
            print(f"  - Updated at: {demo.updated_at}")
        else:
            print("\n❌ Brak danych demograficznych w bazie")

        # Sprawdź employment
        result = await session.execute(
            select(GUSStatistic)
            .where(GUSStatistic.category == "employment")
            .order_by(GUSStatistic.year.desc())
            .limit(1)
        )
        emp = result.scalar_one_or_none()

        if emp:
            print(f"\n✓ Rynek pracy (ID: {emp.id}):")
            print(f"  - Rok: {emp.year}")
            print(f"  - Stopa bezrobocia: {emp.unemployment_rate}%")
            print(f"  - Bezrobotni: {emp.data.get('unemployed_count')}")
            print(f"  - Fetched at: {emp.fetched_at}")
            print(f"  - Updated at: {emp.updated_at}")
        else:
            print("\n❌ Brak danych o rynku pracy w bazie")

        # Wszystkie rekordy
        result = await session.execute(select(GUSStatistic))
        all_stats = result.scalars().all()
        print(f"\n📊 Łączna liczba rekordów w gus_statistics: {len(all_stats)}")

        return demo is not None and emp is not None


async def test_gus_job():
    """Test główny"""
    print("=" * 80)
    print("TEST GUS JOB - Pełny pipeline z bazą danych")
    print("=" * 80)
    print()

    # Test 1: Uruchom job
    print("🚀 Test 1: Uruchamianie GUS job...")
    try:
        # Używamy bezpośrednio async funkcji (zamiast run_gus_job() który miał problem z nested asyncio.run())
        await fetch_gus_statistics()
        print("✓ Job zakończony bez błędów")
    except Exception as e:
        print(f"❌ Job failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test 2: Weryfikuj bazę danych
    print("\n🔍 Test 2: Weryfikacja danych w bazie...")
    try:
        success = await verify_database()

        if success:
            print("\n✅ Wszystkie dane zapisane poprawnie!")
        else:
            print("\n⚠️  Niektóre dane nie zostały zapisane")
            return False

    except Exception as e:
        print(f"\n❌ Weryfikacja bazy failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Podsumowanie
    print("\n" + "=" * 80)
    print("✅ TEST ZAKOŃCZONY POMYŚLNIE")
    print("=" * 80)
    print("\n📝 Następne kroki:")
    print("   1. Uruchom serwer: uvicorn src.api.main:app --reload")
    print("   2. Test endpointu: curl http://localhost:8000/api/stats/demographics")
    print("   3. Test endpointu: curl http://localhost:8000/api/stats/employment")
    print()

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_gus_job())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test przerwany przez użytkownika")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
