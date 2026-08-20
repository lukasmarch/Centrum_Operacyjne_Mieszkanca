"""
Migration: znaczniki maili o końcu okresu próbnego (2026-08-20)

Dodaje `users.trial_reminder_stage` i `users.trial_reminder_sent_at` — który mail
o kończącym się trialu poszedł do użytkownika i kiedy.

Bez tego nie da się wysłać przypomnienia: `trial_expiry_job` chodzi CODZIENNIE
o 5:00, więc przez ostatni tydzień okresu próbnego wysłałby ten sam mail siedem
razy. Ten sam problem, który przy alertach o awariach rozwiązuje
`articles.alert_pushed_at`.

Kolejność etapów: week (−7 dni) → last_day (−1 dzień) → ended (po zmianie planu).
Job wysyła etap tylko wtedy, gdy jest dalszy niż zapisany.

Bez backfillu: jedyne konto z aktywnym triałem kończy go 18.09, więc żaden etap
jeszcze nie minął. Gdyby komuś trial kończył się jutro, mail wyjdzie od razu —
i o to chodzi.

Idempotentny.

Użycie:
    cd backend && python -m scripts.migrations.add_trial_reminder
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
    print("Migration: users.trial_reminder_stage / trial_reminder_sent_at")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_reminder_stage VARCHAR(20) NULL"
        ))
        print("✓ kolumna trial_reminder_stage")

        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_reminder_sent_at TIMESTAMP NULL"
        ))
        print("✓ kolumna trial_reminder_sent_at")

        pending = (await conn.execute(text("""
            SELECT COUNT(*) FROM users
            WHERE trial_ends_at IS NOT NULL AND tier <> 'free' AND is_active = TRUE
        """))).scalar()
        print(f"\n  kont z aktywnym okresem próbnym: {pending}")

    await engine.dispose()
    print("\n✅ Migracja zakończona")


if __name__ == "__main__":
    asyncio.run(migrate())
