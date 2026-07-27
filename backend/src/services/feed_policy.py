"""
Polityka treści — jedno miejsce, w którym stoi, co pokazujemy i w jakiej kolejności.

Konsumenci: `/api/articles` (feed) i `ai/summary_generator.py` (briefing dnia).
Reguła projektu: żadnych prywatnych reguł treści u konsumentów. Briefing miał
własną listę źródeł lokalnych i żadnego filtra reklam — skutkiem był nagłówek
o zgubionych okularach i darmowa reklama restauracji w dniu premiery.

Cztery mechanizmy:
1. `article_score`        — odległość w czasie × waga źródła; dla zdarzeń z terminem
                            liczy się odległość do ZDARZENIA, nie wiek ogłoszenia
2. `is_pinned_alert`      — awaria na górze, dopóki jest sprawą „teraz"
3. `collapse_duplicates`  — ten sam materiał z dwóch źródeł pokazujemy raz
4. `diversify`            — przeplot: między wpisami z tego samego źródła
                            co najmniej SOURCE_GAP innych
"""
import re
import unicodedata
from datetime import datetime
from typing import Callable, Iterable, Optional, TypeVar

# Rozpad połowiczny świeżości: po 18 h wpis waży połowę tego, co świeży
FRESHNESS_HALFLIFE_H = 18.0

# Zdarzenia przyszłe (wyłączenie prądu za trzy dni) też tracą na wadze, tylko
# wolniej — zapowiedź na jutro musi wygrywać z zapowiedzią na przyszły tydzień
LOOKAHEAD_HALFLIFE_H = 48.0

# Ile innych wpisów musi dzielić dwa wpisy z tego samego źródła
SOURCE_GAP = 2

# Awaria bez znanego terminu trafia na górę feedu tylko dopóki jest „teraz"
AWARIA_PIN_HOURS = 24

# Zdarzenie z terminem przypinamy dopiero, gdy jest na wyciągnięcie ręki.
# Bez tego wyłączenie zapowiedziane na przyszły czwartek stało cztery dni
# na szczycie feedu obok trzech innych i zabijało wszystkie wiadomości.
PIN_LOOKAHEAD_H = 30

# Twardy limit bloku przypiętego. Przy burzy Energa potrafi wypuścić kilkanaście
# wyłączeń naraz — feed nie może się zamienić w listę awarii.
MAX_PINNED = 3

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

# Źródła dotyczące bezpośrednio gminy Rybno i powiatu działdowskiego.
# Briefing trzymał tę wiedzę osobno, w postaci ID-ków (`LOCAL_SOURCE_IDS`),
# i przy każdym nowym źródle zostawała nieaktualna: Energa, KPP, Powiat i profil
# gminy liczyły się jako „regionalne", więc nie mogły wygrać nagłówka dnia.
LOCAL_SOURCES: frozenset[str] = frozenset({
    "Gmina Rybno",
    "BIP Gminy Rybno",
    "Facebook - Rybno",
    "Facebook - Syla",
    "Facebook - ZakladGospodarkiKomunalnej",
    "Facebook - Panorama Regionu",
    "Facebook - Gmina Działdowo",
    "Moje Działdowo",
    "Powiat Działdowski (RSS)",
    "KPP Działdowo (RSS)",
    # feedy wojewódzkie zawężone filtrem słów kluczowych do powiatu działdowskiego
    "Energa - wyłączenia bieżące (RSS)",
    "Energa - wyłączenia planowane (RSS)",
})

# Źródła, których nazw NIE eksponujemy w interfejsie.
# Prywatne profile FB pokazujemy jako neutralne „źródło ↗" z linkiem do oryginału:
# atrybucja zostaje (link), ale nie reklamujemy cudzej marki nagłówkiem
# i nie sugerujemy, że feed jest przedrukiem cudzego profilu.
UNNAMED_SOURCES: frozenset[str] = frozenset({
    "Facebook - Syla",
    "Facebook - Panorama Regionu",
})


def source_weight(source_name: Optional[str]) -> float:
    return SOURCE_WEIGHTS.get(source_name or "", DEFAULT_WEIGHT)


def is_local_source(source_name: Optional[str]) -> bool:
    return (source_name or "") in LOCAL_SOURCES


# Nazwy techniczne z tabeli `sources` nie nadają się do pokazania mieszkańcowi
# ("Facebook - ZakladGospodarkiKomunalnej"). Sufiks "(RSS)" zdejmowany automatycznie.
SOURCE_DISPLAY_NAMES: dict[str, str] = {
    "Facebook - ZakladGospodarkiKomunalnej": "ZGK w Rybnie",
    "Facebook - Gmina Działdowo": "Gmina Działdowo",
    "Facebook - Rybno": "Gmina Rybno (Facebook)",
    "KPP Działdowo (RSS)": "Policja — KPP Działdowo",
    "Energa - wyłączenia bieżące (RSS)": "Energa Operator",
    "Energa - wyłączenia planowane (RSS)": "Energa Operator",
}


def source_label(source_name: Optional[str]) -> Optional[str]:
    """Nazwa źródła do pokazania w UI albo None — wtedy front daje 'źródło ↗'."""
    if not source_name or source_name in UNNAMED_SOURCES:
        return None
    if source_name in SOURCE_DISPLAY_NAMES:
        return SOURCE_DISPLAY_NAMES[source_name]
    return source_name.replace(" (RSS)", "").strip()


