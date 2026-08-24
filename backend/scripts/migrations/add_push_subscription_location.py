"""
Miejscowość na subskrypcji push (2026-08-24)

Alert o awarii szedł do WSZYSTKICH subskrybentów, jeśli tylko w komunikacie
padła jakakolwiek nazwa z gminy — mieszkaniec Koszelew dostawał powiadomienie
o wyłączeniu na ulicy Zajeziornej w Rybnie.

Lokalizacja siedzi na subskrypcji, nie na koncie, bo 24.08.2026 pięć z sześciu
aktywnych subskrypcji nie miało `user_id`: to zgody wydane w przeglądarce bez
rejestracji. Filtr oparty o `users.location` objąłby jedną osobę.

Puste = alerty z całej gminy (tak działają wszystkie istniejące subskrypcje,
więc migracja nikomu niczego nie odbiera).

Idempotentna. Użycie:
    cd backend && python -m scripts.migrations.add_push_subscription_location
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text

from src.database.connection import async_session

STATEMENTS = [
    "ALTER TABLE push_subscriptions ADD COLUMN IF NOT EXISTS location VARCHAR(100)",
    "CREATE INDEX IF NOT EXISTS ix_push_subscriptions_location "
    "ON push_subscriptions (location)",
]


async def migrate():
    async with async_session() as session:
        for statement in STATEMENTS:
            print(f"  {statement[:78]}…")
            await session.execute(text(statement))
        await session.commit()

    print("\nGotowe. Subskrypcje bez miejscowości dostają alerty z całej gminy.")


if __name__ == "__main__":
    asyncio.run(migrate())
