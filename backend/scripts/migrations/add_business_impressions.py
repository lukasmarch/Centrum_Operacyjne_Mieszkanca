"""
Migration: rozdzielenie „pokazano kartę" od „ktoś kliknął kontakt" (2026-08-12)

Powód. `views_count` był sprzedawany firmom jako „wyświetlenia wizytówki", ale
liczył co innego: `BusinessCard` w katalogu wywoływał `POST /view` w `useEffect`
przy renderowaniu, więc **jedno wejście na zakładkę Firmy podbijało licznik
WSZYSTKIM wizytówkom naraz**. Przy dziesięciu firmach w katalogu każda dostawała
+1 za jedno wejście przypadkowej osoby. Liczba rosła szybko i nie znaczyła nic.

Statystyka, którą klient przyłapie na zawyżaniu, kosztuje więcej niż jej brak —
ten sam błąd wystąpił już w projekcie przy raporcie ruchu (zawyżał 15×).

Rozdzielenie:
- `impressions_count` — ile razy karta pojawiła się na ekranie (katalog, sekcja
  Reklama). Miara zasięgu.
- `views_count` — od teraz WYŁĄCZNIE kliknięcia w kontakt: telefon, www, e-mail.
  Miara zainteresowania i jedyna, którą wolno sprzedawać jako „ktoś się odezwał".

Przepisanie danych historycznych. Dotychczasowy `views_count` był w istocie
licznikiem pokazów, więc jego wartość ląduje w `impressions_count`, a
`views_count` startuje od zera. To nie jest utrata danych — to poprawienie
etykiety. Kliknięć w kontakt nie mierzyliśmy nigdy, więc każda inna wartość
początkowa byłaby zmyślona.

Idempotentna.

Użycie:
    cd backend && python -m scripts.migrations.add_business_impressions
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text

from src.database.connection import async_session  # noqa: E402


COLUMNS = [
    ("impressions_count", "INTEGER NOT NULL DEFAULT 0"),
    ("impressions_last_report", "INTEGER NOT NULL DEFAULT 0"),
]


async def migrate() -> None:
    async with async_session() as session:
        existing = (await session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'business_profiles'"
        ))).scalars().all()

        added = []
        for name, ddl in COLUMNS:
            if name in existing:
                print(f"  = kolumna {name} już istnieje")
                continue
            await session.execute(text(
                f"ALTER TABLE business_profiles ADD COLUMN {name} {ddl}"
            ))
            added.append(name)
            print(f"  + dodano kolumnę {name}")

        # Przepisanie historii wykonujemy WYŁĄCZNIE przy pierwszym przebiegu,
        # czyli razem z dodaniem kolumn. Powtórne uruchomienie nie może wyzerować
        # kliknięć zebranych już po wdrożeniu
        if "impressions_count" in added:
            result = await session.execute(text(
                "UPDATE business_profiles "
                "SET impressions_count = views_count, "
                "    impressions_last_report = views_last_report, "
                "    views_count = 0, "
                "    views_last_report = 0 "
                "WHERE views_count > 0"
            ))
            print(f"  ~ przepisano historię dla {result.rowcount} wizytówek "
                  f"(dotychczasowe „wyświetlenia" to były pokazy karty)")

        await session.commit()
        print("Migracja zakończona.")


if __name__ == "__main__":
    asyncio.run(migrate())
