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
from src.database.schema import CinemaShowtime, Source
from src.newsletter.name_days import get_name_days, get_special_day
from src.services import waste_policy
from src.services.time_span import local_day_bounds, to_local, when_label
# Newsletter jest obrazem feedu: ten sam materiał, ta sama polityka. Wcześniej
# miał własne zapytania (zwykłe `order by published_at`) i własną listę
# miejscowości, więc mieszkaniec dostawał mailem to, czego na stronie nie było:
# duplikaty i wydarzenia z Ciechanowa.
from src.services.feed_policy import (
    article_score,
    collapse_duplicates,
    dedup_text,
    publishable_conditions,
    time_label,
    visible_event_conditions,
)

logger = logging.getLogger("Newsletter")

# Własny pomiar pogody mają tylko dwie lokalizacje (`weather_job`): Rybno i Działdowo.
# Konto może wskazać dowolną z 24 miejscowości gminy — wtedy pogodę bierzemy z Rybna.
WEATHER_FALLBACK_LOCATION = "Rybno"

# Poland timezone: UTC+1 (CET)
POLAND_TZ = timezone(timedelta(hours=1))

DAYS_PL = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
DAYS_PL_SHORT = ["pon.", "wt.", "śr.", "czw.", "pt.", "sob.", "niedz."]
MONTHS_PL = [
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia"
]
MONTHS_PL_SHORT = ["STY", "LUT", "MAR", "KWI", "MAJ", "CZE",
                   "LIP", "SIE", "WRZ", "PAŹ", "LIS", "GRU"]

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


WEEKLY_NEWSLETTER_PROMPT = """Jesteś redaktorem lokalnego newslettera RybnoLive dla gminy Rybno.
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
    "subject": "Tydzień w gminie Rybno - [data]",
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


DAILY_NEWSLETTER_PROMPT = """Jesteś redaktorem porannego briefingu RybnoLive dla mieszkańców gminy Rybno.
Przygotuj krótki, rzeczowy poranny newsletter w języku polskim.

**Styl:** Zwięzły, praktyczny, na start dnia. Bez powitań i bez emotikon — powitanie
i datę dokłada szablon. Piszesz jak lokalna redakcja, nie jak asystent.

**Priorytet informacji:**
1. Awarie, utrudnienia, ważne ogłoszenia
2. Sprawy urzędowe
3. Kultura, wydarzenia, rozrywka

**status_line:** jedno zdanie (max 140 znaków) opisujące stan gminy na dziś —
to, co czytelnik ma wiedzieć, zanim wyjdzie z domu. Bez daty, bez powitania.

**highlights:** 3-5 wniosków. Każdy przypisz do agenta, który by go zgłosił:
- "Redaktor" — wiadomości lokalne, sprawy bieżące
- "Urzędnik" — urząd, BIP, przetargi, komunikaty gminy
- "Strażnik" — awarie, bezpieczeństwo, utrudnienia, pogoda groźna
- "Przewodnik" — wydarzenia, kultura, rekreacja, gastronomia
- "Organizator" — odpady, harmonogramy, sprawy porządkowe
Pole "meta" to krótka etykieta kontekstu (max 30 znaków), np. "Komunikat urzędowy",
"Droga wojewódzka 538", "Kultura · Rybno". Pole "text" to jedno-dwa zdania konkretu.

**CZAS GRAMATYCZNY — materiał jest rozdzielony i nie wolno go mieszać:**
- Wpisy z bloku JUŻ SIĘ WYDARZYŁO opisuj w czasie PRZESZŁYM: „w Hartowcu
  przeprowadzono…", „wczoraj w Rybnie odbyło się…". To relacje, nie zaproszenia.
- Wpisy z bloku DZIŚ I PRZED NAMI opisuj jako sprawę bieżącą lub nadchodzącą:
  „dziś o 9:00 zbiera się…", „w sobotę wystartuje…".
- Etykieta w nawiasie kwadratowym przed każdym wpisem podaje jego czas
  ([wczoraj 14:00], [ZDARZENIE dziś 09:00–14:00 — TRWA TERAZ], [jutro 18:00]).
  Trzymaj się jej — jest wyliczona z bazy, nie zgadywana.

**Ważne wytyczne:**
- Nie wymyślaj informacji — korzystaj wyłącznie z podanych danych
- Nazwy miejsc podawaj tylko jeśli są w danych
- Trzymaj się gminy Rybno; sprawy powiatowe tylko gdy realnie dotyczą mieszkańców

