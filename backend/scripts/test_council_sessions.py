"""
Test parsowania galerii nagrań gminy.

    python -m scripts.test_council_sessions          # offline, na wklejonym HTML
    python -m scripts.test_council_sessions --live   # + realne odpytanie gminarybno.pl

Galeria miesza sesje rady z nagraniami spotkań i imprez, a każdy wpis występuje
w HTML dwa razy (miniatura i podpis). Test pilnuje, żeby jedno nagranie dawało
jeden rekord z pełnym tytułem — i żeby festyn nie trafił do kolejki transkrypcji.
"""
import argparse
import asyncio
import sys
from datetime import date

from src.scrapers.council_sessions import extract_youtube_id, parse_gallery

FAILURES: list = []

# Fragment realnej galerii (6.08.2026), z zachowaną duplikacją linków.
GALLERY_HTML = """
<div class="gallery">
<a href="nagrania_wideo/transmisja-spotkania-w-sprawie-planu-ogolnego,7574.html"><img src="x.jpg"></a>
<a href="nagrania_wideo/transmisja-spotkania-w-sprawie-planu-ogolnego,7574.html"
   title="Transmisja spotkania w sprawie Planu Ogólnego"> Transmisja spotkania w sprawie Planu </a>
<a href="nagrania_wideo/xxiii-sesja-rady-gminy-rybno-z-dnia-24062026-r,7556.html"><img src="y.jpg"></a>
<a href="nagrania_wideo/xxiii-sesja-rady-gminy-rybno-z-dnia-24062026-r,7556.html"
   title="XXIII Sesja Rady Gminy Rybno z dnia 24.06.2026 r. "> XXIII Sesja Rady Gminy </a>
<a href="nagrania_wideo/xxii-sesja-rady-gminy-rybno-z-dnia-27052026-r,7534.html"
   title="XXII Sesja Rady Gminy Rybno z dnia 27.05.2026 r. "> XXII Sesja </a>
<a href="https://gminarybno.pl/aktywny_wypoczynek/samochodem,69.html" title="Samochodem">Samochodem</a>
</div>
"""

EMBED_HTML = """
<div class="information"><iframe width="560" height="315"
 src="https://www.youtube.com/embed/6h9iKlveTcs?si=4PEXCVZF52AJd1Yo" title="YouTube"></iframe></div>
"""


def check(label: str, got, expected) -> None:
    ok = got == expected
    print(f"  {'OK  ' if ok else 'BŁĄD'} {label}: {got!r}" + ("" if ok else f" (oczekiwano {expected!r})"))
    if not ok:
        FAILURES.append(label)


def test_parsowanie() -> None:
    print("\n== Parsowanie galerii ==")
    recordings = parse_gallery(GALLERY_HTML)

    check("każde nagranie raz", len(recordings), 3)
    check("link spoza galerii pominięty",
          all("nagrania_wideo" in r.page_url for r in recordings), True)

    by_id = {r.page_id: r for r in recordings}
    sesja = by_id["7556"]
    check("pełny tytuł z atrybutu, nie ucięty tekst linku",
          sesja.title, "XXIII Sesja Rady Gminy Rybno z dnia 24.06.2026 r.")
    check("data z tytułu", sesja.session_date, date(2026, 6, 24))
    check("numer sesji", sesja.session_number, "XXIII")
    check("rozpoznana jako sesja", sesja.is_session, True)
    check("adres bezwzględny", sesja.page_url.startswith("https://gminarybno.pl/"), True)

    spotkanie = by_id["7574"]
    check("spotkanie konsultacyjne to NIE sesja", spotkanie.is_session, False)
    check("spotkanie bez daty w tytule", spotkanie.session_date, None)

    check("sortowanie od najnowszej", [r.page_id for r in recordings][:2], ["7556", "7534"])


def test_youtube() -> None:
    print("\n== Adres nagrania ==")
    check("id z iframe", extract_youtube_id(EMBED_HTML), "6h9iKlveTcs")
    check("brak iframe", extract_youtube_id("<div>bez wideo</div>"), None)

    recordings = parse_gallery(GALLERY_HTML)
    sesja = next(r for r in recordings if r.page_id == "7556")
    sesja.youtube_id = "6h9iKlveTcs"
    check("link do nagrania", sesja.video_url, "https://www.youtube.com/watch?v=6h9iKlveTcs")
    check("link do minuty", sesja.watch_url_at(754.6),
          "https://www.youtube.com/watch?v=6h9iKlveTcs&t=754s")


async def test_live() -> None:
    print("\n== Odpytanie na żywo ==")
    from src.scrapers.council_sessions import fetch_recordings

    recordings = await fetch_recordings(limit=5)
    check("galeria coś zwróciła", len(recordings) > 0, True)
    with_video = [r for r in recordings if r.youtube_id]
    check("nagrania mają adresy YouTube", len(with_video) > 0, True)
    for recording in recordings:
        print(f"    {recording.session_date} | {recording.session_number or '-':>6} "
              f"| {recording.youtube_id or 'BRAK':>11} | {recording.title[:48]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Odpytaj gminarybno.pl")
    args = parser.parse_args()

    print("=" * 68)
    print("GALERIA NAGRAŃ GMINY — wykrywanie sesji")
    print("=" * 68)
    test_parsowanie()
    test_youtube()
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
