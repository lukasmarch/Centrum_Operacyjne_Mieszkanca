"""
Test lokalności na 60 wpisach oznaczonych RĘCZNIE (audyt E1, etap A).

Obok golden mastera (`scripts.locality_gold` — „co kod odpowiada dziś") ten test
mówi, co kod POWINIEN odpowiadać. Etykieta `expected` to ocena człowieka:
  gmina Rybno   — sprawa gminy (miejsce ALBO podmiot: drużyna, OSP, szkoła)
  okolice       — powiat działdowski i sąsiedzi
  poza regionem — reszta świata (Ciechanów, Mława, Olsztyn, cudze Rybno)

Wpisy z `flag: "bug:<odpowiedź>"` to ZNANE BŁĘDY kodu: test wymaga, żeby kod
dalej odpowiadał dokładnie tym błędem. Dzięki temu
  • nikt nie ukryje błędu zmianą etykiety,
  • naprawa błędu psuje test i zmusza do zdjęcia flagi (lista błędów nie rośnie po cichu).
Wpisy `granica` to przypadki sporne (lista, w której nasza miejscowość jest jedną
z wielu pozycji) — oceniane jak reszta, ale oznaczone do decyzji właściciela.

Dane: scripts/fixtures/locality_gold_60.json (tytuł + okna wokół trafień; pełne
teksty cudzych źródeł nie wchodzą do repozytorium). Test nie wymaga bazy.

Użycie: cd backend && python -m scripts.test_locality_gold
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.services.feed_policy import article_scope  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "locality_gold_60.json"


def main() -> int:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    failures: list[str] = []
    correct = known = 0
    for case in cases:
        got = article_scope(case["source"], case["title"], case["content"], case["locality"])
        flag = case["flag"]
        label = f"#{case['id']} [{case['source']}] {case['title'][:60]}"
        if flag.startswith("bug:"):
            documented = flag[4:]
            if got == case["expected"]:
                failures.append(f"NAPRAWIONE — zdejmij flagę: {label} (kod mówi już „{got}”)")
            elif got != documented:
                failures.append(f"ZMIENIONY BŁĄD: {label} — było „{documented}”, jest „{got}”, powinno „{case['expected']}”")
            else:
                known += 1
        elif got != case["expected"]:
            failures.append(f"BŁĄD: {label} — kod „{got}”, oczekiwane „{case['expected']}”")
        else:
            correct += 1
    total = len(cases)
    granica = sum(1 for c in cases if c["flag"] == "granica")
    print(f"Zgodne z oceną: {correct}/{total}  znane błędy: {known}  sporne (wliczone w zgodne): {granica}")
    for f in failures:
        print("  ✗", f)
    if not failures:
        print("OK — lokalność zgodna z oceną ręczną; znane błędy bez zmian")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
