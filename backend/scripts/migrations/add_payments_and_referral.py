"""
Migration: Płatności P24, trial, referral (Monetyzacja)

Dodaje:
- Kolumny p24_order_id, p24_session_id do tabeli subscriptions
- Kolumny trial_ends_at, referral_code, referred_by do tabeli users
- Tabelę referrals

Użycie:
    cd backend && python -m scripts.migrations.add_payments_and_referral
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
    print("Migration: add payments, trial, referral columns")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # 1. Kolumny P24 w subscriptions
        print("\n[1/4] Dodawanie kolumn P24 do tabeli subscriptions...")
        await conn.execute(text("""
            ALTER TABLE subscriptions
            ADD COLUMN IF NOT EXISTS p24_order_id VARCHAR(100),
            ADD COLUMN IF NOT EXISTS p24_session_id VARCHAR(100)
        """))
        print("      OK")

        # 2. Kolumny trial i referral w users
        print("[2/4] Dodawanie kolumn trial/referral do tabeli users...")
        await conn.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMP,
            ADD COLUMN IF NOT EXISTS referral_code VARCHAR(20) UNIQUE,
            ADD COLUMN IF NOT EXISTS referred_by INTEGER REFERENCES users(id)
        """))
        print("      OK")

        # 3. Indeks na p24_session_id
        print("[3/4] Tworzenie indeksu na subscriptions.p24_session_id...")
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_subscriptions_p24_session
            ON subscriptions (p24_session_id)
            WHERE p24_session_id IS NOT NULL
        """))
        print("      OK")

        # 4. Tabela referrals
        print("[4/4] Tworzenie tabeli referrals...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_id INTEGER NOT NULL REFERENCES users(id),
                referred_id INTEGER NOT NULL REFERENCES users(id),
                rewarded_at TIMESTAMP,
                reward_days INTEGER NOT NULL DEFAULT 14,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE (referred_id)
            )
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_referral_referrer ON referrals (referrer_id)
        """))
        print("      OK")

    await engine.dispose()
    print("\n✅ Migracja zakończona pomyślnie!")
    print("\nPamiętaj: Dodaj do .env:")
    print("  P24_MERCHANT_ID=<twój ID z panelu Przelewy24>")
    print("  P24_POS_ID=<zwykle = P24_MERCHANT_ID>")
    print("  P24_CRC_KEY=<klucz CRC z panelu P24>")
    print("  P24_API_KEY=<klucz API z panelu P24>")
    print("  P24_SANDBOX=True  # zmień na False na produkcji")


if __name__ == "__main__":
    asyncio.run(migrate())
