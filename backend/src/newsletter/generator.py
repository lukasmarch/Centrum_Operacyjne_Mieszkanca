"""
Newsletter content generator using AI
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from openai import AsyncOpenAI

from src.config import settings
from src.database import Article, Event, Weather, DailySummary

logger = logging.getLogger("Newsletter")


WEEKLY_NEWSLETTER_PROMPT = """Jesteś redaktorem lokalnego newslettera dla Powiatu Działdowskiego.
Przygotuj treść cotygodniowego newslettera w języku polskim.

**Styl:** Przyjazny, angażujący, lokalny. Zwracaj się do czytelnika bezpośrednio.

**Struktura newslettera:**
1. **Nagłówek powitalny** - krótkie powitanie z nawiązaniem do tygodnia
2. **TOP 5 Wiadomości Tygodnia** - najważniejsze wydarzenia z ostatnich 7 dni
3. **Nadchodzące wydarzenia** - co się dzieje w weekend/najbliższym czasie
4. **Prognoza pogody** - krótkie podsumowanie pogody na weekend
5. **Zachęta do Premium** - krótki tekst zachęcający do subskrypcji Premium

**Ważne wytyczne:**
- Priorytetyzuj: PILNE (awarie, zdrowie, urząd) > PRZYDATNE (biznes, edukacja) > CIEKAWE (kultura, rozrywka)
- Używaj konkretnych nazw miejsc (Rybno, Działdowo, Lubawa)
- Dodaj emotikony dla czytelności (🗓️, 📰, ☁️, 💎)
- Tekst powinien być zwięzły ale informatywny
- Nie wymyślaj informacji - używaj tylko podanych danych

Dane wejściowe:
- Artykuły z tygodnia: {articles}
- Nadchodzące wydarzenia: {events}
- Pogoda: {weather}
- Podsumowania dzienne: {summaries}

Zwróć treść w formacie JSON:
{{
    "subject": "Tydzień w Działdowie - [data]",
    "preview_text": "Krótki tekst preview (max 100 znaków)",
    "sections": {{
        "greeting": "Tekst powitalny",
        "top_news": [
            {{"title": "...", "summary": "...", "url": "..."}}
        ],
        "events": [
            {{"title": "...", "date": "...", "location": "..."}}
        ],
        "weather": "Podsumowanie pogody",
        "premium_cta": "Tekst zachęty do Premium"
    }}
}}
"""


DAILY_NEWSLETTER_PROMPT = """Jesteś redaktorem porannego briefingu dla mieszkańców Powiatu Działdowskiego.
Przygotuj krótki, rzeczowy poranny newsletter w języku polskim.

**Styl:** Zwięzły, praktyczny, na start dnia. "Dzień Dobry!" vibe.

**Struktura:**
1. **Powitanie** - krótkie "Dzień Dobry" z datą
2. **Pogoda i jakość powietrza** - co dziś na zewnątrz
3. **Co ważnego dziś** - 3-5 najważniejszych spraw na dziś
4. **Nadchodzące wydarzenia** - co dziś/jutro w okolicy

**Priorytet informacji:**
1. Awarie, utrudnienia, ważne ogłoszenia
2. Wydarzenia urzędowe
3. Kultura i rozrywka

Dane wejściowe:
- Dzisiejsze podsumowanie: {summary}
- Pogoda: {weather}
- Dzisiejsze wydarzenia: {events}
- Nowe artykuły: {articles}

