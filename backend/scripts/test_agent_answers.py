"""
Walidator odpowiedzi agentów — pytanie mieszkańca kontra stan bazy.

Po co to istnieje. 7.08.2026 o 8:21 mieszkaniec zapytał „czy dziś nie będzie
prądu". Wyłączenie zaczynało się o 9:00, stało w bazie z terminem i w RAG-u,
a Strażnik odpowiedział, że nie ma żadnych zgłoszeń. Żaden test tego nie łapał:
polityka alertów ma swój test, briefing swój, a odpowiedź agenta — czyli to,
co mieszkaniec faktycznie czyta — nie miała żadnego.

Dlaczego oczekiwania liczy WYROCZNIA, a nie sztywna lista par pytanie–odpowiedź.
„Czy dziś nie będzie prądu" jest poprawnie odpowiedziane albo błędnie WYŁĄCZNIE
w odniesieniu do tego, co w bazie stoi na dziś. Wpisana na sztywno odpowiedź
byłaby nieaktualna nazajutrz i test zacząłby kłamać w drugą stronę. Każdy
przypadek ma więc wyrocznię: własne zapytanie do bazy, z którego wynika,
co w odpowiedzi MUSI paść, a co paść NIE MOŻE.

Wyrocznia NIE korzysta z kodu agenta — pyta bazę po swojemu. Gdyby dzieliła
zapytanie z agentem, oba byłyby błędne równocześnie i test świeciłby na zielono
dokładnie w sytuacji z 7.08.

Dwa etapy, bo to dwie różne awarie:
  1. KONTEKST — czy fakt w ogóle dotarł do materiału, który agent dostaje
     (błąd zapytania/retrievalu — przypadek z 7.08);
  2. ODPOWIEDŹ — czy model, mając fakt, powiedział go mieszkańcowi
     (błąd promptu — model widzi wyłączenie i mówi „brak zgłoszeń").
Bez rozdzielenia obu każdy czerwony wynik wymagałby śledztwa od zera.

Użycie:
    cd backend && python -m scripts.test_agent_answers             # pełny przebieg
    cd backend && python -m scripts.test_agent_answers --dry       # bez modelu: wyrocznie + kontekst
    cd backend && python -m scripts.test_agent_answers --no-route  # bez sprawdzania routingu (taniej)
    cd backend && python -m scripts.test_agent_answers --only prad-dzis,solectwa
    cd backend && python -m scripts.test_agent_answers --list

Koszt pełnego przebiegu: gpt-4o-mini × (routing + odpowiedź) na przypadek —
grosze. Baza: ta, na którą wskazuje DATABASE_URL (na prodzie: wewnątrz kontenera).
"""
import argparse
import asyncio
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Awaitable, Callable, Optional
from zoneinfo import ZoneInfo

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from src.database.connection import async_session  # noqa: E402
from src.services import feed_policy  # noqa: E402
from src.services.alert_policy import _flat as flat  # noqa: E402  (jedyny normalizator w projekcie)
from src.services.alert_policy import incident_of, places_in  # noqa: E402

LOCAL_TZ = ZoneInfo("Europe/Warsaw")
UTC = ZoneInfo("UTC")

MONTHS_PL = [
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "wrzesnia", "pazdziernika", "listopada", "grudnia",
]

# Zdania, którymi model wypiera się wiedzy. To one były treścią awarii z 7.08,
# więc mają własną nazwę i wracają w kilku przypadkach.
DENIAL = (
    r"(nie ma|brak|nie odnotowano|nie wystepuj|nie zarejestrowano|nie planuje)"
    r"[^.]{0,70}(awari|wylacze|przerw|zglosze|utrudnie|ostrzez)"
)
# „Nie mam aktualnych artykułów, ale ogólnie w gminie…" to ta sama porażka co
# „nie posiadam danych", tylko lepiej ubrana — wzorzec musi łapać oba.
NO_KNOWLEDGE = (
    r"(nie posiadam|nie dysponuje|skontaktuj sie z urzedem"
    r"|nie mam[^.]{0,30}(dan|informacj|artykul|wiadomosc|dostepu)"
    r"|brak[^.]{0,20}(informacj|artykul|danych))"
)

