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
    # ⚠️ `\b` na początku jest KONIECZNE i kosztowało nas fałszywy alarm przez
    # kilkanaście dni. Bez niego „obecNIE WYSTĘPUJE jedna awaria" — zdanie
    # dokładnie odwrotne do zaprzeczenia — trafiało we wzorzec `nie wystepuj`,
    # bo „obecnie występuje" zawiera go jako podłańcuch. Przypadek `awarie`
    # świecił się na czerwono przy POPRAWNEJ odpowiedzi, a wpis w CLAUDE.md
    # opisywał to jako wadę agenta.
    r"\b(nie ma|brak|nie odnotowano|nie wystepuj|nie zarejestrowano|nie planuje)"
    r"[^.]{0,70}(awari|wylacze|przerw|zglosze|utrudnie|ostrzez)"
)

# Zaprzeczenie samym AWARIOM — węższe od `DENIAL` i używane tam, gdzie w bazie
# stoi konkretna awaria, a odpowiedź ma o niej powiedzieć.
#
# ⚠️ Po co osobny wzorzec: odpowiedź, która POPRAWNIE wymienia zablokowaną drogę,
# zwykle kończy zdaniem „nie ma zapowiedzianych wyłączeń" — bo licznik
# `zapowiedziane` wynosi 0 i prompt Strażnika tego wymaga. `DENIAL` łapał to
# zdanie i wywracał przypadek przy odpowiedzi bez zarzutu (zmierzone: 6/6
# przebiegów wymieniało awarię jako pierwszą pozycję). Test ma pilnować, czy
# agent zaprzecza AWARII, a nie czy w ogóle użył słowa „nie ma".
DENIAL_AWARIE = (
    r"\b(nie ma|brak|nie odnotowano|nie wystepuj|nie zarejestrowano)"
    r"[^.]{0,40}awari"
)
# „Nie mam aktualnych artykułów, ale ogólnie w gminie…" to ta sama porażka co
# „nie posiadam danych", tylko lepiej ubrana — wzorzec musi łapać oba.
# Wyparcie się wiedzy — agent MA materiał i mimo to mówi, że nie ma.
#
# ⚠️ NIE MA tu „skontaktuj się z urzędem”, choć było do 24.08. Ten zwrot bywa
# odmową („nie posiadam danych, skontaktuj się z urzędem” — regresja z 3.08),
# ale bywa też najlepszą częścią dobrej odpowiedzi: prompt Urzędnika WYMAGA
# podania konkretnego następnego kroku (gdzie, jak, z czym). Odpowiedź
# o azbeście — z kwotą, terminem i numerem pokoju w urzędzie — raz przechodziła,
# raz nie, zależnie od tego, jak model zakończył zdanie. Test, który losowo
# świeci na czerwono, uczy ignorowania czerwonego.
# Prawdziwą odmowę i tak łapią pozostałe warianty, a każdy przypadek używający
# tego wzorca ma własne `must` (liczba sołectw, nazwisko wójta, temat azbestu).
NO_KNOWLEDGE = (
    r"(nie posiadam|nie dysponuje"
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
    """Materiał Strażnika — to, co zwracają jego narzędzia.

    Od 22.08.2026 Strażnik nie pobiera danych sam: `_fetch_alert_articles`
    i `_fetch_recent_reports` przeniosły się do `ai/tools/alerts.py`. Wyrocznia
    sprawdza więc narzędzia, bo to one są teraz jedynym źródłem jego wiedzy
    o awariach.
    """
    import json

    from src.ai.tools import ToolContext
    from src.ai.tools.alerts import active_alerts, citizen_reports

    ctx = ToolContext(session=session)
    alerts = await active_alerts(ctx)
    reports = await citizen_reports(ctx)
    return json.dumps(
        [alerts.content, reports.content], ensure_ascii=False, default=str
    )


async def _straznik_context_at_incident(session: AsyncSession, question: str) -> str:
    """Materiał Strażnika widziany z chwili, w której odpowiedział błędnie.

    `ToolContext.now` jest tu jedynym powodem, dla którego da się to odtworzyć:
    gdyby narzędzie brało czas z zegara, regresji z 7.08 nie sposób byłoby
    powtórzyć po fakcie.
    """
    import json

    from src.ai.tools import ToolContext
    from src.ai.tools.alerts import active_alerts

    result = await active_alerts(ToolContext(session=session, now=INCIDENT_AT))
    return json.dumps(result.content, ensure_ascii=False, default=str)


async def _session_date_probe(session: AsyncSession, question: str) -> str:
    """Materiał na pytanie o TERMIN posiedzenia — z OBU narzędzi terminu.

    Trzy narzędzia, trzy różne odpowiedzi na to samo pytanie, i o to tu chodzi:
    `council_sessions` zna wyłącznie obrady, które JUŻ BYŁY (25.08 zwróciło
    pustkę i Urzędnik na tym poprzestał — czterokrotnie), `upcoming_events`
    ma datę i godzinę, `search_documents` ma ogłoszenie BIP z salą i porządkiem
    obrad. Sonda bierze wszystkie trzy, żeby czerwony wynik mówił, KTÓRE
    z nich zawiodło.
    """
    import json

    from src.ai.tools import ToolContext
    from src.ai.tools.council import council_sessions
    from src.ai.tools.knowledge import search_documents
    from src.ai.tools.places import upcoming_events

    ctx = ToolContext(session=session)
    obrady = await council_sessions(ctx)
    kalendarz = await upcoming_events(ctx, days=30)
    dokumenty = await search_documents(ctx, query=question)

    return json.dumps({
        "council_sessions": obrady.content,
        "upcoming_events": kalendarz.content,
        "search_documents": dokumenty.content,
    }, ensure_ascii=False, default=str)


async def _documents_probe(session: AsyncSession, question: str) -> str:
    """Materiał Urzędnika — przez NARZĘDZIE, nie przez własną kopię retrievalu.

    Do 24.08 sonda powtarzała retrieval agenta ręcznie (`hybrid_search`
    z jego progami). Po przeniesieniu Urzędnika na narzędzia mierzyłaby coś,
    czego agent już nie robi — a świeciłaby na zielono, bo atrybuty `rag_*`
    dalej stoją w klasie. Dokładnie ten sam błąd, przez który 22.08 sondy
    Strażnika przechodziły na usuniętej metodzie.

    Pytanie idzie tu DOSŁOWNIE, bez ręcznego tłumaczenia na język urzędowy:
    całą wartością tego przypadku jest sprawdzenie, czy „eternit" dociera
    do dokumentu o azbeście.
    """
    import json

    from src.ai.tools import ToolContext
    from src.ai.tools.knowledge import search_documents

    result = await search_documents(ToolContext(session=session), query=question)
    return json.dumps(result.content, ensure_ascii=False, default=str)


async def _legal_acts_probe(session: AsyncSession, question: str) -> str:
    """Materiał Urzędnika o uchwałach — przez `search_legal_acts`.

    Sonda idzie tą samą drogą co agent, bo to jedyny sposób, żeby czerwony
    wynik mówił, CO zawiodło: rejestr (etap 4 nie napełniony, akt bez daty)
    czy prompt (model ma numer w wyniku i go nie podał).
    """
    import json

    from src.ai.tools import ToolContext
    from src.ai.tools.knowledge import search_legal_acts

    result = await search_legal_acts(ToolContext(session=session), rodzaj="uchwały", limit=5)
    return json.dumps(result.content, ensure_ascii=False, default=str)


async def _fresh_feed_probe(session: AsyncSession, question: str) -> str:
    """Materiał Redaktora na pytanie ogólne — przez `latest_local_news`.

    Przypadek `co-nowego` sprawdzał do 24.08 wyłącznie ODPOWIEDŹ, więc czerwony
    wynik nie mówił, czy zawiódł prompt, czy zapytanie. A to jest ten przypadek,
    w którym rozróżnienie kosztowało już jedno śledztwo (9.08).
    """
    import json

    from src.ai.tools import ToolContext
    from src.ai.tools.knowledge import latest_local_news

    result = await latest_local_news(ToolContext(session=session))
    return json.dumps(result.content, ensure_ascii=False, default=str)


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
        must_not=[("wyparcie się wiedzy o awarii", DENIAL_AWARIE)],
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
    """Ile świeżego materiału jest — i ile z niego dotyczy SAMEJ gminy.

    Rozróżnienie kupione 24.08. „W gminie Rybno nie pojawiły się nowe
    wiadomości, oto aktualności z okolic" wygląda jak porażka z 9.08
    („nie mam aktualnych artykułów"), a jest jej przeciwieństwem: to prawda,
    powiedziana wprost, po czym agent i tak dowozi materiał. Zakaz wypierania
    się wiedzy ma sens WYŁĄCZNIE wtedy, gdy wpisy z gminy naprawdę są.

    `locality >= 3` to ocena z kategoryzacji AI, liczona niezależnie od kodu
    agenta — wyrocznia nie może dzielić zapytania z tym, co sprawdza.
    """
    result = await session.execute(
        text("""
            SELECT count(*) AS wszystkie,
                   count(*) FILTER (WHERE a.locality >= 3) AS z_gminy
            FROM articles a
            JOIN sources s ON a.source_id = s.id
            WHERE a.published_at >= now() - INTERVAL '3 days'
              AND a.processed = true
              AND a.is_filler = false AND a.is_promotional = false
        """)
    )
    count, z_gminy = result.one()
    if count < 3:
        return Expect(skip=f"tylko {count} świeżych wpisów — za mało, żeby czegokolwiek wymagać")

    if not z_gminy:
        # Materiał jest, ale żaden wpis nie jest z samej gminy (tak wygląda baza
        # lokalna bez Facebooka — profil gminy chodzi przez płatne Apify).
        # Wymagamy wtedy, żeby agent MIMO TO dowiózł treść, a nie zbył pytania.
        return Expect(
            fact=f"{count} wpisów z ostatnich 3 dni, w tym 0 z samej gminy",
            must=[],
            must_not=[("zbycie pytania mimo materiału z okolic",
                       r"nie mam[^.]{0,30}(artykul|wiadomosc)|brak[^.]{0,20}artykul")],
            min_len=200,
            must_in_context=[("materiał ze świeżego feedu", r"wpisy")],
        )

    return Expect(
        fact=f"{count} wpisów z ostatnich 3 dni, w tym {z_gminy} z gminy",
        must=[],
        must_not=[("wyparcie się wiedzy przy pełnej bazie", NO_KNOWLEDGE)],
        min_len=200,
        # Wymóg celowo słaby, ale NIE pusty: sprawdza, że `latest_local_news`
        # w ogóle dowiozło materiał (klucz „wpisy”, a nie gałąź pustego wyniku).
        # Bez tego czerwony wynik tego przypadku nie mówił, czy zawiodło
        # zapytanie, czy prompt — a rozróżnienie kosztowało już śledztwo (9.08).
        # Nie wiążemy go z KONKRETNYM artykułem, bo `article_score` może
        # przestawić kolejność i test stałby się chwiejny bez powodu.
        must_in_context=[("materiał ze świeżego feedu", r"wpisy")],
    )


async def oracle_latest_acts(session: AsyncSession) -> Expect:
    """Najnowsza uchwała Rady wprost z rejestru — zapytanie NIEZALEŻNE od kodu agenta.

    Pilnuje etapu 4 i jednej konkretnej rzeczy: **numeru**. Uchwała podana
    bez numeru jest bezużyteczna (mieszkaniec idzie z nim do urzędu), a numer
    wymyślony jest gorszy niż brak odpowiedzi.
    """
    rows = (await session.execute(
        text("""
            SELECT act_number FROM legal_acts
            WHERE act_group ILIKE '%Uchwały%' AND act_number IS NOT NULL
              AND adopted_at = (
                  SELECT MAX(adopted_at) FROM legal_acts
                  WHERE act_group ILIKE '%Uchwały%' AND act_number IS NOT NULL
              )
        """)
    )).scalars().all()

    if not rows:
        return Expect(skip="rejestr aktów pusty — uruchom scripts.run_legal_acts")

    # ⚠️ „Najnowsza uchwała" NIE jest jedną uchwałą. Jedna sesja Rady podejmuje
    # ich kilkanaście tego samego dnia (24.06.2026 — osiem), więc wymaganie
    # konkretnego numeru czyniło z tego przypadku loterię. Wystarczy DOWOLNY
    # numer z najświeższej sesji: pilnujemy tego, że numer pochodzi z rejestru,
    # a nie z pamięci modelu.
    # ⚠️ Wzorzec musi przejść przez `flat()` tak jak przeszukiwany tekst —
    # normalizator sprowadza wszystko do małych liter, więc „XXIII/180/2026”
    # nie trafiłoby w „xxiii/180/2026”. Ten sam zabieg co przy nazwie apteki.
    # Numer bywa też zapisany z odstępami („XXIII / 178 / 2026”).
    wzorce = [re.escape(flat(n)).replace("/", r"\s*/\s*") for n in rows]
    dowolny = "(" + "|".join(wzorce) + ")"

    return Expect(
        fact=f"najświeższa sesja dała {len(rows)} uchwał: {', '.join(rows[:4])}…",
        must_any=[("numer uchwały z najświeższej sesji", dowolny)],
        must_not=[("wyparcie się rejestru przy pełnej bazie", NO_KNOWLEDGE)],
        must_in_context=[("numer w materiale agenta", dowolny)],
    )


async def oracle_next_session(session: AsyncSession) -> Expect:
    """Najbliższe posiedzenie Rady albo komisji — z kalendarza, niezależnie od agenta.

    Pytanie ze zrzutu z 25.08: „Kiedy w gminie Rybno posiedzenie rady i komisji".
    Urzędnik odpowiedział „skrótów obrad jeszcze nie opublikowano" — cztery razy,
    mimo dwóch próśb o szukanie dalej. Termin XXIV sesji (27.08, 10:00) leżał
    wtedy i w kalendarzu, i w ogłoszeniu BIP w RAG.

    ⚠️ Wyrocznia pyta o to, co widzi KALENDARZ (`canonical_id IS NULL`), bo to
    ta sama bramka, przez którą patrzy narzędzie. Gdy dedup znów zlepi sesję
    z komisją, przypadek ma zaświecić na czerwono — 24.08 zlepił i nikt tego
    nie zauważył przez dwa dni.
    """
    rows = (await session.execute(
        text("""
            SELECT title, event_date FROM events
            WHERE event_date >= now()
              AND event_date <= now() + interval '30 days'
              AND canonical_id IS NULL
              AND locality >= :min_locality
              AND (title ILIKE '%sesj%' OR title ILIKE '%komisj%')
            ORDER BY event_date
            LIMIT 5
        """),
        {"min_locality": feed_policy.MIN_EVENT_LOCALITY},
    )).all()

    if not rows:
        return Expect(skip="w kalendarzu nie ma posiedzenia na najbliższe 30 dni")

    # Baza trzyma naiwny UTC, a model pisze czasem lokalnym — posiedzenie
    # o 22:30 UTC jest „jutro" dla mieszkańca. `_date_re` zna oba zapisy daty
    # i sam dokłada „dziś"/„jutro", gdy termin na to zasługuje.
    #
    # ⚠️ Wymagamy DOWOLNEJ z najbliższych dat, nie akurat pierwszej. Pytanie
    # brzmi „rady i komisji", a to są różne terminy w różne dni: 25.08 model
    # podał sesję Rady (27.08), gdy pierwszym wpisem w kalendarzu była komisja
    # (26.08) — odpowiedź prawdziwą i użyteczną. Testem jest to, czy agent
    # podaje TERMIN Z KALENDARZA zamiast odmowy, a nie to, który z nich wybrał.
    daty = {
        r[1].replace(tzinfo=UTC).astimezone(LOCAL_TZ).date() for r in rows
    }
    wzorzec_daty = "|".join(f"(?:{_date_re(d)})" for d in sorted(daty))
    najblizsze = rows[0]

    return Expect(
        fact=(f"najbliższe posiedzenie: {najblizsze[0][:52]} — "
              f"{najblizsze[1].strftime('%d.%m.%Y %H:%M')}"
              f" (w oknie 30 dni: {len(rows)})"),
        must_any=[("data posiedzenia z kalendarza", wzorzec_daty)],
        must_not=[
            # Zdanie, którym agent zamknął sprawę 25.08. Jest PRAWDZIWE
            # (skrótów faktycznie nie ma) i właśnie dlatego groźne: brzmi jak
            # odpowiedź, a odpowiedzią na pytanie o termin nie jest.
            ("odesłanie do skrótów obrad zamiast terminu",
             r"skrot(y|ow)?\s+(ostatnich\s+)?posiedzen.{0,40}nie\s+(zostal|sa)"),
            ("wyparcie się kalendarza przy pełnej bazie", NO_KNOWLEDGE),
        ],
        must_in_context=[("data posiedzenia w materiale agenta", wzorzec_daty)],
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

async def oracle_gops(session: AsyncSession) -> Expect:
    """Dane GOPS — sprawdzamy POPRAWNOŚĆ, nie samo udzielenie odpowiedzi.

    Do 24.08.2026 agent odpowiadał na to pytanie płynnie i błędnie: stała
    `OFFICE_HOURS` niosła dla GOPS-u adres i telefon URZĘDU GMINY. Odpowiedź
    wyglądała wzorowo, mieszkaniec pojechałby pod zły adres. Dlatego wyrocznia
    czyta bazę i wymaga tego, co w niej stoi.
    """
    row = (await session.execute(text(
        "SELECT name, address, phone FROM gmina_institutions WHERE slug = 'gops'"
    ))).first()
    if row is None or not row.address:
        return Expect(skip="brak GOPS w gmina_institutions "
                           "(uruchom scripts.run_bip_institutions)")

    # Nazwa ulicy z adresu — „ul. Zajeziorna 58, 13-220 Rybno" → „zajeziorna".
    street = re.sub(r"^ul\.\s*", "", row.address).split(",")[0]
    street_core = re.sub(r"\s*\d+\w*$", "", street).strip()
    phone_tail = re.sub(r"\D", "", row.phone or "")[-6:]

    must = [("adres GOPS z bazy", flat(street_core))]
    if phone_tail:
        # `\D*`, nie `\D`: numer bywa pisany „696 63 39" i „6966339", więc
        # separator między cyframi jest opcjonalny. Wymaganie dokładnie jednego
        # znaku odrzucało poprawną odpowiedź.
        must.append(("telefon GOPS", r"\D*".join(phone_tail)))

    # ⚠️ NO_KNOWLEDGE świadomie NIE jest tu zakazane. Godzin pracy GOPS nie ma
    # w bazie (BIP ich nie publikuje) i agent MA to powiedzieć wprost — zakaz
    # zdania, które jest prawdą, to ta sama chwiejność bramki, którą naprawiano
    # 24.08. Gdyby agent nie znalazł nic, padnie wymaganie adresu.
    return Expect(
        fact=f"{row.address}, tel. {row.phone}",
        must=must,
        must_not=[
            ("adres Urzędu Gminy podany jako adres GOPS", r"lubawska"),
        ],
        must_in_context=[("dane GOPS w materiale", flat(street_core))],
    )


async def oracle_kondycja(session: AsyncSession) -> Expect:
    """Pytanie ze zrzutu z 24.08 — to, które dostało „nie mam możliwości".

    Wyrocznia nie sprawdza konkretnej liczby, bo odpowiedź może sięgnąć po
    dowolny wskaźnik. Sprawdza to, czego zabrakło: żeby w JEDNEJ odpowiedzi
    spotkały się DWIE dziedziny — dane liczbowe GUS i to, co robi gmina
    (uchwały, budżet, inwestycje). Jedna dziedzina to wynik, który mieliśmy
    przed pętlą orkiestracji.
    """
    ludnosc = (await session.execute(text(
        "SELECT value, year FROM gus_gmina_stats "
        "WHERE category = 'demografia' AND var_name ILIKE '%ludno%' "
        "AND unit_id = '042815403062' AND value IS NOT NULL "
        "ORDER BY year DESC LIMIT 1"
    ))).first()
    akty = (await session.execute(text("SELECT count(*) FROM legal_acts"))).scalar()

    if ludnosc is None or not akty:
        return Expect(skip=f"za mało materiału (GUS: {bool(ludnosc)}, akty: {akty})")

    return Expect(
        fact=f"ludność {int(ludnosc.value)} ({ludnosc.year}), {akty} aktów w rejestrze",
        must=[
            ("dane liczbowe", r"\d{3,}"),
            ("wątek demograficzny", r"(mieszkan|ludnos|demograf|migracj)"),
            ("wątek działań gminy", r"(uchwal|budzet|inwestyc|strategi|rada gminy)"),
        ],
        must_not=[
            ("odmowa analizy", NO_KNOWLEDGE),
            ("„nie mam możliwości”", r"nie mam mozliwosci"),
        ],
        # Materiał powstaje z delegacji do innych agentów, nie z jednego
        # zapytania — sondy nie da się zbudować bez powtórzenia całej pracy.
        must_in_context=[],
        min_len=400,
    )


CASES: list[Case] = [
    Case(
        id="gops-godziny",
        question="Do której pracuje GOPS i gdzie się mieści?",
        agent="organizator",
        oracle=oracle_gops,
        why="dane z ręcznie wpisanej stałej były BŁĘDNE — agent podawał adres urzędu",
    ),
    Case(
        id="kondycja-gminy",
        question=("Czy jesteś w stanie sprawdzić kondycję Rybna, podsumować jego "
                  "mocne i słabe strony? Masz informacje bieżące i historyczne?"),
        agent="koordynator",
        oracle=oracle_kondycja,
        why="pytanie ze zrzutu 24.08 — „nie mam możliwości” przy pełnej bazie",
    ),

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
        probe=_documents_probe,
        why="mowa potoczna ('eternit') kontra język BIP ('azbest') — bramka synonimów",
    ),
    Case(
        id="kiedy-sesja",
        question="Kiedy w gminie Rybno posiedzenie rady i komisji?",
        agent="urzednik",
        probe=_session_date_probe,
        oracle=oracle_next_session,
        why="pytanie ze zrzutu 25.08 — cztery razy „skrótów obrad nie ma” zamiast terminu",
    ),
    Case(
        id="uchwaly",
        question="Jakie są najnowsze uchwały Rady Gminy?",
        agent="urzednik",
        oracle=oracle_latest_acts,
        probe=_legal_acts_probe,
        why="etap 4 — podpowiedź z UI; numer uchwały MUSI pochodzić z rejestru, nie z pamięci",
    ),
    Case(
        id="co-nowego",
        question="Co nowego w gminie?",
        agent="redaktor",
        oracle=oracle_fresh_news,
        probe=_fresh_feed_probe,
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
            GUSAnalitykAgent, KoordynatorAgent, OrganizatorAgent,
            PrzewodnikAgent, RedaktorAgent, StraznikAgent, UrzednikAgent,
        )
        from src.ai.agents.orchestrator import orchestrator

        for cls in (RedaktorAgent, UrzednikAgent, GUSAnalitykAgent,
                    PrzewodnikAgent, StraznikAgent, OrganizatorAgent,
                    KoordynatorAgent):
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
