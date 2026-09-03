"""
Uzupełnienie terminu zapowiedzi wyczytanego z treści (2026-09-03)

Od tej zmiany `ArticleProcessor` dopisuje `event_at`/`event_until`, gdy data
stoi w tekście wprost, a model jej nie zwrócił (`time_span.parse_date_span`).
Pomiar 3.09: 27 na 104 wpisów z ostatnich 14 dni miało datę we WŁASNYM tytule
i puste `event_at` — feed liczył je jak świeże wiadomości, briefing otworzył
dzień poborem krwi za trzynaście dni, mając w materiale bieg na jutro.

Zakres: wpisy `processed` bez terminu. Bramka „data nie wcześniej niż
publikacja" chroni relacje — dożynki „30 sierpnia" w poście z 1.09 zostają
bez terminu. Bez `--apply` tylko pokazuje, co by zmienił.

Użycie:
    cd backend && python -u -m scripts.production.backfill_event_dates [--days 14] [--apply]
"""
import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import select  # noqa: E402

from src.database.connection import async_session  # noqa: E402
from src.database.schema import Article  # noqa: E402
from src.services import time_span  # noqa: E402


async def backfill(days: int, apply: bool) -> int:
    cutoff = datetime.utcnow() - timedelta(days=days)
    changed = 0

    async with async_session() as session:
        result = await session.execute(
            select(Article)
            .where(Article.processed == True)  # noqa: E712
            .where(Article.event_at.is_(None))
            .where(Article.published_at >= cutoff)
            .order_by(Article.published_at.desc())
        )
        articles = list(result.scalars().all())
        print(f"Wpisów bez terminu z ostatnich {days} dni: {len(articles)}")

        for article in articles:
            text = f"{article.title or ''}\n{article.content or article.summary or ''}"
            start, end = time_span.parse_date_span(text, article.published_at)
            if not start:
                continue
            changed += 1
            local = time_span.to_local(start)
            when = f"{local:%d.%m %H:%M}" + (f"–{time_span.to_local(end):%H:%M}" if end else "")
            print(f"  {article.id:>5}  {when:<18} {(article.display_title or article.title or '')[:70]}")
            if apply:
                article.event_at = start
                article.event_until = end
                session.add(article)

        if apply:
            await session.commit()
            print(f"\nZapisano: {changed}")
        else:
            print(f"\nDo zmiany: {changed} (uruchom z --apply, żeby zapisać)")
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(backfill(args.days, args.apply))
