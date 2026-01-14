
import asyncio
from src.scrapers.gmina_rybno import GminaRybnoScraper

async def test_rybno():
    scraper = GminaRybnoScraper(source_id=1)
    async with scraper:
        # Fetch the main news page
        url = "https://gminarybno.pl/aktualnosci"  # Adjust if actual URL is different
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
                print(f"Keys present: {list(article.keys())}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_rybno())
