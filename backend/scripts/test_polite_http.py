"""
Grzeczność wobec gminarybno.pl (25.10.2026, przebudowa po trzeciej blokadzie 12.11.2026).

Bez sieci (httpx.MockTransport) i bez bazy (`polite.MemoryStore`) — idzie do CI:
  1. odstęp między zapytaniami ≥ MIN_INTERVAL_S, także przy zapytaniach równoległych,
  2. User-Agent to deklaracja RybnoLive, nawet gdy klient zbudowano z innym,
  3. dwie odmowy 403 pod rząd zamykają host — trzecie zapytanie NIE wychodzi,
     pojedyncze 403 nie zamyka, 429 zamyka od razu, inne domeny nietknięte,
  4. wyłącznik: ZERO żądań; eskalacja 12 h → 3 doby → wyłącznik,
  5. brak odpowiedzi: jedna próba, host zamknięty, dziennik ma wiersz,
  6. limity godzinowy i dobowy,
  7. alarm odróżnia brak odpowiedzi od odmowy (6.11.2026 brzmiały tak samo),
  8. aktualności: znany wpis nie jest pobierany ponownie, stary — raz, bez paginacji,
  9. wiedza stała: strona działu raz, PDF-y tylko przy zmianie strony,
 10. akty prawne: wycinek statusów zamiast pełnego skanu.

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
        transport=polite.transport(httpx.MockTransport(handler)),
        headers={"User-Agent": "Mozilla/5.0 Chrome/121"},
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
                transport=polite.transport(httpx.MockTransport(handler)),
                timeout=self.timeout,
            )
            return self

        async def _known_ids(self, session, external_ids):
            # `session` w teście = wspólna lista „bazy” między przebiegami
            return {e for e in external_ids if e in (session or [])}

        async def save_to_db(self, articles, session):
            ids = [a["external_id"] for a in articles]
            self.saved = self.saved + ids
            if session is not None:
                session.extend(ids)
            return []

    return Fake(source_id=1, config={"download_pdfs": False, **config})


async def section_alarm() -> None:
    print("\n7️⃣  Alarm podaje przyczynę")
    from src.services import source_health

    polite.reset()
    original = polite.MIN_INTERVAL_S
    polite.MIN_INTERVAL_S = 0.01
    url = "https://bip.gminarybno.pl/112/"
    try:
        scraper = bip_scraper(lambda r: None)
        check("BIP czeka 60 s", scraper.timeout == 60, scraper.timeout)
        check("BIP: jedna próba, bez ponawiania", scraper.max_retries == 1, scraper.max_retries)

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
        check("timeout: jedna próba", sent["n"] == 1, sent["n"])
        check("timeout: host zamknięty po braku odpowiedzi", polite.is_blocked("bip.gminarybno.pl"))
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
    print("\n8️⃣  Aktualności: znany i stary wpis bez ponownego pobierania")
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
        db: list = []
        first = bip_scraper(handler)
        await first.scrape_bip(db)
        second = bip_scraper(handler)
        await second.scrape_bip(db)
        check("stary wpis pobrany raz przez dwa przebiegi", hits.get("/112/3772/wpis/") == 1, hits)
        check("stary wpis nie idzie do zapisu", "bip_3772" not in first.saved + second.saved)
        check("świeży wpis zapisany w pierwszym przebiegu", "bip_3782" in first.saved)
        check("znany świeży wpis NIE jest pobierany drugi raz", hits.get("/112/3782/wpis/") == 1, hits)
        check("bez paginacji ?start=", not any("start" in k for k in hits) and hits.get("/112/") == 2, hits)
    finally:
        polite.MIN_INTERVAL_S = original
        polite.reset()
        bip_rybno._TOO_OLD_IDS.clear()


async def section_hold_and_escalation() -> None:
    print("\n4️⃣  Wyłącznik i eskalacja (stan przeżywa restart)")
    from datetime import datetime, timedelta

    store = polite.MemoryStore()
    polite.reset(store)
    original = polite.MIN_INTERVAL_S
    polite.MIN_INTERVAL_S = 0.0
    sent = {"n": 0}

    def refuse(request):
        sent["n"] += 1
        return httpx.Response(403)

    try:
        polite.hold("bip.gminarybno.pl", "test")
        async with make_client(refuse) as c:
            try:
                await c.get("https://bip.gminarybno.pl/112/")
                raised = None
            except polite.HostBlocked as e:
                raised = e
        check("wyłącznik: HostHeld", isinstance(raised, polite.HostHeld), type(raised).__name__)
        check("wyłącznik: ZERO żądań do sieci", sent["n"] == 0, sent["n"])
        check("wyłącznik: dziennik pusty (nic nie wyszło)", not store.requests)

        polite.release("bip.gminarybno.pl")
        clock = {"now": datetime(2026, 11, 12, 6, 0)}
        real_now = polite._now
        polite._now = lambda: clock["now"]
        levels = []
        try:
            for _ in range(3):
                polite._refusals_in_row.clear()  # restart procesu: pamięć w RAM znika
                async with make_client(refuse) as c:
                    for _ in range(2):
                        try:
                            await c.get("https://bip.gminarybno.pl/112/")
                        except polite.HostBlocked:
                            pass
                st = store.state("bip.gminarybno.pl")
                levels.append((st.refusal_level, st.hold,
                               round((st.blocked_until - clock["now"]).total_seconds() / 3600)
                               if st.blocked_until else None))
                clock["now"] += timedelta(days=4)  # po przerwie, w pamięci eskalacji
        finally:
            polite._now = real_now
        check("eskalacja: 12 h → 72 h → wyłącznik", levels == [(1, False, 12), (2, False, 72), (3, True, None)], levels)
        check("eskalacja: każda odmowa w dzienniku", sum(1 for r in store.requests if r[5] == "refused") == 6,
              len(store.requests))
    finally:
        polite.MIN_INTERVAL_S = original
        polite.reset()


async def section_unavailable() -> None:
    print("\n5️⃣  Brak odpowiedzi i błąd serwera")
    store = polite.MemoryStore()
    polite.reset(store)
    original = polite.MIN_INTERVAL_S
    polite.MIN_INTERVAL_S = 0.0
    sent = {"n": 0}

    def hang(request):
        sent["n"] += 1
        raise httpx.ConnectTimeout("wisi", request=request)

    try:
        async with make_client(hang) as c:
            for path in ("/112/", "/125/"):
                try:
                    await c.get(f"https://bip.gminarybno.pl{path}")
                except (httpx.TransportError, polite.HostBlocked):
                    pass
        check("po timeoucie kolejne żądanie NIE wychodzi", sent["n"] == 1, sent["n"])
        check("timeout zapisany w dzienniku", [r[5] for r in store.requests] == ["timeout"], store.requests)
        st = store.state("bip.gminarybno.pl")
        check("timeout nie podnosi eskalacji", st.refusal_level == 0 and not st.hold)

        polite.reset(polite.MemoryStore())
        async with make_client(lambda r: httpx.Response(503)) as c:
            await c.get("https://bip.gminarybno.pl/112/")
        check("5xx zamyka host", polite.is_blocked("bip.gminarybno.pl"))
    finally:
        polite.MIN_INTERVAL_S = original
        polite.reset()


async def section_budget() -> None:
    print("\n6️⃣  Limity wolumenu")
    store = polite.MemoryStore()
    polite.reset(store)
    original = (polite.MIN_INTERVAL_S, polite.HOURLY_LIMIT, polite.DAILY_LIMIT)
    polite.MIN_INTERVAL_S, polite.HOURLY_LIMIT, polite.DAILY_LIMIT = 0.0, 5, 8
    sent = {"n": 0}

    def ok(request):
        sent["n"] += 1
        return httpx.Response(200)

    try:
        async with make_client(ok) as c:
            hit = None
            for i in range(7):
                try:
                    await c.get(f"https://bip.gminarybno.pl/p{i}")
                except polite.BudgetExhausted as e:
                    hit = e
                    break
        check("limit godzinowy zatrzymuje 6. żądanie", sent["n"] == 5 and hit is not None, sent["n"])
        check("domyślne limity z pisma: 60/h, 150/dobę", original[1:] == (60, 150), original[1:])
        check("portal gminy ma osobny licznik", store.count_since("gminarybno.pl", polite._now().replace(year=2000)) == 0)
    finally:
        polite.MIN_INTERVAL_S, polite.HOURLY_LIMIT, polite.DAILY_LIMIT = original
        polite.reset()


async def section_knowledge() -> None:
    print("\n9️⃣  Wiedza stała: mniej żądań")
    from datetime import datetime, timedelta

    from src.scrapers import bip_knowledge as bk

    polite.reset()
    original = polite.MIN_INTERVAL_S
    polite.MIN_INTERVAL_S = 0.0
    hits: dict = {}
    section = (
        '<div class="information">Statut Gminy Rybno — treść działu ' + "x" * 200 +
        ' <a href="/125/7/Zalacznik/">Doc 7</a><a href="/125/8/Inny/">Doc 8</a>'
        ' <a href="/system/pobierz.php?plik=statut.pdf">PDF</a></div>'
    )
    doc = '<div class="information">Dokument ' + "y" * 200 + ' <a href="/system/pobierz.php?plik=d.pdf">p</a></div>'

    def handler(request):
        key = request.url.raw_path.decode()
        hits[key] = hits.get(key, 0) + 1
        if key == "/125/":
            return httpx.Response(200, text=section)
        if "pobierz" in key:
            return httpx.Response(404)
        return httpx.Response(200, text=doc)

    now = datetime(2026, 11, 15, 4, 0)
    known_hash = bk.page_hash(bk.BipKnowledgeScraper()._parse_document(section)["content"],
                              bk.BipKnowledgeScraper()._parse_document(section)["pdf_urls"])
    known = {
        "https://bip.gminarybno.pl/125/": (known_hash, now - timedelta(days=30)),
        "https://bip.gminarybno.pl/125/7/Zalacznik/": (None, now - timedelta(days=10)),
    }

    class Fake(bk.BipKnowledgeScraper):
        async def __aenter__(self):
            self.client = httpx.AsyncClient(transport=polite.transport(httpx.MockTransport(handler)))
            return self

    try:
        scraper = Fake({"sections": [{"id": "125", "name": "Statut Gminy"}]}, known=known, now=now)
        docs = await scraper.scrape_all()
        check("strona działu pobrana RAZ", hits.get("/125/") == 1, hits)
        check("znany, świeżo sprawdzony dokument NIE pobierany", "/125/7/Zalacznik/" not in hits, hits)
        check("nowy dokument pobrany", hits.get("/125/8/Inny/") == 1, hits)
        check("strona działu bez zmian → bez PDF-u działu", "/system/pobierz.php?plik=statut.pdf" not in hits, hits)
        own = next((d for d in docs if d["url"].endswith("/125/")), {})
        check("dział bez zmian zgłoszony jako unchanged", own.get("unchanged") is True, own)
        check("licznik żądań przebiegu", scraper.requests == len([k for k in hits]) or scraper.requests == sum(hits.values()),
              (scraper.requests, hits))
        weeks = {w: [s[0] for s in bk.sections_for_week(bk.DEFAULT_SECTIONS, w)] for w in range(4)}
        covered = sorted(x for v in weeks.values() for x in v)
        check("działy rozłożone na 4 tygodnie, każdy raz", covered == sorted(s[0] for s in bk.DEFAULT_SECTIONS),
              {w: len(v) for w, v in weeks.items()})
        check("w tygodniu najwyżej 5 działów", max(len(v) for v in weeks.values()) <= 5)
    finally:
        polite.MIN_INTERVAL_S = original
        polite.reset()


def section_legal() -> None:
    print("\n🔟  Akty prawne: wycinek statusów")
    from src.scrapers.legal_acts import STATUS_CYCLE_WEEKS, STATUS_SLICE_PAGES, status_slice

    pages = sorted(p for w in range(STATUS_CYCLE_WEEKS) for p in status_slice(w))
    check("cykl obejmuje strony 1–48 bez dziur", pages == list(range(1, 49)), pages[:3])
    check("tygodniowo najwyżej 8 stron statusów", STATUS_SLICE_PAGES <= 8)


async def main() -> None:
    await section_tempo()
    await section_ua()
    await section_stop()
    await section_hold_and_escalation()
    await section_unavailable()
    await section_budget()
    await section_alarm()
    await section_too_old()
    await section_knowledge()
    section_legal()
    ok = sum(results)
    print(f"\n{'✅' if ok == len(results) else '❌'} {ok}/{len(results)} sprawdzeń")
    sys.exit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
