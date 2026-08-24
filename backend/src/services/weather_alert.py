"""
Ostrzeżenia meteorologiczne — od kiedy do kiedy obowiązują (2026-08-02)

Ostrzeżenie IMGW ma ważność wpisaną w treść i nigdzie indziej. Bez niej wpis żyje
w serwisie jak każda inna wiadomość i briefing czyta go nazajutrz jako aktualny:
2.08.2026 o 11:30 briefing ostrzegał przed burzami na podstawie posta z 1.08,
w którym stało „dziś, w godzinach 15:00–01:00" — alert wygasł w nocy, a widget
pogody obok pokazywał zerową szansę opadów.

Energa ma ten sam problem rozwiązany w `services/energa.py`, ale tam termin
parsuje się przy scrapowaniu jednego znanego źródła. Ostrzeżenie meteo potrafi
przyjść z dowolnego kanału (profil FB, RSS radia), więc ważność liczymy z tekstu
po kategoryzacji — i tak samo zapisujemy w `event_at` / `event_until`, żeby
`feed_policy` wygaszał je tym samym mechanizmem, co wyłączenia prądu.

Funkcje są czyste (bez bazy i sieci) — `scripts/test_weather_alert.py`.
"""
import re
from datetime import datetime, timedelta
from typing import Optional

from src.services.time_span import flat as _flat, parse_span

# Ostrzeżenie bez czytelnego terminu ważności. IMGW wydaje je na kilkanaście
# godzin; doba to już relacja, nie ostrzeżenie.
DEFAULT_VALIDITY_H = 12

# Ile godzin po wygaśnięciu wpis jeszcze coś mieszkańcowi mówi („czy to była ta
# burza, o której pisali"). Później nie ma czego ostrzegać.
KEEP_AFTER_END_H = 3


# --- rozpoznanie: czy to w ogóle ostrzeżenie pogodowe ------------------------

# Wzorce działają na tekście BEZ ogonków (patrz `_flat`), stąd „burz", „oblodzeni".
_PHENOMENA = (
    r"burz\w*", r"grad\w*", r"upal\w*", r"upaln\w*", r"wichur\w*", r"huragan\w*",
    r"silny\s+wiatr", r"silnego\s+wiatru", r"poryw\w*\s+wiatru",
    r"oblodzeni\w*", r"gololedzi\w*", r"przymrozk\w*", r"mroz\w*", r"marznac\w*",
    r"intensywn\w*\s+opad\w*", r"ulew\w*", r"nawalnic\w*",
    r"zawiej\w*", r"zamiec\w*", r"sniezyc\w*", r"opad\w*\s+sniegu",
    r"gest\w*\s+mgl\w*", r"mgl\w*\s+intensywn\w*",
)
_PHENOMENA_RE = re.compile("|".join(_PHENOMENA))

# Samo „ostrzeżenie" nie wystarcza — policja ostrzega przed oszustami, sanepid
# przed kąpielą w jeziorze. Musi paść zjawisko meteorologiczne.
_WARNING_RE = re.compile(r"ostrzezeni\w*|alert\w*|uwaga|komunikat\s+meteo\w*")

# Instytucja wydająca — sama w sobie mocny sygnał, ale nadal wymaga zjawiska:
# IMGW podaje też prognozy bez ostrzeżenia.
_ISSUER_RE = re.compile(r"\bimgw\b|instytut\w*\s+meteorologii|\brcb\b|centrum\s+bezpieczenstwa")


def is_weather_alert(title: Optional[str], content: Optional[str] = None) -> bool:
    """Czy wpis jest ostrzeżeniem przed zjawiskiem atmosferycznym."""
    haystack = _flat(f"{title or ''}\n{content or ''}")
    if not _PHENOMENA_RE.search(haystack):
        return False
    return bool(_WARNING_RE.search(haystack) or _ISSUER_RE.search(haystack))


# --- ważność: od kiedy do kiedy ---------------------------------------------


def parse_validity(
    text: Optional[str],
    published_at: Optional[datetime],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Okres obowiązywania ostrzeżenia → (początek, koniec) w UTC.

    Sam odczyt godzin mieszka w `services/time_span.py` — 24.08.2026 okazało się,
    że tego samego zapisu potrzebuje push o wyłączeniu prądu, a nie jest to
    sprawa pogody.
    """
    return parse_span(text, published_at)


def validity_or_default(
    title: Optional[str],
    content: Optional[str],
    published_at: Optional[datetime],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Ważność ostrzeżenia, a gdy nie da się jej wyczytać — DEFAULT_VALIDITY_H od
    publikacji. Alert bez końca ważności byłby gorszy niż alert z domyślnym:
    właśnie taki wisiał w briefingu dobę po wygaśnięciu.
    """
    start, end = parse_validity(f"{title or ''}\n{content or ''}", published_at)
    if end is None and published_at is not None:
        end = published_at + timedelta(hours=DEFAULT_VALIDITY_H)
    return start, end


def expired(
    title: Optional[str],
    content: Optional[str],
    published_at: Optional[datetime],
    event_until: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> bool:
    """
    Czy ostrzeżenie przestało obowiązywać (z zapasem KEEP_AFTER_END_H).

    `event_until` z bazy ma pierwszeństwo, ale liczymy też w locie — wpisy sprzed
    wdrożenia tego modułu mają to pole puste i inaczej zostałyby w briefingu.
    """
    now = now or datetime.utcnow()
    if not is_weather_alert(title, content):
        return False

    end = event_until
    if end is None:
        _, end = validity_or_default(title, content, published_at)
    if end is None:
        return False

    return now - end > timedelta(hours=KEEP_AFTER_END_H)
