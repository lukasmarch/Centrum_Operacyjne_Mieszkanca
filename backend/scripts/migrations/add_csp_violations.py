"""
Migration: zagregowane raporty naruszeń CSP `csp_violations` (2026-10-13)

Audyt 11.10.2026, E8: strona nie ma Content-Security-Policy. Wprowadzamy ją w trybie
RAPORTOWANIA (`Content-Security-Policy-Report-Only` w Caddy) — przeglądarka niczego nie
blokuje, tylko zgłasza, co by zablokowała. Przez ok. 2 tygodnie zbieramy te zgłoszenia i na ich
podstawie decydujemy, co dopuścić, zanim polityka zacznie blokować.

Tabela jest ZAGREGOWANA: jeden wiersz na (dyrektywa, zablokowane źródło, strona) z licznikiem.
Nie trzyma IP, User-Agenta, pełnych adresów ani parametrów zapytania (w linkach bywają tokeny
resetu hasła i zaproszeń). Liczba różnych wpisów jest ograniczona po stronie endpointu,
retencja 30 dni od ostatniego wystąpienia (`scheduler/retention_job.py`).

Addytywna — stary kod jej nie zauważy, więc idzie na produkcję PRZED kodem. Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.add_csp_violations
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
    CREATE TABLE IF NOT EXISTS csp_violations (
        id SERIAL PRIMARY KEY,
        directive VARCHAR(40) NOT NULL,
        blocked VARCHAR(120) NOT NULL,
        page VARCHAR(200) NOT NULL,
        disposition VARCHAR(10) NOT NULL DEFAULT 'report',
        hits INTEGER NOT NULL DEFAULT 1,
        first_seen TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
        last_seen TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
        UNIQUE (directive, blocked, page)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_csp_violations_last_seen ON csp_violations (last_seen)",
)


async def migrate():
    print("=" * 60)
    print("Migration: csp_violations")
    print("=" * 60)
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        for stmt in STATEMENTS:
            await conn.execute(text(stmt))
    await engine.dispose()
    print("✓ csp_violations + indeks")
    print("\n✅ Migracja zakończona")


if __name__ == "__main__":
    asyncio.run(migrate())
