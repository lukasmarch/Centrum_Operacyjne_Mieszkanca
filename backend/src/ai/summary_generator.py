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
        top_article = self._select_top_article(articles_by_category)
        if top_article:
            locality = "LOKALNY" if top_article.source_id in self.LOCAL_SOURCE_IDS else "REGIONALNY"
            self.logger.info(
                f"Top article (deterministic): [ID:{top_article.id}] [{locality}] "
                f"cat={top_article.category} '{top_article.title[:60]}'"
            )
        input_data = self._prepare_input_for_ai(
            date_start,
            articles_by_category,
            events,
            air_quality,
            top_article=top_article
        )

        try:
            # 6. Wywołaj AI agent dwukrotnie, wybierz lepszy wynik
            all_articles_map = {a.id: a for a in articles}
            self.logger.info(f"Calling AI to generate summary (articles: {len(articles)}, events: {len(events)})")
            result_a = await self.agent.run(input_data)
            result_b = await self.agent.run(input_data)

            score_a = result_a.output.headline_importance_score
            score_b = result_b.output.headline_importance_score
            local_a = self._is_headline_local(result_a.output, all_articles_map)
            local_b = self._is_headline_local(result_b.output, all_articles_map)

            a_wins, reason = self._pick_winner(local_a, score_a, local_b, score_b)
            chosen = "A" if a_wins else "B"

            self.logger.info(
                f"Iteration A: score={score_a} local={local_a} headline='{result_a.output.headline[:60]}'"
            )
            self.logger.info(
                f"Iteration B: score={score_b} local={local_b} headline='{result_b.output.headline[:60]}'"
            )
            self.logger.info(f"→ Choosing {chosen} ({reason})")
            summary_data = result_a.output if chosen == "A" else result_b.output

            # 7. Rozwiąż cytowane artykuły → {id, title, url}
            cited_articles = []
            for art_id in summary_data.cited_article_ids:
                art = all_articles_map.get(art_id)
                if art and art.url:
                    cited_articles.append({
                        "id": art.id,
                        "title": art.title,
                        "url": art.url,
                        "source_id": art.source_id,
                        "published_at": art.published_at.isoformat() if art.published_at else None,
                    })

            # 8. Zapisz do bazy
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
                    "cited_articles": cited_articles,
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

    # source_ids bezpośrednio powiązane z Rybnem i gminami powiatu
    LOCAL_SOURCE_IDS = {2, 3, 5, 6, 11, 12, 13}
    # source_ids regionalne (Warmia i Mazury, nie specyficznie powiat)
    REGIONAL_SOURCE_IDS = {1, 9, 10}

    # Hierarchia ważności kategorii (niższy = ważniejszy)
    CATEGORY_PRIORITY = {
        "Awaria": 0,
        "Zdrowie": 1,
        "Transport": 2,
        "Urząd": 3,
        "Biznes": 4,
        "Edukacja": 5,
        "Kultura": 6,
        "Sport": 7,
        "Rekreacja": 8,
        "Nieruchomości": 9,
    }

    def _select_top_article(self, articles_by_category: dict):
        """Deterministycznie wybierz artykuł do nagłówka.

        Priorytet: lokalny > regionalny, Awaria > Zdrowie > Transport > ...
        Wśród artykułów tej samej kategorii i źródła: najnowszy.
        Regionalne mogą wygrać tylko jeśli brak jakichkolwiek lokalnych.
        """
        best = None
        best_key = (999, 1, 0)  # (priorytet kategorii, 0=lokalny/1=regionalny, -timestamp)

        for category, arts in articles_by_category.items():
            cat_prio = self.CATEGORY_PRIORITY.get(category, 10)
            for art in arts:
                is_local = art.source_id in self.LOCAL_SOURCE_IDS
                locality_key = 0 if is_local else 1
                ts = art.published_at.timestamp() if art.published_at else 0
                key = (cat_prio, locality_key, -ts)
                if key < best_key:
                    best_key = key
                    best = art

        return best

    def _pick_winner(self, local_a: bool, score_a: int, local_b: bool, score_b: int) -> tuple[bool, str]:
        """Wybierz lepszą iterację (True = A wygrywa).

        Reguła 1: lokalne score >= 6 zawsze wygrywa z regionalnym (niezależnie od score regionalnego)
        Reguła 2: regionalne score = 9 (kryzys wpływający na lokalnych) wygrywa z lokalnym score <= 5
        Reguła 3: w pozostałych przypadkach (oba lokalne / oba regionalne / lokalne 1-5 vs regionalne 1-8) → wyższy score (remis → A)
        """
        # Reguła 1
        if local_a and not local_b and score_a >= 6:
            return True, f"A=lokalny(score={score_a}>=6) wygrywa z regionalnym"
        if local_b and not local_a and score_b >= 6:
            return False, f"B=lokalny(score={score_b}>=6) wygrywa z regionalnym"

        # Reguła 2
        if not local_a and local_b and score_a == 9 and score_b <= 5:
            return True, f"A=regionalny krytyczny(9) wygrywa z lokalnym(score={score_b}<=5)"
        if not local_b and local_a and score_b == 9 and score_a <= 5:
            return False, f"B=regionalny krytyczny(9) wygrywa z lokalnym(score={score_a}<=5)"

        # Reguła 3
        if score_a >= score_b:
            return True, f"score A={score_a} >= B={score_b}"
        return False, f"score B={score_b} > A={score_a}"

    def _is_headline_local(self, summary_output, articles_map: dict) -> bool:
        """Sprawdź czy artykuł będący podstawą nagłówka pochodzi z lokalnego źródła.
        Pierwszy ID w cited_article_ids = artykuł z nagłówka (konwencja w prompcie).
        """
        if not summary_output.cited_article_ids:
            return False
        headline_art = articles_map.get(summary_output.cited_article_ids[0])
        if headline_art is None:
            return False
        return headline_art.source_id in self.LOCAL_SOURCE_IDS

    def _get_locality_label(self, article) -> str:
        """Zwróć etykietę [LOKALNY] lub [REGIONALNY] dla artykułu"""
        if article.source_id in self.LOCAL_SOURCE_IDS:
            return "[LOKALNY]"
        return "[REGIONALNY]"

    def _prepare_input_for_ai(
        self,
        date: datetime,
        articles_by_category: dict,
        events: list,
        air_quality: Optional[AirQuality],
        top_article=None
    ) -> str:
        """Przygotuj sformatowany tekst dla AI"""

        local_count = sum(
            1 for arts in articles_by_category.values()
            for a in arts if a.source_id in self.LOCAL_SOURCE_IDS
        )
        total_count = sum(len(arts) for arts in articles_by_category.values())

        lines = []

        # Sekcja WYMAGANY ARTYKUŁ NAGŁÓWKA — kod decyduje deterministycznie
        if top_article:
            locality = "LOKALNY" if top_article.source_id in self.LOCAL_SOURCE_IDS else "REGIONALNY"
            lines += [
                "=" * 80,
                f"⚡ WYMAGANY ARTYKUŁ NAGŁÓWKA [ID:{top_article.id}]:",
                f"   Tytuł: {top_article.title}",
                f"   Kategoria: {top_article.category} | Źródło: [{locality}]",
            ]
            if top_article.summary:
                lines.append(f"   Treść: {top_article.summary}")
            lines += [
                f"   ZASADA: Headline MUSI być o tym artykule. cited_article_ids[0] MUSI = {top_article.id}.",
                "=" * 80,
                "",
            ]

        lines += [
            f"Data: {date.strftime('%Y-%m-%d')}",
            f"Liczba artykułów: {total_count} (lokalnych: {local_count}, regionalnych: {total_count - local_count})",
            "",
            "=" * 80,
            "ARTYKUŁY PO KATEGORIACH:",
            "  [LOKALNY]   = dotyczy bezpośrednio Rybna, Działdowa lub gmin powiatu",
            "  [REGIONALNY] = dotyczy Warmii i Mazur lub obszarów poza powiatem",
            "=" * 80,
            ""
        ]

        # Dodaj artykuły pogrupowane po kategoriach
        # W każdej kategorii: najpierw [LOKALNY], potem [REGIONALNY]
        for category, arts in sorted(articles_by_category.items()):
            sorted_arts = sorted(
                arts,
                key=lambda a: (0 if a.source_id in self.LOCAL_SOURCE_IDS else 1, -a.published_at.timestamp() if a.published_at else 0)
            )
            lines.append(f"\n## {category.upper()} ({len(sorted_arts)} artykułów):\n")
            for i, article in enumerate(sorted_arts[:10], 1):  # max 10 per kategoria
                label = self._get_locality_label(article)
                lines.append(f"{i}. {label} [ID:{article.id}] {article.title}")
                if article.summary:
                    lines.append(f"   → {article.summary}")
                # Lokalizację pokazuj tylko dla artykułów LOKALNYCH - dla regionalnych
                # może być halucynowana przez AI kategoryzacji
                if article.location_mentioned and article.source_id in self.LOCAL_SOURCE_IDS:
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
