"""
Przeliczenie oceny lokalności wstecz (2026-09-24)

Od zmiany z 24.09 o `locality` rozstrzyga MIEJSCE ZDARZENIA podane przez model
(`ArticleCategory.event_places`) skonfrontowane z listą wsi gminy w kodzie
(`alert_policy.places_in`). Wcześniej model sam wystawiał ocenę i mylił się
w jedną stronę: nie wiedział, że Tuczki, Koszelewy, Truszczyny czy Dębień leżą
w gminie Rybno, więc wpisy o nich dostawały `locality=2` i lądowały w sekcji
„okolice" razem z Ciechanowem.

Bramka działa od wdrożenia, a baza pamięta wstecz — ta sama lekcja, co przy
`audit_ungrounded_events` (7.09). 24.09 w feedzie stały dwie relacje z otwarcia
drogi Tuczki–Koszelewy z oceną 2; poprawka kodu ich nie dotyczy, bo ocenę
wystawiono wcześniej.

CO ROBI: dla wpisów z `locality < 3`, w których TREŚĆ niesie nazwę wsi z gminy,
pyta model WYŁĄCZNIE o miejsce zdarzenia i — gdy któreś z miejsc należy do gminy
— podnosi `locality` do 3. Nic innego nie rusza: kategoria, tytuł, streszczenie
i termin zostają takie, jakie są.

⚠️ Nie obniża. Obniżanie działało poprawnie od początku (`locality>=3` bez nazwy
w tekście → 2), a ponowne orzekanie w tę stronę kasowałoby oceny wystawione na
pełnej treści wpisami, które od tego czasu zostały przycięte do 300 znaków.

⚠️ Pyta model raz na wpis (gpt-4o-mini). Kandydatów jest rzędu kilkudziesięciu
na miesiąc — bez `--apply` skrypt pokazuje ich listę i NIE woła modelu.

Użycie:
    cd backend && python -u -m scripts.production.backfill_locality [--days 30] [--apply]
"""
import argparse
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from datetime import datetime, timedelta  # noqa: E402

from sqlalchemy import select  # noqa: E402

from src.ai.article_processor import ArticleProcessor, SourceText  # noqa: E402
from src.database.connection import async_session  # noqa: E402
from src.database.schema import Article, Source  # noqa: E402
from src.services.alert_policy import is_foreign_region, places_in  # noqa: E402
from src.services.feed_policy import MIN_ARTICLE_LOCALITY  # noqa: E402


async def backfill(days: int, apply: bool) -> int:
    cutoff = datetime.utcnow() - timedelta(days=days)
    podniesione = 0

    async with async_session() as session:
        rows = (await session.execute(
            select(Article, Source.name)
            .join(Source, Source.id == Article.source_id)
            .where(Article.processed == True)  # noqa: E712
            .where(Article.published_at >= cutoff)
            .where(Article.locality < MIN_ARTICLE_LOCALITY)
            .order_by(Article.id.desc())
        )).all()

        # Kandydat = nazwa wsi z gminy pada w tekście. To NIE jest jeszcze powód
        # do awansu (patrz „Mieszkanki gminy Rybno wspierają akcję w Lubawie"),
        # tylko zawężenie puli, żeby nie pytać modelu o każdy wpis z miesiąca.
        kandydaci = [
            (art, src) for art, src in rows
            if places_in(art.display_title or art.title, art.content)
            and not is_foreign_region(art.display_title or art.title, art.content)
        ]

        print(f"Wpisów z oceną < {MIN_ARTICLE_LOCALITY} z {days} dni: {len(rows)}")
        print(f"Kandydatów (nazwa wsi w treści): {len(kandydaci)}\n")

        if not apply:
            for art, src in kandydaci:
                miejsca = "/".join(places_in(art.display_title or art.title, art.content))
                print(f"  [{art.id}] loc={art.locality} {miejsca:<22} {src[:20]:<20} "
                      f"{(art.display_title or art.title)[:52]!r}")
            print(f"\nBez --apply model nie jest wołany i nic nie zapisuję.")
            return 0

        processor = ArticleProcessor()
        for art, src in kandydaci:
            tekst = art.content or art.summary or ""
            if not tekst.strip():
                continue
            deps = SourceText(title=art.title or "", body=tekst)
            try:
                wynik = await processor.agent.run(
                    f"TYTUŁ: {art.title}\n\nTREŚĆ: {tekst[:2000]}", deps=deps
                )
            except Exception as blad:  # noqa: BLE001 — jeden felerny wpis nie kończy przebiegu
                print(f"  [{art.id}] ✗ model: {blad}")
                continue

            nowa = wynik.output.locality
            miejsca = wynik.output.event_places
            if nowa >= MIN_ARTICLE_LOCALITY and art.locality < MIN_ARTICLE_LOCALITY:
                print(f"  [{art.id}] loc {art.locality}→{nowa}  miejsca={miejsca}  "
                      f"{(art.display_title or art.title)[:50]!r}")
                art.locality = nowa
                podniesione += 1
            else:
                print(f"  [{art.id}] bez zmian (loc={art.locality}, miejsca={miejsca})")

        if podniesione:
            await session.commit()

    return podniesione


def main() -> int:
    parser = argparse.ArgumentParser(description="Przeliczenie oceny lokalności wstecz")
    parser.add_argument("--days", type=int, default=30, help="ile dni wstecz (domyślnie 30)")
    parser.add_argument("--apply", action="store_true", help="zapisz zmiany (bez tego tylko podgląd)")
    args = parser.parse_args()

    podniesione = asyncio.run(backfill(args.days, args.apply))
    print(f"\n{'Podniesiono' if args.apply else 'Do podniesienia'}: {podniesione} wpisów")
    return 0


if __name__ == "__main__":
    sys.exit(main())
