#!/usr/bin/env python3
"""
Script to initialize sources in the database.
Adds Klikaj.info as the first source.
"""
import asyncio
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Import Source model directly without going through database/__init__.py
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.schema import Source


async def init_sources():
    """Initialize sources in the database."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment variables")

    engine = create_async_engine(database_url, echo=True)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Check if Klikaj.info already exists
        result = await session.execute(
            select(Source).where(Source.name == "Klikaj.info")
        )
        existing_source = result.scalar_one_or_none()

        if existing_source:
            print(f"✓ Source 'Klikaj.info' already exists (ID: {existing_source.id})")
            return existing_source.id

        # Create Klikaj.info source
        klikaj_source = Source(
            name="Klikaj.info",
            type="media",
            url="https://klikajinfo.pl",
            scraping_config={
                "base_url": "https://klikajinfo.pl",
                "pattern": "/artykul/",
                "frequency": "hourly"
            },
            status="active",
            created_at=datetime.utcnow()
        )

        session.add(klikaj_source)
        await session.commit()
        await session.refresh(klikaj_source)

        print(f"✓ Created source 'Klikaj.info' (ID: {klikaj_source.id})")
        return klikaj_source.id

    await engine.dispose()


if __name__ == "__main__":
    source_id = asyncio.run(init_sources())
    print(f"\n🎉 Database initialized successfully!")
    print(f"📰 Klikaj.info source ID: {source_id}")
