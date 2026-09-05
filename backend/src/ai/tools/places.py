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

from sqlalchemy import func, select, text

from src.services import provenance as prov
from src.ai.tools import Tool, ToolContext, ToolResult, register
from src.database.schema import Event
from src.services.alert_policy import norm_place, places_in
from src.services.feed_policy import (
    is_truncated, time_label, visible_event_conditions, word_stem,
)
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
    days_back: int = 0,
) -> ToolResult:
    """Wydarzenia z kalendarza gminy — domyślnie nadchodzące, na żądanie wstecz."""
    try:
        days = max(1, min(int(days), 60))
    except (TypeError, ValueError):
        days = 14
    # Okno wstecz istnieje, bo kalendarz był ślepy na własną przeszłość:
    # 5.09.2026 z 1180 wydarzeń w bazie agent widział 7 (0,6%). Pytanie „kiedy
    # był ten bieg" albo „co się działo w sierpniu" nie miało ŻADNEGO narzędzia
    # — a wydarzenie leżało w bazie z datą, miejscem i organizatorem.
    try:
        days_back = max(0, min(int(days_back or 0), 365))
    except (TypeError, ValueError):
        days_back = 0

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
    okno_od = day_start - timedelta(days=days_back)
    stmt = (
        select(Event)
        .where(Event.event_date >= okno_od)
        .where(Event.event_date <= ctx.now + timedelta(days=days))
        .where(*visible_event_conditions(Event))
        # Przy patrzeniu wstecz interesuje nas to, co NAJBLIŻSZE dziś, a nie
        # najstarsze w oknie — inaczej limit puli oddawałby początek sierpnia
        # przy pytaniu o zeszły tydzień.
        .order_by(
            func.abs(func.extract("epoch", Event.event_date - ctx.now)).asc()
            if days_back else Event.event_date.asc()
        )
        .limit(pool)
    )
    rows = list((await ctx.session.execute(stmt)).scalars().all())
    if days_back:
        rows.sort(key=lambda e: e.event_date or ctx.now)

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
                    "To NIE jest jeszcze odpowiedź — kalendarz zna tylko "
                    "wydarzenia wyłuskane z ogłoszeń i bywa niekompletny. "
                    "SZUKAJ DALEJ, zanim cokolwiek napiszesz:\n"
                    "1. search_news z nazwą wydarzenia — ogłoszenie o imprezie "
                    "prawie zawsze jest w wiadomościach, nawet gdy nie ma jej "
                    "w kalendarzu;\n"
                    "2. jeśli pytanie dotyczy czegoś, co JUŻ BYŁO — zawołaj to "
                    "narzędzie jeszcze raz z days_back;\n"
                    "3. jeśli mieszkaniec podał nazwę własną, spróbuj jej samej, "
                    "bez slów opisowych.\n"
                    "Dopiero gdy TO wszystko wróci puste, powiedz wprost, że nic "
                    "o tym nie masz. NIE wymyślaj imprez ani dat i nie zbywaj "
                    "mieszkańca propozycją stałych aktywności zamiast odpowiedzi."
                ),
            },
            empty=True,
            summary=f"kalendarz pusty w oknie {days} dni",
        )

    wybrane = rows[:MAX_EVENTS]
    ogloszenia = await _source_announcements(ctx, wybrane)

    wydarzenia, sources = [], []
    for ev in wybrane:
        wpis = {
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
        }
        zrodlo = ogloszenia.get(ev.source_article_id)
        # Miejscowość rozstrzyga KOD, nie model. Ekstraktor zapisuje w polu
        # miejsca to, co wyczyta — a wyczytuje często „Gmina Rybno", bo tak
        # mówi zdanie wstępne ogłoszenia. Mieszkańca to nie prowadzi nigdzie:
        # gmina ma 22 miejscowości. Nazwa wsi stoi zwykle w TYTULE („…w
        # Kopaniarzach”), a listę odmian trzyma `alert_policy` — jedna w projekcie.
        wsie = places_in(ev.title, f"{ev.location or ''} {zrodlo['tekst'] if zrodlo else ''}")
        if wsie and norm_place(ev.location or "") not in {norm_place(w) for w in wsie}:
            wpis["miejscowosc"] = ", ".join(wsie)
        if zrodlo:
            # Kalendarz jest STRESZCZENIEM ogłoszenia, nie jego zamiennikiem.
            # 5.09.2026 mieszkaniec pytał o szczegóły biegu, a wydarzenie miało
            # w polu miejsca „Gmina Rybno" — nazwa wsi (Kopaniarze), godzina
            # i trasa zostały w ogłoszeniu, którego agent nie miał jak zobaczyć.
            # Dokładamy je TU, bez drugiego narzędzia i bez rundy modelu.
            wpis["ogloszenie"] = zrodlo["tekst"]
            wpis["ogloszenie_zrodlo"] = zrodlo["zrodlo"]
            if zrodlo["urwane"]:
                # Bez tego zdania model czyta wypis jak całość i milczy o tym,
                # że reszta istnieje. Mieszkaniec pytający o godzinę startu ma
                # usłyszeć, że jej u nas nie ma i gdzie ją znajdzie — a nie
                # dostać odpowiedź, z której wynika, że ogłoszenie jej nie zawiera.
                wpis["ogloszenie_urwane"] = (
                    "To WYPIS, nie całe ogłoszenie — pełna treść jest u źródła. "
                    "Jeśli brakuje w nim szczegółu, o który pytano, powiedz to "
                    "wprost i odeślij do oryginału."
                )
            if zrodlo["url"]:
                sources.append({
                    "type": "article", "id": zrodlo["id"],
                    "title": zrodlo["tytul"][:200], "url": zrodlo["url"],
                    "similarity": 1.0,
                })
        wydarzenia.append(wpis)

    okno = f"{days} dni w przód"
    if days_back:
        okno = f"{days_back} dni wstecz i {days} w przód"
    return ToolResult(
        content={"okno": okno, "wydarzenia": wydarzenia},
        sources=sources,
        summary=f"{len(wydarzenia)} wydarzeń ({okno})",
    )


