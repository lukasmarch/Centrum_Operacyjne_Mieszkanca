"""
Wyłączenia prądu ENERGA-OPERATOR — normalizacja wpisów RSS (2026-07-27)

Feed daje surowy rekord: tytuł „Wyłączenie planowane - Region Mława - Rybno gmina
wiejska" i opis „Rybno gmina wiejska 27.07.2026 10:00-14:00 - Rybno ulice Kolonia…".
Trzy rzeczy, których nie ma wprost, a bez których feed się rozjeżdżał:

1. KIEDY — termin wyłączenia siedzi wyłącznie w treści. Bez `event_at` ranking
   i przypinanie liczyły wiek OGŁOSZENIA (bywa sprzed trzech tygodni) zamiast
   odległości do zdarzenia: wyłączenie na 31.07 wypadało z feedu 29.07.
2. TOŻSAMOŚĆ — to samo wyłączenie jest w obu kanałach (planowane i bieżące) pod
   tym samym `guid`, ale innym URL-em. Bez wspólnego `external_id` feed pokazywał
   je dwa razy obok siebie, oba przypięte jako awaria.
3. KONTEKST — w treści nie pada słowo „prąd", więc kategoryzacja AI zgadywała
   („wyłączenie drogi", „wyłączenie wody"). Prefiks dopisujemy na podstawie
   TERMINU (przed / w trakcie), nie kanału — kanał „bieżące" wozi też zapowiedzi.

Zastępuje trzy doraźne flagi w scraping_config (`treat_as_fresh`, `content_prefix`,
per-kanałowy opis) jednym: `item_parser: "energa"`.
"""
import re
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

# Energa podaje godziny czasu lokalnego, baza trzyma naiwny UTC (jak reszta
# projektu). Bez konwersji wyłączenie 10:00–14:00 „trwało" w bazie 12:00–16:00
# i przypięcie awarii rozjeżdżało się o dwie godziny.
LOCAL_TZ = ZoneInfo("Europe/Warsaw")


def _to_utc(local_naive: datetime) -> datetime:
    return local_naive.replace(tzinfo=LOCAL_TZ).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

# „Rybno gmina wiejska 27.07.2026 10:00-14:00 - Rybno ulice Kolonia od 25 do 27…"
WINDOW_RE = re.compile(
    r"(?P<d>\d{1,2})\.(?P<m>\d{1,2})\.(?P<y>\d{4})\s+"
    r"(?P<h1>\d{1,2}):(?P<min1>\d{2})\s*-\s*(?P<h2>\d{1,2}):(?P<min2>\d{2})"
)

# Oba kanały linkują to samo zdarzenie tym samym guid-em, innym URL-em:
#   …/wylaczenia-planowane?guid=f525fde4-…#d6r45
#   …/wylaczenia-biezace/plock?guid=f525fde4-…
GUID_RE = re.compile(r"guid=([0-9a-fA-F-]{36})")

# Ile godzin po zakończeniu wyłączenia wpis jeszcze ma sens (ktoś wraca do domu
# i sprawdza, czy to było planowe). Później nie ma po co go w ogóle pobierać.
KEEP_AFTER_END_H = 6


def parse_window(text: Optional[str]) -> tuple[Optional[datetime], Optional[datetime]]:
    """Termin wyłączenia z treści wpisu → (początek, koniec) w czasie LOKALNYM."""
    if not text:
        return None, None
    match = WINDOW_RE.search(text)
    if not match:
        return None, None
    g = match.groupdict()
    try:
        start = datetime(
            int(g["y"]), int(g["m"]), int(g["d"]), int(g["h1"]), int(g["min1"])
        )
        end = start.replace(hour=int(g["h2"]), minute=int(g["min2"]))
        # Wyłączenie przez północ ("22:00-06:00") kończy się nazajutrz
        if end <= start:
            end += timedelta(days=1)
        return start, end
    except ValueError:
        return None, None


def canonical_id(url: Optional[str]) -> Optional[str]:
    """Wspólny identyfikator zdarzenia dla obu kanałów."""
    if not url:
        return None
    match = GUID_RE.search(url)
    return f"energa_{match.group(1).lower()}" if match else None


def _context_line(local_start: Optional[datetime], local_end: Optional[datetime], state: str) -> str:
    """Zdanie kontekstu dla kategoryzacji AI — o stanie zdarzenia decyduje termin."""
    if local_start is None:
        return "ENERGA-OPERATOR — przerwa w dostawie energii elektrycznej (wyłączenie prądu)."

    termin = local_start.strftime("%d.%m.%Y %H:%M")
    if local_end:
        termin += f"–{local_end.strftime('%H:%M')}"

    if state == "trwa":
        return (
            f"ENERGA-OPERATOR — TRWA przerwa w dostawie energii elektrycznej "
            f"(wyłączenie prądu), {termin}."
        )
    if state == "zapowiedziane":
        return (
            f"ENERGA-OPERATOR — zapowiedziane wyłączenie prądu "
            f"(planowana przerwa w dostawie energii elektrycznej), {termin}."
        )
    return f"ENERGA-OPERATOR — zakończona przerwa w dostawie energii elektrycznej, {termin}."


def enrich(articles: list[dict], now: Optional[datetime] = None) -> list[dict]:
    """
    Uzupełnia wpisy Energi o termin zdarzenia (UTC), wspólny identyfikator i kontekst.
    Odrzuca wyłączenia, które skończyły się ponad KEEP_AFTER_END_H temu.
    """
    now = now or datetime.utcnow()
    enriched: list[dict] = []

    for article in articles:
        body = article.get("content") or article.get("summary") or ""
        local_start, local_end = parse_window(f"{article.get('title', '')} {body}")

        start = _to_utc(local_start) if local_start else None
        end = _to_utc(local_end) if local_end else None

        if end and now - end > timedelta(hours=KEEP_AFTER_END_H):
            continue  # zdarzenie minęło — nie zaśmiecamy bazy

        if start is None:
            state = "nieznany"
        elif end and start <= now <= end:
            state = "trwa"
        elif start > now:
            state = "zapowiedziane"
        else:
            state = "zakonczone"

        article["event_at"] = start
        article["event_until"] = end
        article["content"] = f"{_context_line(local_start, local_end, state)}\n\n{body}".strip()

        guid = canonical_id(article.get("url"))
        if guid:
            article["external_id"] = guid

        enriched.append(article)

    return enriched
