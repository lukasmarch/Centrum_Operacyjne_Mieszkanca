"""
Migration: Admin role + report upvote dedup (sprint bezpieczeństwo/RODO 2026-07-08)

Dodaje:
  - users.is_admin BOOLEAN NOT NULL DEFAULT FALSE — rola administratora
    (moderacja zgłoszeń, operacje serwisowe) niezależna od tieru płatności
  - tabela report_upvotes — deduplikacja głosów "potwierdzam problem"
    (jeden głos na zgłoszenie na użytkownika / hash IP)

Migracja jest idempotentna — można uruchamiać wielokrotnie.

Użycie:
    cd backend && python -m scripts.migrations.add_admin_and_moderation
    # opcjonalnie nadanie roli admina istniejącemu kontu:
    python -m scripts.migrations.add_admin_and_moderation --grant biuro@lumargo.pl
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.config import settings


async def migrate(grant_email: Optional[str] = None):
    print("=" * 60)
    print("Migration: admin role + report_upvotes")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # 1. users.is_admin
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'is_admin'
        """))
        if result.fetchone():
            print("✓ Column 'users.is_admin' already exists – skipping")
        else:
            print("Adding column: users.is_admin...")
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            print("✓ Added users.is_admin")

        # 2. report_upvotes
        result = await conn.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_name = 'report_upvotes'
        """))
        if result.fetchone():
            print("✓ Table 'report_upvotes' already exists – skipping")
        else:
            print("Creating table: report_upvotes...")
            await conn.execute(text("""
                CREATE TABLE report_upvotes (
                    id SERIAL PRIMARY KEY,
                    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                    voter_key VARCHAR(64) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_report_upvotes_report_voter UNIQUE (report_id, voter_key)
                )
            """))
            print("✓ Created report_upvotes")

        # 3. Opcjonalne nadanie roli admina
        if grant_email:
            result = await conn.execute(
                text("UPDATE users SET is_admin = TRUE WHERE email = :email RETURNING id, email"),
                {"email": grant_email},
            )
            row = result.fetchone()
            if row:
                print(f"✓ Granted admin role to {row.email} (id={row.id})")
            else:
                print(f"✗ No user with email '{grant_email}' — admin NOT granted")

    await engine.dispose()
    print("=" * 60)
    print("Migration complete")
    print("=" * 60)


if __name__ == "__main__":
    email = None
    if "--grant" in sys.argv:
        idx = sys.argv.index("--grant")
        if idx + 1 >= len(sys.argv):
            print("Usage: ... --grant <email>")
            sys.exit(1)
        email = sys.argv[idx + 1]
    asyncio.run(migrate(email))
