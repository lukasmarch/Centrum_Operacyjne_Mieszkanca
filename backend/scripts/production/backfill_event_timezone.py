"""
Wyrównanie stref w kalendarzu wydarzeń (2026-08-25)

**Co było nie tak.** `EventExtractor` zapisywał `events.event_date` tak, jak
model odczytał je z ogłoszenia — czyli czasem LOKALNYM — podczas gdy cała reszta
projektu trzyma w bazie naiwny UTC (`article_processor._event_stamp` konwertuje
od początku). Ten sam termin z tego samego ogłoszenia stał więc w bazie dwa razy
i w dwóch różnych postaciach:

    art. 5487 „o godz. 10:00"  →  articles.event_at  = 27.08 08:00  (UTC, dobrze)
                               →  events.event_date  = 27.08 10:00  (lokalny!)

Mieszkaniec widział skutek w kalendarzu, briefingu i newsletterze: XXIV sesja
Rady o 10:00 pokazywała się jako **12:00**, dożynki o 11:00 jako 13:00. Wynik
`upcoming_events` niósł przy tym dwie sprzeczne godziny naraz — `data` z surowego
`strftime` (zgodną z ogłoszeniem) i `kiedy` z `time_label`, który dokładał
przesunięcie strefy.

**Skrypt przesuwa istniejące wiersze o offset strefy właściwy DLA TEJ DATY**
(`time_span.to_utc`), a nie o stałe dwie godziny — inaczej wydarzenia zimowe
rozjechałyby się o godzinę.

⚠️ **Zabezpieczenie przed dwukrotnym uruchomieniem.** Wiersz jest pomijany, gdy
`events.event_date` równa się już `articles.event_at` wpisu źródłowego (znaczy to,
że przeszedł konwersję) albo gdy powstał po wdrożeniu poprawki (`--since`).
Wydarzenia bez artykułu źródłowego takiego punktu odniesienia nie mają, więc
decyduje o nich wyłącznie `created_at`.

Bez `--apply` tylko pokazuje, co by zmienił.

Użycie:
    cd backend && python -u -m scripts.production.backfill_event_timezone \\
        [--since 2026-08-25T18:00] [--apply]
"""
import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.database.schema import Article, Event
from src.services.time_span import to_utc


async def main(since: datetime, apply: bool, force: bool = False) -> int:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        events = (await session.execute(
            select(Event).where(Event.event_date.is_not(None))
            .order_by(Event.event_date.desc())
        )).scalars().all()

        art_ids = {e.source_article_id for e in events if e.source_article_id}
        event_at = {}
        if art_ids:
            event_at = {
                a.id: a.event_at
                for a in (await session.execute(
                    select(Article).where(Article.id.in_(art_ids))
                )).scalars().all()
            }

        do_zmiany, pominiete = [], 0
        for ev in events:
            if ev.created_at and ev.created_at >= since:
                pominiete += 1          # powstało już z poprawnym zapisem
                continue
            wzorzec = event_at.get(ev.source_article_id)
            if wzorzec and wzorzec == ev.event_date:
                pominiete += 1          # zgodne z artykułem → już w UTC
                continue
            nowa = to_utc(ev.event_date)
            if nowa == ev.event_date:
                pominiete += 1          # strefa bez przesunięcia (nie zdarza się w PL)
                continue
            do_zmiany.append((ev, nowa, wzorzec))

        # BEZPIECZNIK: czy baza NIE JEST już przeliczona.
        #
        # `created_at` nie wystarcza — wpisy sprzed wdrożenia mają je zawsze
        # wcześniejsze niż `--since`, więc drugie uruchomienie przesunęłoby
        # wszystko jeszcze raz i wydarzenia wjechałyby dwie godziny w tył.
        # Pomiar na produkcji: PRZED backfillem 0 z 33 par zgadzało się
        # z `articles.event_at`, PO nim 27 z 33. Ta liczba jest więc pewnym
        # świadkiem stanu bazy — pewniejszym niż jakikolwiek znacznik, który
        # trzeba pamiętać, żeby ustawić.
        pary = [(e, event_at[e.source_article_id]) for e in events
                if e.source_article_id in event_at and event_at[e.source_article_id]]
        if pary:
            juz_utc = sum(1 for e, w in pary if e.event_date == w)
            if juz_utc * 2 >= len(pary):
                print(f"Baza wygląda na PRZELICZONĄ: {juz_utc}/{len(pary)} wydarzeń "
                      f"zgadza się z articles.event_at bez żadnej konwersji.")
                print("Powtórne przesunięcie cofnęłoby wszystkie terminy o dwie "
                      "godziny. Przerywam.")
                print("Jeśli mimo to wiesz, co robisz — uruchom z --force.")
                if not force:
                    return 1

        print(f"Wydarzeń z datą: {len(events)}")
        print(f"Pominiętych (już w UTC albo nowsze niż --since): {pominiete}")
        print(f"Do przesunięcia: {len(do_zmiany)}")
        print()

        for ev, nowa, wzorzec in do_zmiany[:20]:
            zgodnosc = ""
            if wzorzec:
                zgodnosc = " ✓ zgodne z artykułem" if wzorzec == nowa else \
                           f" ⚠️ artykuł ma {wzorzec:%d.%m %H:%M}"
            print(f"  #{ev.id} {ev.event_date:%d.%m %H:%M} → {nowa:%d.%m %H:%M}"
                  f"  „{(ev.title or '')[:44]}”{zgodnosc}")
        if len(do_zmiany) > 20:
            print(f"  … i {len(do_zmiany) - 20} dalszych")

        # Kontrola trafności: dla ilu wpisów nowa wartość zgadza się z tym, co
        # niezależnie policzyła kategoryzacja artykułu. To jedyny niezależny
        # świadek, jakiego tu mamy.
        z_wzorcem = [(e, n, w) for e, n, w in do_zmiany if w]
        if z_wzorcem:
            trafione = sum(1 for _, n, w in z_wzorcem if n == w)
            print()
            print(f"Kontrola wobec articles.event_at: {trafione}/{len(z_wzorcem)} zgodnych")

        if not do_zmiany:
            return 0
        if not apply:
            print()
            print("To był podgląd. Uruchom z --apply, żeby zapisać.")
            return 0

        for ev, nowa, _ in do_zmiany:
            if ev.end_date:
                ev.end_date = to_utc(ev.end_date)
            ev.event_date = nowa
            session.add(ev)
        await session.commit()

        print()
        print(f"✓ Przesunięto {len(do_zmiany)} wydarzeń na naiwny UTC.")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default=None,
                        help="ISO: wydarzenia utworzone od tej chwili są pomijane "
                             "(domyślnie: teraz)")
    parser.add_argument("--apply", action="store_true", help="zapisz zmiany")
    parser.add_argument("--force", action="store_true",
                        help="pomiń bezpiecznik „baza już przeliczona”")
    args = parser.parse_args()
    granica = datetime.fromisoformat(args.since) if args.since else datetime.utcnow()
    sys.exit(asyncio.run(main(granica, args.apply, args.force)))
