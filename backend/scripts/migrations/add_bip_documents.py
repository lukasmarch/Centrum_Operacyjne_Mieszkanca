"""
Migration: tabela `bip_documents` — wiedza stała z BIP (2026-08-03)

Powód. 3.08.2026 asystent na pytanie „ile gmina Rybno ma sołectw" odpowiedział,
że nie ma danych i odesłał do urzędu. W bazie faktycznie ich nie było: scraper
BIP czyta wyłącznie dział /112/ (aktualności) i odrzuca wszystko starsze niż dwa
dni, więc statut, procedury, podatki i programy środowiskowe nigdy do nas nie
trafiły. 52 dokumenty BIP w bazie to same obwieszczenia.

Ta tabela trzyma drugą, nieruchomą połowę BIP — tę, o którą ludzie pytają
miesiącami (dofinansowanie na usunięcie eternitu, Czyste Powietrze, stawki
podatku, jak złożyć deklarację). Osobno od `articles`, żeby nie wjechała
do feedu jako świeża wiadomość — patrz docstring modelu `BipDocument`.

Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.add_bip_documents
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
    print("Migration: bip_documents (wiedza stała z BIP)")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bip_documents (
                id SERIAL PRIMARY KEY,
                section_id VARCHAR(20) NOT NULL,
                section_name VARCHAR(200) NOT NULL,
                url VARCHAR(1000) NOT NULL UNIQUE,
                title VARCHAR(500) NOT NULL,
                content TEXT NULL,
                content_hash VARCHAR(64) NOT NULL,
                pdf_count INTEGER NOT NULL DEFAULT 0,
                document_date TIMESTAMP NULL,
                embedded BOOLEAN NOT NULL DEFAULT FALSE,
                first_seen_at TIMESTAMP NOT NULL DEFAULT NOW(),
                last_checked_at TIMESTAMP NOT NULL DEFAULT NOW(),
                content_changed_at TIMESTAMP NULL
            )
        """))
        print("✓ tabela bip_documents")

        for name, ddl in (
            ("ix_bip_documents_section_id",
             "CREATE INDEX IF NOT EXISTS ix_bip_documents_section_id ON bip_documents (section_id)"),
            ("ix_bip_documents_content_hash",
             "CREATE INDEX IF NOT EXISTS ix_bip_documents_content_hash ON bip_documents (content_hash)"),
            # Job pyta „co jeszcze nieosadzone" przy każdym przebiegu
            ("ix_bip_documents_embedded",
             "CREATE INDEX IF NOT EXISTS ix_bip_documents_embedded ON bip_documents (embedded)"),
        ):
            await conn.execute(text(ddl))
            print(f"✓ indeks {name}")

        count = (await conn.execute(text("SELECT COUNT(*) FROM bip_documents"))).scalar()
        print(f"\nDokumentów w tabeli: {count}")

    await engine.dispose()
    print("\nGotowe. Napełnienie: python -m scripts.run_bip_knowledge")


if __name__ == "__main__":
    asyncio.run(migrate())
