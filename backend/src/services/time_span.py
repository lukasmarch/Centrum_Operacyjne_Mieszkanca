"""
Zakres godzin wyczytany z treści komunikatu (2026-08-24)

Powstało z rozdzielenia `services/weather_alert.py`, gdzie ten parser mieszkał
od 2.08.2026. Okazało się, że tego samego zapisu potrzebuje coś zupełnie innego
niż pogoda: 24.08 o 6:08 push wysłał alarm o wyłączeniu prądu, które skończyło
się poprzedniego wieczoru. Post Zakładu Gospodarki Komunalnej mówił „W godzinach
16.00 - 19.00", ale bez daty — model kategoryzujący nie zaryzykował wpisania
`event_at`, więc `alert_policy` mierzyła wiek od publikacji (24 h) i nazajutrz
rano wpis wciąż był „na czasie".

Bramka „po zdarzeniu" w `alert_policy.is_timely` istniała od początku; brakowało
jej wyłącznie `event_until`. Stąd ten moduł: godziny z treści to dana, a nie
sprawa pogody.

Dzień odniesienia to publikacja — „w godzinach 16:00–19:00" znaczy tyle, co
dzień, w którym to napisano. Zakres przez północ kończy się nazajutrz.

⚠️ Ten parser NIE ocenia, czy tekst w ogóle opisuje zdarzenie. „Biuro czynne
w godzinach 8:00–16:00" zwróci poprawny zakres — to wołający musi wcześniej
wiedzieć, że czyta ogłoszenie o awarii (patrz `alert_policy.evaluate`, gdzie
rodzaj zdarzenia rozstrzyga się PRZED sięgnięciem tutaj).

Funkcje są czyste (bez bazy i sieci) — `scripts/test_alert_policy.py`,
sekcja „Termin wyczytany z treści komunikatu".
"""
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

# Komunikaty podają czas lokalny, baza trzyma naiwny UTC (jak reszta projektu).
LOCAL_TZ = ZoneInfo("Europe/Warsaw")


def to_utc(local_naive: datetime) -> datetime:
    return local_naive.replace(tzinfo=LOCAL_TZ).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def to_local(utc_naive: datetime) -> datetime:
    return utc_naive.replace(tzinfo=ZoneInfo("UTC")).astimezone(LOCAL_TZ).replace(tzinfo=None)


def flat(text: Optional[str]) -> str:
    """
    Tekst bez ogonków i wielkości liter. „ł" podmieniane ręcznie — jako jedyna
    polska litera nie rozkłada się w NFKD (ta sama pułapka co w `alert_policy`).
    """
    lowered = (text or "").lower().replace("ł", "l")
    stripped = unicodedata.normalize("NFKD", lowered)
    return "".join(c for c in stripped if not unicodedata.combining(c))


_SEP = r"[-–—]"          # zakres bywa myślnikiem, półpauzą albo pauzą
# Godzina bywa pisana z dwukropkiem („16:00" — IMGW, Energa) albo z kropką
# („16.00" — tak pisze ZGK i połowa profili na Facebooku). Do 24.08.2026
# wzorzec znał tylko dwukropek, więc post o wyłączeniu prądu przechodził bez
# terminu i alarmował dzień po fakcie.
_H = r"(\d{1,2})[:.](\d{2})"
_D = r"(\d{1,2})\.(\d{1,2})(?:\.(\d{4}))?"

# Format urzędowy IMGW: „od godz. 12:00 dnia 01.08.2026 do godz. 01:00 dnia 02.08.2026"
_FULL_RE = re.compile(
    rf"od\s+godz\w*\.?\s*{_H}\s+dnia\s+{_D}\s+do\s+godz\w*\.?\s*{_H}\s+dnia\s+{_D}"
)

# Przedruk na profilu: „Dziś, w godzinach 15:00–01:00" / „od 15:00 do 01:00”
# Po myślniku bywa spacja („16.00 - 19.00"), a stary wzorzec oczekiwał drugiej
# godziny bezpośrednio za separatorem — łapał więc tylko zapis zbity („15:00–01:00").
_SPAN_RE = re.compile(
    rf"(?:w\s+godzinach|w\s+godz\w*\.?|od\s+godz\w*\.?|od)\s*{_H}\s*(?:{_SEP}\s*|\s+do\s+(?:godz\w*\.?\s*)?){_H}"
)

# Sam koniec: „obowiązuje do godz. 01:00”, „ważne do 20:00”
_UNTIL_RE = re.compile(rf"(?:do|obowiazuje\s+do|wazne\s+do)\s+(?:godz\w*\.?\s*)?{_H}")


def _build(local_day: datetime, hour: int, minute: int) -> datetime:
    return local_day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def parse_span(
    text: Optional[str],
    reference_at: Optional[datetime],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Zakres godzin z treści → (początek, koniec) w UTC.

    `reference_at` (UTC, zwykle `published_at`) jest dniem odniesienia dla
    zapisów bez daty — „dziś, w godzinach 15:00–01:00" znaczy tyle, co dzień
    publikacji. Zakres przez północ kończy się nazajutrz; bez tego alert
    do 01:00 „wygasał" przed startem.
    """
    if not reference_at:
        return None, None

    text_flat = flat(text)
    day = to_local(reference_at)

    match = _FULL_RE.search(text_flat)
    if match:
        h1, m1, d1, mo1, y1, h2, m2, d2, mo2, y2 = match.groups()
        try:
            start = datetime(int(y1 or day.year), int(mo1), int(d1), int(h1), int(m1))
            end = datetime(int(y2 or day.year), int(mo2), int(d2), int(h2), int(m2))
        except ValueError:
            return None, None
        return to_utc(start), to_utc(end)

    match = _SPAN_RE.search(text_flat)
    if match:
        h1, m1, h2, m2 = (int(g) for g in match.groups())
        try:
            start = _build(day, h1, m1)
            end = _build(day, h2, m2)
        except ValueError:
            return None, None
        if end <= start:
            end += timedelta(days=1)
        return to_utc(start), to_utc(end)

    match = _UNTIL_RE.search(text_flat)
    if match:
        h2, m2 = int(match.group(1)), int(match.group(2))
        try:
            end = _build(day, h2, m2)
        except ValueError:
            return None, None
        if end <= day:
            end += timedelta(days=1)
        return None, to_utc(end)

    return None, None
