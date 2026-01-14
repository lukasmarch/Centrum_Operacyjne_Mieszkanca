"""
Article Processor - Kategoryzacja artykułów przez AI

Używa Pydantic AI do automatycznej kategoryzacji artykułów do 8 modułów tematycznych,
ekstrakcji tagów, lokalizacji i generowania podsumowań.
"""
from pydantic_ai import Agent
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.models import ArticleCategory
from src.ai.prompts import CATEGORIZATION_PROMPT
from src.database.schema import Article
from src.utils.logger import setup_logger
from src.config import settings

logger = setup_logger("ArticleProcessor")


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
            article.processed = True

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
            .where(Article.content.isnot(None))  # Musi mieć content
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
