
import asyncio
from src.scrapers.mojedzialdowo import MojeDzialdowoScraper

async def test_mojedzialdowo():
    scraper = MojeDzialdowoScraper(source_id=2)
    async with scraper:
        # Fetch the main news page
        url = "https://mojedzialdowo.pl" 
        print(f"Fetching {url}...")
        try:
            html = await scraper.fetch(url)
            articles = await scraper.parse(html, url)
            
            print(f"Found {len(articles)} articles.")
            for i, article in enumerate(articles[:3]):
                print(f"--- Article {i+1} ---")
                print(f"Title: {article.get('title')}")
                print(f"URL: {article.get('url')}")
                print(f"Content (Preview): {article.get('content')}")
                print(f"Date: {article.get('published_at')}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_mojedzialdowo())