# Chwila, w której padła błędna odpowiedź: 7.08.2026, 8:21 czasu lokalnego.
# Baza trzyma naiwny UTC, więc 6:21. Wyłączenie startowało 40 minut później.
INCIDENT_AT = datetime(2026, 8, 7, 6, 21)


# --- pomocnicze: budowanie wzorców z faktów -----------------------------------

def _hour_re(moment: datetime) -> str:
    """Godzina lokalna w zapisie, jakiego użyje model: 9:00, 09:00, „od 9”."""
    local = moment.replace(tzinfo=UTC).astimezone(LOCAL_TZ)
    h = local.hour
    return rf"\b0?{h}[:.]{local.minute:02d}\b|\bod 0?{h}\b|\bo 0?{h}\b"


def _date_re(day: date) -> str:
    """Data w zapisie „12.08", „12 sierpnia" albo słownie, gdy to dziś/jutro."""
    today = datetime.now(LOCAL_TZ).date()
    parts = [
        rf"\b{day.day}\.0?{day.month}\b",
        rf"\b{day.day} {MONTHS_PL[day.month - 1]}\b",
    ]
    if day == today:
        parts.append(r"\bdzis\b|\bdzisiaj\b")
    elif day == today + timedelta(days=1):
        parts.append(r"\bjutro\b")
    return "|".join(parts)


def _places_re(places: tuple[str, ...]) -> str:
    """Dowolna z nazw, odporna na odmianę („w Szczuplinach")."""
    stems = {flat(p)[: max(len(flat(p)) - 2, 4)] for p in places if p}
    return "|".join(re.escape(s) for s in sorted(stems)) or r"rybn"


# --- kontrakt przypadku -------------------------------------------------------

@dataclass
class Expect:
    """Czego wymaga stan bazy — wyliczone, nie wpisane."""
    fact: str = ""                                     # co jest prawdą wg bazy (do wydruku)
    must: list[tuple[str, str]] = field(default_factory=list)      # (opis, regex) — wszystkie
    must_any: list[tuple[str, str]] = field(default_factory=list)  # (opis, regex) — co najmniej jedna
    must_not: list[tuple[str, str]] = field(default_factory=list)
    # Czego szukamy w MATERIALE agenta. None = to samo co `must` (typowy przypadek).
    # Pusta lista = nie sprawdzamy kontekstu, bo fakt nie pochodzi z materiału
    # (karta gminy, wiedza ogólna) albo bazowa prawda brzmi „nic tam nie ma".
    must_in_context: Optional[list[tuple[str, str]]] = None
    min_len: int = 0
    skip: Optional[str] = None                         # brak danych, żeby cokolwiek orzec


@dataclass
class Case:
    id: str
    question: str
    agent: str                                          # kto MA odpowiedzieć
    oracle: Callable[[AsyncSession], Awaitable[Expect]]
    probe: Optional[Callable[[AsyncSession, str], Awaitable[str]]] = None
    why: str = ""                                       # co ten przypadek pilnuje
    context_only: bool = False                          # bez modelu (odtworzenie chwili z przeszłości)


# --- materiał, który agent zobaczy (etap 1) -----------------------------------

async def _straznik_context(session: AsyncSession, question: str) -> str:
    from src.ai.agents.straznik import StraznikAgent

    agent = StraznikAgent()
    return agent._build_context(
        await agent._fetch_recent_reports(session),
        await agent._fetch_alert_articles(session),
        await agent._fetch_recent_bip(session),
    )


