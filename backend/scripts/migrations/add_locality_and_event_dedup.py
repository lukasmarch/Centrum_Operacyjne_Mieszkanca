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

Kolumny są NULL-owalne, a `articles.locality` nie jest backfillowana: ocena powstaje
przy kategoryzacji, więc po jednym przebiegu (6:15 / 13:15) świeży materiał ma komplet,
a wpisy bez oceny mają w feedzie fallback na `places_in`.

`events.locality` backfillujemy — inaczej naprawa nie dotyczy tego, co JUŻ wisi
w kalendarzu: widok przepuszcza NULL (żeby nie skasować lokalnych wpisów sprzed
migracji), więc III Ciechanowski Festiwal zostałby w mailu mimo poprawnego kodu.
Backfill jest deterministyczny i wąski — bez modelu, bez zgadywania:
  3  nazwa z gminy Rybno pada w lokalizacji lub tytule (`alert_policy.places_in`)
  2  ośrodek powiatu działdowskiego
  0  ZAMKNIĘTA lista obcych ośrodków, które realnie zalały kalendarz przez feed
     Radia 7 (Sierpc, Ciechanów, Mława, Żuromin, Płońsk, Warszawa…)
  NULL bez zmian — wszystko inne zostaje widoczne. Wyjazd organizowany przez gminę
     („Wakacyjna wycieczka do Ciechocinka") ma obcą lokalizację, a jest nasz, więc
     lista obcych nie może być domysłem „skoro nie znam, to nie nasze".

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
from src.services.alert_policy import _flat, places_in

# Ośrodki powiatu działdowskiego — mieszkaniec Rybna tam pojedzie (locality 2).
POWIAT_PLACES = ("dzialdow", "lidzbark", "plosnic", "ilow", "narzym", "burkat",
                 "uzdow", "grodki", "turza")

# Zamknięta lista ośrodków, które przez feedy Radia 7, Radia Olsztyn i Powiatu
# weszły do kalendarza, a z gminą Rybno nie mają wspólnego nic (locality 0).
# Dwie grupy: mazowieckie (Radio 7 obsługuje ciechanowskie i płockie) oraz
# warmińsko-mazurskie spoza powiatu działdowskiego. Wpis, którego nie ma tu ani
# w POWIAT_PLACES, zostaje NULL i pozostaje widoczny — patrz Ciechocinek.
# ⚠️ „lidzbark" wyżej złapie też Lidzbark Warmiński jako powiatowy. Świadomie:
# jedno wydarzenie za dużo w kalendarzu boli mniej niż zniknięcie Lidzbarka
# Welskiego, do którego z Rybna jedzie się 20 minut.
OBCE_PLACES = (
    # mazowieckie
    "sierpc", "ciechanow", "mlaw", "zuromin", "plonsk", "warszaw",
    "golotczyzn", "poswietn", "rosciszew", "sochaczew",
    # warmia i mazury poza powiatem działdowskim
    "olsztyn", "ostrod", "morag", "nidzic", "mragow", "gizyck", "ketrzyn",
    "szczytn", "elblag", "ilaw", "lubaw", "byszwald", "brodnic", "chrosle",
)


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

        # --- backfill events.locality -----------------------------------------
        rows = (await conn.execute(text(
            "SELECT id, title, location FROM events WHERE locality IS NULL"
        ))).all()

        counts = {3: 0, 2: 0, 0: 0}
        for event_id, title, location in rows:
            haystack = f"{location or ''} {title or ''}"
            flat = _flat(haystack)
            if places_in(location, title):
                score = 3
            elif any(name in flat for name in POWIAT_PLACES):
                score = 2
            elif any(name in flat for name in OBCE_PLACES):
                score = 0
            else:
                continue  # nieznane — zostaje NULL, czyli widoczne
            await conn.execute(
                text("UPDATE events SET locality = :s WHERE id = :i"),
                {"s": score, "i": event_id},
            )
            counts[score] += 1

        print(f"\n✓ backfill lokalności: gmina {counts[3]}, powiat {counts[2]}, "
              f"poza {counts[0]}, bez zmian {len(rows) - sum(counts.values())}")

        total = (await conn.execute(text("SELECT COUNT(*) FROM events"))).scalar()
        hidden = (await conn.execute(text(
            "SELECT COUNT(*) FROM events WHERE locality IS NOT NULL AND locality < 2"
        ))).scalar()
        print(f"  wydarzeń w bazie: {total}, w tym {hidden} zniknie z kalendarza")

    await engine.dispose()
    print("\n✓ Gotowe.")


if __name__ == "__main__":
    asyncio.run(migrate())