Dane wejściowe:
- Data: {current_date}
- Imieniny: {name_days}
- Dzień specjalny: {special_day}
- Dzisiejsze podsumowanie: {summary}
- Jakość powietrza (Airly): {air_quality_summary}
- Dzisiejsze wydarzenia: {events}

JUŻ SIĘ WYDARZYŁO (relacje — czas przeszły):
{articles_past}

DZIŚ I PRZED NAMI (sprawy bieżące i zapowiedzi):
{articles_ahead}

Zwróć treść w formacie JSON:
{{
    "preview_text": "Krótki tekst preview (max 90 znaków, bez emotikon)",
    "sections": {{
        "status_line": "Jedno zdanie o stanie gminy na dziś",
        "highlights": [
            {{"agent": "Strażnik", "meta": "Droga 538", "text": "..."}}
        ]
    }}
}}
"""


class NewsletterGenerator:
    """Generates newsletter content using AI"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def _weather_for(self, session: AsyncSession, location: str) -> Optional[Weather]:
        """Pogoda dla lokalizacji konta, a gdy jej nie ma — dla gminy.

        `weather_job` pobiera dwa punkty pomiarowe (Rybno, Działdowo), a użytkownik
        wybiera przy rejestracji jedną z 24 miejscowości. Bez tego fallbacku briefing
        mieszkańca Dębienia przychodził bez pogody: zapytanie o `location='Dębień'`
        nie miało prawa niczego znaleźć. Jedna stacja obsługuje całą gminę — lepszy
        pomiar z Rybna niż puste miejsce w mailu.
        """
        for candidate in (location, WEATHER_FALLBACK_LOCATION):
            if not candidate:
                continue
            result = await session.execute(
                select(Weather)
                .where(Weather.location == candidate)
                .where(Weather.is_current == True)
                .limit(1)
            )
            weather = result.scalar_one_or_none()
            if weather:
                return weather
        return None

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
            .where(*visible_event_conditions(Event))
            .order_by(Event.event_date.asc())
            .limit(10)
        )
        events = result.scalars().all()

        # Get current weather
        weather = await self._weather_for(session, location)

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
                "date": to_local(a.published_at).strftime("%Y-%m-%d") if a.published_at else ""
            }
            for a in articles
        ]

        events_data = [
            {
                "title": e.title,
                # Etykieta liczona od TERAZ, nie surowa data w UTC — model
                # dostawał „2026-09-04" o biegu z 5.09 i pisał „dziś"
                "kiedy": when_label(e.event_date, e.end_date, datetime.utcnow()),
                "date": to_local(e.event_date).strftime("%Y-%m-%d"),
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

        # Daty wydarzeń liczone WPROST z bazy (nie z AI — koniec ze znakami "?"),
        # plakietka lokalna z `locality` — patrz komentarz w `generate_daily`
        content["events_db"] = [
            {
                "title": e.title,
                # Czas LOKALNY — patrz `events_today_db` w briefingu dziennym
                "day": to_local(e.event_date).day,
                "month": MONTHS_PL_SHORT[to_local(e.event_date).month - 1],
                "location": e.location or "",
                "time": e.event_time or "",
                "is_local": (e.locality or 0) >= 3,
            }
            for e in events
        ]

        # Puls tygodnia — moduł analityczny "Gmina w liczbach" (dane DB + trend)
        try:
            content["puls"] = await self.get_weekly_stats(session)
        except Exception as e:
            logger.error(f"Nie udało się policzyć Pulsu tygodnia: {e}")
            content["puls"] = None

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

        # Granice DZISIEJSZEJ doby LOKALNEJ w naiwnym UTC. Do 5.09.2026 stało tu
        # `utcnow().replace(hour=0)`, czyli doba przesunięta o dwie godziny —
        # a wpis całodniowy stoi dokładnie na lokalnej północy. Skutek widać było
        # 4.09 o 7:15: pięć skrzynek dostało „Dziś w okolicy: VI Leśny Nocny
        # Bieg", który odbywał się nazajutrz.
        day_start, day_end = local_day_bounds()
        today_str = now_pl.strftime("%d.%m.%Y")

        # Get today's summary
        result = await session.execute(
            select(DailySummary)
            .where(DailySummary.date >= day_start - timedelta(days=1))
            .order_by(DailySummary.date.desc())
            .limit(1)
        )
        summary = result.scalar_one_or_none()

        # Wydarzenia na DZIŚ. Okno było dwudniowe pod nagłówkiem „Dziś w okolicy",
        # więc jutrzejszy festyn czytało się jako dzisiejszy; teraz sekcja mówi
        # to, co obiecuje. Powtórki i wydarzenia spoza powiatu odsiewa wspólny
        # warunek widoczności — ten sam, co w kalendarzu na stronie.
        result = await session.execute(
            select(Event)
            .where(Event.event_date >= day_start)
            .where(Event.event_date < day_end)
            .where(*visible_event_conditions(Event))
            .order_by(Event.event_date.asc())
            .limit(5)
        )
        events = result.scalars().all()

        # Get current weather
        weather = await self._weather_for(session, location)

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

        # Materiał z ostatniej doby — dokładnie ten, który widzi mieszkaniec
        # w feedzie: bez zapychaczy i cudzych reklam (`publishable_conditions`),
        # uszeregowany rankingiem feedu i zdeduplikowany. Bez tego mail brał
        # dziesięć najświeższych wpisów jak leci: 20.08 turniej w Tuczkach
        # opisało sześć postów i wszystkie sześć poszło do modelu jako osobne
        # wiadomości.
        result = await session.execute(
            select(Article, Source.name)
            .join(Source, Article.source_id == Source.id)
            .where(Article.published_at >= day_start - timedelta(days=1))
            .where(*publishable_conditions(Article))
            .order_by(Article.published_at.desc())
            .limit(40)
        )
        rows = list(result)
        now_naive = datetime.utcnow()
        rows.sort(
            key=lambda row: article_score(
                row[0].published_at, row[0].scraped_at, row[1], now_naive,
                row[0].event_at, row[0].event_until, row[0].content_score,
                row[0].locality, row[0].title, row[0].content,
            ),
            reverse=True,
        )
        rows = collapse_duplicates(rows, text_of=lambda row: dedup_text(row[0]))
        articles = [article for article, _ in rows[:10]]

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
            .where(Report.created_at >= day_start)
            .order_by(Report.upvotes.desc(), Report.created_at.desc())
            .limit(5)
        )
        reports = result.scalars().all()
        reports_date_label = "dzisiaj"

        if not reports:
            yesterday_start = day_start - timedelta(days=1)
            result = await session.execute(
                select(Report)
                .where(Report.is_spam == False)
                .where(Report.status != "rejected")
                .where(Report.created_at >= yesterday_start)
                .where(Report.created_at < day_start)
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
            {
                "title": e.title,
                "time": e.event_time or "",
                "location": e.location or "",
                "when": time_label(None, e.event_date, e.end_date, now_naive),
            }
            for e in events
        ]

        # Model dostawał `{"title", "category"}` — ANI JEDNEJ daty — i sam
        # rozstrzygał, co się dopiero wydarzy: 21.08 briefing zapowiadał
        # posiedzenie komisji, które trwało, i pisał o wczorajszym wydarzeniu
        # w czasie przyszłym. Materiał rozdzielamy tu, w kodzie, bo o tym,
        # co minęło, rozstrzyga zegar, nie model.
        def _entry(article) -> dict:
            return {
                "when": time_label(
                    article.published_at or article.scraped_at,
                    article.event_at, article.event_until, now_naive,
                ),
                "title": article.display_title or article.title,
                "category": article.category,
            }

        ahead, past = [], []
        for article in articles:
            reference = article.event_at or article.published_at or article.scraped_at
            target = ahead if reference and reference >= day_start else past
            target.append(_entry(article))

        # Generate with AI
        prompt = DAILY_NEWSLETTER_PROMPT.format(
            current_date=current_date_str,
            name_days=", ".join(name_days) if name_days else "brak",
            special_day=special_day or "brak",
            summary=summary_data,
            air_quality_summary=air_quality_summary,
            weather=weather_data,
            events=events_data,
            articles_past=past or "brak",
            articles_ahead=ahead or "brak",
        )

        response = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        import json
        content = json.loads(response.choices[0].message.content)

        # Temat i nagłówek składamy sami — model potrafił wstawić złą datę,
        # a temat maila decyduje o otwarciu wiadomości
        caqi_label = (
            CAQI_LABELS.get(air_quality.caqi_level, air_quality.caqi_level).lower()
            if air_quality else None
        )
        subject_parts = [f"Rybno, {DAYS_PL_SHORT[now_pl.weekday()]} {now_pl.day} {MONTHS_PL[now_pl.month - 1]}"]
        if weather and weather.temperature is not None:
            subject_parts.append(f"{round(weather.temperature)}°")
        if caqi_label:
            subject_parts.append(f"powietrze {caqi_label}")
        content["subject"] = " · ".join(subject_parts)
        content["date_header"] = (
            f"{DAYS_PL[now_pl.weekday()]} · {now_pl.day} {MONTHS_PL[now_pl.month - 1]} "
            f"{now_pl.year} · {now_pl.strftime('%H:%M')}"
        )
        content["sources_count"] = len(articles) + len(events) + len(reports)

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

        # Wywóz odpadów — dziś albo jutro. Mail powitalny obiecuje przypomnienie,
        # a do 20.08.2026 briefing nie wiedział o harmonogramie nic: `proactive_alerts_job`
        # pomijał posiadaczy newslettera dziennego z adnotacją „dostaną w emailu".
        content["waste"] = await waste_policy.next_collection_for_location(
            session, location, within_days=1, now=now_pl.replace(tzinfo=None)
        )
        content["reports_today"] = reports_data
        content["reports_date_label"] = reports_date_label

        # Prawdziwa pogoda (OpenWeather) — osobno od jakości powietrza (Airly).
        # Wcześniej briefing pokazywał kafel Airly udający pogodę.
        content["weather"] = {
            "temperature": round(weather.temperature) if weather and weather.temperature is not None else None,
            "description": weather.description if weather else None,
            "temp_min": round(weather.temp_min) if weather and weather.temp_min is not None else None,
            "temp_max": round(weather.temp_max) if weather and weather.temp_max is not None else None,
            "wind_kmh": round(weather.wind_speed * 3.6) if weather and weather.wind_speed is not None else None,
        } if weather else None

        # Daty wydarzeń wprost z bazy (chip dzień/miesiąc, marker lokalny).
        # Plakietkę „Gmina Rybno" rozstrzyga `locality` z ekstrakcji — ta sama
        # ocena, która decyduje o wpuszczeniu wydarzenia do kalendarza. Do 21.08
        # stała tu CZWARTA w projekcie lista miejscowości: dwanaście nazw zamiast
        # dwudziestu dwóch, z „wymój", bez Tuczek i Koszelewek, dopasowywana
        # dokładnym stringiem — więc turniej w Tuczkach plakietki nie dostawał,
        # a „Ciechanów, dziedziniec Zamku" i tak wchodził do maila.
        content["events_today_db"] = [
            {
                "title": e.title,
                # Dzień i miesiąc z czasu LOKALNEGO: wpis całodniowy stoi
                # w bazie na 22:00 dnia poprzedniego, więc surowe `.day`
                # dawało na plakietce datę o dobę za wczesną.
                "day": to_local(e.event_date).day,
                "month": MONTHS_PL_SHORT[to_local(e.event_date).month - 1],
                "location": e.location or "",
                "time": e.event_time or "",
                "is_local": (e.locality or 0) >= 3,
            }
            for e in events
        ]

        logger.info(f"Daily newsletter generated: {content.get('subject', 'No subject')}")

        return content

    async def get_weekly_stats(self, session: AsyncSession) -> Dict[str, Any]:
        """
        Returns raw weekly stats for 'Gmina w Liczbach' card.
        No AI — pure DB aggregates for last 7 days.
        """
        week_ago = datetime.utcnow() - timedelta(days=7)
        prev_week_ago = datetime.utcnow() - timedelta(days=14)

        def trend_pct(current: int, previous: int):
            """Zmiana % vs poprzedni tydzień (None gdy brak bazy porównania)."""
            if not previous:
                return None
            return round((current - previous) / previous * 100)

        result = await session.execute(
            select(func.count(Article.id)).where(Article.published_at >= week_ago)
        )
        articles_count = result.scalar() or 0

        result = await session.execute(
            select(func.count(Article.id))
            .where(Article.published_at >= prev_week_ago)
            .where(Article.published_at < week_ago)
        )
        articles_prev = result.scalar() or 0

        result = await session.execute(
            select(Article.category, func.count(Article.id).label("cnt"))
            .where(Article.published_at >= week_ago)
            .group_by(Article.category)
            .order_by(func.count(Article.id).desc())
            .limit(6)
        )
        top_categories = [
            {"category": row[0] or "Inne", "count": row[1]}
            for row in result.all()
        ]
        max_cat = max((c["count"] for c in top_categories), default=0)
        for c in top_categories:
            c["pct"] = round(c["count"] / max_cat * 100) if max_cat else 0

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
            select(func.count(Event.id))
            .where(Event.event_date >= prev_week_ago)
            .where(Event.event_date < week_ago)
        )
        events_prev = result.scalar() or 0

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
            "articles_trend": trend_pct(articles_count, articles_prev),
            "top_categories": top_categories,
            "reports_count": reports_count,
            "events_count": events_count,
            "events_trend": trend_pct(events_count, events_prev),
            "weather": {"temp_avg": temp_avg, "temp_min": temp_min, "temp_max": temp_max},
            "air_quality": {"caqi_avg": caqi_avg, "pm25_avg": pm25_avg},
        }
