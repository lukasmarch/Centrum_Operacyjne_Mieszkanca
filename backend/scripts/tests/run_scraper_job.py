#!/usr/bin/env python3
"""
Ręczne uruchomienie job scrapera dla wybranego źródła (z zapisem do DB).

Uruchomienie:
    cd backend
    python scripts/tests/run_scraper_job.py "Gmina Rybno"
    python scripts/tests/run_scraper_job.py "Moje Działdowo"
    python scripts/tests/run_scraper_job.py "BIP Gminy Rybno"
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_path))

from src.scheduler.article_job import update_articles_job
from src.utils.logger import setup_logger

logger = setup_logger("RunScraperJob")


async def main():
    if len(sys.argv) < 2:
        print("Użycie: python run_scraper_job.py <nazwa_zrodla>")
        print('Przykład: python run_scraper_job.py "Gmina Rybno"')
        sys.exit(1)

    source_name = sys.argv[1]
    logger.info(f"Uruchamiam job scrapera dla: {source_name}")
    await update_articles_job(source_filter=source_name)


if __name__ == "__main__":
    asyncio.run(main())
