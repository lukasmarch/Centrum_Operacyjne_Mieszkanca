#!/usr/bin/env python3
"""
Test script dla nowych scraperów:
- GminaRybnoScraper
- MojeDzialdowoScraper
- ApifyFacebookScraper (mock test - bez rzeczywistego Apify API)

Uruchomienie:
    cd backend
    python scripts/test_new_scrapers.py
"""

import asyncio
import sys
from pathlib import Path

# Dodaj backend do path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from src.scrapers import GminaRybnoScraper, MojeDzialdowoScraper, ApifyFacebookScraper
from src.utils.logger import setup_logger

logger = setup_logger("TestScrapers")


async def test_gmina_rybno():
    """Test GminaRybnoScraper"""
    logger.info("=" * 60)
    logger.info("TEST: GminaRybnoScraper")
    logger.info("=" * 60)

    scraper = GminaRybnoScraper(source_id=999)  # Fake ID dla testu

    async with scraper:
        try:
            # Fetch HTML
            url = "https://gminarybno.pl/aktualnosci.html"
            html = await scraper.fetch(url)
            logger.info(f"Pobrano HTML: {len(html)} znaków")

            # Parse articles
            articles = await scraper.parse(html, url)
            logger.info(f"Sparsowano {len(articles)} artykułów")

            # Pokaż pierwsze 3 artykuły
            for i, article in enumerate(articles[:3], 1):
                logger.info(f"\nArtykuł #{i}:")
                title = article.get('title', 'BRAK')
                logger.info(f"  Tytuł: {title[:80] if title else 'BRAK'}")
                url = article.get('url', 'BRAK')
                logger.info(f"  URL: {url[:80] if url else 'BRAK'}")
                image = article.get('image_url', 'BRAK')
                logger.info(f"  Image: {image[:80] if image else 'BRAK'}")
                logger.info(f"  External ID: {article.get('external_id', 'BRAK')}")

            return len(articles)

        except Exception as e:
            logger.error(f"Błąd w teście GminaRybno: {e}")
            import traceback
            traceback.print_exc()
            return 0


async def test_mojedzialdowo():
    """Test MojeDzialdowoScraper"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST: MojeDzialdowoScraper")
    logger.info("=" * 60)

    scraper = MojeDzialdowoScraper(source_id=998)  # Fake ID dla testu

    async with scraper:
        try:
            # Fetch HTML
            url = "https://mojedzialdowo.pl"
            html = await scraper.fetch(url)
            logger.info(f"Pobrano HTML: {len(html)} znaków")

            # Parse articles
            articles = await scraper.parse(html, url)
            logger.info(f"Sparsowano {len(articles)} artykułów")

            # Pokaż pierwsze 3 artykuły
            for i, article in enumerate(articles[:3], 1):
                logger.info(f"\nArtykuł #{i}:")
                title = article.get('title', 'BRAK')
                logger.info(f"  Tytuł: {title[:80] if title else 'BRAK'}")
                url = article.get('url', 'BRAK')
                logger.info(f"  URL: {url[:80] if url else 'BRAK'}")
                image = article.get('image_url', 'BRAK')
                logger.info(f"  Image: {image[:80] if image else 'BRAK'}")
                logger.info(f"  External ID: {article.get('external_id', 'BRAK')}")
                if article.get('content'):
                    logger.info(f"  Content: {article['content'][:100]}...")

            return len(articles)

        except Exception as e:
            logger.error(f"Błąd w teście MojeDzialdowo: {e}")
            import traceback
            traceback.print_exc()
            return 0


async def test_apify_facebook_mock():
    """Test ApifyFacebookScraper - mock bez rzeczywistego API"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST: ApifyFacebookScraper (MOCK)")
    logger.info("=" * 60)

    # Mock JSON response z Apify
    mock_json_response = """
    [
        {
            "postId": "123456789",
            "text": "Ważna informacja dla mieszkańców Dzialdowa. Jutro od godz 10:00 spotkanie w ratuszu.",
            "url": "https://facebook.com/123456789",
            "timestamp": "2026-01-10T10:00:00Z",
            "imageUrl": "https://example.com/image1.jpg",
            "likes": 42,
            "comments": 5,
            "shares": 2
        },
        {
            "postId": "987654321",
            "text": "Zapraszamy na festyn rodzinny w sobotę. Wstęp wolny!",
            "url": "https://facebook.com/987654321",
            "timestamp": "2026-01-09T15:30:00Z",
            "imageUrl": "https://example.com/image2.jpg",
            "likes": 128,
            "comments": 15,
            "shares": 8
        }
    ]
    """

    # Konfiguracja scraper (bez prawdziwego API key)
    config = {
        "apify_api_key": "mock_api_key_for_test",
        "facebook_page_url": "https://facebook.com/TestPage",
        "max_posts": 20
    }

    try:
        scraper = ApifyFacebookScraper(source_id=997, config=config)

        # Test tylko parse (bez fetch, bo wymaga Apify API)
        articles = await scraper.parse(mock_json_response, "https://facebook.com/TestPage")
        logger.info(f"Sparsowano {len(articles)} postów z mock JSON")

        # Pokaż wszystkie
        for i, article in enumerate(articles, 1):
            logger.info(f"\nPost #{i}:")
            logger.info(f"  Tytuł: {article.get('title', 'BRAK')}")
            logger.info(f"  URL: {article.get('url', 'BRAK')}")
            logger.info(f"  Image: {article.get('image_url', 'BRAK')}")
            logger.info(f"  External ID: {article.get('external_id', 'BRAK')}")
            logger.info(f"  Published: {article.get('published_at', 'BRAK')}")
            logger.info(f"  Content: {article.get('content', 'BRAK')[:100]}...")

        return len(articles)

    except Exception as e:
        logger.error(f"Błąd w teście ApifyFacebook: {e}")
        import traceback
        traceback.print_exc()
        return 0


SCRAPERS = {
    'rybno': test_gmina_rybno,
    'dzialdowo': test_mojedzialdowo,
    'facebook': test_apify_facebook_mock,
}

async def main():
    selected = sys.argv[1:]

    if not selected:
        print("Użycie: python test_new_scrapers.py [rybno] [dzialdowo] [facebook]")
        print(f"Dostępne: {', '.join(SCRAPERS.keys())}")
        sys.exit(1)

    unknown = [s for s in selected if s not in SCRAPERS]
    if unknown:
        print(f"Nieznane scrapery: {', '.join(unknown)}")
        print(f"Dostępne: {', '.join(SCRAPERS.keys())}")
        sys.exit(1)

    logger.info(f"Uruchamiam: {', '.join(selected)}\n")

    results = {}
    for name in selected:
        results[name] = await SCRAPERS[name]()

    logger.info("\n" + "=" * 60)
    logger.info("PODSUMOWANIE")
    logger.info("=" * 60)
    for name, count in results.items():
        logger.info(f"{name}: {count} artykułów")
    logger.info("=" * 60)

    total = sum(results.values())
    if total > 0:
        logger.info(f"SUCCESS: Łącznie {total} artykułów")
    else:
        logger.error("FAILURE: Żaden scraper nie zwrócił wyników")

    return total


if __name__ == "__main__":
    total = asyncio.run(main())
    sys.exit(0 if total > 0 else 1)
