"""
Summary Generator - Generowanie dziennych podsumowań przez AI

Agreguje artykuły z ostatnich 24h, wydarzenia i pogodę,
a następnie generuje przyjazne podsumowanie dla mieszkańców.
"""
from datetime import datetime, timedelta
from typing import Optional
from pydantic_ai import Agent
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.models import DailySummary as DailySummaryModel
from src.ai.prompts import DAILY_SUMMARY_PROMPT
from src.database.schema import Article, Event, AirQuality, DailySummary
from src.utils.logger import setup_logger
from src.config import settings

logger = setup_logger("SummaryGenerator")


class SummaryGenerator:
    """Serwis do generowania dziennych podsumowań"""

    def __init__(self):
        import os

        # Ustaw OPENAI_API_KEY dla Pydantic AI
        os.environ['OPENAI_API_KEY'] = settings.OPENAI_API_KEY

        # Użyj GPT-4o dla lepszej jakości podsumowań
        self.agent = Agent(
            'openai:gpt-4o',
            output_type=DailySummaryModel,
            system_prompt=DAILY_SUMMARY_PROMPT,
            output_retries=3
        )
        self.logger = logger

    async def generate_daily_summary(
        self,
        session: AsyncSession,
        target_date: Optional[datetime] = None
    ) -> Optional[DailySummary]:
        """
        Wygeneruj dzienne podsumowanie dla określonej daty

        Args:
            session: Async database session
            target_date: Data podsumowania (domyślnie wczoraj)

        Returns:
            DailySummary object lub None jeśli brak danych
        """
        # Domyślnie: dzisiejszy dzień (00:00 – teraz)
        # Jeśli mało artykułów z dziś (<10), rozszerzamy okno o wczoraj
        MIN_ARTICLES_THRESHOLD = 10

        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if target_date is None:
            target_date = today_start
        else:
            target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)

        date_start = target_date
        date_end = min(target_date + timedelta(days=1), now)  # nie sięgamy w przyszłość

        self.logger.info(f"Generating daily summary for {date_start.date()}")

        # Sprawdź czy podsumowanie już istnieje
        existing = await session.execute(
            select(DailySummary).where(DailySummary.date == date_start)
        )
        if existing.scalar_one_or_none():
            self.logger.warning(f"Summary for {date_start.date()} already exists")
            return None

        # 1. Pobierz artykuły z dziś (tylko przetworzone, po dacie PUBLIKACJI)
        articles_result = await session.execute(
            select(Article)
            .where(Article.published_at >= date_start)
            .where(Article.published_at < date_end)
            .where(Article.processed == True)
            .order_by(Article.published_at.desc())
        )
        articles = articles_result.scalars().all()

        # Fallback: jeśli mało artykułów z dziś, rozszerz okno o wczoraj
        extended = False
        if len(articles) < MIN_ARTICLES_THRESHOLD and date_start == today_start:
            yesterday_start = today_start - timedelta(days=1)
            self.logger.info(
                f"Only {len(articles)} articles for today – extending window to yesterday ({yesterday_start.date()})"
            )
            articles_result = await session.execute(
                select(Article)
                .where(Article.published_at >= yesterday_start)
                .where(Article.published_at < date_end)
                .where(Article.processed == True)
                .order_by(Article.published_at.desc())
            )
            articles = articles_result.scalars().all()
            extended = True

        if not articles:
            self.logger.warning(f"No articles found for {date_start.date()}")
            return None

        if extended:
            self.logger.info(f"Extended window: {len(articles)} articles (today + yesterday)")

        # 2. Pogrupuj artykuły po kategoriach
        articles_by_category = {}
        for article in articles:
            category = article.category or "Inne"
            if category not in articles_by_category:
                articles_by_category[category] = []
            articles_by_category[category].append(article)

        # 3. Pobierz nadchodzące wydarzenia (następne 7 dni)
        events_start = date_end
        events_end = events_start + timedelta(days=7)
        events_result = await session.execute(
            select(Event)
            .where(Event.event_date >= events_start)
            .where(Event.event_date < events_end)
            .order_by(Event.event_date.asc())
            .limit(10)
        )
        events = events_result.scalars().all()

        # 4. Pobierz aktualne dane air quality (czujnik w Rybnie)
        air_quality_result = await session.execute(
            select(AirQuality)
            .where(AirQuality.is_current == True)
            .order_by(AirQuality.fetched_at.desc())
            .limit(1)
        )
        air_quality = air_quality_result.scalar_one_or_none()

        # 5. Przygotuj dane wejściowe dla AI
        input_data = self._prepare_input_for_ai(
            date_start,
            articles_by_category,
            events,
            air_quality
        )

        try:
            # 6. Wywołaj AI agent
            self.logger.info(f"Calling AI to generate summary (articles: {len(articles)}, events: {len(events)})")
            result = await self.agent.run(input_data)
            summary_data = result.output

            # 7. Zapisz do bazy
            db_summary = DailySummary(
                date=date_start,
                headline=summary_data.headline,
                content={
                    "date": summary_data.date,
                    "headline": summary_data.headline,
                    "highlights": summary_data.highlights,
                    "summary_by_category": summary_data.summary_by_category,
                    "upcoming_events": summary_data.upcoming_events,
                    "air_quality_summary": summary_data.air_quality_summary,
                    "stats": {
                        "total_articles": len(articles),
                        "categories_count": len(articles_by_category),
                        "events_count": len(events)
                    }
                },
                generated_at=datetime.utcnow()
            )

            session.add(db_summary)
            await session.commit()
            await session.refresh(db_summary)

            self.logger.info(
                f"✓ Generated daily summary for {date_start.date()} "
                f"(articles: {len(articles)}, categories: {len(articles_by_category)})"
            )

            return db_summary

        except Exception as e:
            self.logger.error(f"✗ Error generating summary: {e}")
            await session.rollback()
            raise

    def _prepare_input_for_ai(
        self,
        date: datetime,
        articles_by_category: dict,
        events: list,
        air_quality: Optional[AirQuality]
    ) -> str:
        """Przygotuj sformatowany tekst dla AI"""

        lines = [
            f"Data: {date.strftime('%Y-%m-%d')}",
            f"Liczba artykułów: {sum(len(arts) for arts in articles_by_category.values())}",
            "",
            "=" * 80,
            "ARTYKUŁY PO KATEGORIACH:",
            "=" * 80,
            ""
        ]

        # Dodaj artykuły pogrupowane po kategoriach
        for category, arts in sorted(articles_by_category.items()):
            lines.append(f"\n## {category.upper()} ({len(arts)} artykułów):\n")
            for i, article in enumerate(arts[:10], 1):  # max 10 per kategoria
                lines.append(f"{i}. {article.title}")
                if article.summary:
                    lines.append(f"   → {article.summary}")
                if article.location_mentioned:
                    lines.append(f"   📍 {', '.join(article.location_mentioned)}")
                lines.append("")

        # Dodaj wydarzenia
        if events:
            lines.append("\n" + "=" * 80)
            lines.append("NADCHODZĄCE WYDARZENIA:")
            lines.append("=" * 80 + "\n")
            for event in events:
                event_date_str = event.event_date.strftime("%Y-%m-%d")
                if event.event_time:
                    event_date_str += f" {event.event_time}"
                lines.append(f"• {event.title}")
                lines.append(f"  Data: {event_date_str}")
                if event.location:
                    lines.append(f"  Miejsce: {event.location}")
                lines.append("")

        # Dodaj dane air quality (czujnik w Rybnie)
        if air_quality:
            lines.append("\n" + "=" * 80)
            lines.append("JAKOŚĆ POWIETRZA I WARUNKI (czujnik w Rybnie):")
            lines.append("=" * 80 + "\n")
            lines.append(f"Lokalizacja: {air_quality.location}")
            lines.append(f"Temperatura: {air_quality.temperature}°C")
            lines.append(f"Wilgotność: {air_quality.humidity}%")
            lines.append(f"Ciśnienie: {air_quality.pressure} hPa")
            lines.append(f"\nJakość powietrza: {air_quality.caqi_level} (CAQI: {air_quality.caqi})")
            lines.append(f"Pyły zawieszone:")
            lines.append(f"  - PM2.5: {air_quality.pm25} µg/m³")
            lines.append(f"  - PM10: {air_quality.pm10} µg/m³")
            lines.append(f"\nAktualizacja: {air_quality.fetched_at}")

        return "\n".join(lines)
