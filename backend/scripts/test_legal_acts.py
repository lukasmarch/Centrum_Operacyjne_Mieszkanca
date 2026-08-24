"""
Sprawdza rejestr aktów prawnych i skróty obrad — etapy 4 i 5.

    cd backend
    python -m scripts.test_legal_acts          # parsowanie, bez sieci i bazy
    python -m scripts.test_legal_acts --db     # + stan bazy i narzędzia
    python -m scripts.test_legal_acts --live   # + jedna strona z BIP

Trzy rzeczy, każda z innego powodu:

1. **Parsowanie listy** — komórki BIP niosą etykietę w treści („Data podjęcia
   2026-06-24”), bo układ jest responsywny. Bez obcięcia etykiety data nie
   parsuje się wcale, a akt wchodzi do bazy bez daty i wypada z „najnowszych”.
2. **Próg zakresu** — lista jest sortowana kolejnością WPROWADZENIA do BIP,
   nie datą podjęcia. Pierwsza wersja przerywała skan na pierwszym starym
   akcie i przez jedno zarządzenie z 2023 r. wciągnęła 229 aktów zamiast 430.
3. **Bramka akceptacji** — `council_sessions` nie ma prawa pokazać skrótu
   w stanie `pending`. To jedyne zabezpieczenie tej funkcji: cytat da się
   sprawdzić twardo, `description` punktu już nie.
"""
import asyncio
import sys
from datetime import date

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])

from src.scrapers.legal_acts import (  # noqa: E402
    EMPTY_PAGES_TO_STOP, _bip_id, _parse_date, _strip_label,
)

failures: list[str] = []


def check(cond: bool, label: str, detail: str = "") -> None:
    if cond:
        print(f"  OK   {label}")
    else:
        print(f"  FAIL {label}{f' — {detail}' if detail else ''}")
        failures.append(label)


# ------------------------------------------------------------ parsowanie
print("\n== Parsowanie listy aktów ==")
check(_strip_label("Data podjęcia 2026-06-24") == "2026-06-24",
      "etykieta z komórki jest obcinana",
      "układ responsywny BIP wkłada nazwę kolumny do treści")
check(_strip_label("Nr aktu prawnego XXIII/178/2026") == "XXIII/178/2026",
      "numer aktu bez etykiety")
check(_strip_label("Status Obowiązujący") == "Obowiązujący", "status bez etykiety")
check(_strip_label("Grupa tematyczna Uchwały Rady Gminy") == "Uchwały Rady Gminy",
      "grupa bez etykiety")
check(_strip_label("2026-06-24") == "2026-06-24", "wartość bez etykiety zostaje nietknięta")

check(_parse_date("Data podjęcia 2026-06-24") == date(2026, 6, 24), "data z etykietą")
check(_parse_date("") is None, "pusty tekst nie daje daty")
check(_parse_date("brak") is None, "śmieci nie dają daty")

check(_bip_id("/akty/14/2878/UCHWALA_NR/") == 2878, "bip_id z adresu szczegółów")
check(_bip_id("https://bip.gminarybno.pl/akty/14/2/typ/16/") is None,
      "adres paginacji NIE jest aktem",
      "inaczej strona listy trafiłaby do bazy jako akt")
check(_bip_id("/akty/szukaj/126/") is None, "adres wyszukiwarki nie jest aktem")

print("\n== Próg zakresu ==")
check(EMPTY_PAGES_TO_STOP >= 2,
      f"skan przerywa się po {EMPTY_PAGES_TO_STOP} stronach bez trafień",
      "lista NIE jest sortowana po dacie podjęcia — jedna strona to za mało")


