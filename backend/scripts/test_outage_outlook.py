"""
Przegląd awarii dla pulpitu (`services/outage_outlook.py`).

Sprawdza okno (trwa / tydzień w przód / po fakcie), bramkę miejsca, zwijanie
przedruków i flagę „dotyczy Twojej wsi”. Bez bazy i bez modelu.

Użycie:
    cd backend && python -m scripts.test_outage_outlook
"""
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services import outage_outlook

NOW = datetime(2026, 10, 11, 12, 0)


@dataclass
class A:
    id: int
    title: str
    content: str = ""
    category: Optional[str] = None
    locality: Optional[int] = None
    event_at: Optional[datetime] = None
    event_until: Optional[datetime] = None
    published_at: Optional[datetime] = None
    scraped_at: Optional[datetime] = None
    display_title: Optional[str] = None


FAILED = 0


def check(name: str, ok: bool) -> None:
    global FAILED
    print(f"  {'OK ' if ok else 'BŁĄD'} {name}")
    if not ok:
        FAILED += 1


def ids(items) -> list[int]:
    return [i.article_id for i in items]


def main() -> int:
    grady = A(
        1, "Wyłączenie planowane - Region Mława - Rybno gmina wiejska",
        "Grądy 14.10.2026 09:00-13:00", "Awaria", 3,
        NOW + timedelta(days=2, hours=-3), NOW + timedelta(days=2, hours=1), NOW - timedelta(days=3),
    )
    grady_reprint = A(
        2, "Przerwa w dostawie prądu — Grądy", "We wtorek wyłączenie prądu w Grądach", "Awaria", 3,
        NOW + timedelta(days=2, hours=-3), NOW + timedelta(days=2, hours=1), NOW - timedelta(days=1),
    )
    far = A(
        3, "Wyłączenie planowane - Region Mława - Rybno gmina wiejska", "Tuczki", "Awaria", 3,
        NOW + timedelta(days=9), NOW + timedelta(days=9, hours=4), NOW,
    )
    past = A(
        4, "Wyłączenie prądu — Żabiny", "Żabiny wyłączenie prądu", "Awaria", 3,
        NOW - timedelta(hours=8), NOW - timedelta(hours=4), NOW - timedelta(days=2),
    )
    running = A(
        5, "Brak wody w Tuczkach", "Awaria sieci wodociągowej w Tuczkach", "Awaria", 3,
        published_at=NOW - timedelta(hours=2),
    )
    stale_report = A(
        6, "Brak wody w Rumianie", "Awaria wodociągu", "Awaria", 3,
        published_at=NOW - timedelta(hours=30),
    )
    foreign = A(
        7, "Wyłączenie planowane - Region Mława - Płośnica", "Płośnica wyłączenie prądu", "Awaria", 1,
        NOW + timedelta(days=1), NOW + timedelta(days=1, hours=3), NOW,
    )
    festyn = A(8, "Festyn w Żabinach", "Zapraszamy na festyn", "Wydarzenia", 3, NOW + timedelta(days=1), None, NOW)

    items = outage_outlook.build_outlook(
        [festyn, far, grady, grady_reprint, past, running, stale_report, foreign], NOW
    )

    print("Okno i bramki")
    check("zapowiedź za 2 dni wchodzi", 1 in ids(items))
    check("zapowiedź za 9 dni nie wchodzi (okno 7 dni)", 3 not in ids(items))
    check("wyłączenie po fakcie nie wchodzi", 4 not in ids(items))
    check("świeże zgłoszenie bez terminu wchodzi jako trwające", 5 in ids(items))
    check("zgłoszenie bez terminu sprzed 30 h nie wchodzi", 6 not in ids(items))
    check("awaria spoza gminy nie wchodzi", 7 not in ids(items))
    check("festyn to nie awaria", 8 not in ids(items))

    print("Kolejność i przedruki")
    check("trwające przed zapowiedzianym", ids(items)[:1] == [5])
    check("przedruk tej samej awarii zwinięty", 2 not in ids(items))
    by_id = {i.article_id: i for i in items}
    check("miejsce zdarzenia bez nazwy gminy z tytułu Energi", by_id[1].places == ("Grądy",))

    print("Twoja wieś")
    check("Grądy dotyczy mieszkańca Grądów", outage_outlook.concerns_village(by_id[1], "Grądy"))
    check("Grądy nie dotyczy mieszkańca Żabin", not outage_outlook.concerns_village(by_id[1], "Żabiny"))
    check("bez wybranej wsi nic nie jest „Twoje”", not outage_outlook.concerns_village(by_id[1], None))
    check("rejon wywozu „Rybno R1” to Rybno", outage_outlook.concerns_village(
        outage_outlook.OutlookItem(9, "x", "prad", "x", ("Rybno",), None, None, True, NOW), "Rybno R1"))

    print(f"\n{'Wszystko zielone' if not FAILED else f'Błędów: {FAILED}'}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
