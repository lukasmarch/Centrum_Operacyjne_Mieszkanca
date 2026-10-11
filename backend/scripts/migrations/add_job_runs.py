"""
Migration: dziennik przebiegów schedulera `job_runs` (2026-10-11)

Audyt 11.10.2026 (F-033): scheduler trzyma harmonogram wyłącznie w pamięci.
Restart kontenera (każdy deploy) gubił joby zaplanowane na czas przerwy, a nie
było śladu, że się nie wykonały — 11.10 pogoda nie odświeżyła się ponad 2 h,
a ruch drogowy z 10:00 przepadł bez słowa. Tabela jest jednocześnie:
  - dziennikiem (co poszło, co padło, co przerwał restart),
  - pamięcią dla nadrabiania po restarcie (`scheduler/job_runs.py`).

Addytywna — stary kod jej nie zauważy, więc idzie na produkcję PRZED kodem.
Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.add_job_runs
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
    CREATE TABLE IF NOT EXISTS job_runs (
        id SERIAL PRIMARY KEY,
        job_id VARCHAR(60) NOT NULL,
        scheduled_for TIMESTAMP,
        started_at TIMESTAMP,
        finished_at TIMESTAMP,
        status VARCHAR(20) NOT NULL,
        catch_up BOOLEAN NOT NULL DEFAULT FALSE,
        error VARCHAR(500)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_job_runs_job_scheduled ON job_runs (job_id, scheduled_for DESC)",
    "CREATE INDEX IF NOT EXISTS idx_job_runs_started ON job_runs (started_at DESC)",
)


async def migrate():
    print("=" * 60)
    print("Migration: job_runs")
    print("=" * 60)
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        for stmt in STATEMENTS:
            await conn.execute(text(stmt))
    await engine.dispose()
    print("✓ job_runs + indeksy")
    print("\n✅ Migracja zakończona")


if __name__ == "__main__":
    asyncio.run(migrate())