# ------------------------------------------------------------------ baza
async def run_db_tests():
    from sqlalchemy import func, select

    from src.ai.tools import ToolContext
    from src.ai.tools.council import council_sessions
    from src.ai.tools.knowledge import search_legal_acts
    from src.database.connection import async_session
    from src.database.schema import CouncilSession, LegalAct

    print("\n== Rejestr aktów (--db) ==")
    async with async_session() as session:
        ctx = ToolContext(session=session)

        total = (await session.execute(select(func.count(LegalAct.id)))).scalar()
        check(total > 0, f"rejestr niepusty ({total} aktów)",
              "uruchom: python -m scripts.run_legal_acts")
        if not total:
            return

        no_date = (await session.execute(
            select(func.count(LegalAct.id)).where(LegalAct.adopted_at == None)  # noqa: E711
        )).scalar()
        check(no_date == 0, "każdy akt ma datę podjęcia",
              f"{no_date} bez daty — wypadną z „najnowszych”")

        # Najnowsze uchwały: to jest cały powód istnienia tego narzędzia.
        res = await search_legal_acts(ctx, rodzaj="uchwały", limit=3)
        check(not res.empty, "„najnowsze uchwały” zwracają wynik")
        if not res.empty:
            akty = res.content["akty"]
            daty = [a["data_podjecia"] for a in akty]
            check(daty == sorted(daty, reverse=True),
                  "najnowsze uchwały są posortowane malejąco po dacie",
                  f"dostałem {daty}")
            check(all("Uchwał" in a["rodzaj"] for a in akty),
                  "filtr rodzaju nie przepuszcza zarządzeń",
                  "uchwała Rady i zarządzenie Wójta to dwie różne decyzje")
            check(all(a["numer"] for a in akty), "każdy akt niesie NUMER",
                  "mieszkaniec pójdzie z tym numerem do urzędu")

        # Zakres: pustka musi być OPISANA, nie milcząca.
        stary = await search_legal_acts(ctx, rok=2019)
        check(stary.empty, "rok spoza zakresu daje pusty wynik")
        check("2024" in str(stary.content.get("co_powiedziec", "")),
              "pustka tłumaczy ZAKRES rejestru",
              "„nie ma takiej uchwały” bez zakresu brzmi jak sąd o całym prawie gminy")

        # Wielosłowne zapytanie — dosłowna fraza przegrywała z językiem urzędowym.
        wiele = await search_legal_acts(ctx, query="dotacja OSP")
        check(not wiele.empty, "zapytanie wielosłowne trafia (wszystkie słowa, nie fraza)")

        print("\n== Bramka akceptacji skrótów obrad (--db) ==")
        pending = (await session.execute(
            select(func.count(CouncilSession.id)).where(CouncilSession.status == "pending")
        )).scalar()
        published = (await session.execute(
            select(func.count(CouncilSession.id)).where(CouncilSession.status == "published")
        )).scalar()
        print(f"     (w bazie: {published} opublikowanych, {pending} czekających)")

        res = await council_sessions(ctx)
        if published:
            check(not res.empty, f"opublikowane skróty są widoczne ({published})")
            sesja = res.content["sesje"][0]
            check(bool(sesja.get("naglowek")), "skrót niesie nagłówek")
            check(len(sesja.get("punkty") or []) > 0, "skrót niesie punkty obrad")
            # Numery uchwał z rejestru — model nie wyciąga ich z nagrania.
            check(len(sesja.get("uchwaly_z_rejestru") or []) > 0,
                  "uchwały z dnia sesji doklejone z rejestru",
                  "z nagrania numery nie padają — przewodniczący czyta tytuł")
        else:
            check(res.empty, "brak opublikowanych → pusty wynik")
            check("sprawdzenie przez człowieka" in str(res.content.get("co_powiedziec", "")),
                  "pustka tłumaczy, że to bramka akceptacji, a NIE brak obrad")

        # Najważniejsze: `pending` nie ma prawa wyciec do agenta.
        widoczne_id = {s["sesja"] for s in (res.content.get("sesje") or [])}
        pending_rows = (await session.execute(
            select(CouncilSession.session_number).where(CouncilSession.status == "pending")
        )).scalars().all()
        check(not (widoczne_id & set(pending_rows)),
              "skrót w stanie `pending` NIE trafia do agenta",
              "to jedyne zabezpieczenie tej funkcji")


# ------------------------------------------------------------------ live
async def run_live_tests():
    from src.scrapers.legal_acts import LegalActsScraper

    print("\n== Jedna strona z BIP (--live) ==")
    async with LegalActsScraper() as scraper:
        resp = await scraper._get(scraper._list_url(1))
        check(resp is not None, "strona listy odpowiada")
        if resp is None:
            return
        rows = scraper._parse_list(resp.text)
        check(len(rows) >= 5, f"parser czyta wiersze ({len(rows)})",
              "zmiana układu tabeli w BIP wygląda dokładnie tak")
        check(all(r["bip_id"] for r in rows), "każdy wiersz ma bip_id")
        check(sum(1 for r in rows if r["adopted_at"]) >= len(rows) - 1,
              "daty parsują się dla (prawie) wszystkich wierszy")
        check(any("Uchwał" in r["act_group"] or "Zarządz" in r["act_group"] for r in rows),
              "grupa tematyczna jest rozpoznawana")


async def main():
    if "--db" in sys.argv or "--live" in sys.argv:
        await run_db_tests()
    else:
        print("\n(pomijam testy bazy — dodaj --db)")

    if "--live" in sys.argv:
        await run_live_tests()
    else:
        print("(pomijam pobranie z BIP — dodaj --live)")

    print(f"\n{'=' * 60}")
    if failures:
        print(f"BŁĘDY: {len(failures)}")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("Wszystko OK")


if __name__ == "__main__":
    asyncio.run(main())
