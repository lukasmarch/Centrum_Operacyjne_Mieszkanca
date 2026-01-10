"""Test script dla KlikajInfoScraper"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.scrapers.klikajinfo import KlikajInfoScraper

async def main():
    print("=== TEST KLIKAJINFO SCRAPER ===\n")

    scraper = KlikajInfoScraper(source_id=1)

    async with scraper:
        # Fetch homepage
        url = "https://klikajinfo.pl"
        print(f"Fetching: {url}")

        html = await scraper.fetch(url)
        print(f"Downloaded {len(html)} chars\n")

        # Parse articles
        articles = await scraper.parse(html, url)

        print(f"\nZnaleziono {len(articles)} artykułów:\n")
        print("=" * 80)

        for i, article in enumerate(articles[:10], 1):
            print(f"{i}. {article['title']}")
            print(f"   URL: {article['url']}")
            print(f"   ID: {article.get('external_id')}")
            if article.get('image_url'):
                print(f"   IMG: {article['image_url'][:60]}...")
            print()

        print("=" * 80)
        print(f"\nTest OK - {len(articles)} artykułów gotowych do zapisu")

if __name__ == "__main__":
    asyncio.run(main())
