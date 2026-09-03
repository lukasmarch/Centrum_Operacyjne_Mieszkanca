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


# --- data wprost w tekście --------------------------------------------------
#
# 3.09.2026: ten sam post („📅 16 września 2026 r. ⏰ godz. 8:00–11:30") puszczony
# przez model trzy razy dał termin w 2 przebiegach na 3, godzinę końca w 0 na 3.
# W bazie 27 na 104 wpisów z datą we własnym tytule nie miało `event_at`, więc
# feed liczył je jak świeże wiadomości, a briefing otworzył dzień poborem krwi
# za trzynaście dni, mając w materiale bieg na jutro. Data, która stoi w tekście
# wprost, jest zadaniem dla kodu — ta sama zasada, którą godziny dostały 24.08
# (`parse_span`), a odpowiedzi modelu 12.08 (`ground_categorization`).

_MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5,
    "czerwca": 6, "lipca": 7, "sierpnia": 8, "wrzesnia": 9,
    "pazdziernika": 10, "listopada": 11, "grudnia": 12,
}
_MONTH_ALT = "|".join(_MONTHS)

# „16 września 2026 r.", „16 września", „16.09.2026" — numeryczny zapis WYMAGA
# roku: bez niego „8.00" (godzina po kropce, tak pisze ZGK) czytałoby się jako
# ósmy dzień miesiąca zerowego.
_DATE_RE = re.compile(
    rf"\b(\d{{1,2}})\s+({_MONTH_ALT})(?:\s+(\d{{4}}))?\b"
    rf"|\b(\d{{1,2}})\.(\d{{1,2}})\.(\d{{4}})\b"
)

# Godziny przy dacie: „godz. 8:00–11:30", „o godz. 15:00", „o 15:00",
# „w godzinach 10:00-14:00". Szukane w oknie ZA datą, nie w całym tekście —
# „Pełna treść u źródła" i godziny urzędowania na końcu posta to nie termin.
_HOURS_AFTER_DATE_RE = re.compile(
    rf"(?:godz\w*\.?|o\s+godz\w*\.?|o|w\s+godzinach|od)\s*{_H}(?:\s*(?:{_SEP}|do)\s*{_H})?"
)
_HOURS_WINDOW = 60
_SENTENCE_END_RE = re.compile(r"[.!?]\s+(?=[a-z])|\n")

# Ile dni w przód zapowiedź może sięgać. Ten sam bezpiecznik co
# `article_processor._parse_event_time` dla odczytu modelu (pół roku).
MAX_AHEAD_DAYS = 180


def parse_date_span(
    text: Optional[str],
    reference_at: Optional[datetime],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Pierwsza data z tekstu, która nie jest jeszcze za nami → (początek, koniec) w UTC.

    „Nie za nami" liczy się względem DNIA PUBLIKACJI (`reference_at`, UTC),
    nie względem teraz: kategoryzacja chodzi po zaległościach, a wpis sprzed
    tygodnia ma prawo zapowiadać zdarzenie sprzed pięciu dni. Data wcześniejsza
    niż publikacja to relacja („30 sierpnia odbyły się dożynki") — wtedy
    zwracamy (None, None), bo relacji nie wolno zapisać jako zapowiedzi.

    Rok bez podania: ten, w którym data wypada nie wcześniej niż publikacja
    („15 stycznia" w poście grudniowym to styczeń przyszłego roku).

    Sama data bez godziny → lokalna PÓŁNOC, jak zapisuje kategoryzacja
    (zapowiedź całodniowa trwa do końca swojej doby — patrz `_event_is_over`).
    Godziny bierzemy wyłącznie z okna tuż za datą.
    """
    if not reference_at or not text:
        return None, None

    text_flat = flat(text)
    published_day = to_local(reference_at).date()

    for match in _DATE_RE.finditer(text_flat):
        if match.group(2):
            day, month = int(match.group(1)), _MONTHS[match.group(2)]
            year = int(match.group(3)) if match.group(3) else None
        else:
            day, month, year = int(match.group(4)), int(match.group(5)), int(match.group(6))

        candidates = [year] if year else [published_day.year, published_day.year + 1]
        local_date = None
        for y in candidates:
            try:
                d = datetime(y, month, day).date()
            except ValueError:
                continue
            if d >= published_day:
                local_date = d
                break
        if local_date is None:
            continue  # relacja albo śmieć — patrz następną datę
        if (local_date - published_day).days > MAX_AHEAD_DAYS:
            continue

        start = datetime(local_date.year, local_date.month, local_date.day)
        end = None
        # Godziny liczą się tylko w TYM SAMYM ZDANIU co data. Granica zdania
        # to kropka ze spacją i literą za nią („. Biuro czynne w godzinach
        # 7:30-15:30" to godziny urzędowania z następnego zdania), a nie każda
        # kropka — „godz. 8:00" i „2026 r. ⏰" mają kropkę w środku zwrotu.
        window = text_flat[match.end(): match.end() + _HOURS_WINDOW]
        window = _SENTENCE_END_RE.split(window, maxsplit=1)[0]
        hours = _HOURS_AFTER_DATE_RE.search(window)
        if hours:
            h1, m1, h2, m2 = hours.groups()
            try:
                start = start.replace(hour=int(h1), minute=int(m1))
                if h2:
                    end = start.replace(hour=int(h2), minute=int(m2))
                    if end <= start:
                        end += timedelta(days=1)
            except ValueError:
                start = datetime(local_date.year, local_date.month, local_date.day)
                end = None
        return to_utc(start), (to_utc(end) if end else None)

    return None, None