async def _straznik_context_at_incident(session: AsyncSession, question: str) -> str:
    """Materiał Strażnika widziany z chwili, w której odpowiedział błędnie."""
    from src.ai.agents.straznik import StraznikAgent

    agent = StraznikAgent()
    return agent._build_context(
        [], await agent._fetch_alert_articles(session, now=INCIDENT_AT), []
    )


def _rag_probe(agent_name: str) -> Callable[[AsyncSession, str], Awaitable[str]]:
    """
    Materiał z RAG dla agentów, które go używają (Redaktor, Urzędnik).
    Powtarza retrieval agenta 1:1 — łącznie z synonimami, bo to właśnie tam
    „eternit" gubił dokument o azbeście. Bez reranku: sprawdzamy, czy fakt
    W OGÓLE jest w zasięgu wyszukiwarki.
    """

    async def probe(session: AsyncSession, question: str) -> str:
        from src.ai.embeddings import embedding_service
        from src.services.search_synonyms import expand_query

        agent = _agent_instances()[agent_name]
        docs = await embedding_service.hybrid_search(
            session=session,
            query=expand_query(question),
            top_k=max(agent.rag_top_k * 2, 12),
            source_types=agent.source_types or None,
            similarity_threshold=agent.rag_threshold,
            semantic_weight=agent.rag_semantic_weight,
            recency_boost=agent.rag_recency_boost,
        )
        return "\n---\n".join(d["chunk_text"] for d in docs)

    return probe


# --- wyrocznie ----------------------------------------------------------------

def _day_bounds_utc(offset_days: int = 0) -> tuple[datetime, datetime]:
    """Granice doby LOKALNEJ w naiwnym UTC (baza trzyma UTC bez strefy)."""
    local_now = datetime.now(LOCAL_TZ) + timedelta(days=offset_days)
    start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    to_utc = lambda d: d.astimezone(UTC).replace(tzinfo=None)  # noqa: E731
    return to_utc(start), to_utc(end)


async def _events_between(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    kind: Optional[str] = None,
) -> list[dict]:
    """
    Zdarzenia z terminem w oknie — zapytanie NIEZALEŻNE od kodu agenta.
    `kind` filtruje po rodzaju z `alert_policy` (prad/woda/pozar/wypadek/gaz).
    """
    result = await session.execute(
        text("""
            SELECT a.id, a.title, a.display_title, a.content, a.summary,
                   a.event_at, a.event_until, s.name AS source_name
            FROM articles a
            JOIN sources s ON a.source_id = s.id
            WHERE a.event_at >= :start AND a.event_at < :end
              AND a.is_filler = false AND a.is_promotional = false
            ORDER BY a.event_at
        """),
        {"start": start, "end": end},
    )
    rows = [dict(r._mapping) for r in result]

    out = []
    for row in rows:
        incident = incident_of(row["title"], row["content"])
        if kind and (not incident or incident[0] != kind):
            continue
        row["kind"] = incident[0] if incident else None
        row["places"] = places_in(row["title"], row["content"])
        row["is_local"] = feed_policy.is_local_article(
            row["source_name"], row["title"], row["content"]
        )
        out.append(row)
    return out


async def oracle_incident_replay(session: AsyncSession) -> Expect:
    """
    Odtworzenie 7.08.2026, 8:21 — jedyny przypadek z datą wpisaną na sztywno,
    bo dotyczy konkretnego zdarzenia, które już się wydarzyło. Dopóki wpis 5060
    jest w bazie, ten test odpowiada na pytanie „czy tamten błąd wróci".
    """
    result = await session.execute(
        text("""
            SELECT id, title, content, event_at
            FROM articles
            WHERE event_at >= :start AND event_at < :end
              AND lower(title) LIKE '%wy%cze%'
            ORDER BY event_at
            LIMIT 1
        """),
        {"start": INCIDENT_AT, "end": INCIDENT_AT + timedelta(days=1)},
    )
    row = result.first()
    if not row:
        return Expect(skip="wpis o wyłączeniu z 7.08.2026 nie istnieje w tej bazie")

    row = dict(row._mapping)
    return Expect(
        fact=f"art. {row['id']}: wyłączenie {row['event_at']:%d.%m %H:%M} UTC",
        must=[
            ("godzina wyłączenia", _hour_re(row["event_at"])),
            ("miejscowość", _places_re(places_in(row["title"], row["content"]))),
        ],
    )


