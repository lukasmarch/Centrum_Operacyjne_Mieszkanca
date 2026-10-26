"""
Test wykrywania sesji: kanał RSS YouTube gminy i bramka kalendarza.

    python -m scripts.test_council_sessions          # offline, na wklejonym XML
    python -m scripts.test_council_sessions --live   # + realne odpytanie kanału

Od 26.10.2026 źródłem jest kanał YouTube gminy (galeria `nagrania_wideo.html`
zniknęła z nowej strony gminy). Kanał miesza sesje rady ze spotkaniami
konsultacyjnymi — test pilnuje, żeby spotkanie nie trafiło do kolejki
transkrypcji, a job pytał kanał tylko wokół terminu sesji z kalendarza.
"""
import argparse
import asyncio
import sys
from datetime import date, datetime

from src.scrapers.council_sessions import parse_feed

FAILURES: list = []

# Fragment realnego kanału (26.10.2026), w kolejności publikacji.
FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
 <title>Gmina Rybno</title>
 <entry>
  <yt:videoId>quyYDnXDBEY</yt:videoId>
  <title>XXV Sesja Rady Gminy Rybno 30.09.2026 r.</title>
  <published>2026-10-01T00:10:21+00:00</published>
 </entry>
 <entry>
  <yt:videoId>RCZgLvTSnl4</yt:videoId>
  <title>Spotkanie w ramach konsultacji społecznych dot. projektu planu ogólnego Gminy Rybno 23.07.2026 r.</title>
  <published>2026-07-24T02:59:00+00:00</published>
 </entry>
 <entry>
  <yt:videoId>ytBiBVzlduU</yt:videoId>
  <title>XXIV  Sesja Rady Gminy Rybno 27.08.2026 r.</title>
  <published>2026-08-27T23:31:00+00:00</published>
 </entry>
