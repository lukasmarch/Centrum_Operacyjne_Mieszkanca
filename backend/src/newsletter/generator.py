"""
Newsletter content generator using AI
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func
from openai import AsyncOpenAI

from src.config import settings
from src.database import Article, Event, Weather, DailySummary, AirQuality, Report
from src.database.schema import CinemaShowtime
from src.newsletter.name_days import get_name_days, get_special_day

logger = logging.getLogger("Newsletter")

# Poland timezone: UTC+1 (CET)
POLAND_TZ = timezone(timedelta(hours=1))

DAYS_PL = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
MONTHS_PL = [
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia"
]

CAQI_LABELS = {
    "VERY_LOW": "Bardzo Dobra",
    "LOW": "Dobra",
    "MEDIUM": "Umiarkowana",
    "HIGH": "Zła",
    "VERY_HIGH": "Bardzo Zła",
}


def get_poland_now() -> datetime:
    """Zwraca aktualny czas w strefie czasowej Polski (UTC+1)."""
    return datetime.now(POLAND_TZ)


def format_polish_date(dt: datetime) -> str:
    """Formatuje datę w stylu polskim: Środa, 18 lutego 2026."""
    return f"{DAYS_PL[dt.weekday()]}, {dt.day} {MONTHS_PL[dt.month - 1]} {dt.year}"


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
- Nazwy miejsc podawaj WYŁĄCZNIE jeśli są w podanych danych — nie dopisuj lokalizacji z głowy
- Dodaj emotikony dla czytelności (🗓️, 📰, ☁️, 💎)
- Tekst powinien być zwięzły ale informatywny
- Nie wymyślaj informacji - używaj tylko podanych danych

Dane wejściowe:
- Artykuły z tygodnia: {articles}
- Nadchodzące wydarzenia: {events}
- Pogoda: {weather}
- Podsumowania dzienne: {summaries}
- Zgłoszenia mieszkańców (7 dni): {reports}
- Statystyki powietrza tygodnia: {air_quality_stats}

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
1. **Powitanie** - krótkie "Dzień Dobry" z datą (użyj podanej daty: {current_date})
2. **Pogoda i jakość powietrza** - co dziś na zewnątrz (dane Airly: {air_quality_summary})
3. **Co ważnego dziś** - 3-5 najważniejszych spraw na dziś
4. **Nadchodzące wydarzenia** - co dziś/jutro w okolicy

**Priorytet informacji:**
1. Awarie, utrudnienia, ważne ogłoszenia
2. Wydarzenia urzędowe
3. Kultura i rozrywka

WAŻNE: W sekcji "subject" wpisz dokładną datę: {current_date}

Dane wejściowe:
- Data: {current_date}
- Imieniny: {name_days}
- Dzień specjalny: {special_day}
- Dzisiejsze podsumowanie: {summary}
- Jakość powietrza (Airly): {air_quality_summary}
- Dzisiejsze wydarzenia: {events}
- Nowe artykuły: {articles}

Zwróć treść w formacie JSON:
{{
    "subject": "☀️ Dzień Dobry! [{current_date}]",
    "preview_text": "Krótki tekst preview (max 100 znaków)",
    "sections": {{
        "greeting": "Dzień Dobry! Dziś jest {current_date}...",
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

        # Get weather history (7 days) for weekly stats
        result = await session.execute(
            select(Weather)
            .where(Weather.location == location)
            .where(Weather.fetched_at >= week_ago)
            .order_by(Weather.fetched_at.asc())
        )
        weather_history = result.scalars().all()

        # Compute weekly weather stats
        weekly_weather = None
        if weather_history:
            temps = [w.temperature for w in weather_history if w.temperature is not None]
            humidities = [w.humidity for w in weather_history if w.humidity is not None]
            temp_mins = [w.temp_min for w in weather_history if w.temp_min is not None]
            temp_maxs = [w.temp_max for w in weather_history if w.temp_max is not None]
            if temps:
                weekly_weather = {
                    "temp_min": round(min(temp_mins), 1) if temp_mins else None,
                    "temp_max": round(max(temp_maxs), 1) if temp_maxs else None,
                    "temp_avg": round(sum(temps) / len(temps), 1),
                    "humidity_avg": round(sum(humidities) / len(humidities)) if humidities else None,
                }

        # Get air quality history (7 days)
        result = await session.execute(
            select(AirQuality)
            .where(AirQuality.fetched_at >= week_ago)
            .order_by(AirQuality.fetched_at.asc())
        )
        aq_history = result.scalars().all()

        if aq_history and weekly_weather:
            avg_caqi = sum(a.caqi for a in aq_history) / len(aq_history)
            levels = [a.caqi_level for a in aq_history]
            dominant_level = max(set(levels), key=levels.count)
            weekly_weather["caqi_avg"] = round(avg_caqi, 1)
            weekly_weather["caqi_level"] = dominant_level
            weekly_weather["caqi_level_pl"] = CAQI_LABELS.get(dominant_level, dominant_level)
        elif aq_history:
            avg_caqi = sum(a.caqi for a in aq_history) / len(aq_history)
            levels = [a.caqi_level for a in aq_history]
            dominant_level = max(set(levels), key=levels.count)
            weekly_weather = {
                "caqi_avg": round(avg_caqi, 1),
                "caqi_level": dominant_level,
                "caqi_level_pl": CAQI_LABELS.get(dominant_level, dominant_level),
            }

        # Get daily summaries from the week
        result = await session.execute(
            select(DailySummary)
            .where(DailySummary.date >= week_ago)
            .order_by(DailySummary.date.desc())
            .limit(7)
        )
        summaries = result.scalars().all()

        # Get weekly reports
        result = await session.execute(
            select(Report)
            .where(Report.is_spam == False)
            .where(Report.status != "rejected")
            .where(Report.created_at >= week_ago)
            .order_by(Report.upvotes.desc(), Report.created_at.desc())
            .limit(10)
        )
        weekly_reports_list = result.scalars().all()

        by_category: Dict[str, int] = {}
        for r in weekly_reports_list:
            by_category[r.category] = by_category.get(r.category, 0) + 1

        weekly_reports = {
            "total": len(weekly_reports_list),
            "by_category": by_category,
            "top_reports": [
                {
                    "title": r.title,
                    "category": r.category,
                    "address": r.address or r.location_name or "",
                }
                for r in weekly_reports_list[:5]
            ],
        }

        # Prepare data for AI
        articles_data = [
            {
                "title": a.title,
                "summary": a.summary or (a.content[:200] if a.content else ""),
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

        air_quality_stats = {}
        if weekly_weather:
            air_quality_stats = {
                "caqi_avg": weekly_weather.get("caqi_avg"),
                "caqi_level": weekly_weather.get("caqi_level_pl"),
            }

        # Generate with AI
        prompt = WEEKLY_NEWSLETTER_PROMPT.format(
            articles=articles_data[:10],
            events=events_data,
            weather=weather_data,
            summaries=summaries_data,
            reports=weekly_reports,
            air_quality_stats=air_quality_stats,
        )

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        import json
        content = json.loads(response.choices[0].message.content)

        # Attach extra data for email template
        content["weekly_weather"] = weekly_weather
        content["weekly_reports"] = weekly_reports

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

        now_pl = get_poland_now()
        current_date_str = format_polish_date(now_pl)

        today_utc = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_str = now_pl.strftime("%d.%m.%Y")

        # Get today's summary
        result = await session.execute(
            select(DailySummary)
            .where(DailySummary.date >= today_utc - timedelta(days=1))
            .order_by(DailySummary.date.desc())
            .limit(1)
        )
        summary = result.scalar_one_or_none()

        # Get today's events
        result = await session.execute(
            select(Event)
            .where(Event.event_date >= today_utc)
            .where(Event.event_date < today_utc + timedelta(days=2))
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

        # Get current air quality (Airly)
        result = await session.execute(
            select(AirQuality)
            .where(AirQuality.is_current == True)
            .order_by(AirQuality.fetched_at.desc())
            .limit(1)
        )
        air_quality = result.scalar_one_or_none()

        # Fallback: last known air quality
        if not air_quality:
            result = await session.execute(
                select(AirQuality).order_by(AirQuality.fetched_at.desc()).limit(1)
            )
            air_quality = result.scalar_one_or_none()

        # Get recent articles (last 24h)
        result = await session.execute(
            select(Article)
            .where(Article.published_at >= today_utc - timedelta(days=1))
            .order_by(Article.published_at.desc())
            .limit(10)
        )
        articles = result.scalars().all()

        # Get cinema showtimes for tonight
        result = await session.execute(
            select(CinemaShowtime).where(CinemaShowtime.date == today_str).limit(10)
        )
        showtimes = result.scalars().all()

        cinema_data = []
        for s in showtimes:
            def _hour(t: str) -> int:
                try:
                    return int(t.split(':')[-2].split()[-1])
                except (ValueError, IndexError):
                    return 0
            evening_times = [t for t in (s.showtimes or []) if _hour(t) >= 17]
            if evening_times:
                cinema_data.append({
                    "title": s.title,
                    "times": evening_times,
                    "cinema": s.cinema_name,
                    "rating": s.rating,
                    "genre": s.genre,
                })

        # Get today's reports (fallback: yesterday)
        result = await session.execute(
            select(Report)
            .where(Report.is_spam == False)
            .where(Report.status != "rejected")
            .where(Report.created_at >= today_utc)
            .order_by(Report.upvotes.desc(), Report.created_at.desc())
            .limit(5)
        )
        reports = result.scalars().all()
        reports_date_label = "dzisiaj"

        if not reports:
            yesterday_utc = today_utc - timedelta(days=1)
            result = await session.execute(
                select(Report)
                .where(Report.is_spam == False)
                .where(Report.status != "rejected")
                .where(Report.created_at >= yesterday_utc)
                .where(Report.created_at < today_utc)
                .order_by(Report.upvotes.desc(), Report.created_at.desc())
                .limit(5)
            )
            reports = result.scalars().all()
            reports_date_label = "wczoraj"

        reports_data = [
            {
                "title": r.title,
                "description": r.ai_summary or r.description[:200],
                "category": r.category,
                "address": r.address or r.location_name or "",
                "upvotes": r.upvotes,
            }
            for r in reports
        ]

        # Name days and special day
        name_days = get_name_days(now_pl)
        special_day = get_special_day(now_pl)

        # Prepare AI data
        summary_data = {
            "headline": summary.headline if summary else "",
            "highlights": summary.content.get("highlights", []) if summary and summary.content else []
        }

        weather_data = {
            "temperature": weather.temperature if weather else None,
            "description": weather.description if weather else "brak danych"
        }

        air_quality_summary = "brak danych"
        if air_quality:
            caqi_label = CAQI_LABELS.get(air_quality.caqi_level, air_quality.caqi_level)
            air_quality_summary = (
                f"Temperatura: {air_quality.temperature}°C, "
                f"Wilgotność: {air_quality.humidity}%, "
                f"PM2.5: {air_quality.pm25} µg/m³, "
                f"PM10: {air_quality.pm10} µg/m³, "
                f"CAQI: {air_quality.caqi} ({caqi_label})"
            )

        events_data = [
            {"title": e.title, "time": e.event_time or "", "location": e.location or ""}
            for e in events
        ]

        articles_data = [
            {"title": a.title, "category": a.category}
            for a in articles
        ]

        # Generate with AI
        prompt = DAILY_NEWSLETTER_PROMPT.format(
            current_date=current_date_str,
            name_days=", ".join(name_days) if name_days else "brak",
            special_day=special_day or "brak",
            summary=summary_data,
            air_quality_summary=air_quality_summary,
            weather=weather_data,
            events=events_data,
            articles=articles_data,
        )

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        import json
        content = json.loads(response.choices[0].message.content)

        # Attach extra data for email template
        content["air_quality"] = {
            "temperature": air_quality.temperature,
            "humidity": air_quality.humidity,
            "pm25": air_quality.pm25,
            "pm10": air_quality.pm10,
            "caqi": air_quality.caqi,
            "caqi_level": air_quality.caqi_level,
            "caqi_label": CAQI_LABELS.get(air_quality.caqi_level, air_quality.caqi_level),
        } if air_quality else None

        content["name_days"] = name_days
        content["special_day"] = special_day
        content["cinema_evening"] = cinema_data
        content["reports_today"] = reports_data
        content["reports_date_label"] = reports_date_label

        logger.info(f"Daily newsletter generated: {content.get('subject', 'No subject')}")

        return content

    async def get_weekly_stats(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Returns raw weekly stats for 'Gmina w Liczbach' card.
        No AI — pure DB aggregates for last 7 days.
        """
        week_ago = datetime.utcnow() - timedelta(days=7)

        result = await session.execute(
            select(func.count(Article.id)).where(Article.published_at >= week_ago)
        )
        articles_count = result.scalar() or 0

        result = await session.execute(
            select(Article.category, func.count(Article.id).label("cnt"))
            .where(Article.published_at >= week_ago)
            .group_by(Article.category)
            .order_by(func.count(Article.id).desc())
            .limit(3)
        )
        top_categories = [
            {"category": row[0] or "Inne", "count": row[1]}
            for row in result.all()
        ]

        result = await session.execute(
            select(func.count(Report.id))
            .where(Report.created_at >= week_ago)
            .where(Report.is_spam == False)
        )
        reports_count = result.scalar() or 0

        result = await session.execute(
            select(func.count(Event.id)).where(Event.event_date >= week_ago)
        )
        events_count = result.scalar() or 0

        result = await session.execute(
            select(
                func.avg(Weather.temperature),
                func.min(Weather.temp_min),
                func.max(Weather.temp_max),
            )
            .where(Weather.fetched_at >= week_ago)
            .where(Weather.location == "Rybno")
        )
        row = result.one_or_none()
        temp_avg = round(float(row[0]), 1) if row and row[0] else None
        temp_min = round(float(row[1]), 1) if row and row[1] else None
        temp_max = round(float(row[2]), 1) if row and row[2] else None

        result = await session.execute(
            select(func.avg(AirQuality.caqi), func.avg(AirQuality.pm25))
            .where(AirQuality.fetched_at >= week_ago)
        )
        aq_row = result.one_or_none()
        caqi_avg = round(float(aq_row[0]), 1) if aq_row and aq_row[0] else None
        pm25_avg = round(float(aq_row[1]), 1) if aq_row and aq_row[1] else None

        return {
            "period": f"{week_ago.strftime('%d.%m')} – {datetime.utcnow().strftime('%d.%m.%Y')}",
            "articles_count": articles_count,
            "top_categories": top_categories,
            "reports_count": reports_count,
            "events_count": events_count,
            "weather": {"temp_avg": temp_avg, "temp_min": temp_min, "temp_max": temp_max},
            "air_quality": {"caqi_avg": caqi_avg, "pm25_avg": pm25_avg},
        }
