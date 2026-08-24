"""
Uzupełnienie terminu awarii wyczytanego z treści (2026-08-24)

Od tej zmiany `ArticleProcessor` zapisuje `event_at`/`event_until`, gdy komunikat
o awarii podaje same godziny bez daty („W godzinach 16.00 - 19.00 nastąpi
wyłączenie prądu"). Wpisy sprzed wdrożenia mają te pola puste, więc feed liczy
ich wiek od publikacji i pokazuje wczorajsze wyłączenie jako sprawę bieżącą.

Push radzi sobie bez tego (`alert_policy` liczy termin w locie), feed i briefing
potrzebują wartości w bazie.

Zakres celowo wąski: tylko wpisy, które `alert_policy.incident_of` uznaje za
awarię. Zapis „w godzinach 8:00–16:00" bywa godzinami urzędowania, a wpisany
jako termin zdarzenia przestawiłby wpis w rankingu feedu i w kalendarzu.

Bez `--apply` tylko pokazuje, co by zmienił.

Użycie:
    cd backend && python -u -m scripts.production.backfill_incident_spans [--days 14] [--apply]
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
from src.services import alert_policy


async def backfill(days: int, apply: bool):
    cutoff = datetime.utcnow() - timedelta(days=days)
    now = datetime.utcnow()

    async with async_session() as session:
        result = await session.execute(
            select(Article)
            .where(
                or_(
                    Article.published_at >= cutoff,
                    Article.scraped_at >= cutoff,
                )
            )
            .where(Article.event_at.is_(None))
            .where(Article.event_until.is_(None))
            .order_by(Article.published_at.desc().nulls_last())
        )
        articles = result.scalars().all()

        touched = 0
        for article in articles:
            content = article.content or article.summary
            if alert_policy.incident_of(article.title, content) is None:
                continue

            start, end = alert_policy.span_from_text(
                article.title, content, article.published_at
            )
            if end is None:
                continue

            state = "minęło" if now > end else "trwa/przed"
            print(
                f"  id={article.id} [{state}] {start:%d.%m %H:%M}–{end:%H:%M} UTC "
                f"| {(article.title or '')[:64]}"
            )
            touched += 1

            if apply:
                article.event_at = start
                article.event_until = end
                session.add(article)

        if apply and touched:
            await session.commit()

        print()
        print(f"Wpisów z terminem do uzupełnienia: {touched} (na {len(articles)} bez terminu)")
        print("Zapisano." if apply else "Podgląd — uruchom z --apply, żeby zapisać.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(backfill(args.days, args.apply))
