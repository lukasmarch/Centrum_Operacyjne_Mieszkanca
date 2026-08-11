"""
Migration: articles.content_score — ocena treści w rankingu feedu (2026-08-11)

Ranking feedu liczył wagę ŹRÓDŁA razy świeżość. Audyt tygodnia 4–11.08 pokazał,
co z tego wynikło: pierwsza piątka Dashboardu była GORSZA od średniej całego
materiału w lokalności, konkrecie i przyciąganiu. Wygrywał kanał publikujący
najczęściej, nie wpis najważniejszy dla mieszkańca — bo częstotliwość publikacji
jest jedyną rzeczą, którą ranking widział.

`content_score` (0–6) to suma dwóch ocen z kategoryzacji: lokalność i użyteczność,
każda 0–3 — ta sama rubryka, którą audyt walidował w `scripts/analyze_feed_quality.py`.

NULL znaczy „nieocenione" i daje mnożnik neutralny 1,0, więc:
  - historyczne wpisy zachowują dzisiejszą pozycję,
  - kod działa przed i po migracji (kolumna jest NULL-owalna),
  - nie ma backfillu — ocena powstaje przy kategoryzacji, po jednym przebiegu
    (6:15 i 13:15) cały świeży materiał ma już wynik.

Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.add_article_content_score
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
    print("Migration: articles.content_score")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS content_score SMALLINT NULL"
        ))
        print("✓ kolumna content_score (SMALLINT NULL)")

        total = (await conn.execute(text("SELECT COUNT(*) FROM articles"))).scalar()
        scored = (await conn.execute(text(
            "SELECT COUNT(*) FROM articles WHERE content_score IS NOT NULL"
        ))).scalar()
        print(f"  wpisów w bazie: {total}, z oceną: {scored} "
              f"(reszta dostanie ją przy kolejnej kategoryzacji)")

    await engine.dispose()
    print("\n✓ Gotowe.")


if __name__ == "__main__":
    asyncio.run(migrate())
