"""
Grzeczność wobec gminarybno.pl: tempo, User-Agent, stop po odmowie (25.10.2026).

Dostawca BIP zdjął blokadę IP pod warunkiem ≥ 1 s między zapytaniami. Bez sieci
(httpx.MockTransport) — dlatego idzie do CI:
  1. odstęp między zapytaniami ≥ MIN_INTERVAL_S, także przy zapytaniach równoległych,
  2. User-Agent to deklaracja RybnoLive, nawet gdy klient zbudowano z innym,
  3. dwie odmowy 403 pod rząd zamykają host — trzecie zapytanie NIE wychodzi,
  4. pojedyncze 403 (jeden PDF) hosta nie zamyka, a sukces zeruje licznik,
  5. 429 zamyka od razu; inne domeny są nietknięte,
  6. alarm odróżnia brak odpowiedzi od odmowy (6.11.2026 brzmiały tak samo),
  7. wpis BIP z datą sprzed okna jest pobierany tylko raz.

    cd backend && python -m scripts.test_polite_http
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

from src.scrapers import polite

results: list[bool] = []


def check(label: str, ok: bool, detail="") -> None:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "Mozilla/5.0 Chrome/121"},
        event_hooks=polite.hooks(),
    )


async def section_tempo() -> None:
    print("\n1️⃣  Odstęp między zapytaniami")
    polite.reset()
    stamps: list[float] = []

    def handler(request):
        stamps.append(time.monotonic())
        return httpx.Response(200, text="ok")

    original = polite.MIN_INTERVAL_S
    polite.MIN_INTERVAL_S = 0.3  # test nie ma czekać sekund; reguła ta sama
    try:
        async with make_client(handler) as c:
            for _ in range(3):
                await c.get("https://bip.gminarybno.pl/112/")
            seq = [b - a for a, b in zip(stamps, stamps[1:])]
            check("kolejne zapytania: odstęp ≥ interwał", all(g >= 0.29 for g in seq), [round(g, 2) for g in seq])

            stamps.clear()
            await asyncio.gather(*(c.get(f"https://gminarybno.pl/a{i}") for i in range(4)))
            stamps.sort()
            par = [b - a for a, b in zip(stamps, stamps[1:])]
            check("zapytania równoległe też są rozstawiane", all(g >= 0.29 for g in par), [round(g, 2) for g in par])

            stamps.clear()
            await c.get("https://bip.gminarybno.pl/1/")
            await c.get("https://gminarybno.pl/2")
            gap = stamps[1] - stamps[0]
            check("BIP i serwis gminy dzielą jeden limit (ta sama domena)", gap >= 0.29, round(gap, 2))
    finally:
        polite.MIN_INTERVAL_S = original
    check("domyślny interwał spełnia prośbę dostawcy (≥ 1 s)", polite.MIN_INTERVAL_S >= 1.0)


async def section_ua() -> None:
    print("\n2️⃣  User-Agent")
    polite.reset()
    seen: list[str] = []

    def handler(request):
        seen.append(request.headers["user-agent"])
        return httpx.Response(200, text="ok")

    original = polite.MIN_INTERVAL_S
    polite.MIN_INTERVAL_S = 0.0
    try:
        async with make_client(handler) as c:
            await c.get("https://bip.gminarybno.pl/112/")
            await c.get("https://example.org/")
    finally:
        polite.MIN_INTERVAL_S = original
    check("gminarybno.pl dostaje deklarację RybnoLive", seen[0] == polite.RYBNOLIVE_UA, seen[0])
    check("nie udajemy przeglądarki", "Mozilla" not in seen[0])
    check("obca domena zachowuje własny nagłówek klienta", seen[1].startswith("Mozilla"), seen[1])


async def section_stop() -> None:
    print("\n3️⃣  Stop po odmowie")
    original = polite.MIN_INTERVAL_S
    polite.MIN_INTERVAL_S = 0.0
    try:
        polite.reset()
        sent = {"n": 0}

        def refuse(request):
            sent["n"] += 1
            return httpx.Response(403, text="forbidden")

        async with make_client(refuse) as c:
            await c.get("https://bip.gminarybno.pl/112/")
            check("po jednej odmowie host jest otwarty", not polite.is_blocked("bip.gminarybno.pl"))
            await c.get("https://bip.gminarybno.pl/125/")
            check("po drugiej odmowie pod rząd host jest zamknięty", polite.is_blocked("bip.gminarybno.pl"))
            try:
                await c.get("https://bip.gminarybno.pl/2/")
                raised = False
            except polite.HostBlocked:
                raised = True
            check("trzecie zapytanie rzuca HostBlocked", raised)
            check("…i NIE wychodzi do sieci", sent["n"] == 2, sent["n"])

        polite.reset()
        calls = iter([403, 200, 403, 200])

        def mixed(request):
            return httpx.Response(next(calls), text="x")

        async with make_client(mixed) as c:
            for i in range(4):
                await c.get(f"https://bip.gminarybno.pl/p{i}")
        check("pojedyncze 403 przedzielone sukcesem hosta nie zamyka", not polite.is_blocked("bip.gminarybno.pl"))

        polite.reset()
        sent["n"] = 0

        def limited(request):
            sent["n"] += 1
            return httpx.Response(429, headers={"Retry-After": "120"}, text="slow down")

        async with make_client(limited) as c:
            await c.get("https://bip.gminarybno.pl/112/")
            check("429 zamyka host od razu", polite.is_blocked("bip.gminarybno.pl"))
            try:
                await c.get("https://bip.gminarybno.pl/112/")
                raised = False
            except polite.HostBlocked:
                raised = True
            check("…i kolejne zapytanie nie wychodzi", raised and sent["n"] == 1)

        async with make_client(lambda r: httpx.Response(403)) as c:
            await c.get("https://example.org/a")
            await c.get("https://example.org/b")
        check("odmowa obcej domeny niczego nie zamyka", not polite.is_blocked("example.org"))
    finally:
        polite.MIN_INTERVAL_S = original
        polite.reset()


def bip_scraper(handler, **config) -> "BipRybnoScraper":
    """Scraper BIP na atrapie sieci i bez bazy: zapis tylko zbiera wpisy."""
    from src.scrapers.bip_rybno import BipRybnoScraper

    class Fake(BipRybnoScraper):
        saved: list = []

        async def __aenter__(self):
            self.client = httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                timeout=self.timeout,
                event_hooks=polite.hooks(),
            )
            return self

        async def _known_stale_ids(self, session, external_ids, cutoff):
            return set()

        async def save_to_db(self, articles, session):
            self.saved = self.saved + [a["external_id"] for a in articles]
            return []

    return Fake(source_id=1, config={"download_pdfs": False, **config})


async def section_alarm() -> None:
    print("\n6️⃣  Alarm podaje przyczynę")
    from src.services import source_health

    polite.reset()
    original = polite.MIN_INTERVAL_S
    polite.MIN_INTERVAL_S = 0.01
    url = "https://bip.gminarybno.pl/112/"
    try:
        scraper = bip_scraper(lambda r: None)
        check("BIP czeka 60 s", scraper.timeout == 60, scraper.timeout)
        check("BIP ponawia raz", scraper.max_retries == 2, scraper.max_retries)

        sent = {"n": 0}

        def hang(request):
            sent["n"] += 1
            raise httpx.ReadTimeout("wisi", request=request)

        scraper = bip_scraper(hang)
        async with scraper:
            try:
                await scraper.fetch(url)
                message = ""
            except Exception as e:
                message = str(e)
        alert = source_health.alert_text([("BIP", source_health.FAILED, message)]) or ""
        check("timeout: dwie próby", sent["n"] == 2, sent["n"])
        check("timeout: alarm mówi o braku odpowiedzi", "brak odpowiedzi w 60 s" in alert, alert)
        check("timeout: nie udaje blokady", "403" not in alert and "odmówił" not in alert)

        polite.reset()
        scraper = bip_scraper(lambda r: httpx.Response(403))
        async with scraper:
            try:
                await scraper.fetch(url)
                message = ""
            except Exception as e:
                message = str(e)
        alert = source_health.alert_text([("BIP", source_health.FAILED, message)]) or ""
        check("odmowa: alarm mówi o 403", "403" in alert, alert)
        check("odmowa: nie udaje timeoutu", "brak odpowiedzi" not in alert)
    finally:
        polite.MIN_INTERVAL_S = original
        polite.reset()


async def section_too_old() -> None:
    print("\n7️⃣  Wpis sprzed okna pobierany raz")
    from datetime import datetime

    from src.scrapers import bip_rybno

    polite.reset()
    bip_rybno._TOO_OLD_IDS.clear()
    original = polite.MIN_INTERVAL_S
    polite.MIN_INTERVAL_S = 0.01
    today = datetime.utcnow().strftime("%Y-%m-%d")
    listing = "".join(
        f'<div class="information"><a href="/112/{i}/wpis/">Wpis numer {i}</a></div>'
        for i in (3782, 3772)
    )
    dates = {"3782": today, "3772": "2026-10-01"}
    hits: dict = {}

    def handler(request):
        path = request.url.path
        hits[path] = hits.get(path, 0) + 1
        if path == "/112/":
            return httpx.Response(200, text=listing)
        date = dates[path.split("/")[2]]
        return httpx.Response(200, text=(
            f'<div class="information-parameters">Informacja ogłoszona dnia {date} 11:17:43</div>'
            '<div class="information">Treść wpisu dłuższa niż dwadzieścia znaków.</div>'
        ))

    try:
        first = bip_scraper(handler)
        await first.scrape_bip(None)
        second = bip_scraper(handler)
        await second.scrape_bip(None)
        check("stary wpis pobrany raz przez dwa przebiegi", hits.get("/112/3772/wpis/") == 1, hits)
        check("stary wpis nie idzie do zapisu", "bip_3772" not in first.saved + second.saved)
        check("świeży wpis nadal idzie do zapisu", "bip_3782" in first.saved and "bip_3782" in second.saved)
    finally:
        polite.MIN_INTERVAL_S = original
        polite.reset()
        bip_rybno._TOO_OLD_IDS.clear()


async def main() -> None:
    await section_tempo()
    await section_ua()
    await section_stop()
    await section_alarm()
    await section_too_old()
    ok = sum(results)
    print(f"\n{'✅' if ok == len(results) else '❌'} {ok}/{len(results)} sprawdzeń")
    sys.exit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
