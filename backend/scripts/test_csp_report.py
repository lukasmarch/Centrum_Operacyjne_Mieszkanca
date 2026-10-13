"""
Raporty CSP — endpoint, prywatność i granice (audyt 11.10.2026, E8).

Endpoint jest PUBLICZNY i przyjmuje zapis od każdego, więc test pilnuje trzech rzeczy:
  1. PRYWATNOŚĆ: do bazy nie wchodzi nic poza agregatem. Token z adresu strony (`?kod=…`,
     reset hasła) i ścieżka/parametry zablokowanego źródła nie mogą zostać zapisane
  2. GRANICE: sufit różnych wpisów, limit żądań na IP, rozmiar ciała, śmieci → zawsze 204
  3. POPRAWNOŚĆ: oba formaty raportów, licznik rośnie zamiast dublować wiersz, retencja 30 dni

Część 1–2 działa bez bazy, reszta potrzebuje tabeli `csp_violations` (job db-tests w CI).
Własne wiersze mają stronę `/test-csp…` i są kasowane na końcu.

Użycie: cd backend && python -m scripts.test_csp_report
"""
import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from sqlalchemy import text

from src.api.endpoints import csp
from src.database.connection import async_session

results: list[bool] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))
    return ok


def legacy(blocked: str, page: str = "https://rybnolive.pl/test-csp-a", directive: str = "img-src") -> dict:
    return {"csp-report": {"document-uri": page, "effective-directive": directive,
                           "violated-directive": directive, "blocked-uri": blocked, "disposition": "report"}}


def pure() -> None:
    print("\n1️⃣  Normalizacja i prywatność (bez bazy)")
    check("źródło → samo schemat://host (ścieżka i zapytanie odcięte)",
          csp.normalize_blocked("https://cdn.przyklad.pl/obrazy/tajny-id-123.jpg?token=ABC") == "https://cdn.przyklad.pl")
    check("port zostaje (host:port bywa istotny dla polityki)",
          csp.normalize_blocked("http://localhost:3001/x.js") == "http://localhost:3001")
    check("słowa kluczowe: inline, eval", csp.normalize_blocked("inline") == "inline" and csp.normalize_blocked("eval") == "eval")
    check("data: i blob: bez treści", csp.normalize_blocked("data:image/png;base64,AAAA") == "data"
          and csp.normalize_blocked("blob:https://rybnolive.pl/uuid-123") == "blob")
    check("pusty adres → (brak), nie wyjątek", csp.normalize_blocked(None) == "(brak)" and csp.normalize_blocked("") == "(brak)")
    check("strona → sama ścieżka: zapytanie i fragment znikają",
          csp.normalize_page("https://rybnolive.pl/zaproszenie?kod=SEKRET-ZAPROSZENIA#x") == "/zaproszenie")
    check("token resetu hasła z adresu nie przeżywa normalizacji",
          "SEKRETNY" not in csp.normalize_page("https://rybnolive.pl/nowe-haslo?token=SEKRETNY"))
    check("dyrektywa spoza wzorca → „inne” (nie wchodzi obca treść do bazy)",
          csp.normalize_directive("'; DROP TABLE users; --") == "inne" and csp.normalize_directive("img-src 'self'") == "img-src")
    parsed = csp.parse_reports(legacy("https://x.pl/a?b=c", "https://rybnolive.pl/p?kod=SEKRET"))
    check("format starszy (report-uri): jeden raport", len(parsed) == 1 and parsed[0]["blocked"] == "https://x.pl"
          and parsed[0]["page"] == "/p", parsed)
    api = [{"type": "csp-violation", "body": {"documentURL": "https://rybnolive.pl/q?t=1", "effectiveDirective": "script-src-elem",
                                             "blockedURL": "https://zly.pl/a.js", "disposition": "report"}},
           {"type": "deprecation", "body": {"id": "x"}}]
    parsed = csp.parse_reports(api)
    check("Reporting API: bierze tylko csp-violation", len(parsed) == 1 and parsed[0]["directive"] == "script-src-elem", parsed)
    check("śmieci (liczba, napis, pusta lista, zły kształt) → brak raportów",
          all(csp.parse_reports(x) == [] for x in (5, "tekst", [], {}, {"csp-report": "nie-obiekt"}, [1, 2, 3])))
    many = csp.parse_reports([{"type": "csp-violation", "body": {"blockedURL": f"https://h{i}.pl"}} for i in range(50)])
    check(f"co najwyżej {csp.MAX_REPORTS_PER_REQUEST} raportów z jednego żądania", len(many) == csp.MAX_REPORTS_PER_REQUEST, len(many))
    check("disposition: tylko report/enforce", parsed[0]["disposition"] == "report")