</feed>
"""


def check(label: str, got, expected) -> None:
    ok = got == expected
    print(f"  {'OK  ' if ok else 'BŁĄD'} {label}: {got!r}" + ("" if ok else f" (oczekiwano {expected!r})"))
    if not ok:
        FAILURES.append(label)


def test_parsowanie() -> None:
    print("\n== Kanał RSS ==")
    recordings = parse_feed(FEED_XML)
    check("każde nagranie raz", len(recordings), 3)
    check("sortowanie od najnowszej sesji",
          [r.youtube_id for r in recordings], ["quyYDnXDBEY", "ytBiBVzlduU", "RCZgLvTSnl4"])
    sesja = recordings[0]
    check("identyfikator yt: (ten sam co w run_council_session)", sesja.page_id, "yt:quyYDnXDBEY")
    check("data z tytułu", sesja.session_date, date(2026, 9, 30))
    check("numer sesji", sesja.session_number, "XXV")
    check("rozpoznana jako sesja", sesja.is_session, True)
    check("podwójna spacja w tytule nie psuje numeru", recordings[1].session_number, "XXIV")
    spotkanie = recordings[2]
    check("spotkanie konsultacyjne to NIE sesja", spotkanie.is_session, False)
    check("link do nagrania", sesja.video_url, "https://www.youtube.com/watch?v=quyYDnXDBEY")
    check("link do minuty", sesja.watch_url_at(754.6),
          "https://www.youtube.com/watch?v=quyYDnXDBEY&t=754s")


def test_bramka_kalendarza() -> None:
    """Kanał pytamy wokół terminu sesji z kalendarza, nie codziennie."""
    print("\n== Bramka kalendarza ==")
    from src.scheduler.council_job import session_window_open

    xxv = [datetime(2026, 9, 30, 8, 0)]           # 10:00 lokalnie
    check("dzień obrad 14:00", session_window_open(xxv, datetime(2026, 9, 30, 12)), True)
    check("nazajutrz (nagranie wchodzi w nocy)", session_window_open(xxv, datetime(2026, 10, 1, 12)), True)
    check("drugi dzień po", session_window_open(xxv, datetime(2026, 10, 2, 18)), True)
    check("trzeci dzień po — już nie", session_window_open(xxv, datetime(2026, 10, 3, 12)), False)
    check("przed sesją — nie", session_window_open(xxv, datetime(2026, 9, 29, 12)), False)
    całodniowa = [datetime(2026, 9, 29, 22, 0)]    # lokalna północ 30.09
    check("termin bez godziny = właściwa doba", session_window_open(całodniowa, datetime(2026, 9, 30, 12)), True)
    check("zwykły wtorek bez sesji", session_window_open([], datetime(2026, 10, 27, 12)), False)
    check("poniedziałek 14:00 — kontrola tygodniowa", session_window_open([], datetime(2026, 10, 26, 13)), True)
    check("poniedziałek 20:00 — bez drugiej kontroli", session_window_open([], datetime(2026, 10, 26, 19)), False)


def test_bramka_transmisji() -> None:
    """
    Zapowiedziana transmisja to nie awaria nagrania.

    26.08.2026 galeria gminy (dziś kanał) miała wpis o sesji XXIV z adresem YouTube, a sama
    sesja zaczynała się dopiero nazajutrz o 10:00. Bez tej bramki `council_job`
    wpisywał wiersz w `error` i zjadał próbę za każdym razem, gdy zaglądał do
    zapowiedzi.
    """
    print("\n== Bramka transmisji ==")
    from datetime import datetime, timezone

    from src.services.council_transcript import not_ready_reason

    start = datetime(2026, 8, 27, 8, 0, tzinfo=timezone.utc)
    upcoming = not_ready_reason(
        {"live_status": "is_upcoming", "release_at": start, "duration_s": 0.0}
    )
    check("zapowiedź wstrzymuje przebieg", bool(upcoming), True)
    check("powód niesie termin startu", "27.08.2026" in (upcoming or ""), True)

    check("trwająca transmisja czeka",
          not_ready_reason({"live_status": "is_live", "release_at": start}) is not None,
          True)
    # `post_live` przechodzi świadomie: obrady się skończyły, a wartość skrótu
    # bierze się z tego, że powstaje tego samego dnia — ale dopiero gdy YouTube
    # domknie VOD i poda jego długość.
    check("nagranie po transmisji przechodzi",
          not_ready_reason(
              {"live_status": "post_live", "release_at": start, "duration_s": 5185.0}
          ), None)
    check("zwykłe nagranie przechodzi",
          not_ready_reason({"live_status": "was_live", "duration_s": 5185.0}), None)

    # 27.08.2026: z IP serwera YouTube nie oddaje ani metadanych, ani ścieżek,
    # a `live_status` wraca jako `NA` — czyli poza `LIVE_NOT_READY`. Stara bramka
    # przepuszczała to jak gotowe nagranie i próba przepadała na `download_audio`.
    blocked = not_ready_reason(
        {"live_status": "NA", "duration_s": 0.0, "blocked": True}
    )
    check("blokada IP wstrzymuje przebieg", bool(blocked), True)
    check("powód nazywa blokadę", "bot-check" in (blocked or ""), True)
    check("VOD bez ścieżek czeka, nie wybucha",
          bool(not_ready_reason({"live_status": "post_live", "duration_s": 0.0})), True)
    check("brak pola wstrzymuje (nie ma czego pobierać)",
          bool(not_ready_reason({})), True)


async def test_live() -> None:
    print("\n== Odpytanie na żywo ==")
    from src.scrapers.council_sessions import fetch_recordings

    recordings = await fetch_recordings(limit=5)
    check("kanał zwrócił sesje", len(recordings) > 0, True)
    for recording in recordings:
        print(f"    {recording.session_date} | {recording.session_number or '-':>6} "
              f"| {recording.youtube_id or 'BRAK':>11} | {recording.title[:48]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Odpytaj kanał YouTube gminy")
    args = parser.parse_args()

    print("=" * 68)
    print("NAGRANIA SESJI RADY — kanał gminy i bramka kalendarza")
    print("=" * 68)
    test_parsowanie()
    test_bramka_kalendarza()
    test_bramka_transmisji()
    if args.live:
        asyncio.run(test_live())

    print("\n" + "=" * 68)
    if FAILURES:
        print(f"NIEPOWODZENIA ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print("Wszystkie testy przeszły.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
