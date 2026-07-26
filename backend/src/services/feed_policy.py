"""
Polityka feedu — ranking i atrybucja źródeł (Etap 0, 2026-07-26)

Problem: przy czystym sortowaniu po dacie publikacji pierwsza piątka feedu
zawsze pochodzi z jednego profilu FB, bo publikuje kilkanaście razy dziennie
o losowych porach, a instytucje wrzucają serie o stałej godzinie (KPP 5:00).
Podaż jest zróżnicowana — widoczność nie była.

Dwa mechanizmy:
1. `article_score` — świeżość z rozpadem połowicznym × waga źródła
2. `diversify`     — przeplot: między wpisami z tego samego źródła co najmniej
                     SOURCE_GAP innych źródeł
"""
from datetime import datetime
from typing import Callable, Iterable, Optional, TypeVar

# Rozpad połowiczny świeżości: po 18 h wpis waży połowę tego, co świeży
FRESHNESS_HALFLIFE_H = 18.0

# Ile innych wpisów musi dzielić dwa wpisy z tego samego źródła
SOURCE_GAP = 2

# Awaria trafia na górę feedu tylko dopóki jest zdarzeniem "teraz"
AWARIA_PIN_HOURS = 24

DEFAULT_WEIGHT = 1.0

# Waga źródła w rankingu. Instytucje > media > scrapowane profile prywatne.
# Uwaga: typ z tabeli `sources` nie wystarcza — KPP i Radio 7 są oba `rss`,
# a profile gminy i ZGK są `social_media`, choć to źródła urzędowe.
SOURCE_WEIGHTS: dict[str, float] = {
    # infrastruktura — najwyższa wartość użytkowa
    "Energa - wyłączenia bieżące (RSS)": 1.40,
    "Energa - wyłączenia planowane (RSS)": 1.30,
    "Facebook - ZakladGospodarkiKomunalnej": 1.30,
    # urząd i służby
    "Gmina Rybno": 1.35,
    "BIP Gminy Rybno": 1.35,
    "KPP Działdowo (RSS)": 1.30,
    "Facebook - Gmina Działdowo": 1.25,
    "Powiat Działdowski (RSS)": 1.20,
    "Facebook - Rybno": 1.15,
    # media z redakcją i impressum
    "Radio 7 Działdowo (RSS)": 1.00,
    "Radio Olsztyn (RSS)": 0.95,
    "Moje Działdowo": 0.95,
    "Gazeta Olsztyńska (RSS)": 0.90,
    # scrapowane profile prywatne
    "Facebook - Syla": 0.85,
    "Facebook - Panorama Regionu": 0.85,
}

# Źródła, których nazwy NIE eksponujemy w interfejsie.
# Prywatne profile FB pokazujemy jako neutralne "źródło ↗" z linkiem do oryginału:
# atrybucja zostaje (link), ale nie reklamujemy cudzej marki nagłówkiem
# i nie sugerujemy, że feed jest przedrukiem cudzego profilu.
UNNAMED_SOURCES: frozenset[str] = frozenset({
    "Facebook - Syla",
    "Facebook - Panorama Regionu",
})


def source_weight(source_name: Optional[str]) -> float:
    return SOURCE_WEIGHTS.get(source_name or "", DEFAULT_WEIGHT)


def source_label(source_name: Optional[str]) -> Optional[str]:
    """Nazwa źródła do pokazania w UI albo None — wtedy front daje 'źródło ↗'."""
    if not source_name or source_name in UNNAMED_SOURCES:
        return None
    return source_name


def article_score(
    published_at: Optional[datetime],
    scraped_at: Optional[datetime],
    source_name: Optional[str],
    now: Optional[datetime] = None,
) -> float:
    """Świeżość z rozpadem połowicznym przemnożona przez wagę źródła."""
    now = now or datetime.utcnow()
    timestamp = published_at or scraped_at
    if timestamp is None:
        return 0.0
    age_h = max(0.0, (now - timestamp).total_seconds() / 3600)
    freshness = 0.5 ** (age_h / FRESHNESS_HALFLIFE_H)
    return source_weight(source_name) * freshness


def is_pinned_alert(
    category: Optional[str],
    published_at: Optional[datetime],
    scraped_at: Optional[datetime],
    now: Optional[datetime] = None,
) -> bool:
    """Awaria na szczycie feedu tylko przez pierwsze AWARIA_PIN_HOURS godzin."""
    if not category or "awari" not in category.lower():
        return False
    now = now or datetime.utcnow()
    timestamp = published_at or scraped_at
    if timestamp is None:
        return False
    return (now - timestamp).total_seconds() / 3600 <= AWARIA_PIN_HOURS


T = TypeVar("T")


def diversify(
    items: Iterable[T],
    key: Callable[[T], object],
    gap: int = SOURCE_GAP,
    preceding: Optional[Iterable[T]] = None,
) -> list[T]:
    """
    Przeplata posortowaną listę tak, by dwa wpisy z tego samego źródła dzieliło
    co najmniej `gap` innych. Gdy nie ma alternatywy, bierze następny w kolejności
    — dywersyfikacja nigdy nie usuwa treści, tylko zmienia porządek.

    `preceding` to wpisy już umieszczone przed tą listą (np. przypięte awarie);
    bez nich pierwszy element mógłby powtórzyć źródło poprzedniego wpisu.
    """
    pending = list(items)
    placed: list[T] = list(preceding or [])
    offset = len(placed)
    while pending:
        recent = {key(i) for i in placed[-gap:]} if gap else set()
        idx = next((n for n, item in enumerate(pending) if key(item) not in recent), 0)
        placed.append(pending.pop(idx))
    return placed[offset:]
