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
            else:
                continue
            if _excused(lines, idx):
                continue
            hits.append((str(rel), idx + 1, why, line.strip()))
    return hits


def main() -> int:
    print("=" * 78)
    print("Strażnik strefy czasowej — naiwny UTC pokazywany bez konwersji")
    print("=" * 78)

    hits = scan()
    if not hits:
        print("\n✓ Czysto: każdy moment z bazy przechodzi przez warstwę czasu")
        print("  (services/time_span.py: to_local / local_day_bounds / when_label)")
        return 0

    print(f"\n✗ {len(hits)} miejsc(a) omijają warstwę czasu:\n")
    for rel, no, why, code in hits:
        print(f"  {rel}:{no}  [{why}]")
        print(f"      {code}")
    print("\nNapraw przez `to_local(...)` / `local_day_bounds()` / `when_label(...)`")
    print("albo — gdy surowa wartość jest tam poprawna — dopisz w tej linii")
    print("`# tz-ok: <powód>`. Powód jest obowiązkowy.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
