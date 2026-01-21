import logging
import sys
import os

# Add backend to path so imports work
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from src.scrapers.cinema import CinemaScraper

# Configure logging
logging.basicConfig(level=logging.DEBUG)

def debug_scraper():
    scraper = CinemaScraper()
    
    cities = ['Dzialdowo', 'Lubawa']
    
    for city in cities:
        print(f"\n--- Testing city: {city} ---")
        try:
            result = scraper.fetch_repertoire(city)
            print(f"Cinema Name: {result.cinemaName}")
            print(f"Date: {result.date}")
            print(f"Movies found: {len(result.movies)}")
            for movie in result.movies:
                print(f" - {movie.title} | {movie.time} | {movie.link}")
        except Exception as e:
            print(f"CRITICAL ERROR for {city}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug_scraper()
