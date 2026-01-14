#!/usr/bin/env python3
"""
Helper do dodawania źródeł Facebook do bazy danych.

KONFIGURACJA:
1. Załóż konto Apify: https://apify.com
2. Pobierz API token: https://console.apify.com/account/integrations
3. Dodaj do .env: APIFY_API_KEY=apify_api_***
4. Uruchom: python scripts/add_facebook_sources.py

UŻYCIE:
    cd backend
    python scripts/add_facebook_sources.py
"""

import asyncio
import sys
import os
from pathlib import Path
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

logger = setup_logger("AddFacebookSources")

# ============================================================
# KONFIGURACJA KONT FACEBOOK
# ============================================================

# Lista kont Facebook do śledzenia
FACEBOOK_SOURCES = [
    {
        "name": "Facebook - Syla",
        "display_name": "Serwis Informacyjny Syla",
        "url": "https://www.facebook.com/serwis.informacyjny.syla",
        "description": "Lokalne wiadomości z powiatu działdowskiego",
        "status": "inactive",  # Zmień na 'active' po dodaniu API key
    },
    {
        "name": "Facebook - Gmina Działdowo",
        "display_name": "Gmina Działdowo",
        "url": "https://www.facebook.com/GminaDzialdowo",
        "description": "Oficjalna strona Gminy Działdowo",
        "status": "inactive",
    },
    {
        "name": "Facebook - Urząd Miasta Działdowo",
        "display_name": "Urząd Miasta Działdowo",
        "url": "https://www.facebook.com/UrzadMiastaDzialdowo",
        "description": "Urząd Miasta Działdowo - informacje urzędowe",
        "status": "inactive",
    },
    # Dodaj więcej kont tutaj (max 10-15)
    # {
    #     "name": "Facebook - Nazwa Źródła",
    #     "display_name": "Pełna Nazwa",
    #     "url": "https://www.facebook.com/username",
    #     "description": "Opis źródła",
    #     "status": "inactive",
    # },
]

# Wspólna konfiguracja Apify dla wszystkich źródeł FB
APIFY_CONFIG_TEMPLATE = {
    "scraper_class": "ApifyFacebookScraper",
    "actor_id": "apify~facebook-posts-scraper",  # Uwaga: ~ nie /
    "results_limit": 20,
    "caption_text": False,
    "apify_api_key": None,  # Będzie uzupełnione z .env lub ręcznie
}


async def add_facebook_sources():
    """Dodaj źródła Facebook do bazy danych"""

    # Pobierz API key z .env (opcjonalnie)
    apify_api_key = os.getenv("APIFY_API_KEY")

    if apify_api_key:
        logger.info(f"✓ Znaleziono APIFY_API_KEY w .env: {apify_api_key[:20]}...")
        APIFY_CONFIG_TEMPLATE["apify_api_key"] = apify_api_key
    else:
        logger.warning("⚠ APIFY_API_KEY nie znaleziony w .env - źródła będą nieaktywne")
        logger.warning("  Dodaj do .env: APIFY_API_KEY=twój_token")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment variables")

    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    logger.info(f"\n{'=' * 60}")
    logger.info(f"Dodawanie {len(FACEBOOK_SOURCES)} źródeł Facebook")
    logger.info(f"{'=' * 60}\n")

    added_count = 0
    updated_count = 0
    skipped_count = 0

    async with async_session() as session:
        for fb_source in FACEBOOK_SOURCES:
            try:
                # Sprawdź czy źródło już istnieje
                statement = select(Source).where(Source.name == fb_source["name"])
                result = await session.execute(statement)
                existing = result.scalar_one_or_none()

                # Przygotuj config
                config = APIFY_CONFIG_TEMPLATE.copy()
                config["facebook_page_url"] = fb_source["url"]

                # Ustaw status - active tylko jeśli mamy API key
                status = fb_source["status"]
                if apify_api_key and status == "inactive":
                    status = "active"
                    logger.info(f"  ⚡ Automatycznie aktywowano (znaleziono API key)")

                if existing:
                    # Zaktualizuj istniejące źródło
                    existing.url = fb_source["url"]
                    existing.scraping_config = config
                    existing.status = status
                    await session.commit()
                    updated_count += 1
                    logger.info(f"🔄 Zaktualizowano: {fb_source['name']}")
                    logger.info(f"   URL: {fb_source['url']}")
                    logger.info(f"   Status: {status}")
                else:
                    # Utwórz nowe źródło
                    source = Source(
                        name=fb_source["name"],
                        type="social_media",
                        url=fb_source["url"],
                        scraping_config=config,
                        status=status,
                    )
                    session.add(source)
                    await session.commit()
                    await session.refresh(source)
                    added_count += 1
                    logger.info(f"✓ Dodano: {fb_source['name']} (ID: {source.id})")
                    logger.info(f"   URL: {fb_source['url']}")
                    logger.info(f"   Status: {status}")

            except Exception as e:
                logger.error(f"✗ Błąd przy {fb_source['name']}: {e}")
                skipped_count += 1
                await session.rollback()

            logger.info("")

    logger.info(f"{'=' * 60}")
    logger.info("PODSUMOWANIE")
    logger.info(f"{'=' * 60}")
    logger.info(f"✓ Dodano nowych: {added_count}")
    logger.info(f"🔄 Zaktualizowano: {updated_count}")
    logger.info(f"✗ Pominięto (błędy): {skipped_count}")
    logger.info(f"{'=' * 60}\n")

    # Wyświetl wszystkie źródła Facebook
    logger.info("Wszystkie źródła Facebook w bazie:")
    logger.info(f"{'=' * 60}")

    async with async_session() as session:
        statement = select(Source).where(Source.type == "social_media")
        result = await session.execute(statement)
        fb_sources = result.scalars().all()

        for source in fb_sources:
            logger.info(f"\nID: {source.id}")
            logger.info(f"  Nazwa: {source.name}")
            logger.info(f"  URL: {source.url}")
            logger.info(f"  Status: {source.status}")
            if source.scraping_config:
                logger.info(f"  Results limit: {source.scraping_config.get('results_limit', 'N/A')}")
                has_key = "✓" if source.scraping_config.get('apify_api_key') else "✗"
                logger.info(f"  API key: {has_key}")

    logger.info(f"\n{'=' * 60}")
    logger.info("NASTĘPNE KROKI:")
    logger.info(f"{'=' * 60}")

    if not apify_api_key:
        logger.info("1. Załóż konto Apify: https://apify.com")
        logger.info("2. Pobierz API token: https://console.apify.com/account/integrations")
        logger.info("3. Dodaj do .env: APIFY_API_KEY=twój_token")
        logger.info("4. Uruchom ponownie ten script lub zaktualizuj ręcznie w bazie")
    else:
        logger.info("1. ✓ API key skonfigurowany")
        logger.info("2. Uruchom test: python scripts/test_facebook_scraper.py")
        logger.info("3. Backend: uvicorn src.api.main:app --reload")

    logger.info(f"{'=' * 60}")

    await engine.dispose()


async def main():
    logger.info("Rozpoczynam dodawanie źródeł Facebook...\n")
    await add_facebook_sources()
    logger.info("\n✓ Zakończono!")


if __name__ == "__main__":
    asyncio.run(main())
