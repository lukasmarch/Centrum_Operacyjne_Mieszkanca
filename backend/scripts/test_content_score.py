"""
Weryfikacja trzeciego i czwartego czynnika rankingu feedu — oceny treści i miejsca.

Do 11.08.2026 `article_score` liczył wagę ŹRÓDŁA razy świeżość. Audyt tygodnia
pokazał skutek: pierwsza piątka Dashboardu była GORSZA od średniej materiału
w lokalności, konkrecie i przyciąganiu — wygrywał kanał publikujący najczęściej.

`content_score` (0–6 = lokalność + użyteczność z kategoryzacji) daje mnożnik
0,7–1,3. Ten test pilnuje dwóch rzeczy naraz, bo ciągną w przeciwne strony:
czynnik ma realnie przestawiać kolejność, ale NIE MOŻE przebić świeżości —
inaczej dobry wpis sprzed tygodnia stanąłby nad dzisiejszą awarią.

Czwarty czynnik dołożony 22.08.2026. Pomiar tego dnia: w pierwszej dziesiątce
feedu był JEDEN wpis o gminie Rybno — resztę zajęły wyłączenia Energi w Płośnicy,
Lidzbarku i Działdowie, bo `article_score` o miejscu nie wiedział nic, a Energa
ma najwyższą wagę źródła w całej tabeli. Ten test pilnuje obu stron naraz:
kara ma zdejmować cudzą gminę ze szczytu, ale NIE MOŻE zepchnąć świeżej awarii
u sąsiada pod wpisy sprzed kilku dni.

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
    LOCALITY_FACTOR_FOREIGN,
    article_score,
    content_factor,
    locality_factor,
)

NOW = datetime(2026, 8, 14, 12, 0)

SYLA = "Facebook - Syla"          # waga 0,85 — profil publikujący najczęściej
GMINA = "Gmina Rybno"             # waga 1,35
ENERGA = "Energa - wyłączenia bieżące (RSS)"   # waga 1,40 — najwyższa w tabeli
OLSZTYN = "Radio Olsztyn (RSS)"                # źródło wojewódzkie, poza LOCAL_SOURCES

# Prawdziwe tytuły z produkcji, 22.08.2026
T_RYBNO = "Wyłączenie awaryjne - Region Mława - Rybno gmina wiejska"
T_LIDZBARK = "Wyłączenie awaryjne - Region Mława - Lidzbark miasto w gminie miejsko-wiejskiej"
T_OBCE_RYBNO = "Wyłączenie awaryjne - Region Gostynin - Rybno gmina wiejska"
C_OBCE_RYBNO = "Rybno gmina wiejska 22.08.2026 06:21-13:00 - Antosin, Koszajec, Matyldów, Rybionek, Wężyki."


def score(source: str, age_h: float, content_score=None, locality=None,
          title=None, content=None) -> float:
    published = NOW - timedelta(hours=age_h)
    return article_score(published, published, source, NOW, None, None, content_score,
                         locality, title, content)


def main() -> int:
    print("=" * 78)
    print("Ocena treści i miejsce jako trzeci i czwarty czynnik rankingu")
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

        # --- czwarty czynnik: miejsce (22.08.2026) -----------------------------
        # Pomiar tego dnia: w pierwszej dziesiątce feedu był JEDEN wpis lokalny,
        # resztę zajęły wyłączenia Energi w Płośnicy, Lidzbarku i Działdowie.
        (
            "wywołanie bez materiału nie karze (wsteczna zgodność)",
            locality_factor(None, ENERGA) == 1.0,
            f"factor(None, {ENERGA!r}) = {locality_factor(None, ENERGA)}",
        ),
        (
            "wyłączenie w naszej gminie zostaje bez kary",
            locality_factor(None, ENERGA, T_RYBNO) == 1.0,
            f"{locality_factor(None, ENERGA, T_RYBNO)}",
        ),
        (
            "wyłączenie w Lidzbarku dostaje karę",
            locality_factor(None, ENERGA, T_LIDZBARK) == LOCALITY_FACTOR_FOREIGN,
            f"{locality_factor(None, ENERGA, T_LIDZBARK)}",
        ),
        (
            "cudze Rybno (Region Gostynin) dostaje karę mimo nazwy w tekście",
            locality_factor(None, ENERGA, T_OBCE_RYBNO, C_OBCE_RYBNO)
            == LOCALITY_FACTOR_FOREIGN,
            f"{locality_factor(None, ENERGA, T_OBCE_RYBNO, C_OBCE_RYBNO)}",
        ),
        (
            "artykuł o Rybnie w źródle wojewódzkim NIE jest karany",
            locality_factor(None, OLSZTYN, "Łaciate Mazury MTB zadebiutuje w Rybnie") == 1.0,
            f"{locality_factor(None, OLSZTYN, 'Łaciate Mazury MTB zadebiutuje w Rybnie')}",
        ),
        # Do 3.09.2026 ocena mogła wpis wyłącznie PODNIEŚĆ. Skutkiem był feed,
        # w którym „Termin płatności III raty podatku i opłaty za psa
        # w DZIAŁDOWIE" miał wynik 0,792 — najwyższy w całym materiale, wyżej
        # niż awaria wodociągowa w Rybnie. Kategoryzacja oceniła go na
        # `locality=2`, ale profil Gminy Działdowo jest w `LOCAL_SOURCES`,
        # więc mnożnik i tak wychodził 1,00.
        #
        # Obawę „model bywa skąpy" zmierzono na produkcji (30 dni): źródła
        # czysto gminne dostają `locality=3` w 30 przypadkach na 35 — Gmina
        # Rybno 5/5, Facebook Rybno 9/10, BIP 11/13, ZGK 5/7. Reszta to wpisy,
        # które naprawdę dotyczą powiatu. Kara jest mnożnikiem 0,55, nie
        # filtrem, więc pomyłka modelu przesuwa wpis, a nie usuwa go z feedu.
        (
            "ocena z kategoryzacji rozstrzyga w OBIE strony",
            locality_factor(2, GMINA, "Sesja Rady") == LOCALITY_FACTOR_FOREIGN
            and locality_factor(3, ENERGA, T_LIDZBARK) == 1.0,
            "locality=2 → 0,55 mimo źródła · locality=3 przebija tytuł",
        ),
        (
            "wpis bez oceny nadal pyta o źródło i nazwę w treści",
            locality_factor(None, GMINA, "Sesja Rady") == 1.0
            and locality_factor(None, ENERGA, T_LIDZBARK) == LOCALITY_FACTOR_FOREIGN,
            "None → dawna ścieżka: źródło, potem nazwa",
        ),
        (
            "podatek za psa w Działdowie schodzi pod wiadomość z Rybna ← 3.09",
            score("Facebook - Gmina Działdowo", 18, 5, 2, "Termin płatności III raty podatku w Działdowie")
            < score("Facebook - Syla", 18, 5, 3, "Zespoły GSZS Delfin Rybno zagrają w weekend"),
            f"{score('Facebook - Gmina Działdowo', 18, 5, 2, 'Termin płatności III raty podatku w Działdowie'):.4f} < "
            f"{score('Facebook - Syla', 18, 5, 3, 'Zespoły GSZS Delfin Rybno zagrają w weekend'):.4f}",
        ),
        # To jest cel zmiany: świeże wyłączenie w cudzej gminie przestaje
        # otwierać dzień, w którym gmina ma własne wiadomości
        (
            "wyłączenie w Lidzbarku sprzed godziny ustępuje wiadomości z gminy sprzed 6 h",
            score(ENERGA, 1, None, None, T_LIDZBARK)
            < score(GMINA, 6, 5, 3, "Sesja Rady Gminy Rybno"),
            f"{score(ENERGA, 1, None, None, T_LIDZBARK):.4f} < "
            f"{score(GMINA, 6, 5, 3, 'Sesja Rady Gminy Rybno'):.4f}",
        ),
        # A to bezpiecznik w drugą stronę: kara nie może wypchnąć awarii
        # z sąsiedniej gminy pod wpisy sprzed kilku dni
        (
            "wyłączenie w Lidzbarku sprzed godziny nadal bije wpis z gminy sprzed 3 dni",
            score(ENERGA, 1, None, None, T_LIDZBARK)
            > score(GMINA, 72, 5, 3, "Sesja Rady Gminy Rybno"),
            f"{score(ENERGA, 1, None, None, T_LIDZBARK):.4f} > "
            f"{score(GMINA, 72, 5, 3, 'Sesja Rady Gminy Rybno'):.4f}",
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