# Ile treści ogłoszenia dokładamy do jednego wydarzenia. Tyle, żeby zmieściły
# się konkrety (miejscowość, godzina, dystanse), i nie więcej: dziesięć
# wydarzeń po pełnym poście wypchnęłoby z kontekstu wszystko inne.
ANNOUNCEMENT_CHARS = 700


async def _source_announcements(ctx: ToolContext, events: list) -> dict:
    """Ogłoszenia, z których powstały te wydarzenia — po `source_article_id`.

    Jedno zapytanie na całą listę, nie jedno na wydarzenie: `AsyncSession`
    obsługuje jedną operację naraz, a pętla z zapytaniem w środku to dziesięć
    rund tam i z powrotem po dane, które da się wziąć naraz.
    """
    ids = [e.source_article_id for e in events if e.source_article_id]
    if not ids:
        return {}
    from src.database.schema import Article, Source

    rows = (await ctx.session.execute(
        select(Article.id, Article.title, Article.display_title, Article.content,
               Article.summary, Article.url, Source.name)
        .join(Source, Article.source_id == Source.id, isouter=True)
        .where(Article.id.in_(ids))
    )).all()

    out = {}
    for aid, title, display_title, content, summary, url, source_name in rows:
        tekst = (content or summary or "").strip()
        urwane = is_truncated(tekst)
        if len(tekst) > ANNOUNCEMENT_CHARS:
            tekst = tekst[:ANNOUNCEMENT_CHARS].rstrip() + "…"
            urwane = True
        out[aid] = {
            "id": aid,
            "tytul": display_title or title or "",
            "tekst": tekst,
            "url": url or "",
            "zrodlo": source_name or "",
            "urwane": urwane,
        }
    return out


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
                    "Baza miejsc jest niepełna z założenia — to nie znaczy, że "
                    "takiego miejsca nie ma. Zanim odpowiesz: nowo otwarty lokal "
                    "albo obiekt bywa opisany w wiadomościach, więc spróbuj "
                    "search_news z jego nazwą lub rodzajem. Dopiero potem powiedz, "
                    "czego nie masz w bazie. Ogólną wiedzę o okolicy (Rybno, "
                    "Działdowo, Lidzbark, Welski Park Krajobrazowy) wolno podać, "
                    "ale zaznacz, że to nie jest sprawdzona lista."
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
        "Kalendarz wydarzeń gminy Rybno i okolicy: festyny, koncerty, zawody, "
        "zebrania, posiedzenia Rady, imprezy dla dzieci. Zwraca datę, miejsce, "
        "organizatora ORAZ fragment ogłoszenia źródłowego, w którym są szczegóły "
        "(nazwa wsi, godzina startu, zapisy) — kalendarz sam ich nie przechowuje, "
        "więc przy pytaniu o szczegóły odpowiadaj z pola `ogloszenie`. "
        "Użyj przy pytaniu: co się dzieje, co robić w weekend, jakie imprezy, "
        "czy coś się szykuje, a z `days_back` także: kiedy to było, co się działo "
        "w zeszłym tygodniu."
    ),
    short="kalendarz wydarzeń gminy (wstecz i w przód) wraz z ogłoszeniem źródłowym",
    parameters={
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Okno W PRZÓD w dniach, 1-60. Domyślnie 14. Na pytanie "
                               "o weekend użyj 7, o miesiąc — 30.",
                "minimum": 1, "maximum": 60,
            },
            "query": {
                "type": "string",
                "description": "Opcjonalne słowo zawężające, np. „dożynki”, "
                               "„sesja rady”, „dla dzieci”.",
            },
            "days_back": {
                "type": "integer",
                "description": (
                    "Okno WSTECZ w dniach, 0-365. Domyślnie 0 — sam kalendarz "
                    "na przyszłość. Podaj, gdy pytanie dotyczy tego, co JUŻ BYŁO "
                    "(„kiedy był ten bieg”, „co się działo w sierpniu”): 7 dla "
                    "zeszłego tygodnia, 31 dla zeszłego miesiąca. Wydarzenie, "
                    "które odbywa się DZIŚ, widać bez tego parametru."
                ),
                "minimum": 0, "maximum": 365,
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
