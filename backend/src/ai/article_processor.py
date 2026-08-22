"""
Article Processor - Kategoryzacja artykułów przez AI

Używa Pydantic AI do automatycznej kategoryzacji artykułów do 8 modułów tematycznych,
ekstrakcji tagów, lokalizacji i generowania podsumowań.
"""
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic_ai import Agent, RunContext
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.models import ArticleCategory
from src.ai.prompts import CATEGORIZATION_PROMPT
from src.database.schema import Article
from src.services import energa, weather_alert
from src.services.alert_policy import _flat, places_in
from src.services.feed_policy import LOCAL_TZ
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
# Dzień tygodnia w wejściu dla modelu — „w najbliższą sobotę" bez niego
# jest nieprzeliczalne
_WEEKDAYS = (
    "poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela",
)

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


# Zapowiedź dalej niż pół roku w przód to prawie zawsze pomyłka modelu (zwykle
# rok publikacji doklejony do dnia zdarzenia). Wsteczne terminy odrzucamy poza
# marginesem doby: post o wczorajszym festynie to relacja, nie zapowiedź.
MAX_EVENT_LOOKAHEAD_DAYS = 180
MAX_EVENT_BACKDATE_DAYS = 1

# --- próg krótkiej treści ----------------------------------------------------
# 04.08.2026: 40-znakowy post „RyBaśka - Restauracja Rybna 👌🏼🐟" dostał od modelu
# nagłówek „Nowa restauracja RyBaśka otwarta w Rybnie" i summary o „promowaniu
# regionalnych smaków" — wszystko poza nazwą zmyślone, bo `summary` i
# `display_title` są w schemacie obowiązkowe, a przy tak krótkim wejściu jedynym
# materiałem na „własne słowa" jest wiedza ogólna modelu. Poniżej progu NIE
# wołamy modelu wcale: tytuł zostaje po odjęciu emoji, summary zostaje surowe
# (scraper RSS) albo puste, kategoria NULL. Wyjątek: słowa pilne — 45-znakowe
# „jutro brak wody na ul. Leśnej" to pełnoprawna informacja i idzie do modelu.
MIN_CONTENT_CHARS = 120

# Doklejka naszego scrapera FB — nie jest treścią wpisu i nie liczy się do progu
_SOURCE_SUFFIX_RE = re.compile(
    r"\s*Pełna treść u źródła:.*$", re.DOTALL | re.IGNORECASE
)

# Strzałki, symbole, dingbaty, emoji właściwe + modyfikatory (ZWJ, wariant FE0F)
_EMOJI_RE = re.compile(
    "[\u200d\u2190-\u2bff\ufe0f\U0001F000-\U0001FAFF]+"
)


def _informative_text(text: str) -> str:
    return _SOURCE_SUFFIX_RE.sub("", text or "").strip()


def _clean_title(title: str) -> str:
    """Surowy tytuł w wersji do pokazania: bez emoji, wykrzykników i śmieci."""
    cleaned = _EMOJI_RE.sub("", title or "")
    cleaned = cleaned.replace("!", "").strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" -–—|,.")[:120]


def _is_low_content(title: str, text: str) -> bool:
    """Za mało treści na uczciwą parafrazę — i nic pilnego, co by ją wymuszało."""
    core = _informative_text(text)
    if len(core) >= MIN_CONTENT_CHARS:
        return False
    haystack = f"{title or ''}\n{core}".lower()
    return not any(word in haystack for word in _URGENT_WORDS)


# --- grounding odpowiedzi modelu w tekście źródłowym -------------------------
# Reguły w rodzaju „NIE ZGADUJ" stoją w prompcie i bywają ignorowane (12.08:
# post o Nocy Perseidów bez żadnej daty dostał event_start; „Restauracja Rybna"
# 4.08 dostała lokalizację Rybno). Walidator pydantic-ai sprawdza odpowiedź
# KONTRA tekst źródłowy i po cichu przycina, co nie ma pokrycia — bez
# ModelRetry, więc bez dodatkowych wywołań.

@dataclass
class SourceText:
    """Tekst, którym model dysponował — bez naszej linii „Data publikacji"."""
    title: str
    body: str

    @property
    def flat(self) -> str:
        return _flat(f"{self.title} {self.body}")


