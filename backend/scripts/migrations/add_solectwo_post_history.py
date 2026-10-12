"""
Migration: korekta i odwołanie opublikowanego ogłoszenia sołectwa (2026-10-12)

Audyt 10.10.2026 (T-06, etap E7): opublikowanego ogłoszenia nie dało się
poprawić ani wycofać — edycja zwracała 409, a awaryjne `DELETE /api/articles`
padało na kluczach obcych (`solectwo_posts.article_id`, `events.source_article_id`).
Sołtys, który pomylił datę zebrania, nie miał żadnej drogi poza telefonem,
a redakcja — żadnego narzędzia.

  - `solectwo_post_versions` — każda opublikowana postać ogłoszenia (publikacja,
    korekta, odwołanie) z powodem i autorem zmiany. Wiersz nie znika.
  - `solectwo_post_requests` — prośba sołtysa o korektę albo odwołanie;
    publikuje redakcja, jak przy pierwszej wersji.
  - `articles.withdrawn_at` / `events.withdrawn_at` — jedna kolumna w bramce
    `publishable_conditions` / `visible_event_conditions` wyłącza wpis wszędzie
    naraz (feed, briefing, newsletter, push, agenci, kalendarz).
  - `articles.term_corrected_at` — korekta TERMINU wraca do najbliższego
    briefingu z etykietą „KOREKTA”.

Addytywna — stary kod jej nie zauważy, więc idzie na produkcję PRZED kodem.
Idempotentna. Opublikowane ogłoszenia bez historii dostają wersję 1.

Użycie:
    cd backend && python -m scripts.migrations.add_solectwo_post_history
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
    """
    CREATE TABLE IF NOT EXISTS solectwo_post_versions (
        id SERIAL PRIMARY KEY,
        post_id INTEGER NOT NULL REFERENCES solectwo_posts(id) ON DELETE CASCADE,
        version INTEGER NOT NULL,
        kind VARCHAR(20) NOT NULL,
        title VARCHAR(200),
        summary TEXT,
        transcript TEXT,
        event_at TIMESTAMP,
        event_until TIMESTAMP,
        reason VARCHAR(500),
        changed_by VARCHAR(255),
        created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
        UNIQUE (post_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS solectwo_post_requests (
        id SERIAL PRIMARY KEY,
        post_id INTEGER NOT NULL REFERENCES solectwo_posts(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id),
        kind VARCHAR(20) NOT NULL,
        message TEXT NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'open',
        handled_by VARCHAR(255),
        handled_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_solectwo_post_requests_open ON solectwo_post_requests (post_id) WHERE status = 'open'",
    "ALTER TABLE solectwo_posts ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE solectwo_posts ADD COLUMN IF NOT EXISTS corrected_at TIMESTAMP",
    "ALTER TABLE solectwo_posts ADD COLUMN IF NOT EXISTS withdrawn_at TIMESTAMP",
    "ALTER TABLE solectwo_posts ADD COLUMN IF NOT EXISTS withdraw_reason VARCHAR(500)",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS withdrawn_at TIMESTAMP",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS term_corrected_at TIMESTAMP",
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS withdrawn_at TIMESTAMP",
    # Historia zaczyna się od publikacji — ogłoszenia sprzed migracji dostają
    # wersję 1 z dzisiejszą treścią (innej nie znamy)
    """
    INSERT INTO solectwo_post_versions
        (post_id, version, kind, title, summary, transcript, event_at, event_until, changed_by, created_at)
    SELECT p.id, 1, 'publication', p.title, p.summary, p.transcript, p.event_at, p.event_until,
           p.moderated_by, coalesce(p.published_at, now() AT TIME ZONE 'utc')
    FROM solectwo_posts p
    WHERE p.status = 'published'
      AND NOT EXISTS (SELECT 1 FROM solectwo_post_versions v WHERE v.post_id = p.id)
    """,
    "UPDATE solectwo_posts SET version = 1 WHERE status = 'published' AND version = 0",
)


async def migrate():
    print("=" * 60)
    print("Migration: solectwo_post_versions / requests + withdrawn_at")
    print("=" * 60)
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        for stmt in STATEMENTS:
            await conn.execute(text(stmt))
    await engine.dispose()
    print("✓ tabele historii i próśb, kolumny withdrawn_at / term_corrected_at")
    print("\n✅ Migracja zakończona")


if __name__ == "__main__":
    asyncio.run(migrate())