async def with_db() -> None:
    from src.api.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        async def rows(like: str = "/test-csp%") -> list:
            async with async_session() as s:
                return (await s.execute(text(
                    "SELECT directive, blocked, page, hits FROM csp_violations WHERE page LIKE :p ORDER BY blocked"), {"p": like})).all()

        async def send(payload, content_type="application/csp-report"):
            body = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
            return await client.post("/api/csp-report", content=body, headers={"content-type": content_type})

        print("\n2️⃣  Zapis zagregowany")
        csp._hits.clear()
        r = await send(legacy("https://obcy.pl/zdjecie.jpg?tajne=1", "https://rybnolive.pl/test-csp-a?kod=SEKRET-ZAPROSZENIA"))
        check("204", r.status_code == 204, r.status_code)
        got = await rows()
        check("jeden wiersz: źródło jako host, strona jako ścieżka",
              got == [("img-src", "https://obcy.pl", "/test-csp-a", 1)], got)
        await send(legacy("https://obcy.pl/inne-zdjecie.jpg", "https://rybnolive.pl/test-csp-a"))
        check("ten sam klucz zwiększa licznik zamiast dublować wiersz", (await rows())[0][3] == 2, await rows())
        r = await send([{"type": "csp-violation", "body": {"documentURL": "https://rybnolive.pl/test-csp-b",
                                                           "effectiveDirective": "connect-src", "blockedURL": "https://api.obcy.pl/x"}}],
                       "application/reports+json")
        check("Reporting API (application/reports+json) też zapisane",
              r.status_code == 204 and any(g[0] == "connect-src" for g in await rows()), await rows())
        async with async_session() as s:
            dump = (await s.execute(text("SELECT string_agg(concat_ws('|', directive, blocked, page, disposition), ';') FROM csp_violations"))).scalar() or ""
        check("tajne wartości (token, zapytanie, ścieżka źródła) NIE wystąpiły nigdzie w tabeli",
              not any(t in dump for t in ("SEKRET-ZAPROSZENIA", "tajne", "zdjecie.jpg", "inne-zdjecie")), dump[:150])

        print("\n3️⃣  Granice: śmieci, rozmiar, sufit, limit")
        before = await rows()
        for label, body in (("nie-JSON", "to nie jest json {"), ("pusty obiekt", "{}"), ("zły kształt", "[1,2,3]")):
            r = await send(body)
            check(f"{label} → 204 i nic nie zapisano", r.status_code == 204 and await rows() == before, r.status_code)
        r = await send(json.dumps(legacy("https://zaduzy.pl", "https://rybnolive.pl/test-csp-c")) + " " * (csp.MAX_BODY_BYTES + 10))
        check("ciało większe niż 16 kB → 204 bez zapisu", r.status_code == 204 and not any(g[2] == "/test-csp-c" for g in await rows()))
        old_cap, csp.MAX_DISTINCT = csp.MAX_DISTINCT, None
        try:
            async with async_session() as s:
                total = (await s.execute(text("SELECT count(*) FROM csp_violations"))).scalar()
            csp.MAX_DISTINCT = total  # tabela „pełna”: nowe klucze przepadają, istniejące rosną
            csp._hits.clear()
            await send(legacy("https://nowy-przy-pelnej-tabeli.pl", "https://rybnolive.pl/test-csp-d"))
            check("sufit różnych wpisów: nowy klucz przy pełnej tabeli nie wchodzi", not any(g[2] == "/test-csp-d" for g in await rows()))
            await send(legacy("https://obcy.pl/x", "https://rybnolive.pl/test-csp-a"))
            check("sufit nie blokuje liczenia istniejących wpisów", (await rows("/test-csp-a"))[0][3] == 3, await rows("/test-csp-a"))
        finally:
            csp.MAX_DISTINCT = old_cap
        old_limit, csp.RATE_LIMIT_PER_IP_PER_MIN = csp.RATE_LIMIT_PER_IP_PER_MIN, 3
        try:
            csp._hits.clear()
            for i in range(6):
                await send(legacy(f"https://limit{i}.pl", "https://rybnolive.pl/test-csp-e"))
            stored = [g for g in await rows("/test-csp-e")]
            check("limit na IP: tylko pierwsze 3 z 6 zapisane, reszta po cichu (204)", len(stored) == 3, len(stored))
        finally:
            csp.RATE_LIMIT_PER_IP_PER_MIN = old_limit
            csp._hits.clear()

        print("\n4️⃣  Retencja 30 dni")
        from src.scheduler.retention_job import RETENTION_CSP_DAYS, purge_csp_violations
        async with async_session() as s:
            await s.execute(text("UPDATE csp_violations SET last_seen = :t WHERE page = '/test-csp-b'"),
                            {"t": datetime.utcnow() - timedelta(days=RETENTION_CSP_DAYS + 1)})
            await s.commit()
        async with async_session() as s:
            removed = await purge_csp_violations(s, datetime.utcnow())
            await s.commit()
        left_pages = {g[2] for g in await rows()}
        check("wiersz nieaktywny od 31 dni skasowany", "/test-csp-b" not in left_pages and removed >= 1, removed)
        check("świeże wiersze zostają", "/test-csp-a" in left_pages)


async def cleanup() -> None:
    try:
        async with async_session() as s:
            await s.execute(text("DELETE FROM csp_violations WHERE page LIKE '/test-csp%'"))
            await s.commit()
    except Exception:  # noqa: BLE001 — bez tabeli (tryb bez bazy) nie ma czego sprzątać
        pass


async def main() -> int:
    pure()
    if "--no-db" not in sys.argv:
        await cleanup()
        try:
            await with_db()
        finally:
            await cleanup()
    failed = results.count(False)
    print(f"\n{'✅' if not failed else '❌'} {len(results) - failed}/{len(results)} sprawdzeń")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
