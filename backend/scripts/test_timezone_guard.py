"""
Strażnik strefy czasowej — reguła sprawdzalna kodem sprawdzana przez kod.

Baza trzyma naiwny UTC, mieszkaniec i model mówią czasem lokalnym. Zapowiedź
bez godziny stoi jako lokalna PÓŁNOC, czyli 22:00 UTC dnia POPRZEDNIEGO.
Kto tego nie pamięta, przesuwa datę o dobę — i nie dowiaduje się o tym z testu,
tylko od mieszkańca.

Tak było 4–5.09.2026 z jednym wpisem: „VI Leśny Nocny Bieg" (5.09, całodniowy,
w bazie `2026-09-04 22:00`). W piątek briefing napisał „Dziś odbędzie się",
w sobotę — w dniu biegu — wpis zniknął z kalendarza. Ten sam rekord, ten sam
błąd, dwa przeciwne objawy, dwa różne pliki. Kopii tej wiedzy było wtedy pięć.

Ten test skanuje `src/` i pada na dwóch wzorcach:

  1. FORMATOWANIE momentu z bazy bez konwersji — `event_date.strftime(...)`,
     `.day`, `.month`, `.date()`. Data z UTC pokazana człowiekowi to data,
     która przez dwie godziny na dobę jest o dzień wcześniejsza.
  2. DOBA liczona w UTC — `utcnow().replace(hour=0, ...)`. Granica dnia
     w UTC nie jest granicą dnia; okno „dziś" wypuszcza wydarzenie całodniowe
     dzisiejsze i wpuszcza jutrzejsze.
  3. TERMIN porównany z chwilą „teraz" — `event_date >= now`. Zapowiedź bez
     godziny stoi na lokalnej północy, więc taki warunek uznaje ją za przeszłą
     o 00:01 w dniu, w którym się odbywa. Granicą ma być początek doby.
  4. ZAPIS momentu zależny od strefy procesu — `time.mktime(...)` i
     `fromtimestamp(...)` bez `tz`. Kontener ma `TZ=Europe/Warsaw`, więc wynik
     jest lokalny, a trafia do kolumny naiwnego UTC. Tak do 11.10.2026 stały
     wpisy RSS (+1 h latem) i posty z Facebooka (+2 h). Zamiast tego:
     `time_span.from_epoch(...)`.

Wyjątek zapisuje się w kodzie, nie tutaj: dopisek `# tz-ok: <powód>` w tej samej
linii albo w komentarzu bezpośrednio nad nią. Powód jest obowiązkowy — chodzi
o to, żeby następny czytelnik wiedział, dlaczego akurat tam surowa wartość jest
poprawna. Lista wyjątków wewnątrz testu rozjechałaby się przy pierwszym
przeniesieniu kodu; dopisek jedzie razem z linią, której dotyczy.

Pola będące DATĄ KALENDARZOWĄ, a nie momentem (`session_date` sesji Rady,
`DailySummary.date`), są poza zakresem: to identyfikator dnia, nie chwila.

Użycie: python -m scripts.test_timezone_guard
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "src"

# Kolumny niosące MOMENT w czasie (naiwny UTC z bazy).
MOMENT_FIELDS = [
    "event_date", "event_at", "event_until", "end_date",
    "published_at", "created_at", "fetched_at", "scraped_at",
    "sent_at", "generated_at", "alert_pushed_at", "adopted_at",
]

# Co robimy z momentem, żeby zobaczyć jego dzień albo godzinę.
_ACCESSORS = r"strftime|day|month|year|date|hour|minute"

_FORMAT_RE = re.compile(
    rf"\b(?:{'|'.join(MOMENT_FIELDS)})\b\s*\.\s*(?:{_ACCESSORS})\b"
)

# Doba wyznaczona w UTC. Łapiemy oba zapisy: przez `utcnow()` i przez zmienną
# (`now = datetime.utcnow()` wyżej, potem `now.replace(hour=0, ...)`).
_MIDNIGHT_RE = re.compile(r"\.replace\(\s*hour\s*=\s*0\s*,\s*minute\s*=\s*0")

# Termin zdarzenia porównany wprost z „teraz". Bieg całodniowy przestawał
# istnieć o 00:01 w dniu biegu — tak zniknął z `upcoming_events` agenta,
# ze świeżego feedu Redaktora i z tygodniowego newslettera.
# ⚠️ Wzorzec celuje w GOŁE „teraz". `event_at >= now - timedelta(days=1)`
# w `publishable_conditions` to karencja po terminie i jest poprawne —
# stąd negatywny lookahead na działanie za `now`.
_EVENT_NOW_RE = re.compile(
    r"\b(?:event_date|event_at)\s*>=\s*(?:ctx\.)?(?:now\b|datetime\.utcnow\(\))(?!\s*[-+])"
)

# Zapis momentu przez strefę procesu. `utcfromtimestamp` nie pasuje (\b), a linia
# z `tz=`/`timezone.utc`/`ZoneInfo` jest jawna co do strefy — patrz `_TZ_ARG_RE`.
_EPOCH_RE = re.compile(r"\bmktime\(|\bfromtimestamp\(")
_TZ_ARG_RE = re.compile(r"\btz\s*=|timezone\.utc|ZoneInfo\(")

_OK_RE = re.compile(r"#\s*tz-ok:\s*\S")

# Konwersja stojąca w tej samej linii zdejmuje zarzut — `to_local(x).day`
# jest dokładnie tym, o co nam chodzi.
_CONVERTED_RE = re.compile(r"\b(?:to_local|_local|astimezone|local_day_bounds)\s*\(")


def _skip(path: Path) -> bool:
    parts = path.parts
    return "__pycache__" in parts or path.name.startswith(".")


def _excused(lines: list[str], idx: int) -> bool:
    """Czy linia ma zwolnienie — w sobie albo w komentarzu tuż nad nią."""
    if _OK_RE.search(lines[idx]):
        return True
    back = idx - 1
    while back >= 0 and lines[back].lstrip().startswith("#"):
        if _OK_RE.search(lines[back]):
            return True
        back -= 1
    return False


def scan() -> list[tuple[str, int, str, str]]:
    hits = []
    for path in sorted(ROOT.rglob("*.py")):
        if _skip(path):
            continue
        rel = path.relative_to(ROOT.parent)
        lines = path.read_text().splitlines()
        for idx, line in enumerate(lines):
            if _CONVERTED_RE.search(line) or line.lstrip().startswith("#"):
                continue
            if _FORMAT_RE.search(line):
                why = "moment z bazy bez konwersji"
            elif _MIDNIGHT_RE.search(line):
                why = "doba liczona w UTC"
            elif _EVENT_NOW_RE.search(line):
                why = "termin porównany z „teraz”, nie z początkiem doby"
            elif _EPOCH_RE.search(line) and not _TZ_ARG_RE.search(line):
                why = "znacznik czasu przez strefę procesu (mktime/fromtimestamp bez tz)"
            else:
                continue
            if _excused(lines, idx):
                continue
            hits.append((str(rel), idx + 1, why, line.strip()))
    return hits


def epoch_behaviour() -> list[str]:
    """Zachowanie, nie tylko wzorzec: pod strefą produkcji (`TZ=Europe/Warsaw`)
    znacznik UTC ma zostać UTC — latem i zimą. Do 11.10.2026 RSS dawał tu +1 h,
    a Facebook +2 h (Apify zwraca unix timestamp, który `fromtimestamp` bez
    strefy zamieniał na czas lokalny kontenera)."""
    import os
    import time
    from datetime import datetime

    sys.path.insert(0, str(ROOT.parent))
    from src.scrapers.rss_scraper import RSSFeedScraper
    from src.services.time_span import from_epoch

    old_tz = os.environ.get("TZ")
    os.environ["TZ"] = "Europe/Warsaw"
    time.tzset()
    errors = []
    try:
        scraper = RSSFeedScraper.__new__(RSSFeedScraper)
        for utc in (datetime(2026, 10, 10, 10, 0), datetime(2026, 1, 15, 10, 0)):
            # Krotka JAK z feedparsera: `time.gmtime` ma `tm_isdst=0`. Z `timetuple()`
            # (`tm_isdst=-1`) stary `mktime` trafiał przypadkiem — błąd był niewidoczny
            import calendar
            struct = time.gmtime(calendar.timegm(utc.timetuple()))
            parsed = scraper._parse_date({"published_parsed": struct})
            if parsed != utc:
                errors.append(f"RSS {utc:%d.%m %H:%M} UTC → {parsed}")
        # 1791688503 = post Syli z 11.10.2026, 03:15:03 UTC (dataset Apify)
        if from_epoch(1791688503) != datetime(2026, 10, 11, 3, 15, 3):
            errors.append(f"from_epoch → {from_epoch(1791688503)}")
    finally:
        if old_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old_tz
        time.tzset()
    return errors


def main() -> int:
    print("=" * 78)
    print("Strażnik strefy czasowej — naiwny UTC pokazywany bez konwersji")
    print("=" * 78)

    errors = epoch_behaviour()
    if errors:
        print("\n✗ Znacznik czasu przesunięty strefą procesu:")
        for e in errors:
            print(f"  {e}")
        return 1
    print("\n✓ Znaczniki UTC (RSS, Facebook) zostają UTC pod TZ=Europe/Warsaw")

    hits = scan()
    if not hits:
        print("\n✓ Czysto: każdy moment z bazy przechodzi przez warstwę czasu")
        print("  (services/time_span.py: to_local / local_day_bounds / when_label)")
        return 0

    print(f"\n✗ {len(hits)} miejsc(a) omijają warstwę czasu:\n")
    for rel, no, why, code in hits:
        print(f"  {rel}:{no}  [{why}]")
        print(f"      {code}")
    print("\nNapraw przez `to_local(...)` / `local_day_bounds()` / `when_label(...)` / `from_epoch(...)`")
    print("albo — gdy surowa wartość jest tam poprawna — dopisz w tej linii")
    print("`# tz-ok: <powód>`. Powód jest obowiązkowy.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
