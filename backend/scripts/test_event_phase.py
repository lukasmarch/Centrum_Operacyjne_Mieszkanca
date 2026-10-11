"""
Jedna reguła końca i fazy zdarzenia (audyt 11.10.2026, F-004).

Do 11.10 pięć miejsc odpowiadało inaczej na „czy to jeszcze trwa”: feed +3 h,
etykieta dla modelu 0 h, Strażnik 0 h i bez wpisów całodniowych, kalendarz
we froncie +2 h, plakietka wpisu 0 h. Ten test trzyma je razem:

  1. `time_span.phase` / `event_end` — przypadki brzegowe
  2. etykieta feedu, etykieta briefingu i Strażnik mówią to samo
  3. nagłówek briefingu: surowszy warunek, ale wyprowadzony z tej samej fazy
  4. front ma tę samą stałą (`eventTime.ts::DEFAULT_DURATION_H`)

Bez bazy i modelu — w CI.

    cd backend && python -m scripts.test_event_phase
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ai.summary_generator import _event_is_over, _time_label
from src.ai.tools.alerts import _kind
from src.services.feed_policy import time_label
from src.services.time_span import DEFAULT_EVENT_DURATION_H, event_end, phase

results: list[bool] = []


def check(label: str, ok: bool, detail="") -> None:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))


# 11.10.2026, czas letni (UTC+2). Wszystko w naiwnym UTC, jak w bazie.
ALL_DAY = datetime(2026, 10, 10, 22, 0)     # „11 października”, bez godziny
NINE = datetime(2026, 10, 11, 7, 0)         # 9:00 lokalnie, bez końca
SPAN = (datetime(2026, 10, 11, 7, 30), datetime(2026, 10, 11, 13, 0))  # 9:30–15:00
RANGE = (datetime(2026, 10, 4, 22, 0), datetime(2026, 10, 11, 22, 0))  # 5–11 października


def local(h: int, m: int = 0, day: int = 11) -> datetime:
    """Godzina lokalna 11.10 → naiwny UTC."""
    return datetime(2026, 10, day, h, m) - timedelta(hours=2)


def section_core() -> None:
    print("\n1️⃣  Faza i koniec")
    check("całodniowe o 6:00 w dniu zdarzenia → trwa (Strażnik: „minione” od 00:00)",
          phase(ALL_DAY, None, local(6)) == "ongoing")
    check("całodniowe o 23:30 → trwa", phase(ALL_DAY, None, local(23, 30)) == "ongoing")
    check("całodniowe nazajutrz → po", phase(ALL_DAY, None, local(0, 30, day=12)) == "ended")
    check("koniec całodniowego = lokalna północ", event_end(ALL_DAY) == datetime(2026, 10, 11, 22, 0))
    check("9:00 bez końca, o 10:00 → trwa (do 11.10: „już po” w minucie startu)",
          phase(NINE, None, local(10)) == "ongoing")
    check(f"9:00 bez końca, po {DEFAULT_EVENT_DURATION_H} h → po",
          phase(NINE, None, local(9 + DEFAULT_EVENT_DURATION_H)) == "ended")
    check("podany koniec rozstrzyga", phase(*SPAN, local(15, 1)) == "ended" and phase(*SPAN, local(14)) == "ongoing")
    check("zakres dni w środku → trwa", phase(*RANGE, local(12, day=8)) == "ongoing")
    check("przed startem → przed nami", phase(NINE, None, local(8)) == "upcoming")
    check("bez terminu → brak fazy", phase(None, None, local(8)) is None)


def article(start, end=None, category="Awaria"):
    return SimpleNamespace(event_at=start, event_until=end, category=category,
                           published_at=datetime(2026, 10, 8, 10, 0), scraped_at=None)


def agree(name: str, start, end, now, expected: str) -> None:
    """Feed, briefing i Strażnik — ta sama odpowiedź dla tego samego wpisu."""
    feed = time_label(None, start, end, now)
    brief = _time_label(article(start, end), now)
    guard = _kind(start, end, now)
    if expected == "ended":
        ok = "zakończyło" in feed and "JUŻ PO" in brief and guard == "minione"
    elif expected == "ongoing":
        ok = "zakończyło" not in feed and "JUŻ PO" not in brief and guard == "trwa"
    else:
        ok = "zakończyło" not in feed and "JUŻ PO" not in brief and guard == "zapowiedziane"
    check(f"{name}: wszyscy mówią „{expected}”", ok, f"feed={feed!r} | briefing={brief!r} | Strażnik={guard}")


def section_agreement() -> None:
    print("\n2️⃣  Feed, briefing i Strażnik zgodnie")
    agree("całodniowe, 6:00 w dniu", ALL_DAY, None, local(6), "ongoing")
    agree("9:00 bez końca, 10:00", NINE, None, local(10), "ongoing")
    agree("9:00 bez końca, 13:00", NINE, None, local(13), "ended")
    agree("9:30–15:00, 14:00", *SPAN, local(14), "ongoing")
    agree("9:30–15:00, 15:30", *SPAN, local(15, 30), "ended")
    agree("9:00, o 8:00", NINE, None, local(8), "upcoming")
    feed = time_label(None, NINE, None, local(10))
    check("bez podanego końca etykieta NIE zmyśla godziny końca",
          "KONIEC NIEZNANY" in feed and "TRWA TERAZ" not in feed, feed)


def section_headline() -> None:
    print("\n3️⃣  Nagłówek briefingu: surowszy, z tej samej fazy")
    check("9:00 bez końca, o 10:00 → nie nadaje się już na nagłówek (nie da się zdążyć)",
          _event_is_over(article(NINE), local(10)))
    check("całodniowe dziś → wciąż nagłówek", not _event_is_over(article(ALL_DAY), local(13)))
    check("9:30–15:00, o 14:00 → wciąż nagłówek (trwa, koniec znany)", not _event_is_over(article(*SPAN), local(14)))
    check("przed startem → nagłówek", not _event_is_over(article(NINE), local(8)))


def section_frontend() -> None:
    print("\n4️⃣  Front ma tę samą regułę")
    src = (Path(__file__).parent.parent.parent / "frontend/src/utils/eventTime.ts").read_text()
    m = re.search(r"DEFAULT_DURATION_H\s*=\s*(\d+)", src)
    front = int(m.group(1)) if m else None
    check("eventTime.ts::DEFAULT_DURATION_H == time_span.DEFAULT_EVENT_DURATION_H",
          front == DEFAULT_EVENT_DURATION_H, f"front={front}, backend={DEFAULT_EVENT_DURATION_H}")


if __name__ == "__main__":
    section_core()
    section_agreement()
    section_headline()
    section_frontend()
    passed = sum(results)
    print(f"\n{'✅' if passed == len(results) else '❌'} {passed}/{len(results)} sprawdzeń")
    sys.exit(0 if passed == len(results) else 1)