# Ślad daty w tekście: dzień miesiąca jako liczba albo słowo względne.
# Sama nazwa miesiąca („pod koniec sierpnia") nie wystarcza na konkretny termin.
_RELATIVE_DATE_RE = re.compile(
    r"\b(dzis|dzisiaj|jutro|pojutrze|weekend|"
    r"poniedzialek|poniedzialk\w*|wtorek|wtork\w*|srod\w*|czwartek|czwartk\w*|"
    r"piatek|piatk\w*|sobot\w*|niedziel\w*)\b"
)


def _event_date_grounded(value: Optional[str], source: SourceText) -> bool:
    """Czy data podana przez model ma jakikolwiek ślad w tekście źródłowym."""
    if not value:
        return False
    try:
        local = datetime.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return False
    if re.search(rf"\b0?{local.day}\b", source.flat):
        return True
    return bool(_RELATIVE_DATE_RE.search(source.flat))


def _mentioned_in_text(name: str, flat_text: str) -> bool:
    """Nazwa miejscowości pada w tekście — po rdzeniach, odporna na odmianę."""
    words = [w for w in re.split(r"[^0-9a-z]+", _flat(name)) if w]
    if not words:
        return False
    for word in words:
        stem = word.rstrip("aeiouy")
        if len(stem) < 4:
            stem = word
        if stem not in flat_text:
            return False
    return True


async def ground_categorization(
    ctx: RunContext[SourceText], output: ArticleCategory
) -> ArticleCategory:
    """
    Deterministyczne przycięcie odpowiedzi do tego, co JEST w tekście.
    Ciche poprawki zamiast ModelRetry: korekta jest jednoznaczna, a retry
    kosztowałby drugie wywołanie przy każdym potknięciu stylu.
    """
    source = ctx.deps

    # 1. Lokalizacja musi paść w tekście — koniec z dedukcją z nazw firm
    grounded_locations = [
        loc for loc in output.locations_mentioned
        if _mentioned_in_text(loc, source.flat)
    ]
    if len(grounded_locations) != len(output.locations_mentioned):
        dropped = set(output.locations_mentioned) - set(grounded_locations)
        logger.info(f"Grounding: usunięte lokalizacje spoza tekstu: {dropped}")
        output.locations_mentioned = grounded_locations

    # 2. locality=3 wymaga nazwy z gminy Rybno wprost w tekście (ta sama lista
    #    miejscowości co bramka alertów) — „to pewnie u nas" nie jest dowodem
    if output.locality >= 3 and not places_in(source.title, source.body):
        logger.info("Grounding: locality 3→2, w tekście nie pada nazwa z gminy")
        output.locality = 2

    # 3. Styl depeszy egzekwowany kodem, nie prośbą w prompcie
    cleaned = _clean_title(output.display_title)
    if cleaned and cleaned != output.display_title:
        output.display_title = cleaned

    # 4. Termin zdarzenia musi mieć ślad w tekście (liczba dnia albo „jutro",
    #    „w sobotę"). 12.08.2026: Noc Perseidów bez żadnej daty w poście dostała
    #    event_start — model trafił z wiedzy ogólnej, ale to był czysty traf.
    if output.event_start and not _event_date_grounded(output.event_start, source):
        logger.info(
            f"Grounding: event_start {output.event_start} bez śladu daty "
            f"w tekście — odrzucony"
        )
        output.event_start = None
        output.event_end = None

    return output


