"""
Summary Generator - Generowanie dziennych podsumowań przez AI

Agreguje artykuły z ostatnich 24h, wydarzenia i pogodę,
a następnie generuje przyjazne podsumowanie dla mieszkańców.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo
from pydantic_ai import Agent, ModelRetry, RunContext
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.models import DailySummary as DailySummaryModel
from src.ai.prompts import DAILY_SUMMARY_PROMPT
from src.database.schema import Article, Event, AirQuality, DailySummary, Source, Weather
from src.services import energa, weather_alert
from src.services.feed_policy import (
    collapse_duplicates,
    dedup_text,
    is_local_article,
    MIN_ARTICLE_LOCALITY,
    visible_event_conditions,
    is_pinned_alert,
    publishable_conditions,
    same_topic,
    strip_cta_tail,
    strip_foreign_cta,
    topic_signature,
)
# Baza trzyma naiwny UTC, mieszkaniec myśli czasem lokalnym. Konwersja,
# pojęcie doby i etykieta „kiedy" mieszkają w JEDNYM miejscu — briefing był
# do 5.09.2026 jedną z pięciu kopii tej wiedzy i jako jedyna gubiła strefę
# przy wydarzeniach z kalendarza.
from src.services.time_span import (
    LOCAL_TZ,
    is_all_day,
    local_day_bounds,
    to_local,
    when_label,
)
from src.utils.cost_tracker import log_api_cost
from src.utils.logger import setup_logger
from src.config import settings

logger = setup_logger("SummaryGenerator")

# Lokalizacja, której pogodę briefing opisuje. Ta sama, którą widget bierze
# z `/api/weather` — briefing i widget nie mogą mówić o innym miejscu.
WEATHER_LOCATION = "Rybno"

# Ile slotów prognozy (co 3 h) pokazujemy modelowi. Briefing mówi o dzisiaj,
# a nie o pięciu dniach — nadmiar kusi do zapowiadania pogody na przyszły tydzień.
FORECAST_SLOTS = 5


def _local(stamp: datetime) -> datetime:
    """Naiwny UTC z bazy → czas lokalny. Cienka owijka na wspólną warstwę."""
    return to_local(stamp)


def _article_title(article) -> str:
    """
    Tytuł, który widzi model: nasz `display_title`, nie nagłówek źródła.

    Kategoryzacja pisze `display_title` właśnie po to — depesza bez emoji,
    wykrzykników i cudzych sformułowań (`prompts.CATEGORIZATION_PROMPT`, pkt 7).
    Briefing sięgał obok, po surowy `title` z Facebooka, więc 2.08.2026 otworzył
    się nagłówkiem „🔎 Znaleziono tablicę rejestracyjną podczas Dni Rybna!"
    przepisanym z posta co do znaku razem z lupą i wykrzyknikiem.
    """
    return strip_cta_tail(article.display_title or article.title or "")


def _article_body(article) -> str:
    """Streszczenie wpisu bez cudzych apeli o kontakt."""
    return strip_foreign_cta(article.summary or "")




def _event_is_over(article, now: datetime) -> bool:
    """
    Czy termin, którym wpis konkuruje, jest już za mieszkańcem.

    Trzy przypadki, bo `articles.event_at` niesie trzy różne rzeczy:
      • znany koniec (`event_until`) — rozstrzyga on,
      • zapowiedź bez godziny (`event_at` o lokalnej PÓŁNOCY, tak zapisuje ją
        kategoryzacja) — trwa do końca swojej doby, inaczej dożynki byłyby
        „po" już o 00:01 w dniu dożynek,
      • termin z godziną bez końca — zamyka się z chwilą startu.

    Ostatni punkt jest surowy świadomie: nagłówek dnia ma być rzeczą, na którą
    mieszkaniec może jeszcze zdążyć, a briefing z 13:30 wisi na stronie do
    wieczora. 26.08.2026 odświeżenie o 13:30 otworzyło się zdaniem „Posiedzenie
    Komisji Rozwoju Gospodarczego — już dziś o 12:00", czyli półtorej godziny
    po fakcie, mając w materiale sesję Rady nazajutrz.
    """
    start = getattr(article, "event_at", None)
    if start is None:
        return False

    end = getattr(article, "event_until", None)
    if end is not None:
        return end < now

    if is_all_day(start, end):
        return _local(now).date() > _local(start).date()
    return start < now


def _time_label(article, now: datetime) -> str:
    """
    Znacznik czasu przy artykule w prompcie. Bez niego model nie odróżniał
    wpisu sprzed godziny od wpisu sprzed doby i przepisywał „dziś o 17:00"
    z wczorajszego zaproszenia na koncert, który już się odbył.

    „JUŻ PO" jest tu z tego samego powodu: sama data nie mówi modelowi, że
    zapowiedź straciła ważność między porannym przebiegiem a popołudniowym,
    a etykieta jest ostatnią rzeczą, jaką czyta przy wpisie.
    """
    event_at = getattr(article, "event_at", None)
    if event_at:
        end = getattr(article, "event_until", None)
        when = when_label(event_at, end, now)
        if end and event_at <= now <= end:
            return f"[ZDARZENIE {when} — TRWA TERAZ]"
        if _event_is_over(article, now):
            return f"[ZDARZENIE {when} — JUŻ PO]"
        return f"[ZDARZENIE {when}]"

    if not article.published_at:
        return "[bez daty]"

    stamp = when_label(article.published_at, None, now, all_day=False)

    # Awaria bez godzin, która przestała być sprawą teraz. Sama data tego nie
    # mówi: 3.09.2026 model dostał przy awarii wodociągowej ZGK poprawną
    # etykietę „[wczoraj 11:07]" i i tak otworzył briefing zdaniem „DZIŚ
    # w Rybnie spadek ciśnienia wody". Etykieta jest ostatnią rzeczą, jaką
    # czyta przy wpisie — musi nieść nie tylko KIEDY, ale i CO Z TEGO WYNIKA,
    # dokładnie jak „JUŻ PO" przy zapowiedziach.
    #
    # Nie usuwamy wpisu z materiału: mieszkaniec może chcieć wiedzieć, że
    # wczoraj była awaria. Zabraniamy tylko pisać o niej w czasie teraźniejszym.
    if _alert_past_window(article, now):
        return f"[{stamp} — AWARIA SPRZED DOBY, MOGŁA JUŻ ZOSTAĆ USUNIĘTA]"
    return f"[{stamp}]"


def _alert_past_window(article, now: datetime) -> bool:
    """
    Czy to awaria, która nie jest już sprawą najbliższych godzin.

    Ten sam próg (`SummaryGenerator.ONGOING_ALERT_H`), na którym awaria traci
    zwolnienie z reguły powtórki nagłówka — jedno pytanie „czy to jeszcze
    trwa", jedna odpowiedź. Dotyczy wyłącznie wpisów BEZ terminu; te
    z terminem mają własną etykietę „TRWA TERAZ" / „JUŻ PO" wyżej.
    """
    category = (getattr(article, "category", None) or "").lower()
    if "awari" not in category:
        return False
    reference = article.published_at or getattr(article, "scraped_at", None)
    if reference is None:
        return False
    return (now - reference).total_seconds() / 3600 > SummaryGenerator.ONGOING_ALERT_H


# --- walidacja odpowiedzi briefingu ------------------------------------------
# Dwie reguły z promptu, które model łamał mimo przykładów, egzekwowane kodem:
# 12.08.2026 highlights dostały „temperaturą sięgającą 23°C" wbrew zakazowi
# liczb pomiarowych (obok stoi widget na żywo i po godzinie wartości się
# rozjeżdżają). Tu ModelRetry zamiast cichej poprawki — przeredagowanie zdania
# to zadanie modelu, wycięcie liczby kodem zostawiłoby kalekie zdanie.

# Liczba z jednostką pomiarową. Daty i godziny („19 sierpnia", „9:00") są
# dozwolone — wzorce wymagają kontekstu jednostki, nie łapią gołych liczb.
_MEASUREMENT_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:°|stopni\b|µg|ug/m)"
    r"|caqi\D{0,3}\d"
    r"|pm\s?(?:2[.,]?5|10)\D{0,10}\d",
    re.IGNORECASE,
)


@dataclass
class SummaryRun:
    """Kontekst jednego przebiegu: co briefing MUSI i co WOLNO mu cytować."""
    required_headline_id: Optional[int] = None
    known_article_ids: frozenset = field(default_factory=frozenset)


async def validate_summary(
    ctx: RunContext[SummaryRun], output: DailySummaryModel
) -> DailySummaryModel:
    # Cytowania spoza podanego materiału odpadają po cichu — link na kaflu
    # briefingu prowadziłby donikąd
    if ctx.deps.known_article_ids:
        cited = [
            i for i in output.cited_article_ids
            if i in ctx.deps.known_article_ids
        ]
        if cited != output.cited_article_ids:
            logger.info(
                "Walidator: usunięte cytowania spoza materiału: "
                f"{set(output.cited_article_ids) - set(cited)}"
            )
            output.cited_article_ids = cited

    # „WYMAGANY ARTYKUŁ NAGŁÓWKA" to dotąd była prośba w prompcie; kod wybiera
    # artykuł deterministycznie (lokalność → nie-powtórka → kategoria →
    # bliskość), więc nagłówek z innego artykułu to błąd wykonania, nie wybór
    required = ctx.deps.required_headline_id
    if required and (
        not output.cited_article_ids or output.cited_article_ids[0] != required
    ):
        raise ModelRetry(
            f"Nagłówek MUSI bazować na artykule [ID:{required}] wskazanym jako "
            f"WYMAGANY ARTYKUŁ NAGŁÓWKA, a jego ID musi być PIERWSZE w "
            f"cited_article_ids. Napisz headline o tym artykule."
        )

    match = _MEASUREMENT_RE.search(output.highlights)
    if match:
        raise ModelRetry(
            f"W highlights stoi liczba pomiarowa („{match.group(0)}”) — "
            f"zakazana, bo obok jest widget z pomiarem na żywo. Opisz warunki "
            f"jakościowo (np. „ciepło i słonecznie”), liczby zostaw w "
            f"air_quality_summary."
        )

    return output


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
            deps_type=SummaryRun,
            system_prompt=DAILY_SUMMARY_PROMPT,
            output_retries=3
        )
        self.agent.output_validator(validate_summary)
        self.logger = logger

    async def generate_daily_summary(
        self,
        session: AsyncSession,
        target_date: Optional[datetime] = None,
        force_refresh: bool = False,
    ) -> Optional[DailySummary]:
        """
        Wygeneruj dzienne podsumowanie dla określonej daty

        Args:
            session: Async database session
            target_date: Data podsumowania (domyślnie dziś)
            force_refresh: nadpisz istniejący wpis zamiast go pominąć. Briefing
                z 7:00 powstaje z materiału wczorajszego (o świcie nic jeszcze
                nie wyszło); po południowym scrapingu ma czym się odświeżyć.

        Returns:
            DailySummary object lub None jeśli brak danych
        """
        # Domyślnie: dzisiejszy dzień (00:00 – teraz)
        # Jeśli mało artykułów z dziś (<10), rozszerzamy okno o wczoraj
        MIN_ARTICLES_THRESHOLD = 10

        now = datetime.utcnow()
        # tz-ok: `date_start` to KLUCZ DNIA w `daily_summaries` (i w ścieżce
        # `/api/summary/daily/{date}`), a nie okno pokazywane mieszkańcowi.
        # Przestawienie go na dobę lokalną zmieniłoby wartość istniejących
        # wierszy — osobna praca, patrz TODO w CLAUDE.md.
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if target_date is None:
            target_date = today_start
        else:
            target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)  # tz-ok: jak wyżej — klucz dnia

        date_start = target_date
        date_end = min(target_date + timedelta(days=1), now)  # nie sięgamy w przyszłość

        self.logger.info(f"Generating daily summary for {date_start.date()}")

        # Sprawdź czy podsumowanie już istnieje
        existing_result = await session.execute(
            select(DailySummary).where(DailySummary.date == date_start)
        )
        existing_summary = existing_result.scalar_one_or_none()
        if existing_summary and not force_refresh:
            self.logger.warning(f"Summary for {date_start.date()} already exists")
            return None

        # Lokalność mieszka w feed_policy — wspólnie z feedem. Wcześniej briefing
        # trzymał własną listę ID-ków, która po dodaniu Energi, KPP, Powiatu
        # i profilu gminy przestała je uznawać za lokalne.
        source_rows = (await session.execute(select(Source.id, Source.name))).all()
        self._source_names = {row.id: row.name for row in source_rows}

        # 1. Pobierz artykuły z dziś (tylko przetworzone i nadające się do publikacji)
        articles = await self._fetch_articles(session, date_start, date_end)

        # Fallback: jeśli mało artykułów z dziś, rozszerz okno o wczoraj
        extended = False
        if len(articles) < MIN_ARTICLES_THRESHOLD and date_start == today_start:
            yesterday_start = today_start - timedelta(days=1)
            self.logger.info(
                f"Only {len(articles)} articles for today – extending window to yesterday ({yesterday_start.date()})"
            )
            articles = await self._fetch_articles(session, yesterday_start, date_end)
            extended = True

        if not articles:
            self.logger.warning(f"No articles found for {date_start.date()}")
            return None

        # Ostrzeżenie meteo po terminie ważności nie jest ostrzeżeniem. Post
        # z 1.08 („dziś, w godzinach 15:00–01:00") wisiał w briefingu 2.08 o 11:30
        # jako obowiązujący alert burzowy, a prognoza obok dawała zero opadów.
        before_expiry = len(articles)
        articles = [
            article for article in articles
            if not weather_alert.expired(
                article.title,
                article.content,
                article.published_at,
                getattr(article, "event_until", None),
                now,
            )
        ]
        if len(articles) < before_expiry:
            self.logger.info(
                f"Expired weather alerts dropped: {before_expiry} → {len(articles)} articles"
            )

        # Ten sam materiał z dwóch źródeł idzie do AI raz — inaczej wraca
        # w briefingu jako dwie osobne „wiadomości"
        before_collapse = len(articles)
        articles = collapse_duplicates(articles, text_of=dedup_text)
        if len(articles) < before_collapse:
            self.logger.info(
                f"Duplicates collapsed: {before_collapse} → {len(articles)} articles"
            )

        if extended:
            self.logger.info(f"Extended window: {len(articles)} articles (today + yesterday)")

        self._mark_local_articles(articles)

        # 2. Pogrupuj artykuły po kategoriach
        articles_by_category = {}
        for article in articles:
            category = article.category or "Inne"
            if category not in articles_by_category:
                articles_by_category[category] = []
            articles_by_category[category].append(article)

        # 3. Wydarzenia: od początku DZISIEJSZEJ doby lokalnej przez 7 dni.
        #
        # Było `events_start = date_end`, czyli „od teraz" — a wpis całodniowy
        # stoi na lokalnej północy, więc o 7:00 był już przeszłością i wypadał
        # z briefingu w dniu, w którym się odbywał. Dobę liczy wspólna warstwa
        # (`time_span.local_day_bounds`), bo granica UTC to nie granica dnia.
        events_start, events_end = local_day_bounds(now=now, days=8)
        events_result = await session.execute(
            select(Event)
            .where(Event.event_date >= events_start)
            .where(Event.event_date < events_end)
            .where(*visible_event_conditions(Event))
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

        # 4b. Pogoda z tego samego rekordu, który zasila widget na stronie.
        # Airly mierzy pyły — temperatura jest u niego danymi pobocznymi i bywa
        # pusta: 2.08.2026 briefing napisał mieszkańcom „temperatura i wilgotność
        # nie były dostępne", podczas gdy widget obok pokazywał 18°C.
        weather_result = await session.execute(
            select(Weather)
            .where(Weather.location == WEATHER_LOCATION)
            .where(Weather.is_current == True)  # noqa: E712
            .order_by(Weather.fetched_at.desc())
            .limit(1)
        )
        weather = weather_result.scalar_one_or_none()
        if weather is None:
            self.logger.warning(
                f"No current weather for {WEATHER_LOCATION} — briefing bez sekcji pogodowej"
            )

        # 5. Przygotuj dane wejściowe dla AI
        recent_topics = await self._recent_headline_topics(session, date_start)
        top_article = self._select_top_article(
            articles_by_category, now, recent_topics
        )
        if top_article:
            locality = "LOKALNY" if self._is_local(top_article) else "REGIONALNY"
            self.logger.info(
                f"Top article (deterministic): [ID:{top_article.id}] [{locality}] "
                f"cat={top_article.category} '{top_article.title[:60]}'"
            )
            if self._repeats_recent_headline(top_article, recent_topics):
                self.logger.info(
                    "Headline repeats a recent briefing topic — brak innego kandydata"
                )
        input_data = self._prepare_input_for_ai(
            date_start,
            articles_by_category,
            events,
            air_quality,
            top_article=top_article,
            now=now,
            extended=extended,
            weather=weather,
        )

        try:
            # 6. Wywołaj AI agent dwukrotnie, wybierz lepszy wynik
            all_articles_map = {a.id: a for a in articles}
            run_deps = SummaryRun(
                required_headline_id=top_article.id if top_article else None,
                known_article_ids=frozenset(all_articles_map),
            )
            self.logger.info(f"Calling AI to generate summary (articles: {len(articles)}, events: {len(events)})")
            result_a = await self.agent.run(input_data, deps=run_deps)
            result_b = await self.agent.run(input_data, deps=run_deps)

            for res in (result_a, result_b):
                usage = res.usage()
                log_api_cost(
                    session,
                    model="gpt-4o",
                    tokens_input=usage.request_tokens or 0,
                    tokens_output=usage.response_tokens or 0,
                    endpoint="scheduler:daily_summary",
                )

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

            # 8. Zapisz do bazy — przy odświeżeniu nadpisujemy istniejący wpis
            # (`date` ma indeks unikalny, drugi wiersz na ten sam dzień nie powstanie)
            content = {
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
            }

            if existing_summary:
                existing_summary.headline = summary_data.headline
                existing_summary.content = content
                existing_summary.generated_at = datetime.utcnow()
                db_summary = existing_summary
            else:
                db_summary = DailySummary(
                    date=date_start,
                    headline=summary_data.headline,
                    content=content,
                    generated_at=datetime.utcnow()
                )

            session.add(db_summary)
            await session.commit()
            await session.refresh(db_summary)

            self.logger.info(
                f"✓ {'Refreshed' if existing_summary else 'Generated'} daily summary "
                f"for {date_start.date()} "
                f"(articles: {len(articles)}, categories: {len(articles_by_category)})"
            )

            return db_summary

        except Exception as e:
            self.logger.error(f"✗ Error generating summary: {e}")
            await session.rollback()
            raise

    # Ile godzin do przodu briefing patrzy na zdarzenia z terminem (wyłączenia prądu)
    EVENT_LOOKAHEAD_H = 36

    # Wypełniane na każdym przebiegu: nazwy źródeł z tabeli `sources`, a po
    # zebraniu materiału — ID wpisów, które feed_policy uznaje za lokalne
    _source_names: dict = {}
    _local_article_ids: set = set()

    async def _fetch_articles(
        self,
        session: AsyncSession,
        window_start: datetime,
        window_end: datetime,
    ) -> list:
        """
        Materiał do briefingu: to, co opublikowano w oknie, PLUS to, co dopiero
        nastąpi. Wyłączenie prądu ogłoszone trzy tygodnie temu, a zaplanowane na
        dziś na 10:00, nie mieściło się w żadnym oknie publikacji — briefing
        w dniu premiery nie wspomniał o nim ani słowem.
        """
        from sqlalchemy import func, or_

        lookahead_end = window_end + timedelta(hours=self.EVENT_LOOKAHEAD_H)

        result = await session.execute(
            select(Article)
            .where(Article.processed == True)  # noqa: E712
            .where(*publishable_conditions(Article))
            .where(
                or_(
                    (Article.published_at >= window_start)
                    & (Article.published_at < window_end),
                    (Article.event_at >= window_start)
                    & (Article.event_at < lookahead_end),
                )
            )
            .order_by(func.coalesce(Article.event_at, Article.published_at).desc())
        )
        return list(result.scalars().all())

    # Ile poranków wstecz pamięta nagłówek. Trzy, bo zapowiedź wyłączenia potrafi
    # wracać z przerwą: to samo wyłączenie otworzyło briefing 7, 10 i 11.08.2026.
    HEADLINE_MEMORY_DAYS = 3

    # Jak długo po ogłoszeniu awaria bez znanego terminu wciąż uchodzi za
    # trwającą — jedyny tytuł do POWTÓRZENIA wczorajszego nagłówka
    # (`_alert_still_running`). Krótsze niż `AWARIA_PIN_HOURS`, bo odpowiada
    # na trudniejsze pytanie: nie „czy pokazać", tylko „czy otworzyć tym dzień
    # DRUGI RAZ". Awaria wodociągowa ZGK z 2.09.2026 ogłoszona o 9:07 wciąż
    # otwierała briefing nazajutrz o 5:00, dwadzieścia godzin później.
    ONGOING_ALERT_H = 12

    async def _recent_headline_topics(
        self,
        session: AsyncSession,
        date_start: datetime,
        days: Optional[int] = None,
    ) -> list:
        """
        Tematy, którymi otwierały się ostatnie briefingi — jako sygnatury słów.

        Pamiętamy TEMAT, nie identyfikator. Energa zapisuje każde odświeżenie
        wyłączenia jako osobny wiersz, więc porównanie po ID nie widziało, że to
        wciąż ta sama zapowiedź: mieszkaniec dostał ten sam nagłówek 7, 10 i 11.08.2026
        pod trzema różnymi ID, a audyt policzył awarie jako 43% nagłówków tygodnia.

        Okno materiału sięga wczoraj (fallback przy chudym dniu), więc bez tej
        pamięci ten sam wpis potrafi otworzyć briefing dwa poranki z rzędu.
        """
        days = self.HEADLINE_MEMORY_DAYS if days is None else days
        result = await session.execute(
            select(DailySummary)
            .where(DailySummary.date < date_start)
            .where(DailySummary.date >= date_start - timedelta(days=days))
            .order_by(DailySummary.date.desc())
        )
        topics = []
        for previous in result.scalars().all():
            cited = (previous.content or {}).get("cited_articles")
            if not cited:
                continue
            signature = topic_signature(cited[0].get("title"))
            if signature:
                topics.append(signature)
        return topics

    @staticmethod
    def _repeats_recent_headline(article, recent_topics) -> bool:
        """Czy wpis mówi o tym samym, co któryś z ostatnich nagłówków."""
        if not recent_topics:
            return False
        signature = topic_signature(article.title)
        return any(same_topic(signature, seen) for seen in recent_topics)

    def _mark_local_articles(self, articles: list) -> None:
        """
        Które wpisy liczą się jako „nasze" — liczone raz na przebieg, bo
        `_is_local` pyta o to przy każdym sortowaniu, a lokalność jest PIERWSZĄ
        osią klucza nagłówka.

        Ocena z kategoryzacji rozstrzyga, gdy jest — ten sam próg
        (`MIN_ARTICLE_LOCALITY`) i ta sama kolejność zaufania co w rankingu
        feedu (`feed_policy.locality_factor`). 3.09.2026, już po naprawie
        samego feedu, briefing wybrał na nagłówek „Mieszkanki gminy Rybno
        wspierają akcję zdrowotną w LUBAWIE" (art. 5774, `locality=1`, powiat
        iławski), mając w materiale pobór krwi w Rybnie i mecz Delfina:
        `is_local_article` przepuszcza każdy wpis Syli bez patrzenia w treść,
        bo to źródło nie jest w `COUNTY_WIDE_SOURCES`. Ta sama dziura co
        w `locality_factor`, tyle że w osobnej kopii.

        Dla wpisów bez oceny — sprzed 21.08.2026 i czekających na
        kategoryzację — zostaje dawna ścieżka: źródło, potem nazwa w treści.

        ⚠️ Metoda istnieje po to, żeby reguła była w JEDNYM miejscu.
        `scripts/test_summary_headline` trzymał jej kopię pod komentarzem
        „to samo, co briefing robi po zebraniu materiału" — i po tej zmianie
        przestało być to samo, więc test sprawdzałby własną atrapę zamiast
        produkcji. Woła teraz tę metodę.
        """
        self._local_article_ids = {
            article.id
            for article in articles
            if (
                article.locality >= MIN_ARTICLE_LOCALITY
                if getattr(article, "locality", None) is not None
                else is_local_article(
                    self._source_names.get(article.source_id),
                    article.title,
                    article.content,
                )
            )
        }

    def _is_local(self, article) -> bool:
        return article.id in self._local_article_ids

    @staticmethod
    def _time_distance_h(article, now: datetime) -> float:
        """
        Ile godzin dzieli mieszkańca od momentu, którym artykuł konkuruje:
        terminu zdarzenia, a w jego braku — publikacji.

        Liczy się odległość, nie kierunek. Wyłączenie prądu jutro jest pilniejsze
        niż wyłączenie za dziewięć dni, tak samo jak wiadomość sprzed godziny
        bije wczorajszą.
        """
        stamp = getattr(article, "event_at", None) or article.published_at
        if stamp is None:
            return float("inf")
        return abs((stamp - now).total_seconds()) / 3600

    # Hierarchia ważności kategorii (niższy = ważniejszy).
    #
    # Numeracja dziesiątkami, żeby wstawienie kategorii nie wymagało ułamka
    # ani przestawienia całej tabeli. Kolejność względna nie zmieniła się od
    # 25.08.2026 — doszły dwie pozycje.
    #
    # ⚠️ „Urząd" był workiem: 133 widoczne wpisy na 30 dni, czyli 28% całej
    # treści, przy 84 w Kulturze i 72 w Awarii. Wchodziła tam kronika policyjna
    # (45 wpisów KPP — prompt kierował ją tu wprost), zbiórki, zguby i sprawy
    # parafii. Priorytet 30 znaczył więc, że „zatrzymano złodzieja roweru
    # w Działdowie" i „zgubiono okulary w Hartowcu" konkurują o nagłówek dnia
    # z sesją Rady Gminy. Stąd „Bezpieczeństwo" i „Społeczność".
    CATEGORY_PRIORITY = {
        "Awaria": 0,
        "Zdrowie": 10,
        "Transport": 20,
        "Urząd": 30,
        "Bezpieczeństwo": 40,
        "Biznes": 50,
        "Edukacja": 60,
        "Kultura": 70,
        "Społeczność": 80,
        "Sport": 90,
        "Rekreacja": 100,
        "Nieruchomości": 110,
    }

    # Kategoria spoza tabeli — za wszystkim, co potrafimy nazwać
    UNKNOWN_CATEGORY_PRIORITY = 120

    # Awaria, która nie jest sprawą najbliższych godzin. Zapowiedź zostaje
    # w briefingu, ale przestaje być kandydatem na nagłówek — o remis z równie
    # odległą kategorią rozstrzyga bliskość w czasie.
    DISTANT_ALERT_PRIORITY = 110

    # Zapowiedziane wyłączenie planowe: dziś obowiązuje, ale nie dzieje się jeszcze.
    # Stoi za sprawami, po których mieszkaniec ma coś ZROBIĆ (Zdrowie, Transport,
    # Urząd, Biznes, Edukacja), a przed rozrywką (Kultura, Sport, Rekreacja).
    #
    # 25.08.2026 briefing otworzył się pięciogodzinnym wyłączeniem na czterech
    # adresach przy ulicy Wyzwolenia, a konsultacje w sprawie skanalizowania
    # trzech wsi — tego samego dnia o 19:00 — trafiły do bloku „Edukacja".
    # Czwarty raz w sześć dni: Energa wypuszcza wpis dotyczący gminy Rybno
    # praktycznie codziennie (7 wpisów na 7 dni), a priorytet 0 znaczył, że
    # nic w gminie nie ma jak wygrać z zapowiedzią wyłączenia.
    #
    # Awaria NIEPLANOWANA i wyłączenie TRWAJĄCE zostają na priorytecie 0 —
    # „nie mam prądu teraz" jest wiadomością dnia, „wyłączą mi prąd o 9:30"
    # jest informacją użytkową, którą i tak niesie karta alertu i push.
    # Miejsce jest MIĘDZY dwiema kategoriami, nie na miejscu którejś z nich:
    # remis z Edukacją oddawałby nagłówek wyłączeniu (bliżej w czasie),
    # remis z Kulturą — koncertowi sprzed dwóch godzin.
    PLANNED_OUTAGE_PRIORITY = 65

    def _headline_priority(self, category: str, article, now: datetime) -> int:
        """
        Waga kategorii przy wyborze nagłówka.

        Awaria stoi na szczycie tylko dopóki jest sprawą najbliższych godzin —
        próg jest ten sam, na którym feed przypina ją nad wiadomościami. Bez tego
        zapowiedź żyje w materiale tygodniami i wygrywa nagłówek każdego dnia:
        28 i 29.07.2026 briefing otworzył się wyłączeniem prądu zaplanowanym
        dopiero na 7 sierpnia, choć w gminie działo się w tym czasie co innego.
        """
        priority = self.CATEGORY_PRIORITY.get(category, self.UNKNOWN_CATEGORY_PRIORITY)
        if priority != self.CATEGORY_PRIORITY["Awaria"]:
            return priority

        is_now = is_pinned_alert(
            category,
            article.published_at,
            article.scraped_at,
            now,
            article.event_at,
            article.event_until,
            article.title,
            article.content,
            article.locality,
        )
        if not is_now:
            return self.DISTANT_ALERT_PRIORITY

        # Kanał Energi rozstrzyga, czy prąd znika sam, czy zgodnie z zapowiedzią.
        # Zapowiedziane wyłączenie odzyskuje priorytet 0 dopiero, gdy TRWA:
        # wtedy „nie ma prądu" przestaje być zapowiedzią i staje się stanem gminy.
        if energa.is_planned(article.title) and not self._is_ongoing(article, now):
            return self.PLANNED_OUTAGE_PRIORITY

        return priority

    @staticmethod
    def _is_ongoing(article, now: datetime) -> bool:
        """Czy zdarzenie właśnie trwa — znany termin obejmujący tę chwilę."""
        start, end = article.event_at, article.event_until
        return bool(start and end and start <= now <= end)

    @classmethod
    def _alert_still_running(cls, article, now: datetime) -> bool:
        """
        Czy mamy DOWÓD, że awaria trwa nadal — jedyny tytuł do powtórzenia
        wczorajszego nagłówka.

        Dwa dowody, w kolejności pewności: znany termin obejmujący tę chwilę
        (`event_until` z kategoryzacji albo z `alert_policy.span_from_text`)
        oraz świeżość samego ogłoszenia. Drugi jest domysłem i dlatego jest
        krótki: komunikat ZGK „mogą wystąpić spadki ciśnienia" opisuje
        godziny prac naprawczych, nie stan gminy na resztę doby.

        ⚠️ Brak dowodu NIE znaczy „awaria się skończyła" — znaczy tyle, że
        nie wolno na niej drugi raz otwierać dnia. Wpis zostaje w materiale
        i w feedzie; traci wyłącznie zwolnienie z reguły powtórki.
        """
        if cls._is_ongoing(article, now):
            return True

        reference = article.published_at or article.scraped_at
        if reference is None:
            return False
        return (now - reference).total_seconds() / 3600 <= cls.ONGOING_ALERT_H

    def _select_top_article(
        self,
        articles_by_category: dict,
        now: datetime,
        recent_topics: Optional[list] = None,
    ):
        """Deterministycznie wybierz artykuł do nagłówka.

        Kolejność rozstrzygania:
        1. lokalny przed regionalnym — regionalny wygrywa tylko przy braku lokalnych,
        2. zdarzenie po terminie na końcu swojej grupy (`_event_is_over`),
        3. temat ostatnich briefingów na końcu swojej grupy,
        4. ważność kategorii (`_headline_priority`),
        5. bliskość w czasie.

        Punkt 2 istnieje, bo punkt 5 liczy odległość BEZ kierunku — co jest
        słuszne przy zapowiedziach („wyłączenie jutro bije wyłączenie za
        dziewięć dni"), ale po terminie obraca się przeciw mieszkańcowi:
        posiedzenie sprzed półtorej godziny było 26.08.2026 najbliższym
        punktem w całym materiale i wygrało nagłówek z sesją Rady nazajutrz.
        Bramka „czy to jeszcze sprawa najbliższych godzin" istniała dotąd
        wyłącznie dla kategorii Awaria (`_headline_priority`) — reszta
        kategorii nie miała żadnej.

        Punkt 2 porównuje TEMAT (`same_topic`), nie identyfikator: kolejne
        odświeżenie tego samego wyłączenia prądu ma nowe ID i wracało jako
        nagłówek mimo pamięci (7, 10 i 11.08.2026).

        Punkt 2 nie wyklucza artykułu — przepuszcza przed nim każdego innego
        kandydata o tej samej lokalności. Gdy dzień jest chudy i alternatywy nie
        ma, ten sam wpis otworzy briefing ponownie; to wciąż lepsze niż zejście
        na nagłówek regionalny. Wyjątkiem jest awaria, która wciąż trwa: przerwa
        w dostawie wody drugiego dnia jest nadal najważniejszą rzeczą w gminie
        i nie ustępuje miejsca wiadomości tylko dlatego, że była wczoraj.

        ⚠️ Zwolnienie z punktu 2 przysługuje wyłącznie priorytetowi 0, czyli
        awarii nieplanowanej albo trwającej. Zapowiedziane wyłączenie planowe
        ma `PLANNED_OUTAGE_PRIORITY` i podlega regule powtórki jak każdy inny
        temat — a podlega jej skutecznie, bo tytuł źródłowy Energi jest zawsze
        ten sam („Wyłączenie planowe - Region Mława - Rybno gmina wiejska"),
        więc dwie zapowiedzi pod rząd `same_topic` rozpoznaje jako jedną sprawę.

        ⚠️ Zwolnienie wymaga DOWODU trwania (`_alert_still_running`), a nie
        samej przynależności do priorytetu 0. Zdanie wyżej mówi „awaria, która
        WCIĄŻ TRWA" — do 3.09.2026 kod tego nie sprawdzał i zwalniał każdą
        awarię, którą `is_pinned_alert` uznawał za sprawę teraz, czyli również
        taką bez godzin przez pełne `AWARIA_PIN_HOURS` od ogłoszenia. Skutek:
        briefingi 2 i 3.09 otworzyły się TĄ SAMĄ awarią wodociągową ZGK
        (art. 5755, ogłoszoną 2.09 o 9:07 i nigdy nie odwołaną — ZGK nie
        publikuje „już działa"), a 5 z 6 kolejnych briefingów zaczynało się
        słowem „AWARIA". Wyjątek pomyślany jako rzadki stał się regułą.

        Dowodem trwania jest znany termin obejmujący tę chwilę albo świeżość
        samego ogłoszenia (`ONGOING_ALERT_H`). Awaria bez terminu, ogłoszona
        wczoraj i powtarzająca wczorajszy nagłówek, schodzi na koniec swojej
        grupy — nie znika, więc przy chudym dniu wciąż może wygrać.
        """
        best = None
        best_key = (2, 2, 2, 999, float("inf"))

        for category, arts in articles_by_category.items():
            for article in arts:
                priority = self._headline_priority(category, article, now)
                # Awaria, która JEST sprawą teraz, jest zwolniona z degradacji
                # „po terminie": „nie ma prądu" opisuje stan gminy, a nie
                # zaproszenie, na które można było zdążyć.
                alert_now = priority == self.CATEGORY_PRIORITY["Awaria"]
                over = not alert_now and _event_is_over(article, now)
                # Ze zwolnienia z reguły POWTÓRKI korzysta wyłącznie awaria
                # z dowodem trwania — inaczej ta sama awaria bez godzin
                # otwierałaby briefing tyle dni z rzędu, ile trwa jej pin.
                repeats = (
                    not (alert_now and self._alert_still_running(article, now))
                    and self._repeats_recent_headline(article, recent_topics)
                )
                key = (
                    0 if self._is_local(article) else 1,
                    1 if over else 0,
                    1 if repeats else 0,
                    priority,
                    self._time_distance_h(article, now),
                )
                if key < best_key:
                    best_key = key
                    best = article

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
        return self._is_local(headline_art)

    def _get_locality_label(self, article) -> str:
        """Zwróć etykietę [LOKALNY] lub [REGIONALNY] dla artykułu"""
        if self._is_local(article):
            return "[LOKALNY]"
        return "[REGIONALNY]"

    @staticmethod
    def _weather_lines(weather: Weather, now: datetime) -> list[str]:
        """
        Sekcja pogodowa: stan teraz + prognoza na najbliższe godziny.

        Bierze się z rekordu `weather` — tego samego, który `/api/weather` podaje
        widgetowi. Do 2.08.2026 briefing nie miał żadnej prognozy i nie potrafił
        rozpoznać, że wczorajsze ostrzeżenie przed burzami nie ma pokrycia
        w dzisiejszym dniu: model widział alert i tylko alert.
        """
        measured = _local(weather.fetched_at) if weather.fetched_at else None
        lines = [
            "\n" + "=" * 80,
            "POGODA W RYBNIE — TO SAMO ŹRÓDŁO, CO WIDGET NA STRONIE"
            + (f" (pomiar {measured:%H:%M})" if measured else ""),
            "=" * 80,
            "",
            f"Teraz: {weather.temperature:.0f}°C (odczuwalna {weather.feels_like:.0f}°C), "
            f"{weather.description}, wiatr {weather.wind_speed:.0f} m/s",
        ]

        slots = ((weather.forecast or {}).get("hourly") or [])[:FORECAST_SLOTS]
        if slots:
            lines.append("Prognoza (co 3 h; „opady” = prawdopodobieństwo opadów):")
            for slot in slots:
                stamp = slot.get("dt")
                when = (
                    datetime.fromtimestamp(stamp, ZoneInfo("UTC")).astimezone(LOCAL_TZ)
                    if stamp else None
                )
                temp = slot.get("temp")
                pop = slot.get("pop")
                rain = slot.get("rain_3h")
                parts = [
                    f"  {when:%H:%M}" if when else "  ??:??",
                    f"{temp:.0f}°C" if temp is not None else "—",
                    str(slot.get("description") or ""),
                ]
                if pop is not None:
                    parts.append(f"opady {round(pop * 100)}%")
                if rain:
                    parts.append(f"{rain} mm")
                lines.append("  ".join(p for p in parts if p))

        lines += [
            "",
            "⚠️ TA SEKCJA ROZSTRZYGA O POGODZIE. Artykuł zapowiadający burzę, ulewę",
            "   czy alert pogodowy opisuje stan z chwili SWOJEJ publikacji. Jeśli",
            "   prognoza powyżej nie potwierdza zagrożenia (znikoma szansa opadów) —",
            "   NIE ostrzegaj przed nim i nie powtarzaj alertu jako obowiązującego.",
            "   Liczb z tej sekcji NIE przepisuj do `highlights` (obok stoi widget",
            "   z pomiarem na żywo) — opisz pogodę słowami.",
        ]
        return lines

    def _prepare_input_for_ai(
        self,
        date: datetime,
        articles_by_category: dict,
        events: list,
        air_quality: Optional[AirQuality],
        top_article=None,
        now: Optional[datetime] = None,
        extended: bool = False,
        weather: Optional[Weather] = None,
    ) -> str:
        """Przygotuj sformatowany tekst dla AI"""
        now = now or datetime.utcnow()

        local_count = sum(
            1 for arts in articles_by_category.values()
            for a in arts if self._is_local(a)
        )
        total_count = sum(len(arts) for arts in articles_by_category.values())

        lines = []

        # Sekcja WYMAGANY ARTYKUŁ NAGŁÓWKA — kod decyduje deterministycznie
        if top_article:
            locality = "LOKALNY" if self._is_local(top_article) else "REGIONALNY"
            lines += [
                "=" * 80,
                f"⚡ WYMAGANY ARTYKUŁ NAGŁÓWKA [ID:{top_article.id}]:",
                f"   Tytuł: {_article_title(top_article)}",
                f"   Kategoria: {top_article.category} | Źródło: [{locality}]",
            ]
            body = _article_body(top_article)
            if body:
                lines.append(f"   Treść: {body}")
            lines += [
                f"   ZASADA: Headline MUSI być o tym artykule. cited_article_ids[0] MUSI = {top_article.id}.",
                "=" * 80,
                "",
            ]

        lines += [
            f"Data: {date.strftime('%Y-%m-%d')}, teraz jest godzina {_local(now):%H:%M}",
            f"Liczba artykułów: {total_count} (lokalnych: {local_count}, regionalnych: {total_count - local_count})",
            "",
            "=" * 80,
            "ARTYKUŁY PO KATEGORIACH:",
            "  [LOKALNY]   = dotyczy bezpośrednio gminy Rybno (Rybno i sołectwa) oraz najbliższych okolic",
            "  [REGIONALNY] = dotyczy sąsiednich gmin, powiatu, Warmii i Mazur lub obszarów dalszych",
            "",
            # Bez dat przy artykułach model przepisywał „dziś o 17:00" z wpisu sprzed
            # doby i briefing zapraszał na wczorajszy koncert.
            '  Przy każdym artykule stoi CZAS: [wczoraj 22:18], [dziś 08:00],',
            '  a przy zdarzeniach z terminem — [ZDARZENIE …].',
            '  ⚠️ Słowa „dziś", „jutro", „już za chwilę" w TREŚCI artykułu odnoszą się',
            '  do dnia jego publikacji, nie do dzisiaj. Artykuł [wczoraj] piszący',
            '  „dziś o 17:00" opisuje wydarzenie, które JUŻ SIĘ ODBYŁO — nie zapraszaj na nie.',
            "=" * 80,
            ""
        ]
        if extended:
            lines += [
                "UWAGA: dzisiejszy materiał był zbyt skąpy, więc zestaw obejmuje także",
                "artykuły z wczoraj. Sprawdzaj czas przy każdym z nich.",
                "",
            ]

        # Dodaj artykuły pogrupowane po kategoriach
        # W każdej kategorii: najpierw [LOKALNY], potem [REGIONALNY],
        # a w obu grupach — najbliżej dzisiejszego dnia (lista bywa ucinana do 10)
        for category, arts in sorted(articles_by_category.items()):
            sorted_arts = sorted(
                arts,
                key=lambda a: (0 if self._is_local(a) else 1, self._time_distance_h(a, now))
            )
            lines.append(f"\n## {category.upper()} ({len(sorted_arts)} artykułów):\n")
            for i, article in enumerate(sorted_arts[:10], 1):  # max 10 per kategoria
                label = self._get_locality_label(article)
                when = _time_label(article, now)
                lines.append(f"{i}. {label} {when} [ID:{article.id}] {_article_title(article)}")
                body = _article_body(article)
                if body:
                    lines.append(f"   → {body}")
                # Lokalizację pokazuj tylko dla artykułów LOKALNYCH - dla regionalnych
                # może być halucynowana przez AI kategoryzacji
                if article.location_mentioned and self._is_local(article):
                    lines.append(f"   📍 {', '.join(article.location_mentioned)}")
                lines.append("")

        # Dodaj wydarzenia
        if events:
            lines.append("\n" + "=" * 80)
            lines.append("NADCHODZĄCE WYDARZENIA:")
            lines.append("=" * 80 + "\n")
            for event in events:
                # Etykieta, nie surowa data. 4.09.2026 stało tu
                # `event.event_date.strftime("%Y-%m-%d")` — bez konwersji, więc
                # bieg z 5.09 (w bazie 4.09 22:00 UTC = lokalna północ) wszedł
                # do promptu jako „2026-09-04" i briefing napisał „Dziś odbędzie
                # się VI Leśny Nocny Bieg". Model przepisał wiernie to, co dostał;
                # ten sam wpis w bloku SPORT miał obok poprawne „[ZDARZENIE jutro]".
                when = when_label(event.event_date, event.end_date, now)
                lines.append(f"• {event.title}")
                lines.append(f"  Kiedy: {when}")
                if event.location:
                    lines.append(f"  Miejsce: {event.location}")
                lines.append("")

        # Pogoda — ten sam rekord, który zasila widget na stronie
        if weather:
            lines += self._weather_lines(weather, now)

        # Dodaj dane air quality (czujnik w Rybnie).
        # Wyłącznie powietrze: temperatura, wilgotność i ciśnienie stoją wyżej,
        # w sekcji pogodowej. Podane dwa razy z dwóch źródeł dawały dwie różne
        # wartości w jednym briefingu — a czujnik Airly potrafi ich nie mieć wcale.
        if air_quality:
            lines.append("\n" + "=" * 80)
            lines.append("JAKOŚĆ POWIETRZA (czujnik Airly w Rybnie):")
            lines.append("=" * 80 + "\n")
            lines.append(f"Lokalizacja: {air_quality.location}")
            lines.append(f"Jakość powietrza: {air_quality.caqi_level} (CAQI: {air_quality.caqi})")
            lines.append(f"Pyły zawieszone:")
            lines.append(f"  - PM2.5: {air_quality.pm25} µg/m³")
            lines.append(f"  - PM10: {air_quality.pm10} µg/m³")
            # Godzina pomiaru wchodzi do air_quality_summary — dzięki niej liczba
            # nie kłóci się z widgetem live stojącym obok briefingu
            measured_at = (
                f"{to_local(air_quality.fetched_at):%H:%M}"
                if air_quality.fetched_at else "brak danych"
            )
            lines.append(f"\nGodzina pomiaru: {measured_at}")

        return "\n".join(lines)
