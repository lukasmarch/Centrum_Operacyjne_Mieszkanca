"""
Świeżość materiału dla widgetu ruchu (2026-09-07)

**Skąd to.** 7.09.2026 widget pokazywał „Droga do Truszczyn od strony Zwiniarza
jest zablokowana z powodu spadłego konaru (04.09.2026)" — trzeci dzień po
zdarzeniu, i to naraz przy trasie do Lubawy i do Iławy, na żadnej z których ta
droga nie leży.

Model nie zawinił. Prompt mówił mu: „jeśli źródło jest starsze niż 14 dni i nie
potwierdza, że prace nadal trwają — daj Płynnie". Konar sprzed trzech dni
mieścił się w oknie, więc reguła go PRZEPUŚCIŁA zgodnie z własnym brzmieniem.
Materiał sięgał 21 dni wstecz i nie odróżniał zdarzenia chwilowego od robót.

Reguła sprawdzalna kodem należy do kodu — ta sama zasada, co przy walidatorach
kategoryzacji (`ground_categorization`) i przy bramkach `alert_policy`.

Użycie:
    cd backend && python -m scripts.test_road_context
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.road_context import (
    INCIDENT_DAYS,
    _age_label,
    _is_fresh_enough,
    _is_road_related,
    format_road_context,
    is_incident,
)

TERAZ = datetime(2026, 9, 7, 7, 0)


class FakeArticle:
    """Tyle z artykułu, ile czyta polityka świeżości."""
    def __init__(self, title, content, published_at):
        self.title = title
        self.content = content
        self.published_at = published_at


# Wpisy z produkcji, nie wymyślone.
KONAR = FakeArticle(
    "⚠️ UWAGA KIEROWCY! DROGA ZABLOKOWANA! 🌳🚗",
    "Droga do Truszczyn od strony Zwiniarza jest obecnie zablokowana. "
    "Na jezdnię spadł konar, które uniemożliwia przejazd. "
    "🚒 Służby są już w drodze na miejsce.",
    datetime(2026, 9, 4, 20, 14, 13),  # art. 5830
)
REMONT = FakeArticle(
    "Przebudowa drogi wojewódzkiej nr 538",
    "Trwa remont nawierzchni DW538 na odcinku Rybno – Działdowo. "
    "Wprowadzono tymczasową organizację ruchu.",
    datetime(2026, 8, 25, 9, 0),
)


def run() -> int:
    print("=" * 78)
    print("Widget ruchu: zdarzenie chwilowe kontra roboty drogowe")
    print("=" * 78)

    checks = []

    # 1. Rozpoznanie rodzaju — z TREŚCI, nie z kategorii AI (ta powstaje
    #    o 6:15 i 13:15, a konar spadł o 20:14).
    checks.append(("konar to zdarzenie chwilowe",
                   is_incident(KONAR.title, KONAR.content), True))
    checks.append(("remont DW538 to nie incydent",
                   is_incident(REMONT.title, REMONT.content), False))
    checks.append(("kolizja to incydent",
                   is_incident("Zderzenie na DW541", None), True))
    checks.append(("polska litera „ł” nie psuje wzorca",
                   is_incident("Droga zablokowana przez powalone drzewo", None), True))
    checks.append(("oba wpisy dotyczą dróg",
                   _is_road_related(KONAR.title, KONAR.content)
                   and _is_road_related(REMONT.title, REMONT.content), True))

    # 2. Okno. Zdarzenie chwilowe żyje INCIDENT_DAYS, roboty — pełne 21 dni.
    checks.append(("konar w dniu zdarzenia jest w materiale",
                   _is_fresh_enough(KONAR, datetime(2026, 9, 4, 21, 0)), True))
    checks.append(("konar nazajutrz jeszcze jest",
                   _is_fresh_enough(KONAR, datetime(2026, 9, 5, 21, 0)), True))
    checks.append((f"konar po {INCIDENT_DAYS} dniach wypada (stan z 7.09)",
                   _is_fresh_enough(KONAR, TERAZ), False))
    checks.append(("remont sprzed 13 dni zostaje",
                   _is_fresh_enough(REMONT, TERAZ), True))
    checks.append(("wpis bez daty publikacji odpada",
                   _is_fresh_enough(FakeArticle("x", "droga", None), TERAZ), False))

    # 3. Etykieta wieku. Model gorzej liczy odległość dat, niż czyta słowo.
    checks.append(("dziś", _age_label(0), "DZIŚ"))
    checks.append(("wczoraj", _age_label(1), "wczoraj"))
    checks.append(("starsze", _age_label(5), "sprzed 5 dni"))

    # 4. Materiał niesie etykietę do promptu.
    tekst = format_road_context([{
        "date": "25.08.2026", "age_days": 13, "source": "Gmina Rybno",
        "title": "Przebudowa DW538", "snippet": "Trwa remont nawierzchni.",
    }])
    checks.append(("etykieta wieku trafia do promptu",
                   "sprzed 13 dni" in tekst, True))
    checks.append(("pusty materiał mówi wprost",
                   "brak lokalnych wpisów" in format_road_context([]), True))

    failures = 0
    for label, got, expected in checks:
        ok = got == expected
        failures += not ok
        detail = f"{got}" + ("" if ok else f" (oczekiwano {expected})")
        print(f"{'✓' if ok else '✗'} {label:.<58} {detail}")

    print("-" * 78)
    print(f"{len(checks) - failures}/{len(checks)} zgodnych z oczekiwaniem")
    return failures


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
