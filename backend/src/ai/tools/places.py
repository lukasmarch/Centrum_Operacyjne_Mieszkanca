"""
Narzędzia Przewodnika — wydarzenia i miejsca (2026-08-22)

**Co znika razem z tym plikiem.** Przewodnik wybierał kategorię miejsca
słownikiem `PLACE_KEYWORDS`: 40 rdzeni wyrazów w sześciu kubełkach, dopisywanych
za każdym razem, gdy ktoś zapytał inaczej. „Gdzie zjeść" trafiało w `restaurant`,
„gdzie coś przekąsić" nie trafiało nigdzie. Model rozpoznaje intencję bez tej
listy — a przy okazji potrafi zawołać `local_places(category="cafe")`
i `upcoming_events()` naraz, czego słownik nie umiał z definicji.

**Wydarzenia idą przez `feed_policy.visible_event_conditions`** — ten sam
warunek, co kalendarz, briefing i newsletter. To nie jest ozdoba: 21.08 mail
wysłał „Dziś w okolicy: III Ciechanowski Festiwal", bo każde miejsce miało
własną heurystykę lokalności. Jedna polityka, cztery odbiorniki.

**Wyszukiwanie na żywo zostaje przywilejem Premium** (`places_service`), ale
decyzję o nim podejmuje teraz kod narzędzia, a nie regex na treści pytania —
model prosi o miejsca, narzędzie sprawdza tier i albo pyta Google, albo sięga
do lokalnego cache'u.

Test: `cd backend && python -m scripts.test_agent_tools`
"""
from datetime import timedelta
from typing import Optional

from sqlalchemy import select, text

from src.services import provenance as prov
from src.ai.tools import Tool, ToolContext, ToolResult, register
from src.database.schema import Event
from src.services.feed_policy import time_label, visible_event_conditions, word_stem
from src.services.time_span import to_local
from src.utils.logger import setup_logger
from src.services.time_span import local_day_bounds

logger = setup_logger("PlaceTools")

PLACE_CATEGORIES = ("restaurant", "cafe", "hotel", "attraction", "sport", "nature")

# Ile wydarzeń wchodzi do jednej odpowiedzi. Dziesięć to pełny miesiąc w gminie
# tej wielkości — więcej i model zaczyna streszczać zamiast odpowiadać.
MAX_EVENTS = 10
MAX_PLACES = 15


