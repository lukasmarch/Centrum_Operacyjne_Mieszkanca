"""
Migration: log wywołań narzędzi przez agentów (etap 6, 2026-08-24)

Tabela `agent_tool_calls` — jeden wiersz na jedno wywołanie narzędzia.

Skąd potrzeba: 21.08 o 19:07 Przewodnik odpowiedział „nie mam prognozy w bazie",
mając 40 slotów w `weather.forecast`. Dowiedzieliśmy się o tym, bo Łukasz
przypadkiem kliknął podpowiedź i zauważył. To nie jest metoda wykrywania dziur
w danych — a po przejściu agentów na narzędzia dziura ma wreszcie stały kształt:
narzędzie zawołane i zwracające PUSTO.

Co mierzymy i po co:
  * `state` = done / empty / error — pustka to nie awaria, tylko brak danych,
    i te dwie rzeczy naprawia się gdzie indziej (źródło vs kod);
  * `error` — rodzaj awarii (timeout, bad_arguments, unknown_tool, exception).
    `bad_arguments` mówi o złym OPISIE parametru, `timeout` o zapytaniu do bazy;
  * `args` — model wołający `days=1` na pytanie o jutro (błąd z 22.08) jest
    widoczny wyłącznie w argumentach;
  * `question` — bez pytania nie wiadomo, czego szukał ktoś, kto dostał pustkę.

RODO: `question` (200 zn.) i `user_id` znikają po 30 dniach, cały wiersz po 180
(`scheduler/retention_job.py`). Liczniki zostają — do analityki wystarczają
nazwa narzędzia i stan.

Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.add_agent_tool_calls
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings


async def migrate():
    print("=" * 60)
    print("Migration: agent_tool_calls")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # Bez FK na `users`: log przeżywa skasowanie konta (RODO kasuje samo
        # `user_id`, patrz retention_job), a CASCADE zabrałby też liczniki.
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS agent_tool_calls (
                id SERIAL PRIMARY KEY,
                agent_name VARCHAR(50) NOT NULL,
                tool_name VARCHAR(60) NOT NULL,
                state VARCHAR(20) NOT NULL,
                error VARCHAR(30) NULL,
                args JSONB NULL,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                question VARCHAR(200) NULL,
                user_id INTEGER NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        print("✓ Tabela agent_tool_calls")

        # Każdy raport pyta „ostatnie N dni", więc data jest w KAŻDYM zapytaniu.
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_tool_calls_created
            ON agent_tool_calls (created_at)
        """))
        print("✓ Indeks idx_tool_calls_created")

        # Zestawienie per narzędzie — najczęstsze pytanie raportu.
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_tool_calls_tool_state
            ON agent_tool_calls (tool_name, state)
        """))
        print("✓ Indeks idx_tool_calls_tool_state")

    await engine.dispose()
    print("\n✅ Migracja zakończona")


if __name__ == "__main__":
    asyncio.run(migrate())
