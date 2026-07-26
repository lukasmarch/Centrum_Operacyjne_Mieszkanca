"""
Migration: display_title + is_filler na articles (poprawki przedpremierowe, 2026-07-26)

- display_title — nagłówek napisany przez AI; feed pokazuje go zamiast
  surowego tytułu kopiowanego ze źródła (kwestia prawna + jakość)
- is_filler    — posty powitalne/zapychacze ("Dzień dobry, dziś...")
  wykluczone z /api/articles

Migracja jest idempotentna — można uruchamiać wielokrotnie.

Użycie:
    cd backend && python -m scripts.migrations.add_article_display_title
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
    print("Migration: articles.display_title + articles.is_filler")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("""
            ALTER TABLE articles
            ADD COLUMN IF NOT EXISTS display_title VARCHAR(200)
        """))
        print("✓ Kolumna display_title")

        await conn.execute(text("""
            ALTER TABLE articles
            ADD COLUMN IF NOT EXISTS is_filler BOOLEAN NOT NULL DEFAULT FALSE
        """))
        print("✓ Kolumna is_filler")

    await engine.dispose()
    print("=" * 60)
    print("Migracja zakończona.")


if __name__ == "__main__":
    asyncio.run(migrate())