async def upcoming_events(
    ctx: ToolContext,
    days: int = 14,
    query: Optional[str] = None,
) -> ToolResult:
    """Nadchodzące wydarzenia z kalendarza gminy."""
    try:
        days = max(1, min(int(days), 60))
    except (TypeError, ValueError):
        days = 14

    # Pula kandydatów rośnie, gdy model o coś PYTA. Bez tego zawężenie było
    # pozorne: 25.08.2026 na pytanie „czy gmina planuje spotkania z mieszkańcami
    # w sprawie planu ogólnego" narzędzie dostało `query="spotkanie
    # z mieszkańcami"` i okno 60 dni, po czym oddało dziesięć NAJBLIŻSZYCH
    # wydarzeń. „Spotkanie w sprawie Planu Ogólnego" z 12 września stało
    # w kalendarzu na pozycji trzynastej i nie miało jak się pokazać — agent
    # odpowiedział, że takich spotkań nie ma.
    pool = MAX_EVENTS * (8 if query else 2)

    # Od początku DZISIEJSZEJ doby lokalnej, nie „od teraz". Zapowiedź bez
    # godziny stoi na lokalnej północy, więc przy granicy „od teraz" przestawała
    # istnieć dla agenta o 00:01 w dniu, w którym się odbywała — na pytanie
    # „co się dziś dzieje w gminie" nie miał jej jak wymienić.
    day_start, _ = local_day_bounds(now=ctx.now)
    stmt = (
        select(Event)
        .where(Event.event_date >= day_start)
        .where(Event.event_date <= ctx.now + timedelta(days=days))
        .where(*visible_event_conditions(Event))
        .order_by(Event.event_date.asc())
        .limit(pool)
    )
    rows = list((await ctx.session.execute(stmt)).scalars().all())

    if query:
        # Zawężenie po słowach robimy PO pobraniu — kalendarz gminy liczy
        # dziesiątki pozycji, nie tysiące, a filtr w SQL-u wymagałby decyzji,
        # które pole jest ważniejsze.
        #
        # ⚠️ Dopasowanie idzie po SŁOWACH i po ich RDZENIACH, nie po całej
        # frazie. Model pyta językiem pytania („spotkanie z mieszkańcami”),
        # a kalendarz nazywa rzecz po swojemu („Spotkanie w sprawie Planu
        # Ogólnego”) — szukanie frazy jako podłańcucha nie trafia w NIC, a że
        # pusty wynik wraca tu do pełnej listy, filtr wyglądał na działający.
        # Ta sama lekcja, co w `search_legal_acts._stem`.
        slowa = [word_stem(w) for w in query.strip().lower().split() if len(w) > 2]
        if slowa:
            narrowed = []
            for e in rows:
                haystack = " ".join(
                    (e.title or "", e.description or "", e.location or "")
                ).lower()
                if any(s in haystack for s in slowa):
                    narrowed.append(e)
            # Kolejność zostaje chronologiczna, ale wpisy trafione WIĘKSZĄ
            # liczbą słów idą pierwsze — przy dziesięciu miejscach w odpowiedzi
            # to decyduje, czy właściwe wydarzenie w ogóle dojdzie do modelu.
            narrowed.sort(key=lambda e: -sum(
                1 for s in slowa
                if s in " ".join(
                    (e.title or "", e.description or "", e.location or "")
                ).lower()
            ))
            rows = narrowed or rows

    if not rows:
        return ToolResult(
            content={
                "info": f"Brak wydarzeń w kalendarzu na najbliższe {days} dni.",
                "co_powiedziec": (
                    "Powiedz wprost, że kalendarz jest pusty w tym oknie. "
                    "Możesz zaproponować stałe aktywności okolicy, ale NIE "
                    "wymyślaj konkretnych imprez ani dat."
                ),
            },
            empty=True,
            summary=f"kalendarz pusty w oknie {days} dni",
        )

    wydarzenia = []
    for ev in rows[:MAX_EVENTS]:
        wydarzenia.append({
            "tytul": ev.title,
            "kiedy": time_label(None, ev.event_date, None, ctx.now),
            # Czas LOKALNY, jak w `kiedy`. Baza trzyma naiwny UTC, więc surowe
            # `strftime` podawało modelowi drugą, sprzeczną godzinę tego samego
            # wydarzenia — konsultacje o 19:00 jako 17:00. Jedna data w jednym
            # wyniku, inaczej model wybiera losowo, którą przepisze.
            "data": to_local(ev.event_date).strftime("%d.%m.%Y %H:%M") if ev.event_date else None,
            "miejsce": ev.location or "",
            "kategoria": ev.category or "",
            "organizator": ev.organizer or "",
            "opis": (ev.description or "")[:200],
        })

    return ToolResult(
        content={"okno_dni": days, "wydarzenia": wydarzenia},
        summary=f"{len(wydarzenia)} wydarzeń w oknie {days} dni",
    )


