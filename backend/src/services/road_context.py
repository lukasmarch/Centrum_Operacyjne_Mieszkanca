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
from src.services.alert_policy import _flat, places_in
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

# Zdarzenie chwilowe: konar na jezdni, kolizja, potrącenie. Trwa godziny, nie
# tygodnie — a przez to, że materiał sięgał 21 dni wstecz, 7.09.2026 widget
# pokazywał „Droga do Truszczyn od strony Zwiniarza jest zablokowana z powodu
# spadłego konaru (04.09.2026)" — trzy dni po fakcie, i to na DWÓCH trasach.
#
# ⚠️ Odcięcie musi być w KODZIE, nie w prompcie. Prompt mówił modelowi „jeśli
# źródło jest starsze niż 14 dni i nie potwierdza, że prace nadal trwają — daj
# Płynnie"; konar sprzed trzech dni mieścił się w oknie, więc reguła go
# przepuściła zgodnie z własnym brzmieniem. Reguła sprawdzalna kodem należy
# do kodu — ta sama zasada, co przy walidatorach kategoryzacji.
INCIDENT_TERMS: tuple[str, ...] = (
    "konar", "galaz", "drzewo", "drzewa", "powalone",
    "kolizja", "wypadek", "zderzenie", "potracenie", "dachowanie",
    "zablokowana", "zablokowany", "blokada", "nieprzejezdna", "nieprzejezdny",
    "sluzby sa", "sluzby juz", "straz jedzie",
    "oblodzenie", "podtopienie", "zalana",
)

# Ile dni wpis o zdarzeniu CHWILOWYM liczy się jako aktualny.
INCIDENT_DAYS = 2

# Roboty drogowe ogłasza się raz i trwają tygodniami — remont DW538 ruszył
# 3.07.2026 i tylko z takiego wpisu model wie, że coś się na trasie dzieje.
# Skrócenie TEGO okna do dwóch dni cofnęłoby nas do stanu sprzed `road_context`,
# czyli do zgadywania z wyszukiwarki (patrz nagłówek pliku).
DEFAULT_DAYS = 21
MAX_ITEMS = 12
SNIPPET_CHARS = 400


class RoadItem(TypedDict):
    date: str
    # Wiek wpisu w dniach. Sama data publikacji zmuszała model do rachunku
    # („czy 04.09 to dawno, skoro dziś 07.09?") — a on ten rachunek przegrywał.
    age_days: int
    source: str
    title: str
    snippet: str


def _is_road_related(title: Optional[str], content: Optional[str]) -> bool:
    haystack = f"{title or ''} {content or ''}".lower()
    return any(term in haystack for term in ROAD_TERMS)


def is_incident(title: Optional[str], content: Optional[str]) -> bool:
    """
    Czy wpis opisuje zdarzenie CHWILOWE, a nie roboty drogowe.

    Rozstrzyga treść, nie kategoria z AI: kategoria powstaje o 6:15 i 13:15,
    a konar spada o 20:14 (art. 5830, 4.09.2026). Ta sama zasada, co
    w `alert_policy.incident_of` — tam też polityka czyta tekst, bo etykiety
    modelu jeszcze nie ma.
    """
    haystack = _flat(f"{title or ''} {content or ''}")
    return any(term in haystack for term in INCIDENT_TERMS)


def _is_fresh_enough(
    article: Article,
    now: datetime,
) -> bool:
    """
    Czy wpis wciąż opisuje stan drogi, czy już tylko historię.

    Dwa okna, bo to dwa różne rodzaje zdarzeń: zdarzenie chwilowe żyje
    `INCIDENT_DAYS`, roboty — pełne `DEFAULT_DAYS`.
    """
    published = article.published_at
    if not published:
        return False
    if is_incident(article.title, article.content):
        return published >= now - timedelta(days=INCIDENT_DAYS)
    return True


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
    now = datetime.utcnow()
    since = now - timedelta(days=days)

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
        # Zdarzenie chwilowe po swoim oknie NIE trafia do materiału wcale.
        # Podanie go modelowi z adnotacją „stare" nie wystarczało: prompt miał
        # taką regułę i model i tak zgłosił konar sprzed trzech dni.
        if not _is_fresh_enough(article, now):
            continue

        text = (article.content or article.summary or "").strip()
        text = " ".join(text.split())
        age_days = (now - article.published_at).days
        items.append(RoadItem(
            date=f"{to_local(article.published_at):%d.%m.%Y}",
            age_days=age_days,
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
        f"- [{it['date']} — {_age_label(it['age_days'])}, {it['source']}] "
        f"{it['title']}: {it['snippet']}"
        for it in items
    )


def _age_label(age_days: int) -> str:
    """Wiek wpisu słowami. Model liczy odległość dat gorzej, niż czyta etykietę."""
    if age_days <= 0:
        return "DZIŚ"
    if age_days == 1:
        return "wczoraj"
    return f"sprzed {age_days} dni"
