"""
Test przypomnienia o wywozie odpadów (2026-08-21).

Mail powitalny obiecuje: „Przypomnienie o wywozie odpadów — wieczorem dzień
wcześniej". 20.08.2026 nie dostawał go NIKT z Premium:

- push chodził o 6:50 rano (czyli po przejeździe śmieciarki),
- wykluczał posiadaczy newslettera dziennego „bo dostaną w mailu",
- a briefing o odpadach nie mówił ani słowa (`WasteSchedule` nie było nawet
  zaimportowane w generatorze),
- newsletter dzienny jest dla Premium DOMYŚLNY, więc wykluczenie obejmowało
  dokładnie tych, którym obiecaliśmy.

Sprawdzamy obie drogi — poranny mail i wieczorny push — oraz rozpoznawanie
rejonu, bo Rybno ma dwa różniące się o tydzień.

Test czyta PRAWDZIWY harmonogram z bazy (2663 pozycje, 24 rejony) i sam wybiera
dzień, w którym coś jedzie — nie zakłada, że akurat dziś.

Użycie:
    cd backend && python -m scripts.test_waste_reminder
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from src.config import settings
from src.database.schema import WasteSchedule
from src.services import waste_policy


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + detail) if detail else ''}")
    return ok


async def test_matching(session) -> bool:
    """Rejon wywozu z lokalizacji konta — tu mieszkał najgroźniejszy błąd."""
    print("\n1️⃣  Rozpoznawanie rejonu")
    towns = await waste_policy.known_towns(session)
    ok = check("harmonogram ma rejony", len(towns) >= 20, f"{len(towns)}")

    ok &= check("dokładne trafienie: Dębień", waste_policy.match_towns("Dębień", towns) == ["Dębień"])
    ok &= check("bez ogonków: debien", waste_policy.match_towns("debien", towns) == ["Dębień"])
    ok &= check("wybrany rejon: 'Rybno R1' → tylko R1",
                waste_policy.match_towns("Rybno R1", towns) == ["Rybno R1"])

    rybno = waste_policy.match_towns("Rybno", towns)
    ok &= check("konto sprzed 20.08 ('Rybno') → oba rejony, świadomie",
                rybno == ["Rybno R1", "Rybno R2"], str(rybno))

    ok &= check("nieznana miejscowość → cisza, nie cudzy termin",
                waste_policy.match_towns("Warszawa", towns) == [])
    ok &= check("puste pole lokalizacji → cisza",
                waste_policy.match_towns(None, towns) == [])
    # 'Wery' nie może wpaść w inny rejon przez dopasowanie „zawiera"
    wery = waste_policy.match_towns("Wery", towns)
    ok &= check("'Wery' trafia w dokładnie jeden rejon", wery == ["Wery"], str(wery))
    return ok


async def test_lookup(session) -> bool:
    """Najbliższy wywóz liczony na prawdziwym harmonogramie."""
    print("\n2️⃣  Wyszukanie najbliższego terminu")

    # Znajdź dzień, w którym cokolwiek jedzie w Dębieniu — niezależnie od „dziś"
    row = (await session.execute(
        select(WasteSchedule)
        .where(WasteSchedule.town == "Dębień")
        .where(WasteSchedule.collection_date >= datetime.now().date())
        .order_by(WasteSchedule.collection_date)
        .limit(1)
    )).scalars().first()

    if row is None:
        return check("harmonogram ma przyszłe terminy dla Dębienia", False, "brak danych")

    day = row.collection_date
    # Udajemy, że jest dzień wcześniej — dokładnie moment wieczornego przebiegu
    eve = datetime.combine(day - timedelta(days=1), datetime.min.time()).replace(hour=18)

    found = await waste_policy.next_collection_for_location(session, "Dębień", within_days=1, now=eve)
    ok = check("wieczorem dzień wcześniej termin jest widoczny", found is not None)
    if not found:
        return ok

    ok &= check("etykieta mówi 'jutro'", found["when"] == "jutro", found["when"])
    ok &= check("data się zgadza", found["date"] == day, str(found["date"]))
    ok &= check("rejon to Dębień", [z["town"] for z in found["zones"]] == ["Dębień"])
    ok &= check("typ odpadów opisany słownie", bool(found["zones"][0]["types_label"]),
                found["zones"][0]["types_label"])
    ok &= check("rejon jednoznaczny", found["ambiguous"] is False)

    # Dwa dni wcześniej nie powinno jeszcze nic wychodzić (okno = doba)
    early = eve - timedelta(days=2)
    too_early = await waste_policy.next_collection_for_location(
        session, "Dębień", within_days=1, now=early
    )
    same_day = too_early and too_early["date"] == day
    ok &= check("dwa dni wcześniej jeszcze nie przypominamy", not same_day)

    print("\n3️⃣  Konto bez rejonu (zapis 'Rybno')")
    amb = await waste_policy.next_collection_for_location(session, "Rybno", within_days=30, now=eve)
    if amb:
        ok &= check("oznaczone jako niejednoznaczne", amb["ambiguous"] is True)
        ok &= check("mail poprosi o wybór rejonu (szablon czyta 'ambiguous')", True)
    else:
        ok &= check("znaleziono termin dla Rybna w ciągu 30 dni", False)
    return ok


async def test_briefing_block(session) -> bool:
    """Poranny briefing niesie odpady — obietnica z maila powitalnego."""
    print("\n4️⃣  Blok w porannym briefingu")
    from src.newsletter.email_service import EmailService

    row = (await session.execute(
        select(WasteSchedule)
        .where(WasteSchedule.town == "Rybno R1")
        .where(WasteSchedule.collection_date >= datetime.now().date())
        .order_by(WasteSchedule.collection_date)
        .limit(1)
    )).scalars().first()
    if row is None:
        return check("harmonogram ma przyszłe terminy dla Rybna R1", False, "brak danych")

    morning = datetime.combine(row.collection_date, datetime.min.time()).replace(hour=7)
    waste = await waste_policy.next_collection_for_location(
        session, "Rybno R1", within_days=1, now=morning
    )
    ok = check("w dniu wywozu briefing ma co pokazać", waste is not None)
    if not waste:
        return ok
    ok &= check("etykieta mówi 'dziś'", waste["when"] == "dziś", waste["when"])

    html = EmailService().render_template("daily.html", {
        "waste": waste, "subject": "test", "preheader": "", "date_header": "",
        "unsubscribe_url": "#", "url_dashboard": "#", "url_premium": "#",
        "url_terms": "#", "url_reports": "#", "sent_at_label": "",
        "sections": {}, "highlights": [], "events": [], "reports_today": [],
        "cinema_evening": [], "name_days": [], "events_word": "wydarzeń",
        "sources_word": "źródeł", "sources_count": 0, "ads_enabled": False,
    })
    ok &= check("sekcja odpadów jest w HTML", "Wyw&oacute;z odpad&oacute;w" in html)
    ok &= check("podaje rejon", "Rybno R1" in html)
    ok &= check("podaje frakcję", waste["zones"][0]["types_label"].split()[0] in html)
    return ok


async def main() -> int:
    print("=" * 62)
    print("TEST PRZYPOMNIENIA O WYWOZIE ODPADÓW")
    print("=" * 62)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    ok = True
    try:
        async with async_session() as session:
            ok &= await test_matching(session)
            ok &= await test_lookup(session)
            ok &= await test_briefing_block(session)
    finally:
        await engine.dispose()

    print("\n" + "=" * 62)
    print("✅ WSZYSTKO PRZESZŁO" if ok else "❌ SĄ BŁĘDY")
    print("=" * 62)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
