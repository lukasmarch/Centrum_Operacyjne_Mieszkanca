"""
Migration: termin zdarzenia w artykułach + scalenie duplikatów Energi (2026-07-27)

Dodaje `articles.event_at` / `articles.event_until` — moment, którego wpis DOTYCZY,
w odróżnieniu od momentu, w którym został opublikowany. Wyłączenie prądu ogłaszane
jest z tygodniowym wyprzedzeniem; bez terminu ranking liczył wiek ogłoszenia,
więc zapowiedź na 31.07 wypadała z feedu 29.07, zanim zdarzenie nastąpiło.

Backfill dla istniejących wpisów Energi:
  1. termin z treści („Rybno gmina wiejska 27.07.2026 10:00-14:00 - …")
  2. wspólny `external_id` z guid-a w URL — oba kanały (planowane i bieżące)
     opisują to samo zdarzenie tym samym guid-em, ale innym linkiem, więc
     w feedzie stało ono dwa razy obok siebie; scalamy do najstarszego wiersza

Idempotentny.

Użycie:
    cd backend && python -m scripts.migrations.add_article_event_window
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings
from src.services.energa import canonical_id, parse_window, _to_utc


async def migrate():
    print("=" * 60)
    print("Migration: articles.event_at / event_until + dedup Energa")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS event_at TIMESTAMP NULL"
        ))
        await conn.execute(text(
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS event_until TIMESTAMP NULL"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_articles_event_at ON articles (event_at)"
        ))
        print("✓ kolumny event_at / event_until + indeks")

        rows = (await conn.execute(text("""
            SELECT a.id, a.title, a.content, a.summary, a.url, a.scraped_at
            FROM articles a
            JOIN sources s ON s.id = a.source_id
            WHERE s.name ILIKE '%energa%'
            ORDER BY a.id
        """))).fetchall()
        print(f"  wpisów Energi w bazie: {len(rows)}")

        # guid → wiersz, który zostaje (najstarszy)
        keep: dict[str, int] = {}
        merged = 0
        stamped = 0

        for row in rows:
            body = f"{row.title or ''} {row.content or ''} {row.summary or ''}"
            local_start, local_end = parse_window(body)
            start = _to_utc(local_start) if local_start else None
            end = _to_utc(local_end) if local_end else None
            guid = canonical_id(row.url)

            if guid and guid in keep:
                # duplikat tego samego zdarzenia z drugiego kanału
                await conn.execute(text(
                    "DELETE FROM document_embeddings WHERE source_type = 'article' AND source_id = :id"
                ), {"id": row.id})
                await conn.execute(text("DELETE FROM articles WHERE id = :id"), {"id": row.id})
                merged += 1
                print(f"  ↳ scalono duplikat id={row.id} → id={keep[guid]} ({guid})")
                continue

            await conn.execute(text("""
                UPDATE articles
                SET event_at = :start, event_until = :end, external_id = COALESCE(:guid, external_id)
                WHERE id = :id
            """), {"id": row.id, "start": start, "end": end, "guid": guid})
            stamped += 1
            if guid:
                keep[guid] = row.id

        print(f"✓ terminy uzupełnione: {stamped}, duplikatów scalonych: {merged}")

    await engine.dispose()
    print("=" * 60)
    print("Migration complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(migrate())
