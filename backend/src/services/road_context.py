"""
Materiał źródłowy o drogach dla widgetu ruchu.

Model puszczony luzem po Google Search zgaduje: 29.07.2026 zgłosił „utrudnienia
na trasie do Iławy", opierając się na gminnym komunikacie o przebudowie 278 m
drogi transportu rolnego w Hartowcu, a przy kolejnym przebiegu ogłosił start
remontu DW538 „z 27.07" — podczas gdy remont ruszył 3.07, a 25.07 gmina napisała,
że prace dobiegają końca. Data była zmyślona, wniosek odwrotny do prawdy.

Mamy lepsze dane niż wyszukiwarka: własny feed z gminarybno.pl, profilu gminy,
Powiatu i KPP. Ta funkcja wybiera z niego wpisy o drogach i podaje modelowi
jako materiał z DATAMI PUBLIKACJI, żeby nie musiał niczego rekonstruować.
"""
from datetime import datetime, timedelta
from typing import List, Optional, TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.schema import Article, Source
from src.services.alert_policy import places_in
from src.services.feed_policy import is_local_source
from src.services.time_span import to_local

# Źródła o zasięgu szerszym niż gmina: samo „to Powiat/KPP/Energa" nie znaczy
# „to nasze", więc wpis musi jeszcze nazwać miejscowość z gminy Rybno.
# Listę sołectw trzyma `alert_policy.places_in` — jedna na projekt.
WIDER_THAN_GMINA: frozenset[str] = frozenset({
    "Powiat Działdowski (RSS)",
    "KPP Działdowo (RSS)",
    "Energa - wyłączenia bieżące (RSS)",
    "Energa - wyłączenia planowane (RSS)",
})

# Wpis liczy się jako drogowy, gdy pada któreś z tych słów. Lista celowo wąska —
# „inwestycja" czy „przetarg" wpuszczały do materiału plany bez wpływu na przejazd.
ROAD_TERMS: tuple[str, ...] = (
    "droga", "drogi", "drodze", "drogowe", "drogowych",
    "dw538", "dw 538", "dw541", "dw 541", "nr 538", "nr 541",
    "objazd", "zamknięcie", "zamknięta", "zamknięty",
    "remont", "przebudowa", "nawierzchni",
    "utrudnieni", "organizacja ruchu", "przejazd",
    "wypadek", "kolizja", "zderzenie",
)

DEFAULT_DAYS = 21
MAX_ITEMS = 12
SNIPPET_CHARS = 400


class RoadItem(TypedDict):
    date: str
    source: str
    title: str
    snippet: str


def _is_road_related(title: Optional[str], content: Optional[str]) -> bool:
    haystack = f"{title or ''} {content or ''}".lower()
    return any(term in haystack for term in ROAD_TERMS)


def _is_local(
    source_name: Optional[str],
    title: Optional[str],
    content: Optional[str],
) -> bool:
    """Czy wpis dotyczy gminy Rybno i okolic — ta sama zasada co w feedzie."""
    if not is_local_source(source_name):
        return False
    if source_name in WIDER_THAN_GMINA:
        return bool(places_in(title, content))
    return True


async def fetch_road_context(
    session: AsyncSession,
    days: int = DEFAULT_DAYS,
    limit: int = MAX_ITEMS,
) -> List[RoadItem]:
    """
    Lokalne wpisy o drogach z ostatnich `days` dni, najnowsze pierwsze.

    Lokalność rozstrzyga `_is_local` — ta sama zasada co w feedzie: źródło musi
    być lokalne, a przy feedach o zasięgu powiatowym musi jeszcze paść nazwa
    miejscowości z gminy Rybno.
    """
    since = datetime.utcnow() - timedelta(days=days)

    result = await session.execute(
        select(Article, Source.name)
        .join(Source, Source.id == Article.source_id)
        .where(Article.published_at.isnot(None))
        .where(Article.published_at >= since)
        .order_by(Article.published_at.desc())
        .limit(300)
    )

    items: List[RoadItem] = []
    for article, source_name in result.all():
        if not _is_road_related(article.title, article.content):
            continue
        if not _is_local(source_name, article.title, article.content):
            continue

        text = (article.content or article.summary or "").strip()
        text = " ".join(text.split())
        items.append(RoadItem(
            date=f"{to_local(article.published_at):%d.%m.%Y}",
            source=source_name or "źródło lokalne",
            title=" ".join((article.title or "").split())[:120],
            snippet=text[:SNIPPET_CHARS],
        ))
        if len(items) >= limit:
            break

    return items


def format_road_context(items: List[RoadItem]) -> str:
    """Materiał źródłowy w formie do wklejenia w prompt."""
    if not items:
        return "(brak lokalnych wpisów o drogach z ostatnich tygodni)"
    return "\n".join(
        f"- [{it['date']}, {it['source']}] {it['title']}: {it['snippet']}"
        for it in items
    )
