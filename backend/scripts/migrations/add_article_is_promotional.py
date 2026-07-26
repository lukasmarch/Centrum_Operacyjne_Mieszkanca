"""
Migration: is_promotional na articles (Etap 0 dywersyfikacji feedu, 2026-07-26)

Cudze reklamy komercyjne scrapowane z profili FB ("czyszczenie kostki brukowej",
"zapraszamy na stoisko") nie są wiadomością i kolidują z ofertą wizytówek
dla firm — wykluczone z /api/articles.

Migracja jest idempotentna — można uruchamiać wielokrotnie.

Użycie:
    cd backend && python -m scripts.migrations.add_article_is_promotional
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.config import settings


async def migrate():
    print("=" * 60)
    print("Migration: articles.is_promotional")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("""
            ALTER TABLE articles
            ADD COLUMN IF NOT EXISTS is_promotional BOOLEAN NOT NULL DEFAULT FALSE
        """))
        print("✓ Kolumna is_promotional")

    await engine.dispose()
    print("=" * 60)
    print("Migracja zakończona.")


if __name__ == "__main__":
    asyncio.run(migrate())
