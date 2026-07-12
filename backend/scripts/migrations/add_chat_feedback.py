"""
Migration: oceny odpowiedzi agentów 👍/👎 (sprint D, 2026-07-12)

Tabela chat_message_feedback — jeden głos na wiadomość na konto / hash IP,
dane do poprawy RAG i dowód jakości ("93% ocen pozytywnych").

Migracja jest idempotentna — można uruchamiać wielokrotnie.

Użycie:
    cd backend && python -m scripts.migrations.add_chat_feedback
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
    print("Migration: chat_message_feedback")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_message_feedback (
                id SERIAL PRIMARY KEY,
                message_id INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
                rating INTEGER NOT NULL,
                voter_key VARCHAR(60) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_feedback_message_voter UNIQUE (message_id, voter_key)
            )
        """))
        print("✓ Tabela chat_message_feedback")

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_feedback_message
            ON chat_message_feedback (message_id)
        """))
        print("✓ Indeks idx_feedback_message")

    await engine.dispose()
    print("=" * 60)
    print("Migracja zakończona.")


if __name__ == "__main__":
    asyncio.run(migrate())
