"""
Newsletter: czas gramatyczny rozstrzyga TERMIN, nie data publikacji (2026-09-07)

**Skąd to.** Podsumowanie na stronie i mail dostały ten sam materiał i oba
napisały: „Wczoraj w Rybnie odbyło się zebranie dotyczące Funduszu Sołeckiego
na 2027 rok". Zebranie jest **17 września**. Wczorajsza była wyłącznie
publikacja posta.

Model wykonał polecenie, które dostał. Kod dzielił materiał na dwa bloki:

    reference = article.event_at or article.published_at or article.scraped_at
    target = ahead if reference and reference >= day_start else past

Wpis bez `event_at` szedł więc do bloku „JUŻ SIĘ WYDARZYŁO (relacje — czas
przeszły)" na podstawie samej daty publikacji, a prompt podaje tam jako wzór
zdanie „wczoraj w Rybnie odbyło się…". Zapowiedź została zaklasyfikowana jako
relacja przez KOD, nie przez model.

Naprawa: trzeci koszyk. Bez terminu nie zgadujemy zegarem — mówimy modelowi,
że terminu nie ma, a czas gramatyczny zostawiamy treści wpisu.

Użycie:
    cd backend && python -m scripts.test_newsletter_tense
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.newsletter.generator import split_by_time
from src.services.time_span import local_day_bounds


class FakeArticle:
    """Tyle z artykułu, ile czyta podział na bloki czasowe."""
    def __init__(self, title, published_at, event_at=None, event_until=None,
                 category="Urząd"):
        self.title = title
        self.display_title = None
        self.category = category
        self.published_at = published_at
        self.scraped_at = published_at
        self.event_at = event_at
        self.event_until = event_until


TERAZ = datetime(2026, 9, 7, 5, 0)  # przebieg newslettera dziennego, 7:15 lokalnie


def run() -> int:
    print("=" * 78)
    print("Newsletter: zapowiedź bez terminu nie jest relacją")
    print("=" * 78)

    day_start, _ = local_day_bounds(now=TERAZ)

    # Wpisy z produkcji, 7.09.2026.
    zebranie = FakeArticle(  # art. 5856 — przedruk Syli, data poza wypisem
        "Mieszkańcy Rybna zdecydują, na co przeznaczyć ponad 73 tys....",
        published_at=datetime(2026, 9, 6, 16, 26, 3),
    )
    zebranie_z_terminem = FakeArticle(  # ten sam wpis po naprawie scrapera
        "Mieszkańcy Rybna zdecydują, na co przeznaczyć ponad 73 tys....",
        published_at=datetime(2026, 9, 6, 16, 26, 3),
        event_at=datetime(2026, 9, 16, 22, 0),  # 17.09 lokalnie, całodniowe
    )
    mecz = FakeArticle(  # art. 5840 — relacja, też bez `event_at`
        "Kilka ujęć z pierwszego wygranego meczu GSZS Delfin Rybno",
        published_at=datetime(2026, 9, 5, 23, 1, 32),
        category="Sport",
    )
    dozynki = FakeArticle(  # zdarzenie z terminem, już po
        "Dożynki gminne w Rybnie",
        published_at=datetime(2026, 8, 28, 9, 0),
        event_at=datetime(2026, 8, 30, 9, 0),
        event_until=datetime(2026, 8, 30, 18, 0),
        category="Kultura",
    )
    bieg = FakeArticle(  # zdarzenie z terminem, przed nami
        "VI Leśny Nocny Bieg w Kopaniarzach",
        published_at=datetime(2026, 9, 6, 10, 0),
        event_at=datetime(2026, 9, 7, 18, 0),
        category="Sport",
    )

    ahead, past, undated = split_by_time(
        [zebranie, mecz, dozynki, bieg], day_start, TERAZ
    )
    tytuly = lambda blok: [e["title"][:34] for e in blok]

    checks = []

    # 1. Sedno błędu: zapowiedź bez terminu NIE trafia do bloku relacji.
    checks.append(("zebranie nie jest w JUŻ SIĘ WYDARZYŁO",
                   any("Mieszkańcy Rybna" in t for t in tytuly(past)), False))
    checks.append(("zebranie trafia do bloku bez terminu",
                   any("Mieszkańcy Rybna" in t for t in tytuly(undated)), True))
    # ⚠️ Szukamy po POCZĄTKU tytułu: `tytuly` obcina do 34 znaków, a „Delfin"
    #    pada dopiero w 47. znaku — pierwszy przebieg tego testu był czerwony
    #    przez wzorzec, nie przez kod. Ta sama pułapka co w wyroczni 5.09.
    checks.append(("relacja z meczu też czeka na blok bez terminu",
                   any("Kilka ujęć" in t for t in tytuly(undated)), True))
    checks.append(("blok bez terminu ma dokładnie te dwa wpisy",
                   len(undated), 2))

    # 2. Wpisy Z terminem dzieli zegar — i to działało poprawnie wcześniej.
    checks.append(("dożynki po terminie → relacje",
                   any("Dożynki" in t for t in tytuly(past)), True))
    checks.append(("bieg na dziś → przed nami",
                   any("Bieg" in t for t in tytuly(ahead)), True))

    # 3. Etykieta mówi, CZEGO dotyczy data — inaczej model czyta ją jako termin.
    etykieta_bez = undated[0]["when"]
    checks.append(("bez terminu etykieta mówi o publikacji",
                   etykieta_bez.startswith("opublikowano "), True))
    checks.append(("etykieta bez terminu nie udaje zdarzenia",
                   "ZDARZENIE" in etykieta_bez, False))
    checks.append(("z terminem etykieta nazywa ZDARZENIE",
                   "ZDARZENIE" in split_by_time([bieg], day_start, TERAZ)[0][0]["when"],
                   True))

    # 4. Po naprawie scrapera ten sam wpis wraca na właściwe miejsce.
    ahead2, past2, undated2 = split_by_time(
        [zebranie_z_terminem], day_start, TERAZ
    )
    checks.append(("z odczytanym terminem zebranie idzie do ZAPOWIEDZI",
                   len(ahead2) == 1 and not past2 and not undated2, True))
    checks.append(("i niesie termin, nie datę publikacji",
                   "17.09" in ahead2[0]["when"], True))

    failures = 0
    for label, got, expected in checks:
        ok = got == expected
        failures += not ok
        detail = f"{got}" + ("" if ok else f" (oczekiwano {expected})")
        print(f"{'✓' if ok else '✗'} {label:.<58} {detail}")

    print("-" * 78)
    print(f"{len(checks) - failures}/{len(checks)} zgodnych z oczekiwaniem")
    print()
    print("Etykiety, jakie zobaczy model:")
    for nazwa, blok in (("JUŻ SIĘ WYDARZYŁO", past),
                        ("DZIŚ I PRZED NAMI", ahead),
                        ("TERMIN NIEZNANY", undated)):
        for e in blok:
            print(f"  [{nazwa:18}] [{e['when']}] {e['title'][:44]}")
    return failures


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
