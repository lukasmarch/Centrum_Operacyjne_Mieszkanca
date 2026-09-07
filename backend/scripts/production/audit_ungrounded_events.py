"""
Przegląd wsteczny wydarzeń, których terminu nie ma w tekście źródłowym (2026-09-07)

**Skąd to.** 7.09.2026 briefing i kalendarz zapowiadały „Spotkanie w sprawie
Planu Ogólnego, 12.09 15:00". Takiego spotkania nie ma. Wydarzenie (#1064)
powstało 23.07.2026 z artykułu 4945, którego cała treść w bazie to skorupa
strony gminarybno.pl:

    Wstecz / Transmisja spotkania w sprawie Planu Ogólnego
    Opublikowano 2026-07-22 13:26:33. Artykuł wyświetlono: 55 razy.

Zero informacji o terminie — model wpisał datę z niczego.

**Dlaczego to przeszło.** Bramka `ground_event` („termin musi mieć ślad
w tekście", `_event_date_grounded`) weszła commitem 70e2687 z 21.08.2026,
miesiąc PO powstaniu tego rekordu. Kod naprawiono, danych nikt nie przejrzał —
a wydarzenie z lipca dożyło we wrześniu do briefingu, newslettera i narzędzia
`upcoming_events`. Ta sama klasa przeoczenia, co przy `locality`: bramka działa
od dnia wdrożenia w przód, baza pamięta wstecz.

**Co robi ten skrypt.** Puszcza dzisiejszą bramkę po wydarzeniach, które jeszcze
są przed nami, i pokazuje te, których data nie ma śladu w artykule źródłowym.
Nie zgaduje poprawnego terminu — kasuje wpis, bo wydarzenia bez potwierdzonej
daty nie da się naprawić, można je tylko usunąć; przy następnym przetworzeniu
artykułu ekstraktor zapisze je na nowo, jeśli termin faktycznie gdzieś padnie.

⚠️ Wydarzenie BEZ artykułu źródłowego (`source_article_id IS NULL`) zostaje
nietknięte — wpisy dodane ręcznie (jak konsultacje w Naguszewie, 25.08) nie
mają tekstu, względem którego dałoby się cokolwiek sprawdzić.

⚠️ Kasujemy wraz z powtórkami scalonymi na ten wpis (`canonical_id`), inaczej
zostałyby sierotami wskazującymi na nieistniejący rekord.

Bez `--apply` tylko pokazuje, co by zmienił.

Użycie:
    cd backend && python -u -m scripts.production.audit_ungrounded_events [--apply] [--days N]
"""
import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.ai.article_processor import SourceText, _event_date_grounded
from src.config import settings
from src.database.schema import Article, Event
from src.services.time_span import to_local


async def main(apply: bool, days: int) -> int:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        # Tylko to, co jeszcze przed nami — wydarzenie po terminie nikogo już
        # nie wprowadzi w błąd, a kasowanie historii kalendarza to osobna decyzja.
        horizon = datetime.utcnow() - timedelta(days=1)
        events = (await session.execute(
            select(Event)
            .where(Event.canonical_id.is_(None))
            .where(Event.event_date >= horizon)
            .where(Event.event_date <= datetime.utcnow() + timedelta(days=days))
            .order_by(Event.event_date)
        )).scalars().all()

        print(f"Wydarzeń przed nami (do {days} dni): {len(events)}")
        print()

        bez_sladu = []
        bez_zrodla = 0
        for event in events:
            if not event.source_article_id:
                bez_zrodla += 1
                continue
            article = (await session.execute(
                select(Article).where(Article.id == event.source_article_id)
            )).scalar_one_or_none()
            if not article:
                bez_zrodla += 1
                continue

            source = SourceText(
                title=article.title or "",
                body=(article.content or article.summary or ""),
            )
            # Model zwraca czas lokalny i tak porównywaliśmy go z tekstem przy
            # zapisie — więc i tutaj sprawdzamy datę lokalną, nie zapis w UTC.
            stamp = to_local(event.event_date).strftime("%Y-%m-%dT%H:%M")
            if not _event_date_grounded(stamp, source):
                bez_sladu.append((event, article))

        for event, article in bez_sladu:
            kiedy = to_local(event.event_date).strftime("%d.%m.%Y %H:%M")
            print(f"  ❌ #{event.id} {kiedy}  „{(event.title or '')[:56]}”")
            print(f"       artykuł {article.id} „{(article.title or '')[:56]}”")
            print(f"       utworzono {event.created_at:%Y-%m-%d}, "
                  f"treść {len(article.content or '')} zn.")
            print()

        print(f"Bez śladu daty w tekście: {len(bez_sladu)}")
        print(f"Bez artykułu źródłowego (pominięte): {bez_zrodla}")

        if not bez_sladu:
            return 0
        if not apply:
            print("\n(podgląd — uruchom z --apply, żeby usunąć)")
            return 0

        usuniete = 0
        for event, _ in bez_sladu:
            powtorki = (await session.execute(
                select(Event).where(Event.canonical_id == event.id)
            )).scalars().all()
            for dup in powtorki:
                await session.delete(dup)
                usuniete += 1
            await session.delete(event)
            usuniete += 1
        await session.commit()
        print(f"\n✅ Usunięto {usuniete} rekordów "
              f"({len(bez_sladu)} wydarzeń + powtórki).")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--days", type=int, default=120)
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.apply, args.days)))
