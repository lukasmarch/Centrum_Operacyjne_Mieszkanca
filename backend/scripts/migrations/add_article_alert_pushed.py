"""
Migration: znacznik wysłanego alertu push (2026-07-27)

Dodaje `articles.alert_pushed_at` — moment, w którym wpis wywołał powiadomienie.
Bez niego nie da się wysłać pusha o awarii w ciągu dnia: job chodzi co 15 minut,
a Energa aktualizuje ten sam wpis co 3 godziny pod wspólnym `external_id`, więc
to samo wyłączenie prądu budziłoby telefon kilkanaście razy.

Backfill: istniejące wpisy dostają znacznik `now()`, żeby po wdrożeniu job nie
wystrzelił serią powiadomień o zdarzeniach, które mieszkańcy dawno przeczytali
w feedzie. Alerty liczymy dopiero od tego, co przyjdzie po migracji.

Idempotentny.

Użycie:
    cd backend && python -m scripts.migrations.add_article_alert_pushed
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
    print("Migration: articles.alert_pushed_at")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        existed = (await conn.execute(text("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_name = 'articles' AND column_name = 'alert_pushed_at'
        """))).scalar()

        await conn.execute(text(
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS alert_pushed_at TIMESTAMP NULL"
        ))
        print("✓ kolumna alert_pushed_at")

        if existed:
            print("  kolumna już istniała — backfill pominięty")
        else:
            result = await conn.execute(text(
                "UPDATE articles SET alert_pushed_at = NOW() WHERE alert_pushed_at IS NULL"
            ))
            print(f"✓ backfill: {result.rowcount} istniejących wpisów oznaczonych jako obsłużone")

        # Job pyta wyłącznie o świeże wpisy bez znacznika — indeks częściowy
        # trzyma to zapytanie w kilku milisekundach niezależnie od rozmiaru tabeli.
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_articles_alert_pending
            ON articles (scraped_at) WHERE alert_pushed_at IS NULL
        """))
        print("✓ indeks częściowy ix_articles_alert_pending")

    await engine.dispose()
    print("=" * 60)
    print("Migration complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(migrate())
