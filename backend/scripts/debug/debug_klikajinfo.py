
import asyncio
from src.scrapers.klikajinfo import KlikajInfoScraper

async def test_klikajinfo():
    scraper = KlikajInfoScraper(source_id=3)
    async with scraper:
        url = "https://klikajinfo.pl"
        print(f"Fetching {url}...")
        try:
            html = await scraper.fetch(url)
            articles = await scraper.parse(html, url)
            
            print(f"Found {len(articles)} articles.")
            for i, article in enumerate(articles[:3]):
                print(f"--- Article {i+1} ---")
                print(f"Title: {article.get('title')}")
                print(f"URL: {article.get('url')}")
                print(f"Content: {article.get('content')}")
                print(f"Date: {article.get('published_at')}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_klikajinfo())
