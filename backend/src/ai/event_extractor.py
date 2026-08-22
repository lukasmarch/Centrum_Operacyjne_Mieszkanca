"""
Event Extractor - Ekstrakcja wydarzeń z artykułów

Używa Pydantic AI (GPT-4o) do identyfikacji i ekstrakcji szczegółów wydarzeń
z lokalnych wiadomości.

Trzy bramki stoją MIĘDZY modelem a bazą, w tej kolejności — od najtańszej:

1. ARTYKUŁ  — jeden artykuł daje najwyżej jedno wydarzenie. Bramka przed
              wywołaniem modelu, bo powtórka to zwykle powtórne przetworzenie
              tego samego posta, nie nowa informacja.
2. TREŚĆ    — `ground_event` przycina odpowiedź modelu do tego, co JEST
              w tekście: data ze śladem, miejscowość z tekstu, lokalność
              potwierdzona nazwą z gminy, relacja z przeszłości odrzucona.
              Ten sam wzorzec, co `article_processor.ground_categorization`.
3. TOŻSAMOŚĆ — to samo wydarzenie opisane przez kilka źródeł zapisujemy raz.
              Rozstrzyga embedding, za który i tak płacimy (patrz `find_duplicate`).
"""
from datetime import datetime, timedelta
from typing import Optional

from pydantic_ai import Agent, RunContext
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.ai.article_processor import (
    MAX_EVENT_BACKDATE_DAYS,
    MAX_EVENT_LOOKAHEAD_DAYS,
    SourceText,
    _event_date_grounded,
    _mentioned_in_text,
)
from src.ai.chunker import chunker
from src.ai.embeddings import embedding_service
from src.ai.models import ExtractedEvent
from src.ai.prompts import EVENT_EXTRACTION_PROMPT
from src.config import settings
from src.database.schema import Article, Event
from src.services.alert_policy import places_in
from src.services.feed_policy import MIN_EVENT_LOCALITY
from src.utils.cost_tracker import log_api_cost
from src.utils.logger import setup_logger

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

# Powyżej tego podobieństwa kosinusowego dwa wydarzenia TEGO SAMEGO DNIA uznajemy
# za jedno. Próg zmierzony 21.08.2026 na embeddingach z bazy (`document_embeddings`,
# source_type='event'), 40 par z 20 dni:
#   duplikaty       0,66–0,98  (turniej w Tuczkach z sześciu postów; „Msza Święta
#                               dziękczynna" i „Pożegnanie księdza Tomasza" = 0,80)
#   różne wydarzenia ≤ 0,54    (Msza vs Zarybinek MTB 0,38–0,51; Turniej Rycerski
#                               vs warsztaty plastyczne 0,54)
# Porównanie tekstowe tego nie umie i nie da się go dostroić: „Pożegnanie księdza
# Tomasza" kontra „Msza Święta dziękczynna w Rybnie" ma zawieranie rdzeni 0,00
# (to samo wydarzenie), a „Komisja Skarg" kontra „Komisja Rewizyjna" — 0,50
# (dwa różne). Każdy próg tekstowy myli te przypadki, embedding rozdziela je
# z zapasem 0,12.
DUPLICATE_SIMILARITY = 0.60


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

    # Lokalność jest już policzona przy kategoryzacji (`articles.locality`) —
    # nie ma powodu płacić za gpt-4o, żeby wyekstrahować wydarzenie, które
    # bramka miejsca i tak odrzuci przy zapisie. NULL = wpis sprzed migracji
    # albo poniżej progu treści; wtedy decyduje dopiero ocena wydarzenia.
    if article.locality is not None and article.locality < MIN_EVENT_LOCALITY:
        return False

    return True


