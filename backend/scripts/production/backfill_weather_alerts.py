"""
Uzupełnienie ważności ostrzeżeń meteo w istniejących artykułach (2026-08-02)

Od tej zmiany `ArticleProcessor` liczy `event_at`/`event_until` dla ostrzeżeń
pogodowych przy kategoryzacji — ale wpisy sprzed wdrożenia mają te pola puste
i feed rankuje wygasły alert burzowy jak każdą inną wiadomość. Briefing radzi
sobie bez tego (liczy ważność w locie), feed potrzebuje wartości w bazie.

Bez `--apply` tylko pokazuje, co by zmienił.

Użycie:
    cd backend && python -u -m scripts.production.backfill_weather_alerts [--days 14] [--apply]
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
from src.services import weather_alert


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
            .where(Article.event_until.is_(None))
            .order_by(Article.published_at.desc().nulls_last())
        )
        articles = result.scalars().all()

        touched = 0
        for article in articles:
            if not weather_alert.is_weather_alert(article.title, article.content):
                continue

            start, end = weather_alert.validity_or_default(
                article.title, article.content, article.published_at
            )
            if end is None:
                continue

            state = "wygasłe" if now > end else "aktualne"
            print(
                f"#{article.id} pub {article.published_at} → ważne do {end} UTC [{state}]\n"
                f"    {(article.display_title or article.title or '')[:90]}"
            )
            touched += 1

            if apply:
                article.event_at = article.event_at or start
                article.event_until = end
                session.add(article)

        if apply and touched:
            await session.commit()

        print(
            f"\nOstrzeżeń meteo bez ważności: {touched} "
            f"({'zapisano' if apply else 'próba na sucho — dodaj --apply'})"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(backfill(args.days, args.apply))