def _parse_event_time(
    value: Optional[str],
    published_at: Optional[datetime],
) -> Optional[datetime]:
    """
    Termin podany przez model → naiwny UTC, albo None.

    Model dostaje i zwraca czas lokalny (tak mówi wpis), baza trzyma naiwny UTC.
    Bezpieczniki liczymy względem daty publikacji, nie „teraz": kategoryzacja
    chodzi też po zaległościach, a wpis sprzed tygodnia ma prawo zapowiadać
    zdarzenie sprzed pięciu dni.
    """
    if not value:
        return None

    try:
        local = datetime.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        return None

    if local.tzinfo is None:
        local = local.replace(tzinfo=LOCAL_TZ)
    stamp = local.astimezone(timezone.utc).replace(tzinfo=None)

    reference = published_at or datetime.utcnow()
    if stamp > reference + timedelta(days=MAX_EVENT_LOOKAHEAD_DAYS):
        return None
    if stamp < reference - timedelta(days=MAX_EVENT_BACKDATE_DAYS):
        return None
    return stamp


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
            deps_type=SourceText,
            system_prompt=CATEGORIZATION_PROMPT
        )
        # Grounding kontra tekst źródłowy — patrz komentarz nad SourceText
        self.agent.output_validator(ground_categorization)
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

        # Za krótki na uczciwą parafrazę → bez modelu. Obowiązkowe `summary`
        # i `display_title` przy 40 znakach wejścia zamieniają kategoryzację
        # w konfabulację (RyBaśka, 4.08.2026). Summary zostaje, jakie jest
        # (surowe ze scrapera albo None) — to jedyna wersja, która nie kłamie.
        # Wyłączenia Energi tytułuje KOD, nie model — komunikat jest
        # ustrukturyzowany, a model gubił w nim to jedno, co odróżnia dwa
        # wyłączenia tego samego dnia: godzinę i ulicę. Patrz `energa.headline`.
        # `None` znaczy „to nie ten format" i nie zmienia niczego.
        energa_headline = energa.headline(article.title, text_content)

        if _is_low_content(article.title, text_content):
            article.display_title = energa_headline or _clean_title(article.title) or None
            article.is_filler = article.is_filler or _looks_like_filler(
                article.title, text_content
            )
            article.processed = True
            session.add(article)
            await session.commit()
            await session.refresh(article)
            self.logger.info(
                f"✓ Article {article.id}: poniżej progu {MIN_CONTENT_CHARS} zn. "
                f"— bez kategoryzacji, tytuł źródłowy bez emoji"
            )
            return article

        # Data publikacji w treści zapytania — bez niej model nie przeliczy
        # „w najbliższą sobotę" ani „jutro o 18:00" na konkretny termin
        stamp = article.published_at or article.scraped_at
        published_line = (
            f"Data publikacji: {stamp.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ):%Y-%m-%d %H:%M} "
            f"({_WEEKDAYS[stamp.weekday()]})\n"
            if stamp else ""
        )
        content = f"{published_line}Title: {article.title}\n\n{text_content}"

        try:
            # Wywołaj AI agent z retry logic
            self.logger.info(f"Processing article {article.id}: {article.title[:50]}...")

            source_text = SourceText(title=article.title or "", body=text_content)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    result = await self.agent.run(content, deps=source_text)
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
            article.display_title = energa_headline or category_data.display_title
            article.is_filler = category_data.is_filler or _looks_like_filler(
                article.title, text_content
            )
            article.is_promotional = category_data.is_promotional
            # Trzeci czynnik rankingu obok wagi źródła i świeżości — patrz
            # `feed_policy.content_factor`. Liczony RAZ, tutaj, bo ranking feedu
            # chodzi przy każdym żądaniu i nie może pytać modelu.
            article.content_score = category_data.locality + category_data.usefulness
            # Sama lokalność zostaje osobno: w sumie z użytecznością jest nie do
            # odzyskania, a pytają o nią feed (przypięte awarie), kalendarz
            # i newsletter. Bez tego każdy z nich zgadywał ją własną heurystyką.
            article.locality = category_data.locality
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

            # Zapowiedź z terminem rankuje się terminem, nie datą ogłoszenia
            # (`feed_policy._reference_time`). Do 11.08.2026 `event_at` ustawiała
            # wyłącznie Energa przy scrapowaniu i alerty meteo wyżej — 11 wpisów
            # na 264 z miesiąca. Festyn zapowiedziany na sobotę wypadał z feedu
            # w czwartek, bo liczył się wiek ogłoszenia.
            # Energa i meteo mają pierwszeństwo: ich termin pochodzi z komunikatu,
            # nie z odczytu modelu.
            if article.event_at is None and article.event_until is None:
                start = _parse_event_time(
                    category_data.event_start, article.published_at
                )
                if start:
                    article.event_at = start
                    article.event_until = _parse_event_time(
                        category_data.event_end, article.published_at
                    )
                    self.logger.info(
                        f"Event {article.id}: termin {start} (UTC) "
                        f"[{category_data.primary_category}]"
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
