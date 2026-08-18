"""
Event Extractor - Ekstrakcja wydarzeń z artykułów

Używa Pydantic AI (GPT-4o) do identyfikacji i ekstrakcji szczegółów wydarzeń
z lokalnych wiadomości.
"""
from pydantic_ai import Agent
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Optional

from src.ai.models import ExtractedEvent
from src.ai.prompts import EVENT_EXTRACTION_PROMPT
from src.database.schema import Article, Event
from src.utils.logger import setup_logger
from src.config import settings

logger = setup_logger("EventExtractor")


# Bramka wyboru artykułów do ekstrakcji. Do 18.08.2026 była to biała lista
# ["Kultura", "Edukacja", "Urząd"] — i przez to kalendarz nie zobaczył ANI JEDNEGO
# wydarzenia sportowego (0 na 1132 wpisów). Prompt kategoryzacji słusznie wysyła
# „zawody, turnieje, biegi" do kategorii Sport, więc zapowiedź zawodów MTB
# w Rybnie 23.08.2026 wypadła tu, mimo że wisiała w bazie z trzech źródeł od 14.08.
# Odwracamy logikę: wykluczamy to, co wydarzeniem NIE JEST, zamiast zgadywać z góry,
# które kategorie mieszkaniec wpisuje sobie do kalendarza.
SKIP_CATEGORIES = frozenset({
    # Awaria ma własną ścieżkę: alert_policy + push co 15 min. Jej „termin" to czas
    # trwania usterki, nie impreza — 17 wyłączeń Energi na dwa tygodnie zalałoby
    # kalendarz i wypchnęło z niego dożynki.
    "Awaria",
    # Obwieszczenia o działkach i planach — termin składania uwag żyje w feedzie,
    # ale nikt nie idzie na to w niedzielę.
    "Nieruchomości",
})


def is_event_candidate(article: Article) -> bool:
    """
    Czy warto zapytać model, czy ten artykuł zapowiada wydarzenie.

    Bramka jest tania i ma być czytana bez uruchamiania modelu — dlatego
    osobna funkcja, a nie warunek wpleciony w zapytanie SQL.
    """
    # Zapychacze i cudza reklama nigdy nie były odsiewane, a szły do gpt-4o
    # jak wszystko inne: w kategorii Biznes 20 z 23 wpisów z dwóch tygodni to
    # była powtarzana reklama ubezpieczeń.
    if article.is_filler or article.is_promotional:
        return False

    if article.category in SKIP_CATEGORIES:
        return False

    return True


class EventExtractor:
    """Serwis do ekstrakcji wydarzeń z artykułów"""

    def __init__(self):
        # Utwórz agenta w __init__ żeby OPENAI_API_KEY był załadowany
        import os
        
        # Ustaw OPENAI_API_KEY jako zmienną środowiskową dla Pydantic AI
        os.environ['OPENAI_API_KEY'] = settings.OPENAI_API_KEY
        
        self.agent = Agent(
            'openai:gpt-4o',  # GPT-4o dla lepszej ekstrakcji strukturalnej
            output_type=ExtractedEvent,
            system_prompt=EVENT_EXTRACTION_PROMPT
        )
        self.logger = logger

    async def extract_event(
        self,
        article: Article,
        session: AsyncSession
    ) -> Optional[Event]:
        """
        Wyekstrahuj wydarzenie z artykułu

        Args:
            article: Artykuł (przetworzony przez ArticleProcessor)
            session: Async database session

        Returns:
            Event object lub None jeśli artykuł nie opisuje wydarzenia
        """

        # Przygotuj treść do analizy
        content = f"""
Title: {article.title}
Content: {article.content or article.summary or ''}
Published: {article.published_at}
URL: {article.url}
"""

        try:
            self.logger.info(f"Checking article {article.id} for events...")

            # Wywołaj AI agent
            result = await self.agent.run(content)
            event_data = result.output

            if not event_data.is_event:
                self.logger.debug(f"Article {article.id} is not an event")
                return None

            # WALIDACJA: Wydarzenie musi mieć datę (event_date jest REQUIRED w bazie)
            if not event_data.event_date:
                self.logger.warning(
                    f"Event '{event_data.title}' has no date - skipping (article {article.id})"
                )
                return None

            # Sprawdź duplikaty (ten sam tytuł + data + lokalizacja)
            if event_data.event_date:
                existing = await session.execute(
                    select(Event)
                    .where(
                        Event.title == event_data.title,
                        Event.event_date == event_data.event_date,
                        Event.location == event_data.location
                    )
                )
                if existing.scalar_one_or_none():
                    self.logger.info(f"Event already exists: {event_data.title} on {event_data.event_date} at {event_data.location}")
                    return None

            # Utwórz nowe wydarzenie
            event = Event(
                title=event_data.title,
                description=event_data.description,
                short_description=event_data.short_description,
                event_date=event_data.event_date,
                event_time=event_data.event_time,
                end_date=event_data.end_date,
                location=event_data.location,
                address=event_data.address,
                organizer=event_data.organizer,
                price_info=event_data.price_info,
                contact_info=event_data.contact_info,
                source_article_id=article.id,
                external_url=article.url,
                image_url=article.image_url,
                category=article.category
            )

            session.add(event)
            await session.commit()
            await session.refresh(event)

            self.logger.info(
                f"✓ Extracted event: {event.title} on {event.event_date}"
            )
            return event

        except Exception as e:
            self.logger.error(f"✗ Event extraction failed for article {article.id}: {e}")
            await session.rollback()
            return None

    async def extract_from_recent(
        self,
        session: AsyncSession,
        hours: int = 24
    ) -> int:
        """
        Wyekstrahuj wydarzenia z ostatnich X godzin

        O tym, które artykuły trafiają do modelu, decyduje `is_event_candidate`:
        odrzucamy zapychacze, reklamy i kategorie, które wydarzeniem nie są
        (patrz SKIP_CATEGORIES). Reszta idzie do modelu — również Sport
        i Rekreacja, których stara biała lista nie przepuszczała wcale.

        Args:
            session: Async database session
            hours: Ile godzin wstecz sprawdzać artykuły

        Returns:
            Liczba wyekstrahowanych wydarzeń
        """

        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Pobierz przetwórzone artykuły z ostatnich X godzin
        result = await session.execute(
            select(Article)
            .where(
                Article.processed == True,
                Article.scraped_at >= cutoff,
                Article.category.is_not(None),
            )
            .order_by(Article.scraped_at.desc())
        )
        candidates = result.scalars().all()
        articles = [a for a in candidates if is_event_candidate(a)]

        if not articles:
            self.logger.info("No articles to extract events from")
            return 0

        self.logger.info(
            f"Checking {len(articles)} articles for events "
            f"({len(candidates) - len(articles)} odrzuconych przez bramkę)..."
        )

        # Ekstrahuj wydarzenia
        event_count = 0
        for article in articles:
            event = await self.extract_event(article, session)
            if event:
                event_count += 1

        self.logger.info(f"Extracted {event_count} events from {len(articles)} articles")
        return event_count
