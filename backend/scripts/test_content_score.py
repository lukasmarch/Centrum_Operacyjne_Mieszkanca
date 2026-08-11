"""
Weryfikacja trzeciego czynnika rankingu feedu — oceny treści.

Do 11.08.2026 `article_score` liczył wagę ŹRÓDŁA razy świeżość. Audyt tygodnia
pokazał skutek: pierwsza piątka Dashboardu była GORSZA od średniej materiału
w lokalności, konkrecie i przyciąganiu — wygrywał kanał publikujący najczęściej.

`content_score` (0–6 = lokalność + użyteczność z kategoryzacji) daje mnożnik
0,7–1,3. Ten test pilnuje dwóch rzeczy naraz, bo ciągną w przeciwne strony:
czynnik ma realnie przestawiać kolejność, ale NIE MOŻE przebić świeżości —
inaczej dobry wpis sprzed tygodnia stanąłby nad dzisiejszą awarią.

Użycie:
    cd backend && python -m scripts.test_content_score
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from src.services.feed_policy import (
    FRESHNESS_HALFLIFE_H,
    article_score,
    content_factor,
)

NOW = datetime(2026, 8, 14, 12, 0)

SYLA = "Facebook - Syla"          # waga 0,85 — profil publikujący najczęściej
GMINA = "Gmina Rybno"             # waga 1,35


def score(source: str, age_h: float, content_score=None) -> float:
    published = NOW - timedelta(hours=age_h)
    return article_score(published, published, source, NOW, None, None, content_score)


def main() -> int:
    print("=" * 78)
    print("Ocena treści jako trzeci czynnik rankingu")
    print("=" * 78)

    checks = [
        (
            "brak oceny nie zmienia wyniku (wpisy sprzed migracji)",
            abs(score(GMINA, 6, None) - score(GMINA, 6) * 1.0) < 1e-9
            and content_factor(None) == 1.0,
            f"factor(None)={content_factor(None)}",
        ),
        (
            "mnożnik rośnie monotonicznie od 0,7 do 1,3",
            [round(content_factor(n), 2) for n in range(7)]
            == [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3],
            str([round(content_factor(n), 2) for n in range(7)]),
        ),
        (
            "wynik spoza skali jest przycinany, nie wysadza rankingu",
            content_factor(-3) == 0.7 and content_factor(99) == 1.3,
            f"{content_factor(-3)} / {content_factor(99)}",
        ),
        # To jest cel zmiany: przy zbliżonej świeżości wygrywa lepsza treść,
        # choćby źródło ważyło mniej
        (
            "użyteczny wpis gminy bije świeższy o 3 h zapychacz z profilu FB",
            score(GMINA, 5, 6) > score(SYLA, 2, 1),
            f"{score(GMINA, 5, 6):.4f} > {score(SYLA, 2, 1):.4f}",
        ),
        (
            "przy równej treści nadal decyduje świeżość",
            score(SYLA, 2, 4) > score(SYLA, 20, 4),
            f"{score(SYLA, 2, 4):.4f} > {score(SYLA, 20, 4):.4f}",
        ),
        # A to jest bezpiecznik: rozpiętość 0,7–1,3 to ~±9 h przy półokresie 18 h,
        # więc najlepsza treść sprzed doby nie może przebić przeciętnej z rana
        (
            "najlepsza treść sprzed doby przegrywa z przeciętną sprzed 2 h",
            score(GMINA, 24, 6) < score(GMINA, 2, 3),
            f"{score(GMINA, 24, 6):.4f} < {score(GMINA, 2, 3):.4f}",
        ),
        (
            "rozpiętość czynnika odpowiada mniej niż półokresowi świeżości",
            (1.3 / 0.7) < 2 ** 1.0,
            f"1,3/0,7 = {1.3 / 0.7:.2f} < 2,00 "
            f"(półokres {FRESHNESS_HALFLIFE_H:.0f} h)",
        ),
    ]

    failures = 0
    for label, ok, detail in checks:
        failures += not ok
        print(f"{'✓' if ok else '✗'} {label:.<58} {detail}")

    print("-" * 78)
    print(f"{len(checks) - failures}/{len(checks)} zgodnych z oczekiwaniem")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
