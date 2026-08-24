"""
Migration: uchwały Rady i zarządzenia Wójta (etap 4, 2026-08-24)

Tabela `legal_acts` — rejestr aktów prawnych gminy z modułu BIP `/akty/14/`.

**Dlaczego osobna tabela, a nie `bip_documents`.** Tamta trzyma wiedzę stałą
(statut, procedury, podatki) i ma dokładnie tyle metadanych, ile trzeba do
wyszukiwania semantycznego: dział, tytuł, treść. Akt prawny ma NUMER
(`XXIII/178/2026`), DATĘ PODJĘCIA, STATUS i GRUPĘ — a pytanie „jakie są
najnowsze uchwały" to `ORDER BY adopted_at DESC`, nie zadanie dla wyszukiwarki
wektorowej. Bez tych kolumn odpowiedź na najczęstsze pytanie o uchwały byłaby
losowaniem po podobieństwie.

**Dlaczego nie `articles`.** Ten sam powód co przy `bip_documents`: BIP jest
w `feed_policy.LOCAL_SOURCES`, więc uchwała budżetowa z 2024 r. wjechałaby
mieszkańcowi na Dashboard jako świeża wiadomość z gminy.

Zakres: **2024–2026** (decyzja z 22.08). Moduł ma ~2900 aktów wstecz do 2003 r.;
rok 2024 kończy się mniej więcej na stronie 43 listy. Zakres tłumaczymy
użytkownikowi — agent ma mówić wprost, od kiedy ma dane.

`content` to tekst wyciągnięty z załącznika PDF (mają warstwę tekstową —
sprawdzone 24.08 na uchwale XXIII/178/2026: 1766 znaków z pliku 1,5 MB).
`content_hash` decyduje o ponownym osadzeniu, bo BIP odświeża strony bez
zmiany treści, a embedding kosztuje.

Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.add_legal_acts
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
    print("Migration: legal_acts")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS legal_acts (
                id SERIAL PRIMARY KEY,
                bip_id INTEGER NOT NULL UNIQUE,
                act_number VARCHAR(60),
                act_group VARCHAR(120) NOT NULL,
                title TEXT NOT NULL,
                adopted_at DATE,
                effective_from DATE,
                status VARCHAR(60),
                url TEXT NOT NULL,
                pdf_url TEXT,
                content TEXT,
                content_hash VARCHAR(64),
                embedded BOOLEAN NOT NULL DEFAULT FALSE,
                first_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
                last_checked_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        print("✓ Tabela legal_acts")

        # „Jakie są najnowsze uchwały" — najczęstsze pytanie, czysty ORDER BY.
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_legal_acts_adopted
            ON legal_acts (adopted_at DESC)
        """))
        print("✓ Indeks idx_legal_acts_adopted")

        # Uchwały Rady kontra zarządzenia Wójta — mieszkaniec pyta o jedno albo
        # o drugie i nie wolno mu mieszać dwóch różnych rodzajów decyzji.
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_legal_acts_group_date
            ON legal_acts (act_group, adopted_at DESC)
        """))
        print("✓ Indeks idx_legal_acts_group_date")

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_legal_acts_embedded
            ON legal_acts (embedded)
        """))
        print("✓ Indeks idx_legal_acts_embedded")

        count = (await conn.execute(text("SELECT COUNT(*) FROM legal_acts"))).scalar()
        print(f"\n  aktów w tabeli: {count}")

    await engine.dispose()
    print("\n✅ Migracja zakończona")
    print("   Napełnienie: python -m scripts.run_legal_acts [--dry]")


if __name__ == "__main__":
    asyncio.run(migrate())
