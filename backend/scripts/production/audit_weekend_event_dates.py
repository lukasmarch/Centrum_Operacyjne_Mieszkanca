"""
Terminy przepuszczone przez „weekend" jako ślad daty (2026-09-08)

`_RELATIVE_DATE_RE` w kategoryzacji miała na liście śladów daty słowo
„weekend". Słowo wskazuje porę, nie dzień, więc bramka `_event_date_grounded`
przepuszczała PRZY NIM DOWOLNY termin podany przez model — dokładnie to,
przed czym miała chronić.

Objaw z 8.09.2026: post „[WYNIKI] Piłkarski weekend Delfina Rybno — seniorzy
z pierwszą wygraną" (art. 5878) to RELACJA z rozegranych meczów, a stanął
w bazie z `event_at` = 13 września. Zapowiedź żyje w feedzie i newsletterze
do swojego terminu, więc relacja udawała przyszłość przez pięć dni.

Bramka działa od dnia wdrożenia, baza pamięta wstecz — ta sama klasa
przeoczenia co przy `audit_ungrounded_events`. Skrypt szuka wpisów, którym
termin ostał się WYŁĄCZNIE dzięki słowu „weekend": brak liczby dnia w tekście
i brak nazwy dnia tygodnia. Takiego terminu nie da się już zweryfikować, więc
go czyścimy — wpis bez `event_at` liczy się od publikacji i po prostu gaśnie,
zamiast udawać zapowiedź.

Bez `--apply` tylko pokazuje, co by zmienił.

Użycie:
    cd backend && python -u -m scripts.production.audit_weekend_event_dates [--days 30] [--apply]
"""
import argparse
import asyncio
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import select  # noqa: E402

from src.ai.article_processor import _RELATIVE_DATE_RE, _flat  # noqa: E402
from src.database.connection import async_session  # noqa: E402
from src.database.schema import Article  # noqa: E402
from src.services import time_span  # noqa: E402

# Lista sprzed poprawki — „weekend" jest tu jedyną różnicą wobec dzisiejszej
_WEEKEND_RE = re.compile(r"\bweekend\w*\b")


async def audit(days: int, apply: bool) -> int:
    cutoff = datetime.utcnow() - timedelta(days=days)
    suspect = 0

    async with async_session() as session:
        result = await session.execute(
            select(Article)
            .where(Article.event_at.isnot(None))
            .where(Article.published_at >= cutoff)
            .order_by(Article.published_at.desc())
        )
        articles = list(result.scalars().all())
        print(f"Wpisów z terminem z ostatnich {days} dni: {len(articles)}\n")

        for article in articles:
            flat = _flat(f"{article.title or ''} {article.content or article.summary or ''}")
            if not _WEEKEND_RE.search(flat):
                continue

            # Termin obroniłby się i bez „weekendu"? Wtedy nic mu nie jest.
            day = time_span.to_local(article.event_at).day
            if re.search(r"\b0?" + str(day) + r"\b", flat):
                continue
            if _RELATIVE_DATE_RE.search(flat):
                continue

            suspect += 1
            when = f"{time_span.to_local(article.event_at):%d.%m %H:%M}"
            print(
                f"  {article.id:>5}  termin {when}  "
                f"{(article.display_title or article.title or '')[:64]}"
            )
            if apply:
                article.event_at = None
                article.event_until = None
                session.add(article)

        if apply and suspect:
            await session.commit()
            print(f"\n✓ Wyczyszczono termin w {suspect} wpisach")
        elif suspect:
            print(f"\n{suspect} wpisów do wyczyszczenia — uruchom z --apply")
        else:
            print("Brak wpisów, których termin trzymał się wyłącznie na „weekendzie”")

    return suspect


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(audit(args.days, args.apply))


if __name__ == "__main__":
    main()
