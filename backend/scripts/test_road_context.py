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
    WORKS_DAYS,
    _is_local,
    _age_label,
    _is_fresh_enough,
    _is_road_related,
    format_road_context,
    is_incident,
    note_is_outdated,
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

# art. 6848 (wypis 300 zn. — bez terminu zakończenia)
DW538_SYLA = FakeArticle(
    "🚧 Trwają prace na DW 538 między Rybnem a Tuczkami!",
    "Drogowcy remontują najbardziej zniszczony fragment drogi.",
    datetime(2026, 10, 22, 10, 0, 33),
)
ZAKRES = FakeArticle(
    "Remont nawierzchni DW538",
    "Od 3 do 20 listopada remont nawierzchni na odcinku Rybno – Hartowiec, ruch wahadłowy.",
    datetime(2026, 10, 28, 9, 0),
)
ZAPOWIEDZ = FakeArticle(
    "Zamknięcie drogi w Żabinach",
    "10 listopada zamknięcie drogi w Żabinach, objazd przez Rumian.",
    datetime(2026, 10, 27, 9, 0),
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
    checks.append(("remont sprzed 13 dni bez terminu wypada",
                   _is_fresh_enough(REMONT, TERAZ), False))
    checks.append(("remont sprzed 5 dni bez terminu zostaje",
                   _is_fresh_enough(REMONT, REMONT.published_at + timedelta(days=5)), True))

    # 2a. Roboty: termin z treści wygrywa z WORKS_DAYS (stan 27.10.2026:
    #     post Syli z 22.10 bez terminu budził pasek przez dwa tygodnie).
    checks.append((f"DW538 22.10 bez terminu: po {WORKS_DAYS} dniach wypada",
                   _is_fresh_enough(DW538_SYLA, datetime(2026, 10, 30, 9, 0)), False))
    checks.append(("DW538 22.10 bez terminu: 27.10 jeszcze jest",
                   _is_fresh_enough(DW538_SYLA, datetime(2026, 10, 27, 9, 0)), True))
    checks.append(("zakres „od 3 do 20 listopada” trzyma wpis do końca",
                   _is_fresh_enough(ZAKRES, datetime(2026, 11, 19, 12, 0)), True))
    checks.append(("… i zwalnia go po zakresie",
                   _is_fresh_enough(ZAKRES, datetime(2026, 11, 21, 12, 0)), False))
    checks.append(("zapowiedź zamknięcia z wyprzedzeniem nie wygasa przed startem",
                   _is_fresh_enough(ZAPOWIEDZ, datetime(2026, 11, 12, 9, 0)), True))

    # 2b. Słowa drogowe to CAŁE wyrazy (27.10: kondolencje weszły przez „drogiej").
    checks.append(("„drogiej” to nie droga",
                   _is_road_related("Piękna miłość", "Z głębi serca żegnamy naszą drogiej pamięci mamę"), False))
    checks.append(("„drogowcy remontują” to droga",
                   _is_road_related(DW538_SYLA.title, DW538_SYLA.content), True))
    checks.append(("ogłoszenie o posiedzeniu komisji to nie droga (29.10)",
                   _is_road_related("Ogłoszenie o posiedzeniu Komisji Budżetu i Finansów Rady Gminy Rybno.",
                                    "Porządek: 5. Podjęcie uchwały w sprawie przebudowy drogi gminnej."), False))
    checks.append(("ogłoszenie o XXVI sesji Rady to nie droga",
                   _is_road_related("Ogłoszenie o XXVI sesji Rady Gminy Rybno", "zmiana planu, drogi"), False))
    checks.append(("„przebudowa drogi Ostrowy–Bryńsk” zostaje",
                   _is_road_related("Ruszyła przebudowa drogi Ostrowy–Bryńsk", None), True))
    checks.append(("odmiana „zamknięcie drogi” łapie się",
                   _is_road_related("Zamknięcie drogi w Hartowcu", None), True))

    # 2c. Lokalność wpisu, nie tylko źródła.
    checks.append(("locality 1 (Mława) odpada mimo lokalnego źródła",
                   _is_local("Facebook - Syla", "Wypadek w Mławie", None, 1), False))
    checks.append(("locality 3 zostaje",
                   _is_local("Facebook - Syla", DW538_SYLA.title, DW538_SYLA.content, 3), True))
    checks.append(("brak oceny (NULL) przechodzi po staremu",
                   _is_local("Facebook - Syla", DW538_SYLA.title, None, None), True))
    checks.append(("wpis bez daty publikacji odpada",
                   _is_fresh_enough(FakeArticle("x", "droga", None), TERAZ), False))

    # 2b. Odpowiedź modelu z minionym terminem (wyniki Google nie mają bramek
    #     materiału). 28.10.2026: zamknięcie DW538 „do 31 grudnia 2025 roku”.
    teraz_x = datetime(2026, 10, 28, 12, 0)
    checks.append(("NOTE z terminem z 2025 r. jest nieaktualny",
                   note_is_outdated(
                       "Na drodze wojewódzkiej nr 538 w miejscowości Rybno od 2 czerwca "
                       "2025 roku do 31 grudnia 2025 roku trwa całkowite zamknięcie odcinka "
                       "drogi w związku z przebudową przepustu drogowego. Obowiązują objazdy.",
                       teraz_x), True))
    checks.append(("NOTE z zakresem zakończonym 14.10 jest nieaktualny",
                   note_is_outdated("Od 3 do 14 października zamknięcie DW538 w Rybnie.",
                                    teraz_x), True))
    checks.append(("NOTE z trwającym zakresem zostaje",
                   note_is_outdated("Od 20 października do 14 listopada zamknięcie DW538 w Rybnie.",
                                    teraz_x), False))
    checks.append(("NOTE z przyszłym zakresem zostaje",
                   note_is_outdated("Od 3 do 14 listopada zamknięcie DW538 w Rybnie.",
                                    teraz_x), False))
    checks.append(("NOTE z rokiem bieżącym i przyszłym zostaje",
                   note_is_outdated("Przebudowa DW538 w Rybnie, prace 2026–2027.",
                                    teraz_x), False))
    checks.append(("NOTE bez daty zostaje (decyduje reszta bramek)",
                   note_is_outdated("Wahadło na DW538 w Tuczkach.", teraz_x), False))
    checks.append(("grudniowe „od 15 stycznia” to przyszły rok",
                   note_is_outdated("Od 15 stycznia do 30 stycznia zamknięcie DW538 w Rybnie.",
                                    datetime(2026, 12, 20, 12, 0)), False))

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
