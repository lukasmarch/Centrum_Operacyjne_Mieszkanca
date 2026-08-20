"""
Migration: znaczniki maili o kończącej się subskrypcji opłaconej (2026-08-21)

Dodaje `subscriptions.reminder_stage` i `subscriptions.reminder_sent_at`.

Skąd potrzeba: przypomnienia zbudowane 20.08 były przypięte WYŁĄCZNIE do trialu
(`users.trial_ends_at`). Konto, które zapłaciło, ma `trial_ends_at = NULL`, więc
zapytanie jobu go nie widziało — 20.09 straciłoby dostęp bez jednego maila.
Płacący klient był traktowany gorzej niż testujący.

Plan nie odnawia się automatycznie (regulamin §6.5), więc przypomnienie jest
jedyną drogą, żeby ktokolwiek przedłużył subskrypcję świadomie.

Kolejność etapów: week (−7 dni) → last_day (−1 dzień) → ended (po wygaśnięciu).

Bez backfillu: jedyna opłacona subskrypcja (id 13, biuro@lumargo.pl) kończy się
20.09, więc żaden etap jeszcze nie minął.

Idempotentny.

Użycie:
    cd backend && python -m scripts.migrations.add_subscription_reminder
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
    print("Migration: subscriptions.reminder_stage / reminder_sent_at")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS reminder_stage VARCHAR(20) NULL"
        ))
        print("✓ kolumna reminder_stage")

        await conn.execute(text(
            "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS reminder_sent_at TIMESTAMP NULL"
        ))
        print("✓ kolumna reminder_sent_at")

        rows = (await conn.execute(text("""
            SELECT COUNT(*) FROM subscriptions
            WHERE status = 'active' AND expires_at IS NOT NULL AND expires_at > NOW()
        """))).scalar()
        print(f"\n  aktywnych subskrypcji z terminem: {rows}")

    await engine.dispose()
    print("\n✅ Migracja zakończona")


if __name__ == "__main__":
    asyncio.run(migrate())
