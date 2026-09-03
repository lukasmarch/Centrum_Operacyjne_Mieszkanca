"""
Migration: usunięcie `idx_event_unique (title, event_date, location)` (2026-09-03)

Ten indeks jest reliktem sprzed deduplikacji semantycznej (21.08.2026). Wtedy
był jedynym mechanizmem rozpoznawania powtórek — i nie działał: CLAUDE.md
odnotowuje, że `scripts/migrations/remove_duplicate_events.py` „jest martwy —
szuka po (title, event_date, location), czyli po kluczu, który tych powtórek
nie widzi", bo model przy każdym przebiegu tytułował to samo wydarzenie inaczej.

3.09.2026 okazało się, że nie tylko nie pomaga, ale przeszkadza. Nadrabianie
ekstrakcji za 7 dni (65 artykułów) padło na trzecim wpisie:

    Event 'Powiatowe Młodzieżowe Zawody Sportowo-Pożarnicze'
        = powtórzenie #1205 (podobieństwo 0.94) — scalone
    IntegrityError: duplicate key value violates unique constraint "idx_event_unique"

Dedup semantyczny ROZPOZNAŁ powtórkę i ustawił `canonical_id`, po czym stary
indeks zablokował zapis tego samego wiersza — bo drugi opis tego wydarzenia miał
identyczny tytuł, datę i miejsce. `PendingRollbackError` w następnej iteracji
zabrał resztę przebiegu (ten sam wzorzec co `article_processor` 2.09 i ta sama
pętla 22.08).

POMIAR, który rozstrzygnął o usunięciu (produkcja, 3.09):
  521 powtórek zapisanych z `canonical_id`, w tym 86 o IDENTYCZNYM tytule
  co ich wzorzec — przeszły tylko dlatego, że różniły się godziną albo
  miejscem. Indeks blokuje więc wyłącznie dokładnie identyczne trójki, czyli
  podzbiór tego, co `find_duplicate` łapie embeddingiem (identyczne tytuły to
  podobieństwo ~1,0 przy progu 0,60).

Czy coś zostaje bez ochrony? Nie:
  • `idx_event_one_per_article` (częściowy unikat na `source_article_id`)
    pilnuje idempotencji: jeden artykuł = jedno widoczne wydarzenie;
  • `find_duplicate` + `canonical_id` rozstrzygają o powtórkach z RÓŻNYCH
    artykułów — i tylko one widzą „Pożegnanie księdza Tomasza" = „Msza
    dziękczynna w Rybnie" (zawieranie rdzeni 0,00, podobieństwo 0,79);
  • gdy embedding się nie policzy (np. wyczerpane kredyty OpenAI, 2.09),
    `extract_event` kończy się wyjątkiem i wydarzenie NIE POWSTAJE wcale —
    nie ma więc wiersza, przed którym indeks miałby chronić.

Zysk jest skromny i uczciwie mały: artykuł, którego wydarzenie jest powtórką,
dostaje wreszcie swój wiersz ze śladem `source_article_id` i przestaje wracać
do gpt-4o przy każdym przebiegu, dopóki nie wypadnie z okna. Główny powód to
usunięcie źródła błędu, który potrafi wywrócić cały przebieg ekstrakcji.

⚠️ `except IntegrityError` w `event_extractor.extract_event` ZOSTAJE — teraz
jako pas bezpieczeństwa dla `idx_event_one_per_article`, nie dla tego indeksu.

Idempotentna (`DROP INDEX IF EXISTS`). Nie wymaga zmiany kodu, więc kolejność
„migracja przed kodem" jest tu spełniona sama z siebie.

Użycie:
    cd backend && python -m scripts.migrations.drop_event_text_unique
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from src.config import settings  # noqa: E402

INDEX_NAME = "idx_event_unique"


async def migrate():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        existing = (await conn.execute(text(
            "SELECT indexdef FROM pg_indexes WHERE indexname = :n"
        ), {"n": INDEX_NAME})).scalar()

        if not existing:
            print(f"• {INDEX_NAME} już nie istnieje — nic do zrobienia")
        else:
            print(f"• znaleziono: {existing}")
            await conn.execute(text(f"DROP INDEX IF EXISTS {INDEX_NAME}"))
            print(f"✓ usunięto {INDEX_NAME}")

        # Kontrola: mechanizmy, które przejmują jego rolę, muszą istnieć.
        remaining = [r[0] for r in (await conn.execute(text(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'events'"
        ))).all()]
        print(f"\n  indeksy na `events`: {', '.join(sorted(remaining))}")

        if "idx_event_one_per_article" not in remaining:
            print("  ⚠️ BRAK `idx_event_one_per_article` — idempotencja jednego "
                  "artykułu nie jest pilnowana! Uruchom "
                  "`add_locality_and_event_dedup` przed dalszą pracą.")

        stats = (await conn.execute(text(
            "SELECT COUNT(*) FILTER (WHERE canonical_id IS NOT NULL), COUNT(*) FROM events"
        ))).first()
        print(f"  wydarzeń: {stats[1]}, w tym powtórek scalonych: {stats[0]}")

    await engine.dispose()
    print("\n✓ Gotowe.")


if __name__ == "__main__":
    asyncio.run(migrate())
