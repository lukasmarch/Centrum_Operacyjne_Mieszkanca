#!/usr/bin/env python3
"""
Inicjalizacja nowych źródeł danych w bazie:
- Gmina Rybno
- Moje Działdowo
- Facebook (Apify) - szablon

Uruchomienie:
    cd backend
    python scripts/init_new_sources.py
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Dodaj backend do path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.database.schema import Source
from src.utils.logger import setup_logger

logger = setup_logger("InitNewSources")


async def init_sources():
    """Dodaj nowe źródła do bazy danych"""

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment variables")

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    new_sources = [
        {
            "name": "Gmina Rybno",
            "type": "urząd",
            "url": "https://gminarybno.pl/aktualnosci.html",
            "scraping_config": {
                "scraper_class": "GminaRybnoScraper",
                "rate_limit": 0.5,  # 0.5 req/s (2s delay)
                "user_agent": "Mozilla/5.0 (compatible; CentrumOperacyjneMieszkanca/1.0)",
            },
            "status": "active"
        },
        {
            "name": "Moje Działdowo",
            "type": "media",
            "url": "https://mojedzialdowo.pl",
            "scraping_config": {
                "scraper_class": "MojeDzialdowoScraper",
                "rate_limit": 0.5,  # 0.5 req/s
                "user_agent": "Mozilla/5.0 (compatible; CentrumOperacyjneMieszkanca/1.0)",
            },
            "status": "active"
        },
        {
            "name": "Gmina Działdowo Facebook",
            "type": "social_media",
            "url": "https://facebook.com/GminaDzialdowo",
            "scraping_config": {
                "scraper_class": "ApifyFacebookScraper",
                "apify_api_key": "UZUPEŁNIJ_W_BAZIE",  # Należy uzupełnić ręcznie
                "facebook_page_url": "https://facebook.com/GminaDzialdowo",
                "max_posts": 20,
                "actor_id": "apify/facebook-pages-scraper",
            },
            "status": "inactive"  # Nieaktywny do momentu skonfigurowania Apify
        },
    ]

    async with async_session() as session:
        for source_data in new_sources:
            try:
                # Sprawdź czy źródło już istnieje
                statement = select(Source).where(Source.url == source_data["url"])
                result = await session.execute(statement)
                existing = result.scalar_one_or_none()

                if existing:
                    logger.info(f"Źródło już istnieje: {source_data['name']}")
                    # Opcjonalnie: zaktualizuj config
                    existing.scraping_config = source_data["scraping_config"]
                    existing.status = source_data["status"]
                    await session.commit()
                    logger.info(f"  ✓ Zaktualizowano konfigurację")
                else:
                    # Utwórz nowe źródło
                    source = Source(**source_data)
                    session.add(source)
                    await session.commit()
                    await session.refresh(source)
                    logger.info(f"✓ Dodano nowe źródło: {source.name} (ID: {source.id})")

            except Exception as e:
                logger.error(f"Błąd przy dodawaniu źródła {source_data['name']}: {e}")
                await session.rollback()

    logger.info("\n" + "=" * 60)
    logger.info("PODSUMOWANIE - Wszystkie źródła w bazie:")
    logger.info("=" * 60)

    # Wyświetl wszystkie źródła
    async with async_session() as session:
        statement = select(Source)
        result = await session.execute(statement)
        sources = result.scalars().all()

        for source in sources:
            logger.info(f"\nID: {source.id}")
            logger.info(f"  Nazwa: {source.name}")
            logger.info(f"  Typ: {source.type}")
            logger.info(f"  URL: {source.url}")
            logger.info(f"  Status: {source.status}")
            logger.info(f"  Scraper: {source.scraping_config.get('scraper_class', 'BRAK')}")
            if source.last_scraped:
                logger.info(f"  Ostatnio: {source.last_scraped}")

    logger.info("\n" + "=" * 60)
    logger.info("UWAGI:")
    logger.info("=" * 60)
    logger.info("1. Gmina Rybno i Moje Działdowo są AKTYWNE i gotowe do scrapingu")
    logger.info("2. Facebook (Apify) jest NIEAKTYWNY - wymaga konfiguracji:")
    logger.info("   - Załóż konto na https://apify.com")
    logger.info("   - Pobierz API token")
    logger.info("   - Zaktualizuj źródło w bazie: UPDATE sources SET")
    logger.info("     scraping_config['apify_api_key'] = 'twój_token'")
    logger.info("   - Zmień status na 'active'")
    logger.info("=" * 60)

    await engine.dispose()


async def main():
    logger.info("Rozpoczynam inicjalizację nowych źródeł...\n")
    await init_sources()
    logger.info("\n✓ Inicjalizacja zakończona!")


if __name__ == "__main__":
    asyncio.run(main())