Zwróć treść w formacie JSON:
{{
    "subject": "☀️ Dzień Dobry! [dzień tygodnia, data]",
    "preview_text": "Krótki tekst preview (max 100 znaków)",
    "sections": {{
        "greeting": "Dzień Dobry! Dziś jest...",
        "weather_brief": "🌡️ X°C | Jakość powietrza: Dobra",
        "highlights": [
            {{"icon": "🚗", "text": "..."}}
        ],
        "events_today": [
            {{"title": "...", "time": "...", "location": "..."}}
        ]
    }}
}}
"""


class NewsletterGenerator:
    """Generates newsletter content using AI"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def generate_weekly(
        self,
        session: AsyncSession,
        location: str = "Rybno"
    ) -> Dict[str, Any]:
        """
        Generate weekly newsletter content.

        Args:
            session: Database session
            location: Target location for personalization

        Returns:
            Dict with newsletter content (subject, sections, etc.)
        """
        logger.info(f"Generating weekly newsletter for {location}")

        # Get data from last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)

        # Get articles
        result = await session.execute(
            select(Article)
            .where(Article.published_at >= week_ago)
            .order_by(Article.published_at.desc())
            .limit(20)
        )
        articles = result.scalars().all()

        # Get upcoming events (next 10 days)
        result = await session.execute(
            select(Event)
            .where(Event.event_date >= datetime.utcnow())
            .where(Event.event_date <= datetime.utcnow() + timedelta(days=10))
            .order_by(Event.event_date.asc())
            .limit(10)
        )
        events = result.scalars().all()

        # Get current weather
        result = await session.execute(
            select(Weather)
            .where(Weather.location == location)
            .where(Weather.is_current == True)
            .limit(1)
        )
        weather = result.scalar_one_or_none()

        # Get daily summaries from the week
        result = await session.execute(
            select(DailySummary)
            .where(DailySummary.date >= week_ago)
            .order_by(DailySummary.date.desc())
            .limit(7)
        )
        summaries = result.scalars().all()

        # Prepare data for AI
        articles_data = [
            {
                "title": a.title,
                "summary": a.summary or a.content[:200] if a.content else "",
                "category": a.category,
                "url": a.url,
                "date": a.published_at.strftime("%Y-%m-%d") if a.published_at else ""
            }
            for a in articles
        ]

        events_data = [
            {
                "title": e.title,
                "date": e.event_date.strftime("%Y-%m-%d"),
                "time": e.event_time or "",
                "location": e.location or "",
                "description": e.short_description or ""
            }
            for e in events
        ]

        weather_data = {
            "temperature": weather.temperature if weather else None,
            "description": weather.description if weather else "brak danych",
            "humidity": weather.humidity if weather else None
        }

        summaries_data = [
            {
                "date": s.date.strftime("%Y-%m-%d"),
                "headline": s.headline,
                "highlights": s.content.get("highlights", []) if s.content else []
            }
            for s in summaries
        ]

        # Generate with AI
        prompt = WEEKLY_NEWSLETTER_PROMPT.format(
            articles=articles_data[:10],  # Limit for token efficiency
            events=events_data,
            weather=weather_data,
            summaries=summaries_data
        )

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        import json
        content = json.loads(response.choices[0].message.content)

        logger.info(f"Weekly newsletter generated: {content.get('subject', 'No subject')}")

        return content

    async def generate_daily(
        self,
        session: AsyncSession,
        location: str = "Rybno"
    ) -> Dict[str, Any]:
        """
        Generate daily morning newsletter (Premium only).

        Args:
            session: Database session
            location: Target location for personalization

        Returns:
            Dict with newsletter content
        """
        logger.info(f"Generating daily newsletter for {location}")

        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # Get today's summary
        result = await session.execute(
            select(DailySummary)
            .where(DailySummary.date >= today - timedelta(days=1))
            .order_by(DailySummary.date.desc())
            .limit(1)
        )
        summary = result.scalar_one_or_none()

        # Get today's events
        result = await session.execute(
            select(Event)
            .where(Event.event_date >= today)
            .where(Event.event_date < today + timedelta(days=2))
            .order_by(Event.event_date.asc())
            .limit(5)
        )
        events = result.scalars().all()

        # Get current weather
        result = await session.execute(
            select(Weather)
            .where(Weather.location == location)
            .where(Weather.is_current == True)
            .limit(1)
        )
        weather = result.scalar_one_or_none()

        # Get recent articles (last 24h)
        result = await session.execute(
            select(Article)
            .where(Article.published_at >= today - timedelta(days=1))
            .order_by(Article.published_at.desc())
            .limit(10)
        )
        articles = result.scalars().all()

        # Prepare data
        summary_data = {
            "headline": summary.headline if summary else "",
            "highlights": summary.content.get("highlights", []) if summary and summary.content else []
        }

        weather_data = {
            "temperature": weather.temperature if weather else None,
            "description": weather.description if weather else "brak danych"
        }

        events_data = [
            {
                "title": e.title,
                "time": e.event_time or "",
                "location": e.location or ""
            }
            for e in events
        ]

        articles_data = [
            {
                "title": a.title,
                "category": a.category
            }
            for a in articles
        ]

        # Generate with AI
        prompt = DAILY_NEWSLETTER_PROMPT.format(
            summary=summary_data,
            weather=weather_data,
            events=events_data,
            articles=articles_data
        )

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        import json
        content = json.loads(response.choices[0].message.content)

        logger.info(f"Daily newsletter generated: {content.get('subject', 'No subject')}")

        return content
