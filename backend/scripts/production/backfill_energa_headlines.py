"""
Tytuły wyłączeń Energi złożone przez kod, nie przez model (2026-08-25)

22.08.2026 `services/energa.headline` przejęła tytułowanie wyłączeń, bo model
dostawał dwa komunikaty różniące się godziną i listą ulic, a produkował nagłówki
różniące się słowem „roku". Kategoryzacja chodzi RAZ (`articles.processed`),
więc wpisy sprzed tamtej zmiany zostały z tytułami modelu — i tak zostaną,
bo re-scrape odświeża `scraped_at`, nie `display_title`.

Skutek na produkcji 25.08.2026: feed otworzył się dwiema kartami
„Planowane wyłączenie prądu w Rybnie 25 sierpnia 2026" i „…2026 roku" — dwoma
RÓŻNYMI wyłączeniami (09:30–15:00 na Wyzwolenia 90 oraz 10:00–15:00 na
Kościelnej, Lubawskiej, Stromej i Zajeziornej), nie do odróżnienia dla czytelnika.

Ten skrypt przelicza `display_title` przez `energa.headline` dla wpisów, którym
komunikat na to pozwala. Nie rusza kategorii, ocen ani terminów — zero kosztu
modelu, zero konfabulacji.

⚠️ Uruchamiać PO wdrożeniu poprawki rdzenia „planow" w `energa.is_planned`.
Wcześniejsza wersja szukała w tytule wyłącznie formy „planowane", a feed pisze
„Wyłączenie planowe" (14 na 15 wpisów w bazie) — backfill z tamtym warunkiem
zdjąłby z zapowiedzianych wyłączeń słowo „Planowane" i zrównał je z awariami.

Bez `--apply` tylko pokazuje, co by zmienił.

Użycie:
    cd backend && python -u -m scripts.production.backfill_energa_headlines [--days 30] [--apply]
"""
import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import or_, select

from src.database.connection import async_session
from src.database.schema import Article
from src.services import energa


async def backfill(days: int, apply: bool):
    cutoff = datetime.utcnow() - timedelta(days=days)

    async with async_session() as session:
        result = await session.execute(
            select(Article)
            .where(
                or_(
                    Article.published_at >= cutoff,
                    Article.scraped_at >= cutoff,
                    # Zapowiedź sprzed miesiąca, której termin dopiero nadchodzi,
                    # jest dziś na szczycie feedu — okno po dacie ogłoszenia
                    # zgubiłoby dokładnie te wpisy, dla których to piszemy.
                    Article.event_until >= datetime.utcnow(),
                )
            )
            # Wspólny identyfikator obu kanałów Energi (`energa.canonical_id`).
            # Pewniejszy niż nazwa źródła: ten sam guid nosi wpis z kanału
            # „planowane" i z „bieżących".
            .where(Article.external_id.like("energa\\_%", escape="\\"))
            .order_by(Article.event_at.desc().nulls_last())
        )
        articles = result.scalars().all()

        touched = 0
        for article in articles:
            composed = energa.headline(article.title, article.content or article.summary)
            if composed is None:
                print(f"  id={article.id} [POMINIĘTY — komunikat nie w tym formacie] "
                      f"{(article.display_title or article.title or '')[:70]}")
                continue
            if composed == article.display_title:
                continue

            print(f"  id={article.id}")
            print(f"      było: {article.display_title or '(brak)'}")
            print(f"      jest: {composed}")
            touched += 1

            if apply:
                article.display_title = composed
                session.add(article)

        if apply and touched:
            await session.commit()

        print()
        print(f"Wpisów Energi w oknie: {len(articles)}, tytułów do złożenia: {touched}")
        print("Zapisano." if apply else "Podgląd — uruchom z --apply, żeby zapisać.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(backfill(args.days, args.apply))