def publishable_conditions(article_model):
    """
    Warunki SQL „to nadaje się do pokazania mieszkańcowi" — wspólne dla feedu
    i briefingu. Dopisanie kolejnej reguły ma działać w obu miejscach naraz.
    """
    return [
        article_model.is_filler == False,        # noqa: E712 — SQLAlchemy
        article_model.is_promotional == False,   # noqa: E712
    ]


def _reference_time(
    published_at: Optional[datetime],
    scraped_at: Optional[datetime],
    event_at: Optional[datetime] = None,
) -> Optional[datetime]:
    """Moment, względem którego liczymy wagę wpisu."""
    return event_at or published_at or scraped_at


def article_score(
    published_at: Optional[datetime],
    scraped_at: Optional[datetime],
    source_name: Optional[str],
    now: Optional[datetime] = None,
    event_at: Optional[datetime] = None,
    event_until: Optional[datetime] = None,
) -> float:
    """
    Waga źródła × odległość w czasie od momentu, który dla mieszkańca się liczy.

    Dla zwykłej wiadomości to data publikacji. Dla zdarzenia z terminem
    (wyłączenie prądu) — sam termin: ogłoszenie sprzed trzech tygodni o jutrzejszym
    wyłączeniu jest świeżą informacją, a nie starą.
    """
    now = now or datetime.utcnow()
    timestamp = _reference_time(published_at, scraped_at, event_at)
    if timestamp is None:
        return 0.0

    delta_h = (now - timestamp).total_seconds() / 3600
    if delta_h < 0:
        freshness = 0.5 ** (-delta_h / LOOKAHEAD_HALFLIFE_H)
    else:
        freshness = 0.5 ** (delta_h / FRESHNESS_HALFLIFE_H)

    # Zdarzenie, które się skończyło, przestaje konkurować z bieżącymi wiadomościami
    if event_until and now > event_until:
        freshness *= 0.25

    return source_weight(source_name) * freshness


def is_pinned_alert(
    category: Optional[str],
    published_at: Optional[datetime],
    scraped_at: Optional[datetime],
    now: Optional[datetime] = None,
    event_at: Optional[datetime] = None,
    event_until: Optional[datetime] = None,
) -> bool:
    """Awaria na szczycie feedu tylko wtedy, gdy dotyczy najbliższych godzin."""
    if not category or "awari" not in category.lower():
        return False
    now = now or datetime.utcnow()

    if event_at:
        if event_until and now > event_until:
            return False  # po zdarzeniu
        hours_ahead = (event_at - now).total_seconds() / 3600
        return hours_ahead <= PIN_LOOKAHEAD_H

    timestamp = published_at or scraped_at
    if timestamp is None:
        return False
    return (now - timestamp).total_seconds() / 3600 <= AWARIA_PIN_HOURS


# --- deduplikacja ------------------------------------------------------------

# Powyżej tego podobieństwa zbiorów słów uznajemy dwa wpisy za ten sam materiał
SIMILARITY_THRESHOLD = 0.72

# Słowa zbyt częste, by cokolwiek różnicowały
_STOPWORDS = frozenset({
    "the", "i", "w", "we", "z", "ze", "na", "do", "o", "od", "od", "po", "za",
    "u", "a", "e", "przy", "dla", "oraz", "lub", "to", "jest", "sie", "sa",
    "gmina", "gminie", "gminy", "wiejska", "region", "ul", "ulica", "ulice",
})

_WORD_RE = re.compile(r"[0-9a-ząćęłńóśźż]+")


def _tokens(text: str) -> frozenset[str]:
    """Zbiór znaczących słów — bez ogonków, emoji i interpunkcji."""
    flat = unicodedata.normalize("NFKD", (text or "").lower())
    words = _WORD_RE.findall(flat)
    return frozenset(w for w in words if len(w) > 2 and w not in _STOPWORDS)


def _similarity(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def dedup_text(article) -> str:
    """
    Materiał wpisu w postaci, w jakiej porównujemy go z innymi. Termin zdarzenia
    wchodzi do sygnatury osobno — dwa wyłączenia w Rybnie mają identyczny tytuł
    („Wyłączenie planowane - Region Mława - Rybno gmina wiejska") i różnią się
    wyłącznie datą i listą ulic.
    """
    body = (article.content or article.summary or "")[:300]
    base = f"{article.title or ''} {body}"
    event_at = getattr(article, "event_at", None)
    return f"{event_at:%Y-%m-%d %H:%M} {base}" if event_at else base


D = TypeVar("D")


def collapse_duplicates(items: Iterable[D], text_of: Callable[[D], str]) -> list[D]:
    """
    Ten sam materiał z dwóch źródeł zostawia raz — wygrywa pozycja wcześniejsza,
    więc kolejność wejściowa musi już być rankingiem.

    Powstało po tym, jak jedno wyłączenie prądu w Rybnie stanęło w feedzie dwa
    razy obok siebie (kanał „planowane" i „bieżące" Energi), oba jako awaria.
    Deduplikacja po `external_id` łapie tylko wpisy o wspólnym identyfikatorze —
    to jest siatka bezpieczeństwa na przedruki między źródłami.
    """
    kept: list[D] = []
    signatures: list[frozenset[str]] = []

    for item in items:
        signature = _tokens(text_of(item))
        if signature and any(
            _similarity(signature, seen) >= SIMILARITY_THRESHOLD for seen in signatures
        ):
            continue
        kept.append(item)
        signatures.append(signature)

    return kept


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
