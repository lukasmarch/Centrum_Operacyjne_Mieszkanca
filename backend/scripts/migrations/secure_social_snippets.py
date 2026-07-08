"""
Migration: Model snippet+link dla źródeł social (Etap C planu prawnego — zabezpieczenie Syli)

Dla wszystkich artykułów ze źródeł typu 'social' (Facebook przez Apify):
  1. content → snippet ≤300 znaków + "Pełna treść u źródła: {url}"
     (nie przechowujemy pełnych tekstów cudzych postów — prawo autorskie)
  2. image_url → NULL (wizerunek osób — RODO)
  3. usunięcie embeddingów RAG tych artykułów (chunki zawierały pełne teksty)

Migracja jest idempotentna — artykuły już skrócone (marker "Pełna treść u źródła")
są pomijane. Uruchamiać wielokrotnie bezpiecznie.

UWAGA: operacja skraca treść nieodwracalnie — przed uruchomieniem na produkcji
wykonać dump bazy (pg_dump).

Użycie:
    cd backend && python -m scripts.migrations.secure_social_snippets [--dry-run]
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from src.config import settings
from src.scrapers.apify_facebook import make_social_snippet

MARKER = "Pełna treść u źródła"
BATCH = 500


async def migrate(dry_run: bool = False):
    print("=" * 60)
    print(f"Migration: snippet+link dla źródeł social {'(DRY RUN)' if dry_run else ''}")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # Źródła social
        result = await conn.execute(text(
            "SELECT id, name FROM sources WHERE type IN ('social_media', 'social')"
        ))
        sources = result.fetchall()
        if not sources:
            print("Brak źródeł typu 'social' — nic do zrobienia")
            await engine.dispose()
            return
        source_ids = [s.id for s in sources]
        print(f"Źródła social: {', '.join(f'{s.name} (id={s.id})' for s in sources)}")

        # 1. Skrócenie treści (batchami, granica słowa liczona w Pythonie)
        total_trimmed = 0
        while True:
            result = await conn.execute(text("""
                SELECT id, content, url FROM articles
                WHERE source_id = ANY(:sids)
                  AND content IS NOT NULL
                  AND content NOT LIKE :marker
                LIMIT :batch
            """), {"sids": source_ids, "marker": f"%{MARKER}%", "batch": BATCH})
            rows = result.fetchall()
            if not rows:
                break
            for row in rows:
                snippet = make_social_snippet(row.content, row.url or "")
                if not dry_run:
                    await conn.execute(
                        text("UPDATE articles SET content = :c WHERE id = :id"),
                        {"c": snippet, "id": row.id},
                    )
            total_trimmed += len(rows)
            print(f"  ...skrócono {total_trimmed} artykułów")
            if dry_run:
                break
        print(f"✓ Treść skrócona do snippetu: {total_trimmed} artykułów")

        # 2. Usunięcie zdjęć (wizerunek)
        result = await conn.execute(text(f"""
            {'SELECT COUNT(*) FROM' if dry_run else 'UPDATE'} articles
            {'' if dry_run else 'SET image_url = NULL'}
            WHERE source_id = ANY(:sids) AND image_url IS NOT NULL
        """), {"sids": source_ids})
        cleared = result.scalar() if dry_run else result.rowcount
        print(f"✓ Usunięte image_url: {cleared}")

        # 3. Embeddingi z pełnymi tekstami — do usunięcia
        if dry_run:
            result = await conn.execute(text("""
                SELECT COUNT(*) FROM document_embeddings
                WHERE source_type = 'article'
                  AND source_id IN (SELECT id FROM articles WHERE source_id = ANY(:sids))
            """), {"sids": source_ids})
            print(f"✓ Embeddingi do usunięcia: {result.scalar()}")
        else:
            result = await conn.execute(text("""
                DELETE FROM document_embeddings
                WHERE source_type = 'article'
                  AND source_id IN (SELECT id FROM articles WHERE source_id = ANY(:sids))
            """), {"sids": source_ids})
            print(f"✓ Usunięte embeddingi (pełne teksty w chunkach): {result.rowcount}")

    await engine.dispose()
    print("=" * 60)
    print("Migration complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(migrate(dry_run="--dry-run" in sys.argv))