async def ground_event(
    ctx: RunContext[SourceText], output: ExtractedEvent
) -> ExtractedEvent:
    """
    Deterministyczne przycięcie odpowiedzi do tego, co JEST w tekście.

    Ciche poprawki zamiast ModelRetry — tak samo jak w kategoryzacji: korekta
    jest jednoznaczna, a ponowne wywołanie gpt-4o kosztowałoby przy każdym
    potknięciu. Wyłączenie wydarzenia robimy przez `is_event=False`, bo to
    jedyne pole, które czyta kod zapisujący.
    """
    if not output.is_event:
        return output

    source = ctx.deps

    # 1. Relacja z tego, co już było, nie jest wydarzeniem do kalendarza.
    #    Model deklaruje to sam w `is_upcoming` — pole istnieje po to, żeby
    #    nie było kolejnym akapitem w prompcie.
    if not output.is_upcoming:
        logger.info(
            f"Grounding: „{(output.title or '')[:40]}” to relacja z przeszłości, "
            f"nie zapowiedź — pominięte"
        )
        output.is_event = False
        return output

    # 2. Termin musi mieć ślad w tekście — liczba dnia albo „jutro"/„w sobotę".
    #    Ta sama funkcja, którą kategoryzacja przycina `event_start`.
    if output.event_date:
        stamp = output.event_date.strftime("%Y-%m-%dT%H:%M")
        if not _event_date_grounded(stamp, source):
            logger.info(f"Grounding: data {stamp} bez śladu w tekście — odrzucona")
            output.is_event = False
            return output

    # 3. Miejsce musi paść w tekście. Model dopisywał je z nazwy organizatora
    #    („Restauracja Rybna" → lokalizacja Rybno, 4.08.2026).
    if output.location and not _mentioned_in_text(output.location, source.flat):
        logger.info(f"Grounding: miejsce „{output.location}” spoza tekstu — usunięte")
        output.location = None

    # 4. locality=3 wymaga nazwy z gminy Rybno wprost w tekście — ta sama zasada
    #    i ta sama lista miejscowości, co przy artykułach i przy alertach push.
    if output.locality >= 3 and not places_in(source.title, source.body):
        logger.info("Grounding: locality 3→2, w tekście nie pada nazwa z gminy")
        output.locality = 2

    return output


# Separatory dopisku do nazwy miejscowości: „Ciechanów, dziedziniec Zamku",
# „Rybno – Zarybinek", „Grądy, Gmina Rybno". Myślnik dopisany 21.08.2026 — bez
# niego ten sam wyścig MTB stał w kalendarzu dwa razy, bo „Rybno" i „Rybno –
# Zarybinek" liczyły się jako dwa różne miejsca.
_PLACE_SEPARATORS = (",", "–", "—", " - ", "/")


def _place_key(location: Optional[str]) -> str:
    """
    Miejscowość w postaci porównywalnej: nazwa bez dopisku o miejscu w niej.

    „Ciechanów" i „Ciechanów, dziedziniec Zamku Książąt Mazowieckich" to jedno
    miejsce — dwa rekordy tego samego festiwalu z tego samego artykułu różniły
    się wyłącznie tym dopiskiem i unikat `(title, event_date, location)` ich
    nie widział.

    ⚠️ Klucz nie rozpoznaje opisowych lokalizacji („Zagroda Edukacyjna w Sąpach"
    kontra „Sąpy, gmina Młynary"). Takie pary zostają nierozstrzygnięte
    i wypisuje je `scripts/test_event_dedup.py --db` do przejrzenia — celowo:
    reguła miejsca ma chronić przed scaleniem dwóch różnych imprez tego samego
    dnia, więc w razie wątpliwości nie scala.
    """
    from src.services.alert_policy import _flat

    text = location or ""
    for separator in _PLACE_SEPARATORS:
        text = text.split(separator)[0]
    return _flat(text).strip()


