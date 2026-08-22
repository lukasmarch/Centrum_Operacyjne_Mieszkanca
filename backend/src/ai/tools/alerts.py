"""
Narzędzia Strażnika — awarie, zdarzenia z terminem, zgłoszenia (2026-08-22)

**Dwa okna czasowe przeniesione bez zmiany — one są tu całą wartością.**
7.08.2026 o 8:21 mieszkaniec pyta „czy dziś nie będzie prądu", Strażnik
odpowiada, że nie ma zgłoszeń. Wyłączenie zaczynało się o 9:00 i stało w bazie,
tyle że ogłoszone 28.07 — a zapytanie filtrowało po DACIE OGŁOSZENIA. Stąd:

* awaria bez terminu żyje datą publikacji → 7 dni wstecz;
* zdarzenie z terminem żyje datą ZDARZENIA → od 6 h po zakończeniu do 72 h
  w przód, **bez względu na to, jak dawno je ogłoszono**.

Kolejność: najbliżej zdarzenia, nie najświeżej ogłoszone.

**Zasięg jest częścią odpowiedzi, nie ozdobą.** Feed Energi obejmuje cały
powiat, więc każdy wpis niesie `zasieg` z `feed_policy.is_local_article` —
bez tego wyłączenie w Płośnicy szło do mieszkańca Rybna jako jego awaria.

⚠️ To zapytanie SQL jest JEDYNYM źródłem wiedzy Strażnika o awariach. Strażnik
nie używa RAG (`source_types = []`), więc obecność wpisu w `document_embeddings`
niczego tu nie gwarantuje.

Test: `cd backend && python -m scripts.test_agent_tools`
"""
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select, text

from src.ai.tools import Tool, ToolContext, ToolResult, register
from src.database.schema import Article, Source
from src.services.feed_policy import is_local_article, publishable_conditions, time_label
from src.utils.logger import setup_logger

logger = setup_logger("AlertTools")

LOCAL_TZ = ZoneInfo("Europe/Warsaw")

# Zdarzenie z terminem: ile do przodu jeszcze o nim mówimy. Trzy doby to horyzont
# pytania „czy w tym tygodniu wyłączą prąd"; briefing ma własne 36 h, bo tam
# chodzi o jeden nagłówek, a tu o kompletną odpowiedź.
EVENT_LOOKAHEAD_H = 72
# Ile po zakończeniu wpis jeszcze coś wyjaśnia („wróciłem, było ciemno — czemu?")
EVENT_KEEP_AFTER_H = 6
# Wpisy BEZ terminu (awaria, która po prostu się wydarzyła)
PUBLISHED_WINDOW_D = 7


def _local(value: datetime) -> datetime:
    return value.replace(tzinfo=ZoneInfo("UTC")).astimezone(LOCAL_TZ)


async def active_alerts(ctx: ToolContext) -> ToolResult:
    """Awarie i zdarzenia z terminem — dwa okna, patrz docstring modułu."""
    now = ctx.now

    result = await ctx.session.execute(
        select(Article, Source.name)
        .join(Source, Article.source_id == Source.id)
        .where(Article.processed == True)  # noqa: E712
        .where(*publishable_conditions(Article))
        .where(
            or_(
                (Article.category == "Awaria")
                & (Article.published_at >= now - timedelta(days=PUBLISHED_WINDOW_D)),
                Article.event_at.is_not(None)
                & (Article.event_at <= now + timedelta(hours=EVENT_LOOKAHEAD_H))
                & (
                    func.coalesce(Article.event_until, Article.event_at)
                    >= now - timedelta(hours=EVENT_KEEP_AFTER_H)
                ),
            )
        )
        .limit(20)
    )

    items = []
    for article, source_name in result:
        stamp = article.event_at or article.published_at or now
        items.append({
            "tytul": article.display_title or article.title,
            "kiedy": time_label(
                article.published_at, article.event_at, article.event_until, now,
                published_prefix="zgłoszono ",
            ),
            "zasieg": (
                "gmina Rybno"
                if is_local_article(source_name, article.title, article.content)
                else "poza gminą Rybno"
            ),
            "ogloszono": (
                f"{_local(article.published_at):%d.%m.%Y}"
                if article.event_at and article.published_at else None
            ),
            "opis": article.summary or "",
            "zrodlo": source_name,
            "_distance": abs((stamp - now).total_seconds()),
        })

    items.sort(key=lambda a: a["_distance"])
    items = [{k: v for k, v in it.items() if k != "_distance"} for it in items[:10]]

    if not items:
        return ToolResult(
            content={
                "info": (
                    "Brak awarii i zapowiedzianych zdarzeń w oknie: 7 dni wstecz "
                    "(awarie bez terminu) i 72 h w przód (zdarzenia z terminem)."
                ),
                "co_powiedziec": (
                    "Powiedz KRÓTKO i wprost: nie ma teraz żadnych awarii ani "
                    "zapowiedzianych wyłączeń. Nie buduj zdań typu „zapowiedziano "
                    "brak przerw” — jeśli nic nie ma, po prostu tak napisz."
                ),
            },
            empty=True,
            summary="brak awarii i zapowiedzianych zdarzeń",
        )

    lokalne = sum(1 for i in items if i["zasieg"] == "gmina Rybno")
    return ToolResult(
        content={"zdarzenia": items},
        summary=f"{len(items)} zdarzeń ({lokalne} w gminie Rybno)",
    )


