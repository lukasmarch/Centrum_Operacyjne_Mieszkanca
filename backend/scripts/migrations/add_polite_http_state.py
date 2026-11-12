"""
Migration: stan dostępu do serwerów gminy i dziennik żądań (2026-11-12)

Trzecia blokada BIP („wykrycie nietypowej aktywności”, ok. 6–10.11.2026).
Do tej pory `scrapers/polite.py` trzymał stan w pamięci procesu: deploy zerował
karencję po odmowie, a logi żądań ginęły z kontenerem — dwa razy nie umieliśmy
pokazać dostawcy, co wysłaliśmy. Ta migracja daje:
  - `polite_hosts`    — wyłącznik (`hold`), przerwa (`blocked_until`), poziom eskalacji,
  - `polite_requests` — każde WYSŁANE żądanie (limity + dowód), retencja 90 dni.

**Wyłącznik dla bip.gminarybno.pl startuje WŁĄCZONY** — do odpowiedzi E-LINE
serwer nie wysyła do BIP ani jednego żądania. Zdjęcie:
`python -m scripts.bip_access --release` (tylko po zgodzie dostawcy).

Addytywna, idempotentna; idzie na produkcję PRZED kodem (stary kod tabel nie widzi).

    cd backend && python -m scripts.migrations.add_polite_http_state
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
    CREATE TABLE IF NOT EXISTS polite_hosts (
        host VARCHAR(120) PRIMARY KEY,
        hold BOOLEAN NOT NULL DEFAULT FALSE,
        hold_reason VARCHAR(300),
        blocked_until TIMESTAMP,
        block_reason VARCHAR(300),
        refusal_level INTEGER NOT NULL DEFAULT 0,
        last_refusal_at TIMESTAMP,
        updated_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS polite_requests (
        id BIGSERIAL PRIMARY KEY,
        at TIMESTAMP NOT NULL,
        host VARCHAR(120) NOT NULL,
        method VARCHAR(8) NOT NULL,
        path VARCHAR(500) NOT NULL,
        status SMALLINT,
        outcome VARCHAR(20) NOT NULL,
        duration_ms INTEGER
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_polite_requests_host_at ON polite_requests (host, at DESC)",
    """
    INSERT INTO polite_hosts (host, hold, hold_reason, refusal_level, last_refusal_at, updated_at)
    VALUES ('bip.gminarybno.pl', TRUE,
            'trzecia blokada E-LINE (403 „nietypowa aktywność”, od ok. 6–10.11.2026) — czekamy na odpowiedź dostawcy',
            3, now() AT TIME ZONE 'UTC', now() AT TIME ZONE 'UTC')
    ON CONFLICT (host) DO NOTHING
    """,
)


async def migrate():
    print("=" * 60)
    print("Migration: polite_hosts, polite_requests")
    print("=" * 60)
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        for stmt in STATEMENTS:
            await conn.execute(text(stmt))
        row = (await conn.execute(text(
            "SELECT hold, hold_reason FROM polite_hosts WHERE host = 'bip.gminarybno.pl'"
        ))).first()
    await engine.dispose()
    print(f"✓ tabele; bip.gminarybno.pl hold={row[0]} ({row[1]})")
    print("\n✅ Migracja zakończona")


if __name__ == "__main__":
    asyncio.run(migrate())
