"""
Migration: locality i scalanie wydarzeń (2026-08-21)

Trzy zmiany, wszystkie o jednym: przestać wyrzucać wiedzę, którą już mamy.

1. `articles.locality` (0–3) — kategoryzacja LICZY tę ocenę przy każdym wpisie
   (`ArticleCategory.locality`), po czym `article_processor` dodaje ją do
   użyteczności i zapisuje wyłącznie sumę w `content_score`. Informacja „to jest
   gmina Rybno / to jest Ciechanów" ginęła w tym dodawaniu: wpis z Ciechanowa
   użyteczny (0+3) ma dziś ten sam `content_score` co lokalna ciekawostka (3+0).
   Przez to każde miejsce, które potrzebowało lokalności, budowało własną
   heurystykę — a `feed_policy.is_pinned_alert` nie miało jej wcale i 21.08
   przypięło mieszkańcom Rybna wyłączenie prądu w Iłowie-Osadzie.

2. `events.locality` — ta sama ocena dla wydarzeń. Do 21.08 kalendarz nie miał
   bramki miejsca żadnej: na 130 wydarzeń z 30 dni gmina Rybno dawała ~56,
   reszta to Sierpc (14), Działdowo (12), Ciechanów (9), Żuromin (8), Mława (6),
   Warszawa (3). Newsletter wysłał je mieszkańcom jako „Dziś w okolicy".

3. `events.canonical_id` — wskaźnik na wydarzenie, którego dany wpis jest
   powtórzeniem. Scalamy, nie kasujemy: rekord powtórzony niesie własne źródło
   (`source_article_id`), a decyzja o scaleniu ma być odwracalna.
   Ten sam turniej w Tuczkach 23.08 stał w bazie SZEŚĆ razy z sześciu postów.

Plus częściowy unikat na `source_article_id`: jeden artykuł = jedno wydarzenie.
Powtórki z tego samego artykułu to 39 rekordów na 129 z ostatnich 30 dni —
`extract_from_recent` filtruje po `scraped_at`, który re-scrape nadpisuje, więc
ten sam post szedł do gpt-4o kilka razy, a model za każdym razem tytułował
inaczej i unikat `(title, event_date, location)` tego nie widział.

Kolumny są NULL-owalne i nic nie backfillujemy: ocena powstaje przy kategoryzacji
i ekstrakcji, więc po jednym przebiegu (6:15 / 13:15) świeży materiał ma komplet.
Stary kod działa przed i po migracji.

Idempotentna. Migracja idzie na produkcję PRZED kodem.

Użycie:
    cd backend && python -m scripts.migrations.add_locality_and_event_dedup
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
    print("Migration: locality (articles, events) + scalanie wydarzeń")
    print("=" * 60)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE articles ADD COLUMN IF NOT EXISTS locality SMALLINT NULL"
        ))
        print("✓ articles.locality (SMALLINT NULL)")

        await conn.execute(text(
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS locality SMALLINT NULL"
        ))
        print("✓ events.locality (SMALLINT NULL)")

        await conn.execute(text(
            "ALTER TABLE events ADD COLUMN IF NOT EXISTS canonical_id INTEGER NULL "
            "REFERENCES events(id) ON DELETE SET NULL"
        ))
        print("✓ events.canonical_id → events.id (ON DELETE SET NULL)")

        # Kandydatów do scalenia szukamy zawsze w obrębie jednego dnia i jednej
        # miejscowości — pomiar na 90 dniach: 20 takich grup, wszystkie poza
        # dwiema to realne powtórki. Bez indeksu to seq scan przy każdej ekstrakcji.
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_event_day_place "
            "ON events (date(event_date), location)"
        ))
        print("✓ indeks (date(event_date), location)")

        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_event_canonical ON events (canonical_id)"
        ))
        print("✓ indeks canonical_id")

        # Częściowy unikat: wpisy scalone (canonical_id NOT NULL) są z niego
        # wyłączone — inaczej scalenie dwóch wydarzeń z tego samego artykułu
        # (legalne: „dożynki w sobotę i niedzielę") kolidowałoby z powtórką.
        duplicates = (await conn.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT source_article_id FROM events
                WHERE source_article_id IS NOT NULL AND canonical_id IS NULL
                GROUP BY source_article_id HAVING COUNT(*) > 1
            ) t
        """))).scalar()

        if duplicates:
            print(f"\n⚠ {duplicates} artykułów ma po kilka nierozstrzygniętych wydarzeń.")
            print("  Unikat NIE zostanie założony — najpierw scal je:")
            print("      python -m scripts.dedupe_events --apply")
            print("  potem uruchom tę migrację ponownie (jest idempotentna).")
        else:
            await conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_event_one_per_article "
                "ON events (source_article_id) "
                "WHERE source_article_id IS NOT NULL AND canonical_id IS NULL"
            ))
            print("✓ unikat: jeden artykuł = jedno wydarzenie")

        total = (await conn.execute(text("SELECT COUNT(*) FROM events"))).scalar()
        print(f"\n  wydarzeń w bazie: {total} "
              f"(lokalność dostaną przy kolejnej ekstrakcji)")

    await engine.dispose()
    print("\n✓ Gotowe.")


if __name__ == "__main__":
    asyncio.run(migrate())
