"""
Migration: tabela `council_sessions` — skróty obrad Rady Gminy (2026-08-09)

Powód. Sesja Rady trwa do trzech godzin i wisi na YouTube, gdzie nikt jej nie
ogląda — jawność obrad jest formalna. Pilot z 6.08 pokazał, że nagranie da się
przepisać i streścić za $0,59 w trzy minuty, ale też że skrótu NIE wolno
publikować automatycznie: model dopisał do jednego punktu cel zagospodarowania
działki, którego w nagraniu nie było, a bramka cytatów tego nie łapie (sprawdza
`quote`, nie `description`).

Stąd kształt tabeli: skrót powstaje sam, ale rodzi się w stanie `pending`
i czeka na kliknięcie człowieka. Kolumny `review_*` to cała ta bramka.

Transkrypt trzymamy w bazie, bo bez segmentów ze znacznikami czasu nie da się
później zweryfikować cytatu ani osadzić obrad w RAG, a Whisper za powtórkę
weźmie $0,52.

Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.add_council_sessions
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
    print("Migration: council_sessions (skróty obrad Rady Gminy)")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS council_sessions (
                id SERIAL PRIMARY KEY,

                external_id VARCHAR(32) NOT NULL UNIQUE,
                title VARCHAR(500) NOT NULL,
                session_number VARCHAR(20) NULL,
                session_date TIMESTAMP NULL,
                page_url VARCHAR(1000) NOT NULL,
                youtube_id VARCHAR(20) NULL,

                duration_s DOUBLE PRECISION NOT NULL DEFAULT 0,
                transcript_chars INTEGER NOT NULL DEFAULT 0,
                transcript_json TEXT NULL,
                summary_json TEXT NULL,

                quotes_total INTEGER NOT NULL DEFAULT 0,
                quotes_verified INTEGER NOT NULL DEFAULT 0,
                quotes_dropped INTEGER NOT NULL DEFAULT 0,
                timestamps_fixed INTEGER NOT NULL DEFAULT 0,
                claims_total INTEGER NOT NULL DEFAULT 0,
                claims_flagged INTEGER NOT NULL DEFAULT 0,
                claims_flagged_text TEXT NULL,
                quotes_clean BOOLEAN NOT NULL DEFAULT FALSE,

                status VARCHAR(20) NOT NULL DEFAULT 'new',
                review_token VARCHAR(64) NULL UNIQUE,
                review_note VARCHAR(1000) NULL,
                reviewed_at TIMESTAMP NULL,
                reviewed_by INTEGER NULL REFERENCES users(id),
                published_at TIMESTAMP NULL,

                attempts INTEGER NOT NULL DEFAULT 0,
                last_error VARCHAR(1000) NULL,
                cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
                embedded BOOLEAN NOT NULL DEFAULT FALSE,

                first_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
                processed_at TIMESTAMP NULL
            )
        """))
        print("✓ tabela council_sessions")

        # Kolumny drugiej bramki (weryfikacja opisów) dopisane 9.08.2026,
        # gdy tabela stała już na lokalnej bazie. `IF NOT EXISTS` sprawia,
        # że migracja jest idempotentna także dla wcześniejszego wariantu.
        for column, ddl in (
            ("claims_total", "ADD COLUMN IF NOT EXISTS claims_total INTEGER NOT NULL DEFAULT 0"),
            ("claims_flagged", "ADD COLUMN IF NOT EXISTS claims_flagged INTEGER NOT NULL DEFAULT 0"),
            ("claims_flagged_text", "ADD COLUMN IF NOT EXISTS claims_flagged_text TEXT NULL"),
        ):
            await conn.execute(text(f"ALTER TABLE council_sessions {ddl}"))
            print(f"✓ kolumna {column}")

        for name, ddl in (
            # Job przy każdym przebiegu pyta „czy to nagranie już znam"
            ("ix_council_sessions_external_id",
             "CREATE INDEX IF NOT EXISTS ix_council_sessions_external_id "
             "ON council_sessions (external_id)"),
            # Panel akceptacji pyta „co czeka", strona publiczna „co zatwierdzone"
            ("ix_council_sessions_status",
             "CREATE INDEX IF NOT EXISTS ix_council_sessions_status "
             "ON council_sessions (status)"),
            ("ix_council_sessions_session_date",
             "CREATE INDEX IF NOT EXISTS ix_council_sessions_session_date "
             "ON council_sessions (session_date)"),
            # Link akceptacyjny z maila trafia tu jako jedyny klucz wyszukiwania
            ("ix_council_sessions_review_token",
             "CREATE INDEX IF NOT EXISTS ix_council_sessions_review_token "
             "ON council_sessions (review_token)"),
            ("ix_council_sessions_embedded",
             "CREATE INDEX IF NOT EXISTS ix_council_sessions_embedded "
             "ON council_sessions (embedded)"),
        ):
            await conn.execute(text(ddl))
            print(f"✓ indeks {name}")

        rows = (await conn.execute(text("SELECT COUNT(*) FROM council_sessions"))).scalar()
        pending = (await conn.execute(
            text("SELECT COUNT(*) FROM council_sessions WHERE status = 'pending'")
        )).scalar()
        print(f"\nSesji w tabeli: {rows} (czeka na akceptację: {pending})")

    await engine.dispose()
    print("\nGotowe. Pierwszy przebieg ręcznie:")
    print("  python -m scripts.run_council_session --latest --save")


if __name__ == "__main__":
    asyncio.run(migrate())