async def oracle_power_today(session: AsyncSession) -> Expect:
    start, end = _day_bounds_utc()
    events = [e for e in await _events_between(session, start, end, kind="prad") if e["is_local"]]

    if not events:
        # „Dziś nic" nie znaczy „nic" — jeśli wyłączenie jest zapowiedziane na
        # pojutrze, odpowiedź z terminem jest lepsza od samego zaprzeczenia
        # i obie muszą przejść. Ocenianie tylko po zaprzeczeniu karałoby
        # agenta za odpowiedź bardziej użyteczną.
        upcoming = [
            e for e in await _events_between(
                session, datetime.utcnow(), datetime.utcnow() + timedelta(hours=72), kind="prad"
            )
            if e["is_local"]
        ]
        if upcoming:
            day = upcoming[0]["event_at"].replace(tzinfo=UTC).astimezone(LOCAL_TZ).date()
            return Expect(
                fact=f"dziś nic, najbliższe wyłączenie {day:%d.%m} (art. {upcoming[0]['id']})",
                must_any=[
                    ("zaprzeczenie na dziś", DENIAL),
                    ("termin najbliższego wyłączenia", _date_re(day)),
                ],
                must_in_context=[],
            )
        return Expect(
            fact="na dziś nie ma w bazie żadnego wyłączenia prądu w gminie Rybno",
            must=[("informacja o braku wyłączeń", DENIAL)],
            must_in_context=[],
        )

    first = events[0]
    return Expect(
        fact=(
            f"wyłączenie prądu dziś {first['event_at']:%H:%M} UTC, "
            f"miejscowości: {', '.join(first['places']) or '?'} (art. {first['id']})"
        ),
        must=[
            ("godzina rozpoczęcia", _hour_re(first["event_at"])),
            ("miejscowość", _places_re(first["places"])),
        ],
        must_not=[("wyparcie się wiedzy o awarii", DENIAL)],
    )


async def oracle_power_upcoming(session: AsyncSession) -> Expect:
    start = datetime.utcnow()
    events = [
        e for e in await _events_between(session, start, start + timedelta(hours=72), kind="prad")
        if e["is_local"]
    ]

    if not events:
        return Expect(
            fact="brak zapowiedzianych wyłączeń prądu w gminie Rybno na najbliższe 72 h",
            must=[("informacja o braku wyłączeń", DENIAL)],
            must_in_context=[],
        )

    nearest = events[0]
    local_day = nearest["event_at"].replace(tzinfo=UTC).astimezone(LOCAL_TZ).date()
    return Expect(
        fact=f"najbliższe wyłączenie {local_day:%d.%m} {nearest['event_at']:%H:%M} UTC (art. {nearest['id']})",
        must=[
            ("termin", _date_re(local_day)),
            ("godzina", _hour_re(nearest["event_at"])),
        ],
        must_not=[("wyparcie się wiedzy o wyłączeniu", DENIAL)],
    )


