"""
Migration: zgłoszenia drogowe z wynikiem wiarygodności `road_reports` (2026-10-29)

Pasek „Drogi” pokazywał to, co napisał model: 28.10 zamknięcie DW538 „do
31 grudnia 2025” ze strony ZDW, 29.10 remont z posta sprzed siedmiu dni (+10 min,
naraz na dwóch trasach). Każde utrudnienie jest teraz wierszem z wynikiem
wiarygodności liczonym w KODZIE (`services/road_reports.py`): wysoki → pasek,
średni → Telegram z przyciskami „Akceptuj / Usuń”, niski → nigdzie.

Addytywna — stary kod jej nie zauważy, więc idzie na produkcję PRZED kodem. Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.add_road_reports
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
    CREATE TABLE IF NOT EXISTS road_reports (
        id SERIAL PRIMARY KEY,
        report_key VARCHAR(200) NOT NULL,
        route VARCHAR(40) NOT NULL,
        note TEXT NOT NULL,
        origin VARCHAR(10) NOT NULL,
        kind VARCHAR(10) NOT NULL,
        article_id INTEGER REFERENCES articles(id) ON DELETE SET NULL,
        source_name VARCHAR(120),
        source_published_at TIMESTAMP,
        score DOUBLE PRECISION NOT NULL,
        score_reason VARCHAR(300),
        status VARCHAR(10) NOT NULL,
        review_token VARCHAR(64) UNIQUE,
        notified_at TIMESTAMP,
        decided_at TIMESTAMP,
        approved_until TIMESTAMP,
        first_seen_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
        last_seen_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_road_reports_key ON road_reports (report_key)",
    "CREATE INDEX IF NOT EXISTS idx_road_reports_status ON road_reports (status)",
)


async def migrate():
    print("=" * 60)
    print("Migration: road_reports")
    print("=" * 60)
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        for stmt in STATEMENTS:
            await conn.execute(text(stmt))
    await engine.dispose()
    print("✓ road_reports + indeksy")
    print("\n✅ Migracja zakończona")


if __name__ == "__main__":
    asyncio.run(migrate())
