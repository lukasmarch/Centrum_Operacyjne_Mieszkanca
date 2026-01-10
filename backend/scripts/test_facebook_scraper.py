#!/usr/bin/env python3
"""
Test Facebook scraper z Apify API.

UWAGA: Ten test wykonuje PRAWDZIWE wywołanie Apify API i kosztuje kredyty!
- Free tier: $5/miesiąc (~1000 postów)
- Ten test: ~20 postów z 1 źródła (~$0.10)

Uruchomienie:
    cd backend
    python scripts/test_facebook_scraper.py
"""

import asyncio
import sys
from pathlib import Path

# Dodaj backend do path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.database.schema import Source, Article
from src.scrapers.apify_facebook import ApifyFacebookScraper
from src.utils.logger import setup_logger
import os
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

logger = setup_logger("TestFacebookScraper")


async def test_facebook_scraper():
    """Test Facebook scraper z Apify API"""

    # Sprawdź API key
    apify_key = os.getenv("APIFY_API_KEY")
    if not apify_key:
        logger.error("APIFY_API_KEY nie znaleziony w .env!")
        logger.error("Dodaj: APIFY_API_KEY=apify_api_twój_token")
        return

    logger.info(f"✓ APIFY_API_KEY: {apify_key[:20]}...")

    database_url = os.getenv("DATABASE_URL")
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    logger.info("\n" + "=" * 60)
    logger.info("TEST FACEBOOK SCRAPER - APIFY API")
    logger.info("=" * 60)
    logger.info("UWAGA: Ten test kosztuje ~$0.10 kredytów Apify!")
    logger.info("=" * 60 + "\n")

    # Testuj tylko jedno źródło (Facebook - Syla)
    async with async_session() as session:
        # Pobierz Facebook - Syla
        statement = select(Source).where(Source.name == "Facebook - Syla")
        result = await session.execute(statement)
        source = result.scalar_one_or_none()

        if not source:
            logger.error("Źródło 'Facebook - Syla' nie znalezione!")
            logger.error("Uruchom: python scripts/add_facebook_sources.py")
            return

        if source.status != "active":
            logger.error(f"Źródło '{source.name}' nie jest aktywne (status: {source.status})")
            logger.error("Uruchom: python scripts/add_facebook_sources.py")
            return

        logger.info(f"Testowanie źródła: {source.name}")
        logger.info(f"URL: {source.url}")
        logger.info(f"Status: {source.status}")
        logger.info(f"Config: {source.scraping_config}")
        logger.info("")

        # Inicjalizuj scraper
        try:
            scraper = ApifyFacebookScraper(
                source_id=source.id,
                config=source.scraping_config
            )
            logger.info(f"✓ Scraper zainicjalizowany")
            logger.info(f"  Actor: {scraper.actor_id}")
            logger.info(f"  Results limit: {scraper.results_limit}")
            logger.info(f"  Caption text: {scraper.caption_text}")
            logger.info("")

        except ValueError as e:
            logger.error(f"✗ Błąd konfiguracji scrapera: {e}")
            return

        # Scrape Facebook
        logger.info("=" * 60)
        logger.info("ROZPOCZYNAM SCRAPING FACEBOOK (Apify API)")
        logger.info("=" * 60)
        logger.info("To może zająć 1-3 minuty (Apify uruchamia actor)...")
        logger.info("")

        try:
            async with scraper:
                saved_ids = await scraper.scrape([source.url], session)

            logger.info("")
            logger.info("=" * 60)
            logger.info("WYNIK SCRAPINGU")
            logger.info("=" * 60)
            logger.info(f"✓ Zapisano {len(saved_ids)} postów z Facebook")

            if len(saved_ids) > 0:
                # Pobierz przykładowe posty
                logger.info("\nPrzykładowe posty:")
                statement = select(Article).where(Article.id.in_(saved_ids[:3]))
                result = await session.execute(statement)
                articles = result.scalars().all()

                for i, article in enumerate(articles, 1):
                    logger.info(f"\n{i}. {article.title}")
                    logger.info(f"   URL: {article.url}")
                    logger.info(f"   External ID: {article.external_id}")
                    if article.image_url:
                        logger.info(f"   Image: {article.image_url[:50]}...")
                    if article.published_at:
                        logger.info(f"   Published: {article.published_at}")
                    content_preview = article.content[:100] if article.content else "N/A"
                    logger.info(f"   Content: {content_preview}...")

            logger.info("\n" + "=" * 60)
            logger.info("TEST ZAKOŃCZONY POMYŚLNIE! ✓")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"\n✗ Błąd podczas scrapingu: {e}")
            logger.error(f"Typ błędu: {type(e).__name__}")
            import traceback
            logger.error(traceback.format_exc())

    await engine.dispose()


async def main():
    logger.info("Rozpoczynam test Facebook scrapera...\n")
    await test_facebook_scraper()
    logger.info("\n✓ Test zakończony!")


if __name__ == "__main__":
    asyncio.run(main())