async def local_places(
    ctx: ToolContext,
    category: Optional[str] = None,
    query: Optional[str] = None,
) -> ToolResult:
    """Miejsca w gminie i okolicy — cache Google Maps, dla Premium na żywo."""
    if category and category not in PLACE_CATEGORIES:
        category = None

    tier = getattr(ctx.user, "tier", "free") if ctx.user else "free"
    is_premium = tier in ("premium", "business")

    if is_premium and query:
        from src.integrations.places_service import places_service
        live = await places_service.search_live(query, category=category)
        if live:
            return ToolResult(
                content={
                    "zrodlo": "Google Maps — wyszukiwanie na żywo",
                    "miejsca": [_place_row(p) for p in live[:MAX_PLACES]],
                },
                summary=f"{len(live[:MAX_PLACES])} miejsc (wyszukiwanie na żywo)",
            )
        logger.warning("Live search bez wyniku — sięgam do cache'u")

    if category:
        result = await ctx.session.execute(
            text("""
                SELECT name, category, description, address, maps_uri
                FROM local_places
                WHERE active = TRUE AND category = :cat
                ORDER BY updated_at DESC LIMIT :lim
            """),
            {"cat": category, "lim": MAX_PLACES},
        )
    else:
        result = await ctx.session.execute(
            text("""
                SELECT name, category, description, address, maps_uri
                FROM local_places
                WHERE active = TRUE
                ORDER BY category, updated_at DESC LIMIT :lim
            """),
            {"lim": MAX_PLACES + 5},
        )
    rows = [dict(r._mapping) for r in result]

    if not rows:
        return ToolResult(
            content={
                "info": (
                    f"Brak miejsc w bazie dla kategorii: {category or 'wszystkie'}."
                ),
                "co_powiedziec": (
                    "Powiedz, czego nie masz w bazie. Możesz podać ogólną wiedzę "
                    "o okolicy (Rybno, Działdowo, Lidzbark, Welski Park "
                    "Krajobrazowy), ale zaznacz, że to nie jest sprawdzona lista."
                ),
            },
            empty=True,
            summary=f"brak miejsc w bazie ({category or 'wszystkie kategorie'})",
        )

    return ToolResult(
        content={
            "zrodlo": "baza miejsc RybnoLive (Google Maps)",
            "miejsca": [_place_row(p) for p in rows],
        },
        summary=f"{len(rows)} miejsc z bazy",
    )


def _place_row(place: dict) -> dict:
    return {
        "nazwa": place.get("name"),
        "kategoria": place.get("category"),
        "adres": place.get("address") or "",
        "opis": (place.get("description") or "")[:180],
        "mapa": place.get("maps_uri") or "",
    }


register(Tool(
    name="upcoming_events",
    provenance=prov.MEDIA,
    description=(
        "Wydarzenia zaplanowane w gminie Rybno i okolicy: festyny, koncerty, "
        "zawody, zebrania, imprezy dla dzieci. Zwraca datę, miejsce i organizatora. "
        "Użyj przy pytaniu: co się dzieje, co robić w weekend, jakie imprezy, "
        "czy coś się szykuje."
    ),
    short="kalendarz wydarzeń w gminie (do 60 dni w przód)",
    parameters={
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Okno w dniach, 1-60. Domyślnie 14. Na pytanie "
                               "o weekend użyj 7, o miesiąc — 30.",
                "minimum": 1, "maximum": 60,
            },
            "query": {
                "type": "string",
                "description": "Opcjonalne słowo zawężające, np. „dożynki”, "
                               "„sesja rady”, „dla dzieci”.",
            },
        },
        "required": [],
    },
    fn=upcoming_events,
    status_message="Przeglądam kalendarz wydarzeń…",
))

register(Tool(
    name="local_places",
    provenance=prov.ZEWNETRZNE,
    description=(
        "Miejsca w gminie Rybno i okolicy: restauracje, kawiarnie, noclegi, "
        "atrakcje turystyczne, obiekty sportowe, szlaki i przyroda. Zwraca nazwę, "
        "adres i link do map. Użyj przy pytaniu gdzie zjeść, gdzie przenocować, "
        "co zwiedzić, gdzie pobiegać, gdzie iść z rodziną."
    ),
    short="restauracje, noclegi, atrakcje i szlaki w okolicy",
    parameters={
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": list(PLACE_CATEGORIES),
                "description": "Rodzaj miejsca. Pomiń, żeby dostać przegląd wszystkich.",
            },
            "query": {
                "type": "string",
                "description": "Czego dokładnie szuka mieszkaniec, własnymi słowami. "
                               "Dla kont Premium uruchamia wyszukiwanie na żywo.",
            },
        },
        "required": [],
    },
    fn=local_places,
    status_message="Szukam miejsc w okolicy…",
))
