"""
Tabela `gmina_institutions` — dane teleadresowe jednostek gminy (etap 7 pkt 5).

Zastępuje stałą `OFFICE_HOURS` z `ai/tools/daily.py`, która miała dwie pozycje
i BŁĘDY W OBU: urząd czynny 8:00–16:00 (w kodzie 7:15–15:15), GOPS przy
ul. Zajeziornej 58 z telefonem 696 63 39 (w kodzie stały dane Urzędu Gminy).

Idempotentna, jak wszystkie migracje w tym katalogu — `alembic_version`
zostaje nietknięte (patrz CLAUDE.md, „WYRÓWNANIE BAZ").

Uruchomienie:  python -m scripts.migrations.add_gmina_institutions
Napełnienie:   python -m scripts.run_bip_institutions [--dry]
"""
import asyncio

from sqlalchemy import text

from src.database.connection import async_session
from src.utils.logger import setup_logger

logger = setup_logger("MigrationGminaInstitutions")

# Osobne polecenia, nie jeden blok: asyncpg wykonuje przez prepared statement
# i odrzuca „multiple commands" (`PostgresSyntaxError`). Ten sam układ mają
# pozostałe migracje w tym katalogu.
STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS gmina_institutions (
        id                 SERIAL PRIMARY KEY,
        slug               VARCHAR(60)  NOT NULL UNIQUE,
        name               VARCHAR(250) NOT NULL,
        kind               VARCHAR(30)  NOT NULL,
        address            VARCHAR(250),
        phone              VARCHAR(60),
        email              VARCHAR(200),
        website            VARCHAR(300),
        manager            VARCHAR(150),
        hours              VARCHAR(250),
        scope              VARCHAR(600),
        bip_url            VARCHAR(500),
        content_hash       VARCHAR(64),
        active             BOOLEAN NOT NULL DEFAULT TRUE,
        first_seen_at      TIMESTAMP NOT NULL DEFAULT NOW(),
        last_checked_at    TIMESTAMP NOT NULL DEFAULT NOW(),
        content_changed_at TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_gmina_institutions_kind ON gmina_institutions (kind)",
    "CREATE INDEX IF NOT EXISTS ix_gmina_institutions_active ON gmina_institutions (active)",
)


async def main() -> None:
    async with async_session() as session:
        for statement in STATEMENTS:
            await session.execute(text(statement))
        await session.commit()

        count = (await session.execute(
            text("SELECT count(*) FROM gmina_institutions")
        )).scalar()

    logger.info(f"Tabela gmina_institutions gotowa ({count} wierszy).")
    print(f"OK — gmina_institutions ({count} wierszy). "
          f"Napełnienie: python -m scripts.run_bip_institutions")


if __name__ == "__main__":
    asyncio.run(main())