async def oracle_any_alert(session: AsyncSession) -> Expect:
    """Ogólne „czy coś się dzieje" — zdarzenie z terminem ALBO świeża awaria."""
    now = datetime.utcnow()
    events = [
        e for e in await _events_between(session, now - timedelta(hours=6), now + timedelta(hours=72))
        if e["is_local"] and e["kind"]
    ]

    result = await session.execute(
        text("""
            SELECT a.id, a.title, a.content, s.name AS source_name
            FROM articles a
            JOIN sources s ON a.source_id = s.id
            WHERE a.category = 'Awaria'
              AND a.published_at >= now() - INTERVAL '3 days'
              AND a.event_at IS NULL
              AND a.is_filler = false AND a.is_promotional = false
        """)
    )
    fresh = [
        dict(r._mapping) for r in result
        if feed_policy.is_local_article(
            dict(r._mapping)["source_name"], dict(r._mapping)["title"], dict(r._mapping)["content"]
        )
    ]

    if not events and not fresh:
        return Expect(
            fact="brak lokalnych awarii i zapowiedzianych zdarzeń",
            must=[("informacja o braku awarii", DENIAL)],
            must_in_context=[],
        )

    if events:
        item = events[0]
        label = incident_of(item["title"], item["content"])
        return Expect(
            fact=f"aktywne/zapowiedziane: {label[1] if label else '?'} (art. {item['id']})",
            must=[("miejscowość zdarzenia", _places_re(item["places"]))],
            must_not=[("wyparcie się wiedzy o zdarzeniu", DENIAL)],
        )

    item = fresh[0]
    return Expect(
        fact=f"świeża awaria: {item['title'][:60]} (art. {item['id']})",
        must=[("miejscowość zdarzenia", _places_re(places_in(item["title"], item["content"])))],
        must_not=[("wyparcie się wiedzy o awarii", DENIAL)],
    )


async def oracle_waste_rybno(session: AsyncSession) -> Expect:
    result = await session.execute(
        text("""
            SELECT collection_date, waste_type
            FROM waste_schedule
            WHERE town = 'Rybno R1' AND collection_date >= CURRENT_DATE
            ORDER BY collection_date
            LIMIT 1
        """)
    )
    row = result.first()
    if not row:
        return Expect(skip="brak przyszłych terminów w waste_schedule dla Rybno R1")

    when, waste_type = row[0], row[1]
    return Expect(
        fact=f"najbliższy wywóz w Rybnie: {when:%d.%m.%Y} ({waste_type})",
        must=[("data odbioru", _date_re(when))],
        must_not=[("wyparcie się wiedzy", NO_KNOWLEDGE)],
    )


async def oracle_pharmacy_today(session: AsyncSession) -> Expect:
    today = date.today()
    result = await session.execute(
        text("""
            SELECT pharmacy_name, address
            FROM pharmacy_duties
            WHERE valid_year = :year
              AND (duty_type = 'weekday'
                   OR (duty_type = 'weekend' AND :dow IN (5, 6))
                   OR day_of_week = :dow)
            LIMIT 3
        """),
        {"year": today.year, "dow": today.weekday()},
    )
    rows = [dict(r._mapping) for r in result]
    if not rows:
        return Expect(skip="brak dyżurów aptek na dziś w bazie")

    names = "|".join(re.escape(flat(r["pharmacy_name"])[:8]) for r in rows)
    return Expect(
        fact="dyżur: " + ", ".join(r["pharmacy_name"] for r in rows),
        must=[("nazwa apteki", names)],
        must_not=[("wyparcie się wiedzy", NO_KNOWLEDGE)],
    )


async def oracle_solectwa(session: AsyncSession) -> Expect:
    """Karta gminy — fakt stały, wchodzi do KAŻDEGO agenta poza RAG-iem."""
    from src.services.gmina_facts import SOLECTWA

    return Expect(
        fact=f"{len(SOLECTWA)} sołectw (karta gminy)",
        must=[("liczba sołectw", rf"\b{len(SOLECTWA)}\b")],
        must_not=[("odesłanie do urzędu zamiast odpowiedzi", NO_KNOWLEDGE)],
        must_in_context=[],
    )


async def oracle_wojt(session: AsyncSession) -> Expect:
    return Expect(
        fact="wójt: Tomasz Węgrzynowski (karta gminy)",
        must=[("nazwisko wójta", r"wegrzynowski")],
        must_not=[("odesłanie do urzędu zamiast odpowiedzi", NO_KNOWLEDGE)],
        must_in_context=[],
    )


