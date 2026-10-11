"""
Migration: sprawa (`story_id`) dla artykułów (2026-10-11)

Audyt 11.10.2026 (F-040, E3c): ta sama sprawa opisana dwiema redakcjami albo
w dwóch odsłonach (zapowiedź → relacja) stała w feedzie dwa razy, a żaden próg
podobieństwa jej nie rozdziela — różne mecze tego samego klubu mają 0,74,
ten sam wypadek 0,776. Rozstrzyga sędzia (`services/story_judge.py`) i zapisuje
wynik RAZ, tutaj:
  - `story_id` — id najstarszego wpisu sprawy (ON DELETE SET NULL: takedown
    wpisu-korzenia nie kasuje pozostałych);
  - `story_checked_at` — wpis był już oceniany; sędzia nie pyta drugi raz.

Addytywna — stary kod jej nie zauważy, więc idzie na produkcję PRZED kodem.
Bez wypełniania wstecz. Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.add_article_story
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings

STATEMENTS = (
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS story_id INTEGER "
    "REFERENCES articles(id) ON DELETE SET NULL",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS story_checked_at TIMESTAMP",
    "CREATE INDEX IF NOT EXISTS idx_articles_story_id ON articles (story_id) WHERE story_id IS NOT NULL",
)


async def migrate():
    print("=" * 60)
    print("Migration: articles.story_id / story_checked_at")
    print("=" * 60)
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        for stmt in STATEMENTS:
            await conn.execute(text(stmt))
    await engine.dispose()
    print("✓ articles.story_id (FK, ON DELETE SET NULL), story_checked_at, indeks")
    print("\n✅ Migracja zakończona")


if __name__ == "__main__":
    asyncio.run(migrate())