async def find_duplicate(
    session: AsyncSession,
    embedding: list[float],
    event_date: datetime,
    location: Optional[str],
    exclude_id: Optional[int] = None,
) -> Optional[tuple[int, float]]:
    """
    Wydarzenie, którego to jest powtórzeniem — albo None.

    Kandydatów zawęża DZIEŃ: dwa wpisy o różnych datach nie są tym samym
    wydarzeniem, choćby brzmiały identycznie (dwa wyłączenia w tej samej wsi
    to ta sama lekcja, którą feed odrobił w `collapse_duplicates`). W obrębie
    dnia rozstrzyga embedding — porównanie tekstowe tu nie wystarcza, patrz
    komentarz przy `DUPLICATE_SIMILARITY`.

    Miejscowość jest warunkiem WYKLUCZAJĄCYM, nie grupującym: gdy oba wpisy ją
    mają i jest różna, nie ma o czym mówić; gdy jednemu jej brakuje (model
    czasem jej nie poda), decyduje sam embedding.
    """
    day = event_date.date()
    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

    # Wykluczenie wchodzi do zapytania jako FRAGMENT SQL, nie jako parametr
    # o wartości NULL. asyncpg wysyła zapytanie protokołem rozszerzonym i przy
    # `:exclude_id IS NULL` nie ma z czego wywnioskować typu parametru —
    # PostgreSQL odpowiada `AmbiguousParameterError: could not determine data
    # type of parameter $2`. Ekstraktor woła tę funkcję ZAWSZE bez wykluczenia
    # (wydarzenie jeszcze nie istnieje), więc gałąź z NULL-em była gałęzią
    # domyślną: od 21.08.2026 wywracała każdą ekstrakcję wydarzenia na
    # produkcji, a `dedupe_events` działał, bo podaje konkretne ID.
    params: dict = {"day": day}
    exclude_clause = ""
    if exclude_id is not None:
        exclude_clause = "AND e.id <> :exclude_id"
        params["exclude_id"] = exclude_id

    rows = (await session.execute(sql_text(f"""
        SELECT e.id, e.location, 1 - (d.embedding <=> $emb${embedding_str}$emb$::vector) AS sim
        FROM events e
        JOIN document_embeddings d
          ON d.source_type = 'event' AND d.source_id = e.id AND d.chunk_index = 0
        WHERE date(e.event_date) = :day
          AND e.canonical_id IS NULL
          {exclude_clause}
        ORDER BY sim DESC
        LIMIT 10
    """), params)).all()

    key = _place_key(location)
    for event_id, other_location, sim in rows:
        other_key = _place_key(other_location)
        if key and other_key and key != other_key:
            continue  # dwie różne miejscowości tego samego dnia
        if sim >= DUPLICATE_SIMILARITY:
            return int(event_id), float(sim)
    return None


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
            deps_type=SourceText,
            system_prompt=EVENT_EXTRACTION_PROMPT
        )
        # Grounding kontra tekst źródłowy — patrz komentarz nad `ground_event`
        self.agent.output_validator(ground_event)
        self.logger = logger

    async def _embed(self, session: AsyncSession, event: Event) -> tuple[dict, list[float]]:
        """
        Embedding wydarzenia liczony PRZY EKSTRAKCJI, nie w nocnym jobie.

        Do 21.08.2026 robił to `embedding_job` o 6:50 — czterdzieści minut po
        ekstrakcji. Dla RAG to bez znaczenia, ale embedding jest teraz częścią
        tożsamości wydarzenia (`find_duplicate`), a wpisy z jednego przebiegu
        muszą się widzieć nawzajem. Koszt się nie zmienia: ten sam jeden chunk,
        policzony wcześniej. Job zostaje siatką bezpieczeństwa dla wydarzeń,
        przy których to się nie powiodło (`embedded=False`).
        """
        chunk = chunker.chunk_event(
            title=event.title,
            description=event.description,
            location=event.location,
            date=event.event_date.isoformat() if event.event_date else "",
            category=event.category or "",
        )[0]

        embedding = await embedding_service.embed_text(chunk["text"])
        log_api_cost(
            session,
            model="text-embedding-3-small",
            tokens_input=embedding_service.last_usage_tokens,
            tokens_output=0,
            endpoint="extractor:event_embedding",
        )
        return chunk, embedding

    async def _persist_embedding(
        self, session: AsyncSession, event: Event, chunk: dict, embedding: list[float]
    ) -> None:
        """Zapis policzonego już embeddingu — dopiero gdy wydarzenie ma ID."""
        await embedding_service.store_embedding(
            session=session,
            source_type="event",
            source_id=event.id,
            chunk_index=0,
            chunk_text=chunk["text"],
            embedding=embedding,
            metadata={
                **chunk["metadata"],
                "title": event.title,
                "event_date": event.event_date.isoformat() if event.event_date else "",
            },
        )
        event.embedded = True

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
            (albo opisuje wydarzenie już znane — patrz bramki w nagłówku modułu)
        """

        # Bramka 1: ten artykuł już dał wydarzenie. Sprawdzana także tutaj,
        # nie tylko w zapytaniu `extract_from_recent`, bo `extract_event` bywa
        # wołane pojedynczo (skrypty diagnostyczne, ponowne przetworzenie).
        existing_for_article = await session.execute(
            select(Event.id).where(Event.source_article_id == article.id).limit(1)
        )
        if existing_for_article.scalar_one_or_none():
            self.logger.debug(f"Article {article.id} already has an event")
            return None

        # Data publikacji w treści zapytania — bez niej model nie przeliczy
        # „w najbliższą sobotę" na konkretny termin ani nie odróżni zapowiedzi
        # od relacji. Ta sama linia, co w kategoryzacji.
        content = f"""
