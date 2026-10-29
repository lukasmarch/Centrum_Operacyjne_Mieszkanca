"""
Pasek „Drogi”: wiarygodność liczy kod, nie model (2026-10-29). BEZ BAZY — działa w CI.

**Skąd to.** 29.10.2026 o 6:01 pasek stał żółty na trasach do Działdowa i Lubawy
(„+10 min”) z jednego posta Syli sprzed siedmiu dni („trwają prace na DW 538”,
bez terminu, nikt nie ogłosił końca). Dzień wcześniej — zamknięcie DW538
„do 31 grudnia 2025” z listy ZDW, której nikt nie sprząta. W obu przypadkach
model zdecydował, kod tylko nie zdążył zawetować.

Sprawdza:
  1. trasy i tożsamość zdarzenia (rok w opisie NIE jest numerem drogi)
  2. jedno zdarzenie = jedna trasa — stan z 29.10 znika z obu tras
  3. wynik: źródło × świeżość (+ potwierdzenie) i werdykt auto/redakcja/nic
  4. parser odpowiedzi modelu: REF, brak minut, weta miejsca i minionego terminu
  5. materiał ma numery [M1] dla REF
  6. decyzja redakcji: akceptacja ma termin, usunięcie zużywa token

Użycie: cd backend && python -m scripts.test_road_reports
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.schema import RoadReport
from src.integrations.traffic_service import TrafficService
from src.services.road_context import format_road_context
from src.services.road_reports import (
    APPROVAL_HOURS,
    Candidate,
    apply_decision,
    canonical_route,
    drop_multi_route,
    is_visible,
    note_tokens,
    score_candidates,
    verdict,
)

TERAZ = datetime(2026, 10, 29, 5, 1)          # odczyt z paskiem żółtym
SYLA_6848 = datetime(2026, 10, 22, 12, 0, 33)  # art. 6848, prawdziwa godzina z produkcji
NOTE_6848 = ("Trwają prace remontowe na DW 538 między Rybnem a Tuczkami, gdzie wymieniana "
             "jest nawierzchnia (źródło z 22.10.2026).")

results: list = []


def check(label, got, expected):
    ok = got == expected
    results.append(ok)
    print(f"{'✓' if ok else '✗'} {label:.<66} {got}" + ("" if ok else f" (oczekiwano {expected})"))


def syla(route, published, note=NOTE_6848, kind="works", has_term=False, article_id=6848,
         source="Facebook - Syla"):
    return Candidate(route=route, note=note, origin="feed", kind=kind, article_id=article_id,
                     source_name=source, published_at=published, has_term=has_term)


def score_of(c, now=TERAZ):
    return score_candidates([c], now)[0].score


def run() -> int:
    print("=" * 78)
    print("Pasek „Drogi”: wynik wiarygodności i decyzja redakcji")
    print("=" * 78)

    # 1. Trasy i tożsamość
    check("„Rybno -> Działdowo” to ta sama trasa", canonical_route("Rybno -> Działdowo"), "Rybno-Działdowo")
    check("„Rybno–Iława (przez Hartowiec)”", canonical_route("Rybno–Iława (przez Hartowiec)"), "Rybno-Iława")
    check("nieznana trasa → None", canonical_route("Rybno-Gdańsk"), None)
    tokens = note_tokens(NOTE_6848)
    check("opis 6848: numer drogi jest tokenem", "#538" in tokens, True)
    check("opis 6848: rok 2026 NIE jest numerem drogi", "#2026" in tokens, False)
    check("opis 6848: nazwa gminy nie odróżnia zdarzeń", "Rybno" in tokens, False)
    check("powiatowa „1255N” rozpoznana", "#1255" in note_tokens("Wahadło na drodze 1255N w Rumianie"), True)

    # 2. Jedno zdarzenie = jedna trasa (29.10: ten sam post przy Działdowie i Lubawie)
    kept, dropped = drop_multi_route([syla("Rybno-Działdowo", SYLA_6848), syla("Rybno-Lubawa", SYLA_6848)])
    check("29.10: post 6848 na dwóch trasach → żadnej", (len(kept), len(dropped)), (0, 2))
    kept, _ = drop_multi_route([syla("Rybno-Działdowo", SYLA_6848),
                                syla("Rybno-Iława", SYLA_6848, note="Konar w Hartowcu", article_id=1)])
    check("dwa różne zdarzenia na dwóch trasach zostają", len(kept), 2)
    web = [Candidate("Rybno-Działdowo", "Wahadło na DW 538 w Tuczkach (gazeta.pl, 28.10)", "search"),
           Candidate("Rybno-Lubawa", "Remont DW538 w Tuczkach, ruch wahadłowy", "search")]
    check("wynik z Google o tych samych drogach/wsiach na dwóch trasach → żadnej",
          len(drop_multi_route(web)[0]), 0)

    # 3. Wynik i werdykt
    s = score_of(syla("Rybno-Działdowo", SYLA_6848))
    check("STAN 29.10: Syla bez terminu, 6,7 dnia → poza paskiem i redakcją", verdict(s), None)
    s = score_of(syla("Rybno-Działdowo", SYLA_6848), SYLA_6848 + timedelta(hours=20))
    check("Syla bez terminu, < 2 dni → pasek od razu", verdict(s), "auto")
    s = score_of(syla("Rybno-Działdowo", SYLA_6848), SYLA_6848 + timedelta(days=3))
    check("Syla bez terminu, 3 dni → pytamy redakcję, czy trwa", verdict(s), "pending")
    s = score_of(syla("Rybno-Działdowo", SYLA_6848, source="BIP Gminy Rybno"), SYLA_6848 + timedelta(days=6))
    check("urząd bez terminu, 6 dni → jeszcze redakcja (0,35)", verdict(s), "pending")
    s = score_of(syla("Rybno-Działdowo", SYLA_6848, has_term=True), SYLA_6848 + timedelta(days=12))
    check("termin w treści trzyma pełny wynik (bramkę terminu ma materiał)", verdict(s), "auto")
    s = score_of(syla("Rybno-Iława", SYLA_6848, kind="incident"), SYLA_6848 + timedelta(hours=30))
    check("zdarzenie chwilowe po dobie → redakcja", verdict(s), "pending")
    s = score_of(Candidate("Rybno-Lubawa", "Zamknięcie DW541 w Grabaczu (radio7, 27.10)", "search"))
    check("sam Google NIGDY nie wchodzi na pasek sam", verdict(s), "pending")

    base = syla("Rybno-Działdowo", SYLA_6848)
    google = Candidate("Rybno-Działdowo", "Ruch wahadłowy na DW 538 w Tuczkach (28.10)", "search")
    merged = score_candidates([base, google], SYLA_6848 + timedelta(days=3))
    check("Google potwierdzający feed znika jako osobne zgłoszenie", len(merged), 1)
    check("… i podnosi wynik wpisu z feedu (0,48 + 0,3)", merged[0].score, 0.78)
    other = Candidate("Rybno-Iława", "Ruch wahadłowy na DW 538 w Tuczkach", "search")
    merged = score_candidates([syla("Rybno-Działdowo", SYLA_6848), other], SYLA_6848 + timedelta(days=3))
    check("potwierdzenie liczy się tylko na TEJ SAMEJ trasie", [c.score for c in merged], [0.48, 0.4])

    # 4. Parser odpowiedzi modelu
    svc = TrafficService.__new__(TrafficService)
    roads = svc._parse_response(
        "ROUTE: Rybno-Działdowo | STATUS: Utrudnienia | REF: M1 | NOTE: Prace na DW 538 między Rybnem a Tuczkami (22.10.2026).\n"
        "ROUTE: Rybno-Lubawa | TIME: 50 min | STATUS: Utrudnienia | DELAY: 20 min | NOTE: Na drodze wojewódzkiej "
        "nr 538 w miejscowości Rybno od 2 czerwca 2025 roku do 31 grudnia 2025 roku trwa całkowite zamknięcie.\n"
        "**ROUTE:** Rybno-Iława | STATUS: Korki | NOTE: Zablokowana droga w Hartowcu po kolizji (dziś).\n"
        "ROUTE: Rybno-Olsztyn | STATUS: Utrudnienia | REF: WWW | NOTE: Utrudnienia na drogach województwa.\n"
    )
    check("4 trasy sparsowane", len(roads), 4)
    check("REF z materiału przeniesiony", roads[0].ref, "M1")
    check("minut NIE ma — nawet gdy model je podał (DELAY: 20)", [r.delayMinutes for r in roads], [0, 0, 0, 0])
    check("czasów przejazdu NIE ma", {r.travelTime for r in roads}, {""})
    check("28.10: ZDW „do 31 grudnia 2025” → Płynnie", roads[1].status, "Płynnie")
    check("utrudnienie bez REF traktowane jak sam Google", (roads[2].status, roads[2].ref), ("Utrudnienia", "WWW"))
    check("komunikat wojewódzki bez miejsca → Płynnie, bez REF", (roads[3].status, roads[3].ref), ("Płynnie", None))

    # 5. Materiał z numerami pozycji
    text = format_road_context([
        {"date": "22.10.2026", "age_days": 6, "source": "Facebook - Syla", "title": "DW538", "snippet": "Prace."},
        {"date": "28.10.2026", "age_days": 0, "source": "Gmina Rybno", "title": "Konar", "snippet": "Droga."},
    ])
    check("materiał ma [M1] i [M2]", "[M1]" in text and "[M2]" in text, True)

    # 6. Decyzja redakcji
    row = RoadReport(report_key="k", route="Rybno-Działdowo", note="x", origin="search", kind="works",
                     score=0.4, status="pending", review_token="t")
    check("oczekujące NIE jest na pasku", is_visible(row, TERAZ), False)
    apply_decision(row, "approve", TERAZ)
    check("Akceptuj → na pasku", is_visible(row, TERAZ), True)
    check(f"… ale tylko {APPROVAL_HOURS} h", is_visible(row, TERAZ + timedelta(hours=APPROVAL_HOURS + 1)), False)
    check("token zużyty", row.review_token, None)
    row2 = RoadReport(report_key="k2", route="Rybno-Lubawa", note="x", origin="feed", kind="works",
                      score=0.5, status="pending", review_token="t2")
    apply_decision(row2, "reject", TERAZ)
    check("Usuń → poza paskiem", (row2.status, is_visible(row2, TERAZ)), ("rejected", False))

    print("-" * 78)
    failures = results.count(False)
    print(f"{len(results) - failures}/{len(results)} zgodnych z oczekiwaniem")
    return failures


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