async def citizen_reports(ctx: ToolContext, days: int = 14) -> ToolResult:
    """Zgłoszenia mieszkańców ze Zgłoszeń 24."""
    try:
        days = max(1, min(int(days), 60))
    except (TypeError, ValueError):
        days = 14

    result = await ctx.session.execute(
        text("""
            SELECT title, description, category, ai_severity, status,
                   created_at, address, location_name, ai_summary
            FROM reports
            WHERE created_at >= now() - :days * INTERVAL '1 day'
              AND status NOT IN ('rejected')
              AND is_spam = False
            ORDER BY created_at DESC
            LIMIT 20
        """),
        {"days": days},
    )
    rows = [dict(r._mapping) for r in result]

    if not rows:
        return ToolResult(
            content={
                "info": f"Brak zgłoszeń mieszkańców z ostatnich {days} dni.",
                "co_powiedziec": (
                    "Powiedz wprost, że zgłoszeń nie ma, i przypomnij, że można "
                    "je złożyć w zakładce Zgłoszenia 24."
                ),
            },
            empty=True,
            summary=f"brak zgłoszeń z {days} dni",
        )

    return ToolResult(
        content={
            "zgloszenia": [{
                "tytul": r["title"],
                "kategoria": (r.get("category") or "").upper(),
                "status": r.get("status"),
                "waga": r.get("ai_severity"),
                "kiedy": f"{r['created_at']:%d.%m.%Y %H:%M}" if r.get("created_at") else "",
                "miejsce": r.get("location_name") or r.get("address") or "",
                "opis": r.get("ai_summary") or (r.get("description") or "")[:200],
            } for r in rows],
        },
        summary=f"{len(rows)} zgłoszeń z {days} dni",
    )


register(Tool(
    name="active_alerts",
    description=(
        "Awarie i zdarzenia z terminem dotyczące gminy Rybno i okolic: wyłączenia "
        "prądu, przerwy w dostawie wody, ostrzeżenia meteo, utrudnienia drogowe, "
        "pożary. Obejmuje zdarzenia ZAPOWIEDZIANE (do 72 h w przód) niezależnie "
        "od tego, kiedy je ogłoszono, oraz awarie z ostatnich 7 dni. Każdy wpis "
        "ma zasięg: „gmina Rybno” albo „poza gminą Rybno”. Użyj przy KAŻDYM "
        "pytaniu o awarie, prąd, wodę, zagrożenia i bezpieczeństwo."
    ),
    short="awarie i zapowiedziane wyłączenia (7 dni wstecz, 72 h w przód)",
    parameters={"type": "object", "properties": {}, "required": []},
    fn=active_alerts,
    status_message="Sprawdzam awarie i zapowiedziane wyłączenia…",
))

register(Tool(
    name="citizen_reports",
    description=(
        "Zgłoszenia mieszkańców ze Zgłoszeń 24: dziury w drodze, przepalone "
        "latarnie, dzikie wysypiska, uszkodzona infrastruktura. Zwraca kategorię, "
        "status i miejsce. Użyj przy pytaniu, co zgłaszają mieszkańcy albo czy "
        "ktoś już zgłosił dany problem."
    ),
    short="zgłoszenia mieszkańców ze Zgłoszeń 24",
    parameters={
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Okno w dniach, 1-60. Domyślnie 14.",
                "minimum": 1, "maximum": 60,
            },
        },
        "required": [],
    },
    fn=citizen_reports,
    status_message="Przeglądam zgłoszenia mieszkańców…",
))
