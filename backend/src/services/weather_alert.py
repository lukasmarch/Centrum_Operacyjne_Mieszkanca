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
import unicodedata
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

# Komunikaty podają czas lokalny, baza trzyma naiwny UTC (jak reszta projektu).
LOCAL_TZ = ZoneInfo("Europe/Warsaw")

# Ostrzeżenie bez czytelnego terminu ważności. IMGW wydaje je na kilkanaście
# godzin; doba to już relacja, nie ostrzeżenie.
DEFAULT_VALIDITY_H = 12

# Ile godzin po wygaśnięciu wpis jeszcze coś mieszkańcowi mówi („czy to była ta
# burza, o której pisali"). Później nie ma czego ostrzegać.
KEEP_AFTER_END_H = 3


def _to_utc(local_naive: datetime) -> datetime:
    return local_naive.replace(tzinfo=LOCAL_TZ).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def _to_local(utc_naive: datetime) -> datetime:
    return utc_naive.replace(tzinfo=ZoneInfo("UTC")).astimezone(LOCAL_TZ).replace(tzinfo=None)


def _flat(text: Optional[str]) -> str:
    """
    Tekst bez ogonków i wielkości liter. „ł" podmieniane ręcznie — jako jedyna
    polska litera nie rozkłada się w NFKD (ta sama pułapka co w `alert_policy`).
    """
    lowered = (text or "").lower().replace("ł", "l")
    stripped = unicodedata.normalize("NFKD", lowered)
    return "".join(c for c in stripped if not unicodedata.combining(c))


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

_SEP = r"[-–—]"          # zakres bywa myślnikiem, półpauzą albo pauzą
_H = r"(\d{1,2}):(\d{2})"
_D = r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?"

# Format urzędowy IMGW: „od godz. 12:00 dnia 01.08.2026 do godz. 01:00 dnia 02.08.2026"
_FULL_RE = re.compile(
    rf"od\s+godz\w*\.?\s*{_H}\s+dnia\s+{_D}\s+do\s+godz\w*\.?\s*{_H}\s+dnia\s+{_D}"
)

# Przedruk na profilu: „Dziś, w godzinach 15:00–01:00" / „od 15:00 do 01:00”
_SPAN_RE = re.compile(
    rf"(?:w\s+godzinach|w\s+godz\w*\.?|od\s+godz\w*\.?|od)\s*{_H}\s*(?:{_SEP}|\s+do\s+(?:godz\w*\.?\s*)?){_H}"
)

# Sam koniec: „obowiązuje do godz. 01:00”, „ważne do 20:00”
_UNTIL_RE = re.compile(rf"(?:do|obowiazuje\s+do|wazne\s+do)\s+(?:godz\w*\.?\s*)?{_H}")


def _build(local_day: datetime, hour: int, minute: int) -> datetime:
    return local_day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def parse_validity(
    text: Optional[str],
    published_at: Optional[datetime],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Okres obowiązywania ostrzeżenia → (początek, koniec) w UTC.

    `published_at` (UTC) jest dniem odniesienia dla zapisów bez daty — „dziś,
    w godzinach 15:00–01:00" znaczy tyle, co dzień publikacji. Zakres przez
    północ kończy się nazajutrz; bez tego alert do 01:00 „wygasał" przed startem.
    """
    if not published_at:
        return None, None

    flat = _flat(text)
    day = _to_local(published_at)

    match = _FULL_RE.search(flat)
    if match:
        h1, m1, d1, mo1, y1, h2, m2, d2, mo2, y2 = match.groups()
        try:
            start = datetime(int(y1 or day.year), int(mo1), int(d1), int(h1), int(m1))
            end = datetime(int(y2 or day.year), int(mo2), int(d2), int(h2), int(m2))
        except ValueError:
            return None, None
        return _to_utc(start), _to_utc(end)

    match = _SPAN_RE.search(flat)
    if match:
        h1, m1, h2, m2 = (int(g) for g in match.groups())
        try:
            start = _build(day, h1, m1)
            end = _build(day, h2, m2)
        except ValueError:
            return None, None
        if end <= start:
            end += timedelta(days=1)
        return _to_utc(start), _to_utc(end)

    match = _UNTIL_RE.search(flat)
    if match:
        h2, m2 = int(match.group(1)), int(match.group(2))
        try:
            end = _build(day, h2, m2)
        except ValueError:
            return None, None
        if end <= day:
            end += timedelta(days=1)
        return None, _to_utc(end)

    return None, None


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