Title: {article.title}
Content: {article.content or article.summary or ''}
Published: {article.published_at}
URL: {article.url}
"""

        try:
            self.logger.info(f"Checking article {article.id} for events...")

            source_text = SourceText(
                title=article.title or "",
                body=article.content or article.summary or "",
            )
            result = await self.agent.run(content, deps=source_text)
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

            # Termin poza rozsądnym oknem to prawie zawsze pomyłka modelu (zwykle
            # zły rok) albo relacja przebrana za zapowiedź. Te same progi, co
            # przy `event_start` w kategoryzacji — liczone od daty publikacji,
            # bo ekstrakcja chodzi też po zaległościach.
            reference = article.published_at or datetime.utcnow()
            if event_data.event_date > reference + timedelta(days=MAX_EVENT_LOOKAHEAD_DAYS):
                self.logger.info(
                    f"Event '{event_data.title}' poza oknem zapowiedzi "
                    f"({event_data.event_date}) — pominięty"
                )
                return None
            if event_data.event_date < reference - timedelta(days=MAX_EVENT_BACKDATE_DAYS):
                self.logger.info(
                    f"Event '{event_data.title}' z przeszłości "
                    f"({event_data.event_date}) — to relacja, nie zapowiedź"
                )
                return None

            # Bramka 2: miejsce. Kalendarz mieszkańca gminy kończy się na
            # sąsiednich gminach powiatu — patrz MIN_EVENT_LOCALITY.
            if event_data.locality < MIN_EVENT_LOCALITY:
                self.logger.info(
                    f"Event '{event_data.title}' poza gminą i powiatem "
                    f"(locality={event_data.locality}) — pominięty"
                )
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
                category=article.category,
                locality=event_data.locality,
            )

            # Bramka 3: tożsamość. Embedding liczymy raz — służy najpierw do
            # rozpoznania powtórki, a potem trafia do bazy jako materiał RAG.
            chunk, embedding = await self._embed(session, event)
            duplicate = await find_duplicate(
                session, embedding, event.event_date, event.location
            )
            if duplicate:
                canonical_id, similarity = duplicate
                event.canonical_id = canonical_id
                self.logger.info(
                    f"Event '{event.title}' = powtórzenie #{canonical_id} "
                    f"(podobieństwo {similarity:.2f}) — scalone"
                )

            session.add(event)
            await session.commit()
            await session.refresh(event)

            # Embedding zapisujemy dopiero teraz: przed commitem wydarzenie nie
            # ma ID, a `document_embeddings.source_id` musi na coś wskazywać.
            # Powtórki nie embedujemy — nie jest materiałem RAG i nie może być
            # kandydatem na wzorzec dla kolejnych wpisów.
            if not event.canonical_id:
                await self._persist_embedding(session, event, chunk, embedding)
                session.add(event)

            usage = result.usage()
            log_api_cost(
                session,
                model="gpt-4o",
                tokens_input=usage.request_tokens or 0,
                tokens_output=usage.response_tokens or 0,
                endpoint="scheduler:event_extraction",
            )
            await session.commit()

            if event.canonical_id:
                return None  # powtórka zapisana, ale kalendarzowi nic nie przybyło

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
        odrzucamy zapychacze, reklamy, kategorie, które wydarzeniem nie są
        (SKIP_CATEGORIES), oraz wpisy spoza gminy i powiatu.

        Artykuły, które już dały wydarzenie, odsiewa samo zapytanie. Bez tego
        ten sam post szedł do gpt-4o wielokrotnie: okno liczy się od `scraped_at`,
        a re-scrape ten znacznik NADPISUJE, więc wpis wracał w okno przy każdym
        odświeżeniu źródła i przy obu przebiegach dnia (6:15 i 13:15). Model za
        każdym razem tytułował trochę inaczej, więc unikat `(title, event_date,
        location)` tego nie widział: 129 wydarzeń z 30 dni pochodziło z 90
        artykułów — 39 rekordów to była ta sama informacja opłacona po raz drugi.

        Args:
            session: Async database session
            hours: Ile godzin wstecz sprawdzać artykuły

        Returns:
            Liczba NOWYCH wydarzeń (powtórki scalone nie liczą się do wyniku)
        """

        cutoff = datetime.utcnow() - timedelta(hours=hours)

        already_extracted = select(Event.source_article_id).where(
            Event.source_article_id.is_not(None)
        )

        result = await session.execute(
            select(Article)
            .where(
                Article.processed == True,
                Article.scraped_at >= cutoff,
                Article.category.is_not(None),
                Article.id.not_in(already_extracted),
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

        # Po pętli chodzą ID, nie obiekty ORM. `extract_event` przy błędzie robi
        # `session.rollback()`, a rollback UNIEWAŻNIA wszystkie wczytane obiekty
        # — niezależnie od `expire_on_commit=False`. Sięgnięcie po `article.id`
        # następnego wpisu próbowałoby wtedy dociągnąć go z bazy w kodzie
        # synchronicznym i wywracało CAŁY przebieg na `MissingGreenlet`
        # (22.08.2026: jeden felerny artykuł zabrał pozostałe trzynaście).
        # `session.get` czyta świadomie i asynchronicznie, więc jeden zły wpis
        # kosztuje wyłącznie siebie.
        article_ids = [article.id for article in articles]

        event_count = 0
        for article_id in article_ids:
            article = await session.get(Article, article_id)
            if article is None:
                continue
            event = await self.extract_event(article, session)
            if event:
                event_count += 1

        self.logger.info(f"Extracted {event_count} events from {len(articles)} articles")
        return event_count
