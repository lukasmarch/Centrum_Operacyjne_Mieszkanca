"""
Grzeczność wobec gminarybno.pl: tempo, User-Agent, stop po odmowie (25.10.2026).

Dostawca BIP zdjął blokadę IP pod warunkiem ≥ 1 s między zapytaniami. Bez sieci
(httpx.MockTransport) — dlatego idzie do CI:
  1. odstęp między zapytaniami ≥ MIN_INTERVAL_S, także przy zapytaniach równoległych,
  2. User-Agent to deklaracja RybnoLive, nawet gdy klient zbudowano z innym,
  3. dwie odmowy 403 pod rząd zamykają host — trzecie zapytanie NIE wychodzi,
  4. pojedyncze 403 (jeden PDF) hosta nie zamyka, a sukces zeruje licznik,
  5. 429 zamyka od razu; inne domeny są nietknięte.

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


async def main() -> None:
    await section_tempo()
    await section_ua()
    await section_stop()
    ok = sum(results)
    print(f"\n{'✅' if ok == len(results) else '❌'} {ok}/{len(results)} sprawdzeń")
    sys.exit(0 if ok == len(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