async def oracle_fresh_news(session: AsyncSession) -> Expect:
    result = await session.execute(
        text("""
            SELECT count(*)
            FROM articles a
            JOIN sources s ON a.source_id = s.id
            WHERE a.published_at >= now() - INTERVAL '3 days'
              AND a.processed = true
              AND a.is_filler = false AND a.is_promotional = false
        """)
    )
    count = result.scalar_one()
    if count < 3:
        return Expect(skip=f"tylko {count} świeżych wpisów — za mało, żeby czegokolwiek wymagać")

    return Expect(
        fact=f"{count} wpisów z ostatnich 3 dni",
        must=[],
        must_not=[("wyparcie się wiedzy przy pełnej bazie", NO_KNOWLEDGE)],
        min_len=200,
        must_in_context=[],
    )


async def oracle_azbest(session: AsyncSession) -> Expect:
    result = await session.execute(
        text("""
            SELECT title FROM bip_documents
            WHERE lower(content) LIKE '%azbest%'
            LIMIT 1
        """)
    )
    row = result.first()
    if not row:
        return Expect(skip="brak dokumentu BIP o azbeście (uruchom scripts.run_bip_knowledge)")

    return Expect(
        fact=f"BIP: {row[0][:70]}",
        must=[("temat azbestu/eternitu", r"azbest|eternit")],
        must_not=[("odesłanie do urzędu zamiast odpowiedzi", NO_KNOWLEDGE)],
    )


async def oracle_weather(session: AsyncSession) -> Expect:
    result = await session.execute(
        text("""
            SELECT temperature, fetched_at
            FROM weather
            WHERE location = 'Rybno'
            ORDER BY fetched_at DESC
            LIMIT 1
        """)
    )
    row = result.first()
    if not row or (datetime.utcnow() - row[1]) > timedelta(hours=6):
        return Expect(skip="brak świeżego odczytu pogody (weather_job nie chodził)")

    return Expect(
        fact=f"{row[0]:.0f}°C, odczyt {row[1]:%d.%m %H:%M} UTC",
        must=[("temperatura w odpowiedzi", r"-?\d{1,2}\s*(°|st\b|stopni)")],
        must_not=[("wyparcie się wiedzy o pogodzie", NO_KNOWLEDGE)],
        must_in_context=[],
    )


# --- przypadki ----------------------------------------------------------------

CASES: list[Case] = [
    Case(
        id="replay-07-08",
        question="Czy dziś nie będzie prądu? (odtworzenie 7.08.2026, 8:21)",
        agent="straznik",
        oracle=oracle_incident_replay,
        probe=_straznik_context_at_incident,
        context_only=True,
        why="chwila, w której Strażnik odpowiedział 'brak zgłoszeń' 40 minut przed wyłączeniem",
    ),
    Case(
        id="prad-dzis",
        question="Czy dziś nie będzie prądu?",
        agent="straznik",
        oracle=oracle_power_today,
        probe=_straznik_context,
        why="regresja z 7.08.2026 — wyłączenie ogłoszone 10 dni wcześniej wypadało z okna publikacji",
    ),
    Case(
        id="prad-planowane",
        question="Czy są planowane przerwy w dostawie prądu?",
        agent="straznik",
        oracle=oracle_power_upcoming,
        probe=_straznik_context,
        why="podpowiedź z UI — pytanie o zapowiedzi, nie o stan bieżący",
    ),
    Case(
        id="awarie",
        question="Czy są jakieś awarie w gminie Rybno?",
        agent="straznik",
        oracle=oracle_any_alert,
        probe=_straznik_context,
        why="pytanie otwarte: agent ma wymienić to, co realnie wisi nad gminą",
    ),
    Case(
        id="smieci",
        question="Kiedy najbliższy wywóz śmieci w Rybnie?",
        agent="organizator",
        oracle=oracle_waste_rybno,
        why="harmonogram jest w bazie co do dnia — nie ma miejsca na 'sprawdź u operatora'",
    ),
    Case(
        id="apteka",
        question="Która apteka dziś dyżuruje?",
        agent="organizator",
        oracle=oracle_pharmacy_today,
        why="jeden tryb dyżuru na dzień (audyt 26.07)",
    ),
    Case(
        id="solectwa",
        question="Ile sołectw ma gmina Rybno?",
        agent="urzednik",
        oracle=oracle_solectwa,
        why="regresja z 3.08.2026 — 'nie posiadam danych' na fakt z karty gminy",
    ),
    Case(
        id="wojt",
        question="Kto jest wójtem gminy Rybno?",
        agent="urzednik",
        oracle=oracle_wojt,
        why="karta gminy musi działać bez retrievalu",
    ),
    Case(
        id="azbest",
        question="Czy gmina dofinansuje wywóz eternitu z dachu?",
        agent="urzednik",
        oracle=oracle_azbest,
        probe=_rag_probe("urzednik"),
        why="mowa potoczna ('eternit') kontra język BIP ('azbest') — bramka synonimów",
    ),
    Case(
        id="co-nowego",
        question="Co nowego w gminie?",
        agent="redaktor",
        oracle=oracle_fresh_news,
        why="przy pełnej bazie odpowiedź 'brak informacji' jest zawsze błędem",
    ),
    Case(
        id="pogoda",
        question="Jaka jest dziś pogoda w Rybnie?",
        agent="przewodnik",
        oracle=oracle_weather,
        why="pogoda jest poza RAG — agent czyta ją zapytaniem, łatwo o cichą regresję",
    ),
]


