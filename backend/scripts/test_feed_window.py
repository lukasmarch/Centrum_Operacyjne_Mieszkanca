"""
Strażnik okna feedu (`feed_policy.in_feed_window`).

Pytanie, na które ten test odpowiada: CO DZIŚ NALEŻY DO FEEDU. Polityka rozjechała
się tu trzykrotnie i za każdym razem w tę samą stronę — do feedu wracała przyszłość:
  27.07.2026  „drugie życie zapowiedzi" w rankingu (`_reference_time`),
  25.08.2026  `still_relevant_event` w oknie — zapowiedź stoi w feedzie od
              ogłoszenia aż do terminu, choćby ogłoszenie miało trzy tygodnie,
  wrzesień    coraz więcej wpisów dostaje `event_at` (czytanie daty z treści),
              więc ta sama reguła obejmowała ich coraz więcej.
Pomiar 15.09.2026: na 35 wpisów feedu 15 dotyczyło przyszłości (zebranie ogłoszone
21.08, certyfikat QMP z 7.08), a 3 były starsze niż dwie doby, bo `scraped_at`
odmładza wpis przy każdym ponownym pobraniu.

Reguły (ustalone 16.09.2026):
  - wiadomość żyje trzy doby lokalne od PUBLIKACJI,
  - zapowiedź czeka w kalendarzu i wchodzi do feedu w przeddzień terminu,
  - wyjątek: awaria i sprawa urzędowa DOTYCZĄCA GMINY — od ogłoszenia.

Przypadki są prawdziwymi wpisami z produkcji (ID w opisie), żeby test mówił
o tym, co widział mieszkaniec, a nie o wymyślonych danych.

Użycie:
    cd backend && python -m scripts.test_feed_window
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from src.services.feed_policy import NEWS_MAX_AGE_DAYS, in_feed_window
from src.services.time_span import local_day_bounds, to_utc

# Środa 16.09.2026, 14:00 czasu lokalnego (12:00 UTC — baza trzyma naiwny UTC).
NOW = datetime(2026, 9, 16, 12, 0)


def local(day: int, hour: int = 0, minute: int = 0, month: int = 9) -> datetime:
    """Czas LOKALNY zapisany tak, jak stoi w bazie (naiwny UTC)."""
    return to_utc(datetime(2026, month, day, hour, minute))


# Wpis całodniowy to lokalna północ — w bazie 22:00 dnia poprzedniego (czas letni).
ALL_DAY_17 = local(17)
ALL_DAY_18 = local(18)

CASES = [
    # (opis, artykuł, czy ma być w feedzie)
    (
        "wiadomość opublikowana dziś (art. 6034, łódź OSP Hartowiec)",
        dict(published_at=local(16, 10, 22), locality=3, category="Społeczność"),
        True,
    ),
    (
        "wiadomość sprzed dwóch dni (art. 6003, Dekorglass)",
        dict(published_at=local(14, 9, 41), locality=2, category="Sport"),
        True,
    ),
    (
        f"wiadomość starsza niż {NEWS_MAX_AGE_DAYS} doby (art. 5986, warsztaty 12.09)",
        dict(published_at=local(12, 13, 56), locality=3, category="Sport"),
        False,
    ),
    (
        "stary wpis odświeżony dziś przez re-scrape — liczy się PUBLIKACJA",
        dict(published_at=local(12, 13, 56), scraped_at=local(16, 13, 0),
             locality=3, category="Sport"),
        False,
    ),
    (
        "wpis bez daty publikacji — zostaje data pobrania",
        dict(published_at=None, scraped_at=local(16, 11, 0), locality=2),
        True,
    ),
    # --- zapowiedzi -----------------------------------------------------------
    (
        "zapowiedź na jutro — przeddzień, wchodzi (art. 5502, zebranie 17.09)",
        dict(published_at=local(6, 9, 3), event_at=ALL_DAY_17, locality=3,
             category="Urząd", title="Zebranie wiejskie w Rybnie"),
        True,
    ),
    (
        "impreza pojutrze (art. 6048, OLD BOYS 18.09 w Fijewie) — jeszcze kalendarz",
        dict(published_at=local(15, 14, 3), event_at=ALL_DAY_18, locality=2,
             category="Sport", title="Turniej Piłkarskich Wspomnień OLD BOYS 40+"),
        False,
    ),
    (
        "impreza w gminie za dwa tygodnie (art. 5980, Popołudnia z Pasją 1.10)",
        dict(published_at=local(11, 13, 22), event_at=local(1, 0, month=10),
             locality=3, category="Kultura",
             title="Powrót „Popołudni z Pasją” w gminie Rybno"),
        False,
    ),
    (
        "zapowiedź, która właśnie trwa (art. 5887, wyłączenie 08:00–17:00)",
        dict(published_at=local(8, 9, 39), event_at=local(16, 8), event_until=local(16, 17),
             locality=2, category="Awaria", title="Wyłączenie prądu — Lipówka"),
        True,
    ),
    (
        "impreza wczorajsza — doba karencji, czyta się jak relacja",
        dict(published_at=local(14, 12), event_at=local(15, 18), locality=3,
             category="Kultura", title="Koncert w Rybnie"),
        True,
    ),
    # --- wyjątek: awaria i sprawa urzędowa gminy -------------------------------
    (
        "wyłączenie w gminie za 6 dni (art. 6000, Żabiny 22.09) — ostrzegamy wcześniej",
        dict(published_at=local(14, 13, 26), event_at=local(22, 9),
             event_until=local(22, 14), locality=3, category="Awaria",
             title="Planowane wyłączenie prądu 22 września — Żabiny"),
        True,
    ),
    (
        "wyłączenie poza gminą za 5 dni (art. 6021, Działdowo 21.09) — czeka do przeddnia",
        dict(published_at=local(15, 9, 53), event_at=local(21, 9, 30),
             event_until=local(21, 14, 30), locality=2, category="Awaria",
             title="Planowane wyłączenie prądu 21 września — Działdowo"),
        False,
    ),
    (
        "zebranie wiejskie ogłoszone dziesięć dni wcześniej (art. 5856, 17.09 18:00)",
        dict(published_at=local(6, 15, 31), event_at=local(17, 18), locality=3,
             category="Urząd", title="Zebranie wiejskie w Rybnie — Fundusz Sołecki"),
        True,
    ),
    (
        "awaria rozpoznana z TREŚCI, gdy kategorii jeszcze nie ma (okno Energi 18:05)",
        dict(published_at=local(15, 18, 5), event_at=local(20, 9), locality=3,
             category=None, title="Planowane wyłączenie prądu 20 września — Rybno"),
        True,
    ),
    (
        "sprawa gminy, ale ani awaria, ani urząd (turniej sołectw 27.09) — kalendarz",
        dict(published_at=local(8, 10), event_at=local(27, 10), locality=3,
             category="Sport", title="Sołecki Turniej Halowej Piłki Nożnej"),
        False,
    ),
    (
        "nabór trwający do końca miesiąca spoza gminy (art. 5248, QMP do 30.09)",
        dict(published_at=local(7, 8, 44, month=8), event_at=local(30, 0),
             locality=0, category="Urząd", title="Certyfikat QMP dla rolników"),
        False,
    ),
    (
        "wpis bez oceny lokalności — o gminie rozstrzyga nazwa wsi w tytule",
        dict(published_at=local(10, 8), event_at=local(24, 9), locality=None,
             category="Awaria", title="Przerwa w dostawie wody w Tuczkach"),
        True,
    ),
    (
        "wpis bez oceny lokalności i bez nazwy wsi — czeka do przeddnia",
        dict(published_at=local(10, 8), event_at=local(24, 9), locality=None,
             category="Awaria", title="Przerwa w dostawie wody w Lidzbarku"),
        False,
    ),
]


def _article(**fields):
    base = dict(
        published_at=None, scraped_at=NOW, event_at=None, event_until=None,
        locality=None, category=None, title=None, display_title=None, content=None,
    )
    base.update(fields)
    return SimpleNamespace(**base)


def run() -> int:
    failed = 0
    start, _ = local_day_bounds(now=NOW, days=1)
    print("=" * 78)
    print("OKNO FEEDU — co dziś należy do feedu (16.09.2026, 14:00 lokalnego)")
    print(f"wiadomości od {(start - timedelta(days=NEWS_MAX_AGE_DAYS - 1)).date()} "
          f"(doba lokalna), zapowiedzi od przeddnia terminu")
    print("=" * 78)

    for label, fields, expected in CASES:
        got = in_feed_window(_article(**fields), NOW)
        ok = got == expected
        failed += 0 if ok else 1
        state = "w feedzie" if got else "poza feedem"
        print(f"  {'✓' if ok else '✗'} {label}: {state}")
        if not ok:
            print(f"      oczekiwano: {'w feedzie' if expected else 'poza feedem'}")

    print()
    print(f"{'✓ Wszystko zielone' if not failed else f'✗ Błędów: {failed}'} "
          f"({len(CASES) - failed}/{len(CASES)})")
    return failed


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
