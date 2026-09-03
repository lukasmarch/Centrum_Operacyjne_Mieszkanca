"""
Weryfikacja terminów zdarzeń: parsowanie odczytu modelu + wpływ na ranking feedu.

Od 11.08.2026 `event_at` ustawia nie tylko Energa, ale i kategoryzacja — dla
każdej zapowiedzi z datą (festyn, zebranie, dyżur). To pole wchodzi wprost do
`feed_policy.article_score`, więc zmyślony albo źle przeliczony termin wypycha
wpis na górę feedu w losowym dniu. Stąd ten test.

Trzy części:
  1. parsowanie — co model może zwrócić i co z tego wolno zapisać;
  2. ranking — zapowiedź musi być widoczna DWA razy: w dniu ogłoszenia
     i przed samym terminem, a między nimi gasnąć;
  3. brak regresji na Enerdze — wyłączenie ogłoszone z wyprzedzeniem.

Użycie:
    cd backend && python -m scripts.test_event_terms
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from src.ai.article_processor import _parse_event_time
from src.services.feed_policy import article_score

# Publikacja: piątek 14.08.2026, 10:00 UTC (12:00 czasu lokalnego)
PUBLISHED = datetime(2026, 8, 14, 10, 0)

GMINA = "Gmina Rybno"
ENERGA = "Energa - wyłączenia planowane (RSS)"


# (opis, odczyt modelu, oczekiwany naiwny UTC albo None)
PARSE_CASES = [
    ("festyn tego samego dnia o 15:00",
     "2026-08-15T15:00", datetime(2026, 8, 15, 13, 0)),
    ("sama data bez godziny → północ lokalna",
     "2026-08-22T00:00", datetime(2026, 8, 21, 22, 0)),
    ("brak terminu",
     None, None),
    ("pusty łańcuch",
     "", None),
    ("śmieci zamiast daty",
     "w najbliższą sobotę", None),
    ("zdarzenie sprzed tygodnia — to relacja, nie zapowiedź",
     "2026-08-07T18:00", None),
    ("zdarzenie wczoraj — mieści się w marginesie doby",
     "2026-08-13T18:00", datetime(2026, 8, 13, 16, 0)),
    ("rok w przód — model pomylił rok publikacji ze zdarzeniem",
     "2027-08-15T15:00", None),
    ("pół roku bez dwóch dni — jeszcze przechodzi",
     "2027-02-08T12:00", datetime(2027, 2, 8, 11, 0)),
]


def run_parse() -> int:
    print("=" * 78)
    print("Parsowanie terminu zwróconego przez model")
    print("=" * 78)

    failures = 0
    for label, raw, expected in PARSE_CASES:
        got = _parse_event_time(raw, PUBLISHED)
        ok = got == expected
        failures += not ok
        detail = f"{got}" + (f" (oczekiwano {expected})" if not ok else "")
        print(f"{'✓' if ok else '✗'} {label:.<58} {detail}")

    print("-" * 78)
    print(f"{len(PARSE_CASES) - failures}/{len(PARSE_CASES)} zgodnych z oczekiwaniem")
    return failures


# (opis, ile godzin od publikacji minęło, termin względem publikacji, warunek)
def run_ranking() -> int:
    print()
    print("=" * 78)
    print("Ranking zapowiedzi — widoczna w dniu ogłoszenia i przed terminem")
    print("=" * 78)

    event_at = PUBLISHED + timedelta(days=20)          # festyn za 20 dni
    checks = []

    def score(hours_after_publish: float, with_event: bool) -> float:
        now = PUBLISHED + timedelta(hours=hours_after_publish)
        return article_score(
            PUBLISHED, PUBLISHED, GMINA, now,
            event_at if with_event else None, None,
        )

    # 1. W dniu ogłoszenia termin NIE MOŻE pogorszyć wyniku — to wciąż świeża
    #    wiadomość, a nie odległe zdarzenie
    checks.append((
        "w dniu ogłoszenia zapowiedź waży tyle, co wpis bez terminu",
        abs(score(2, True) - score(2, False)) < 1e-9,
        f"{score(2, True):.4f} vs {score(2, False):.4f}",
    ))

    # 2. Tydzień później zapowiedź gaśnie razem z ogłoszeniem
    checks.append((
        "tydzień po ogłoszeniu wynik jest niski",
        score(24 * 7, True) < 0.05,
        f"{score(24 * 7, True):.4f}",
    ))

    # 3. Dzień przed terminem wraca wysoko — TO jest cel zmiany
    day_before = score(24 * 19, True)
    checks.append((
        "dzień przed terminem zapowiedź wraca na górę",
        day_before > 0.5,
        f"{day_before:.4f}",
    ))

    # 4. Bez terminu ten sam wpis po 19 dniach jest martwy
    checks.append((
        "ten sam wpis bez terminu po 19 dniach nie wraca",
        score(24 * 19, False) < 0.001,
        f"{score(24 * 19, False):.6f}",
    ))

    # 5. Energa: wyłączenie ogłoszone 10 dni przed terminem, dzień przed nim
    energa_event = PUBLISHED + timedelta(days=10)
    energa = article_score(
        PUBLISHED, PUBLISHED, ENERGA, PUBLISHED + timedelta(days=9),
        energa_event, energa_event + timedelta(hours=5),
    )
    checks.append((
        "wyłączenie Energi dzień przed terminem stoi wysoko",
        energa > 0.5,
        f"{energa:.4f}",
    ))

    # 6. Zakończone zdarzenie schodzi z góry (mnożnik 0,25)
    finished = article_score(
        PUBLISHED, PUBLISHED, ENERGA, energa_event + timedelta(hours=8),
        energa_event, energa_event + timedelta(hours=5),
    )
    checks.append((
        "zakończone wyłączenie traci na wadze",
        finished < energa,
        f"{finished:.4f} < {energa:.4f}",
    ))

    failures = 0
    for label, ok, detail in checks:
        failures += not ok
        print(f"{'✓' if ok else '✗'} {label:.<58} {detail}")

    print("-" * 78)
    print(f"{len(checks) - failures}/{len(checks)} zgodnych z oczekiwaniem")
    return failures


# --- 4. data wprost w tekście — czyta kod (3.09.2026) --------------------------
# Ten sam post puszczony przez model trzy razy dał termin w 2 przebiegach na 3,
# godzinę końca w 0 na 3. Data, która stoi w tekście, nie może zależeć od losu.
# (opis, tekst, publikacja UTC, oczekiwany początek UTC, oczekiwany koniec UTC)
DATE_CASES = [
    ("pobór krwi ← art. 5770, model gubił termin w 1 na 3 przebiegów",
     "HDK PCK zaprasza na Jesienny Pobór Krwi. 📅 16 września 2026 r. ⏰ godz. 8:00–11:30 📍 Rybno",
     datetime(2026, 9, 2, 13, 44), datetime(2026, 9, 16, 6, 0), datetime(2026, 9, 16, 9, 30)),
    ("sama data bez godziny → lokalna północ",
     "Weekend z GSZS Delfin Rybno 5 września. Zapraszamy kibiców.",
     datetime(2026, 9, 2, 10, 27), datetime(2026, 9, 4, 22, 0), None),
    ("zapis numeryczny z rokiem",
     "Czasowe wyłączenie wody 31.08.2026 w godzinach 8:00-15:00",
     datetime(2026, 8, 29, 9, 0), datetime(2026, 8, 31, 6, 0), datetime(2026, 8, 31, 13, 0)),
    ("zapis 8.00 to godzina, nie ósmy dzień miesiąca zerowego",
     "Awaria wodociągu. Prace od 8.00 do 15.00.",
     datetime(2026, 9, 2, 9, 0), None, None),
    ("relacja z datą sprzed publikacji → nie zapowiedź",
     "30 sierpnia odbyło się Święto Plonów. Dziękujemy wszystkim!",
     datetime(2026, 9, 1, 12, 0), None, None),
    ("data bez roku po przełomie roku → następny rok",
     "Zapisy do 15 stycznia w sekretariacie.",
     datetime(2026, 12, 20, 12, 0), datetime(2027, 1, 14, 23, 0), None),
    ("pierwsza data minęła, druga przed nami → bierzemy drugą",
     "Po turnieju z 30 sierpnia zapraszamy na rewanż 12 września o 17:00.",
     datetime(2026, 9, 1, 12, 0), datetime(2026, 9, 12, 15, 0), None),
    ("godziny poza oknem za datą nie są terminem",
     "Zebranie 10 września. Biuro czynne w godzinach 7:30-15:30, telefon czynny w godzinach 8:00-16:00.",
     datetime(2026, 9, 1, 12, 0), datetime(2026, 9, 9, 22, 0), None),
    ("pół roku w przód — za daleko, jak dla modelu",
     "Wielki finał 20 marca 2027 w Rybnie.",
     datetime(2026, 9, 1, 12, 0), None, None),
    ("brak publikacji → nic",
     "16 września 2026", None, None, None),
]


def run_dates() -> int:
    from src.services.time_span import parse_date_span
    print()
    print("=" * 78)
    print("Data wprost w tekście — czyta kod, nie model")
    print("=" * 78)

    failures = 0
    for label, text, published, exp_start, exp_end in DATE_CASES:
        got = parse_date_span(text, published)
        ok = got == (exp_start, exp_end)
        failures += not ok
        detail = f"{got[0]} → {got[1]}" + ("" if ok else f" (oczekiwano {exp_start} → {exp_end})")
        print(f"{'✓' if ok else '✗'} {label:.<58} {detail}")

    print("-" * 78)
    print(f"{len(DATE_CASES) - failures}/{len(DATE_CASES)} zgodnych z oczekiwaniem")
    return failures


if __name__ == "__main__":
    failed = run_parse() + run_ranking() + run_dates()
    sys.exit(1 if failed else 0)
