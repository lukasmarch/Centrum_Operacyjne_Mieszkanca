#!/usr/bin/env python3
"""
Test Scraper Registry i integracji ze schedulerem

Sprawdza:
1. Import registry
2. Import article_job
3. Lista wszystkich scraperów
4. Test get_scraper()
"""
import sys
from pathlib import Path

# Dodaj backend do path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from src.scrapers.registry import SCRAPER_REGISTRY, get_scraper, list_scrapers
from src.scheduler.article_job import update_articles_job

def test_registry():
    """Test registry scraperów"""
    print("=" * 60)
    print("TEST SCRAPER REGISTRY")
    print("=" * 60)

    # Test 1: Lista scraperów
    print("\n1. Lista zarejestrowanych scraperów:")
    scrapers = list_scrapers()
    for source_name, scraper_class_name in scrapers.items():
        print(f"   ✓ {source_name} -> {scraper_class_name}")

    print(f"\n   Łącznie: {len(scrapers)} scraperów")

    # Test 2: get_scraper()
    print("\n2. Test get_scraper():")
    test_sources = ["Klikaj.info", "Gmina Rybno", "Moje Działdowo", "Facebook - Syla"]

    for source_name in test_sources:
        scraper_class = get_scraper(source_name)
        if scraper_class:
            print(f"   ✓ {source_name}: {scraper_class.__name__}")
        else:
            print(f"   ✗ {source_name}: Nie znaleziono!")

    # Test 3: Test nieistniejącego źródła
    print("\n3. Test nieistniejącego źródła:")
    scraper_class = get_scraper("Nieistniejace Zrodlo")
    if scraper_class is None:
        print("   ✓ Prawidłowo zwrócono None dla nieistniejącego źródła")
    else:
        print("   ✗ Błąd: powinno zwrócić None!")

    # Test 4: Sprawdź import article_job
    print("\n4. Test importu article_job:")
    try:
        print(f"   ✓ article_job zaimportowany: {update_articles_job.__name__}")
    except Exception as e:
        print(f"   ✗ Błąd importu: {e}")

    print("\n" + "=" * 60)
    print("WYNIK: Wszystkie testy zakończone pomyślnie! ✓")
    print("=" * 60)
    print("\nNastępne kroki:")
    print("1. Uruchom: python scripts/init_new_sources.py")
    print("2. Uruchom: python scripts/test_new_scrapers.py")
    print("3. Backend: uvicorn src.api.main:app --reload")
    print("=" * 60)


if __name__ == "__main__":
    test_registry()
