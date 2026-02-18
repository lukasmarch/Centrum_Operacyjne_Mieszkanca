"""
Setup: Insert BIP Gminy Rybno source (Sprint 5D)

Dodaje źródło "BIP Gminy Rybno" do tabeli sources w bazie danych.
Uruchom raz po wdrożeniu BipRybnoScraper.

Użycie:
    cd backend && python scripts/setup/add_bip_source.py
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from src.config import settings
from src.database.schema import Source


BIP_SOURCE = {
    "name": "BIP Gminy Rybno",
    "type": "html",
    "url": "https://bip.gminarybno.pl/112/",
    "scraping_config": {
        "news_url": "https://bip.gminarybno.pl/112/",
        "download_pdfs": True,
        "pdf_extraction": "pdfplumber",
        "firecrawl_fallback": True,
        "max_pages_per_run": 3,
    },
    "status": "active",
}


async def add_source():
    print("=" * 60)
    print("Setup: Add BIP Gminy Rybno source")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Sprawdź czy źródło już istnieje
        result = await session.execute(
            select(Source).where(Source.name == "BIP Gminy Rybno")
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"✓ Source 'BIP Gminy Rybno' already exists (id={existing.id})")
            print(f"  URL: {existing.url}")
            print(f"  Status: {existing.status}")
        else:
            source = Source(**BIP_SOURCE)
            session.add(source)
            await session.commit()
            await session.refresh(source)
            print(f"✓ Source 'BIP Gminy Rybno' created (id={source.id})")
            print(f"  URL: {source.url}")

    await engine.dispose()
    print("\n✅ Done!")


if __name__ == "__main__":
    asyncio.run(add_source())
