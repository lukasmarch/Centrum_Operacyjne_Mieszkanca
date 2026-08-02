"""
Article Processor - Kategoryzacja artykułów przez AI

Używa Pydantic AI do automatycznej kategoryzacji artykułów do 8 modułów tematycznych,
ekstrakcji tagów, lokalizacji i generowania podsumowań.
"""
import re

from pydantic_ai import Agent
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.models import ArticleCategory
from src.ai.prompts import CATEGORIZATION_PROMPT
from src.database.schema import Article
from src.services import weather_alert
from src.utils.cost_tracker import log_api_cost
from src.utils.logger import setup_logger
from src.config import settings

logger = setup_logger("ArticleProcessor")

# Powitanie + data na początku posta ("Dzień dobry! ☀️ Dziś 26 lipca...") — typowy
# zapychacz feedu. Bezpiecznik na wypadek, gdy AI go nie oznaczy.
_GREETING_RE = re.compile(
    r'^\W*(dzień dobry|dobry wieczór|witajcie|witamy|miłego dnia|dobranoc)\W+'
    r'.{0,40}?dziś\s+(jest\s+)?\d{1,2}',
    re.IGNORECASE | re.DOTALL,
)
# Słowa, których obecność wyklucza uznanie wpisu za zapychacz — nawet po powitaniu
_URGENT_WORDS = (
    'awari', 'brak wody', 'brak prądu', 'wypadek', 'pożar', 'utrudnien',
    'ostrzeżen', 'alert', 'zamknięt', 'ewakuac', 'zagrożen',
)


def _looks_like_filler(title: str, content: str) -> bool:
    """Deterministyczny bezpiecznik dla postów powitalnych bez treści informacyjnej."""
    if not _GREETING_RE.match((title or '').strip()):
        return False
    haystack = f"{title}\n{content}".lower()
    return not any(word in haystack for word in _URGENT_WORDS)


class ArticleProcessor:
    """Serwis do przetwarzania artykułów przez AI"""

    def __init__(self):
        # Utwórz agenta w __init__ (nie na poziomie modułu)
        # żeby OPENAI_API_KEY był już załadowany z .env
        import os
        
        # Ustaw OPENAI_API_KEY jako zmienną środowiskową dla Pydantic AI
        os.environ['OPENAI_API_KEY'] = settings.OPENAI_API_KEY
        
        self.agent = Agent(
            'openai:gpt-4o-mini',
            output_type=ArticleCategory,
            system_prompt=CATEGORIZATION_PROMPT
        )
        self.logger = logger

    async def process_article(
        self,
        article: Article,
        session: AsyncSession
    ) -> Article:
        """
        Przetwórz pojedynczy artykuł przez AI

        Args:
            article: Artykuł do przetworzenia (z processed=False)
            session: Async database session

        Returns:
            Przetworzony artykuł z category, tags, summary, etc.

        Raises:
            Exception: Jeśli przetwarzanie nie powiedzie się
        """

        # Przygotuj treść do analizy (użyj content lub summary)
        text_content = article.content or article.summary or ""

        # Walidacja - artykuł musi mieć jakąś treść
        if not text_content.strip():
            self.logger.warning(f"Article {article.id} has no content or summary - skipping")
            return None

        content = f"Title: {article.title}\n\n{text_content}"

        try:
            # Wywołaj AI agent z retry logic
            self.logger.info(f"Processing article {article.id}: {article.title[:50]}...")

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    result = await self.agent.run(content)
                    category_data = result.output
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        self.logger.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s: {str(e)[:50]}")
                        import asyncio
                        await asyncio.sleep(wait_time)
                    else:
                        raise

            # Aktualizuj artykuł z wynikami AI
            article.category = category_data.primary_category
            article.tags = category_data.tags
            article.location_mentioned = category_data.locations_mentioned
            article.summary = category_data.summary
            article.display_title = category_data.display_title
            article.is_filler = category_data.is_filler or _looks_like_filler(
                article.title, text_content
            )
            article.is_promotional = category_data.is_promotional
            article.processed = True

            # Ostrzeżenie meteo obowiązuje do godziny wpisanej w jego treść
            # i nigdzie indziej. Bez `event_until` feed rankował je jak zwykłą
            # wiadomość, a briefing czytał nazajutrz jako aktualne (2.08.2026).
            # Termin liczymy tylko dla wpisów bez własnego (Energa ma swój
            # z `services/energa.py`, ustawiony już przy scrapowaniu).
            if article.event_until is None and weather_alert.is_weather_alert(
                article.title, text_content
            ):
                start, end = weather_alert.validity_or_default(
                    article.title, text_content, article.published_at
                )
                article.event_at = article.event_at or start
                article.event_until = end
                self.logger.info(
                    f"Weather alert {article.id}: ważne do {end} (UTC)"
                )

            usage = result.usage()
            log_api_cost(
                session,
                model="gpt-4o-mini",
                tokens_input=usage.request_tokens or 0,
                tokens_output=usage.response_tokens or 0,
                endpoint="scheduler:categorization",
            )

            # Zapisz do bazy
            session.add(article)
            await session.commit()
            await session.refresh(article)

            self.logger.info(
                f"✓ Processed article {article.id}: "
                f"{category_data.primary_category} "
                f"(confidence: {category_data.confidence:.2f})"
            )

            return article

        except Exception as e:
            self.logger.error(f"✗ Error processing article {article.id}: {e}")
            await session.rollback()
            raise

    async def process_batch(
        self,
        session: AsyncSession,
        batch_size: int = 10,
        days_back: int = 2
    ) -> int:
        """
        Przetwórz batch nieprzetworzonych artykułów

        Args:
            session: Async database session
            batch_size: Liczba artykułów do przetworzenia w jednym batch
            days_back: Ile dni wstecz sprawdzać artykuły (domyślnie 2 = wczoraj + dziś)

        Returns:
            Liczba pomyślnie przetworzonych artykułów
        """
        from datetime import datetime, timedelta

        # Data graniczna (2 dni wstecz)
        date_threshold = datetime.utcnow() - timedelta(days=days_back)

        # Znajdź nieprzetwórzone artykuły z ostatnich 2 dni LUB bez daty
        # (artykuły bez daty też przetwarzamy, bo mogą być świeże)
        from sqlalchemy import or_

        result = await session.execute(
            select(Article)
            .where(Article.processed == False)
            .where(
                or_(
                    Article.published_at >= date_threshold,  # Świeże (ostatnie 2 dni)
                    Article.published_at.is_(None)  # Lub bez daty (przetwórz i tak)
                )
            )
            .where(
                or_(
                    Article.content.isnot(None),  # Musi mieć content
                    Article.summary.isnot(None)   # LUB summary (dla RSS)
                )
            )
            .order_by(Article.published_at.desc().nulls_last())  # Najpierw z datą, potem NULL
            .limit(batch_size)
        )
        articles = result.scalars().all()

        if not articles:
            self.logger.info("No articles to process")
            return 0

        self.logger.info(f"Found {len(articles)} articles to process")

        # Przetwórz każdy artykuł
        processed_count = 0
        for article in articles:
            try:
                await self.process_article(article, session)
                processed_count += 1
            except Exception as e:
                self.logger.error(f"Batch processing failed for article {article.id}: {e}")
                # Kontynuuj dla pozostałych artykułów
                continue

        self.logger.info(f"Processed {processed_count}/{len(articles)} articles successfully")
        return processed_count