# --- przebieg -----------------------------------------------------------------

GREEN, RED, YELLOW, GREY, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[90m", "\033[0m"


def _check(patterns: list[tuple[str, str]], haystack: str) -> list[str]:
    """Zwraca opisy wymagań, które NIE zostały spełnione."""
    flat_hay = flat(haystack)
    return [desc for desc, pattern in patterns if not re.search(pattern, flat_hay)]


def _check_absent(patterns: list[tuple[str, str]], haystack: str) -> list[str]:
    flat_hay = flat(haystack)
    return [desc for desc, pattern in patterns if re.search(pattern, flat_hay)]


async def _run_case(session: AsyncSession, case: Case, args) -> str:
    print(f"\n{'─' * 78}\n[{case.id}] {case.question}")
    if case.why:
        print(f"{GREY}  ↳ {case.why}{RESET}")

    expect = await case.oracle(session)
    if expect.skip:
        print(f"{YELLOW}  SKIP — {expect.skip}{RESET}")
        return "skip"

    print(f"  Stan bazy: {expect.fact or '—'}")
    failures: list[str] = []

    # Etap 1: czy fakt dotarł do materiału agenta
    context_reqs = expect.must if expect.must_in_context is None else expect.must_in_context
    if case.probe and context_reqs:
        context = await case.probe(session, case.question)
        missing = _check(context_reqs, context)
        if missing:
            failures.append("KONTEKST nie zawiera: " + ", ".join(missing))
            print(f"{RED}  ✗ KONTEKST — brak: {', '.join(missing)}{RESET}")
        else:
            print(f"{GREEN}  ✓ KONTEKST — fakt jest w materiale agenta{RESET}")

    if args.dry or case.context_only:
        return "fail" if failures else "pass"

    # Etap 2: routing
    if not args.no_route:
        from src.ai.agents.orchestrator import orchestrator

        routed = await orchestrator.route(case.question)
        if routed != case.agent:
            failures.append(f"routing → {routed}, oczekiwano {case.agent}")
            print(f"{RED}  ✗ ROUTING — {routed} (oczekiwano {case.agent}){RESET}")
        else:
            print(f"{GREEN}  ✓ ROUTING — {routed}{RESET}")

    # Etap 3: odpowiedź dla mieszkańca
    agent = _agent_instances()[case.agent]
    result = await agent.respond(session, case.question, stream=False)
    answer = result["answer"]

    missing = _check(expect.must, answer)
    if expect.must_any and len(_check(expect.must_any, answer)) == len(expect.must_any):
        missing.append("żadne z: " + ", ".join(desc for desc, _ in expect.must_any))
    forbidden = _check_absent(expect.must_not, answer)
    too_short = len(answer) < expect.min_len

    if missing:
        failures.append("odpowiedź nie zawiera: " + ", ".join(missing))
        print(f"{RED}  ✗ ODPOWIEDŹ — brak: {', '.join(missing)}{RESET}")
    if forbidden:
        failures.append("odpowiedź zawiera: " + ", ".join(forbidden))
        print(f"{RED}  ✗ ODPOWIEDŹ — niedozwolone: {', '.join(forbidden)}{RESET}")
    if too_short:
        failures.append(f"odpowiedź krótsza niż {expect.min_len} znaków")
        print(f"{RED}  ✗ ODPOWIEDŹ — {len(answer)} znaków, wymagane {expect.min_len}{RESET}")
    if not (missing or forbidden or too_short):
        print(f"{GREEN}  ✓ ODPOWIEDŹ{RESET}")

    snippet = " ".join(answer.split())
    print(f"{GREY}  „{snippet[:300]}{'…' if len(snippet) > 300 else ''}”{RESET}")

    return "fail" if failures else "pass"


_INSTANCES: dict = {}


def _agent_instances() -> dict:
    if not _INSTANCES:
        from src.ai.agents import (
            GUSAnalitykAgent, OrganizatorAgent, PrzewodnikAgent,
            RedaktorAgent, StraznikAgent, UrzednikAgent,
        )
        from src.ai.agents.orchestrator import orchestrator

        for cls in (RedaktorAgent, UrzednikAgent, GUSAnalitykAgent,
                    PrzewodnikAgent, StraznikAgent, OrganizatorAgent):
            instance = cls()
            _INSTANCES[instance.name] = instance
            orchestrator.register_agent(instance)  # router waliduje nazwę po rejestrze
    return _INSTANCES


async def main() -> int:
    parser = argparse.ArgumentParser(description="Walidator odpowiedzi agentów")
    parser.add_argument("--only", help="lista id przypadków po przecinku")
    parser.add_argument("--dry", action="store_true", help="bez modelu — same wyrocznie i kontekst")
    parser.add_argument("--no-route", action="store_true", help="pomiń sprawdzanie routingu")
    parser.add_argument("--list", action="store_true", help="wypisz przypadki i zakończ")
    args = parser.parse_args()

    if args.list:
        for case in CASES:
            print(f"{case.id:16} {case.agent:12} {case.question}")
        return 0

    cases = CASES
    if args.only:
        wanted = {c.strip() for c in args.only.split(",")}
        cases = [c for c in CASES if c.id in wanted]
        unknown = wanted - {c.id for c in cases}
        if unknown:
            print(f"Nieznane przypadki: {', '.join(sorted(unknown))}")
            return 2

    tally = {"pass": 0, "fail": 0, "skip": 0}
    if not args.dry:
        _agent_instances()  # router waliduje nazwę po rejestrze — bez tego każdy routing pada na redaktora

    async with async_session() as session:
        for case in cases:
            try:
                tally[await _run_case(session, case, args)] += 1
            except Exception as exc:  # przypadek nie może przewrócić przebiegu
                tally["fail"] += 1
                print(f"{RED}  ✗ WYJĄTEK — {type(exc).__name__}: {exc}{RESET}")

    print(f"\n{'═' * 78}")
    print(
        f"Wynik: {GREEN}{tally['pass']} OK{RESET}, "
        f"{RED if tally['fail'] else GREY}{tally['fail']} błędnych{RESET}, "
        f"{YELLOW if tally['skip'] else GREY}{tally['skip']} pominiętych{RESET}"
    )
    return 1 if tally["fail"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
