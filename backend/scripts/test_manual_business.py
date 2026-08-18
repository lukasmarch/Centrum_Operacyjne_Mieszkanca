"""
Test pętli: firma spoza CEIDG — od zgłoszenia do katalogu i z powrotem.

Sprawdza cztery rzeczy, z których każda była osobnym błędem do popełnienia:

1. **Zgłoszenie jest niewidoczne publicznie**, dopóki człowiek go nie zatwierdzi.
   Bez tego formularz „dodaj firmę" byłby otwartym wejściem do katalogu.
2. **Sync CEIDG nie rusza wpisu ręcznego.** `ceidg_job` oznacza WYKRESLONY
   każdy wiersz nieobecny w odpowiedzi API — wpis ręczny z definicji tam nie
   jest, więc bez znacznika `source` znikałby z katalogu w pierwszą niedzielę.
3. **Po zatwierdzeniu firma wchodzi do katalogu** na tych samych prawach
   co wizytówka przejęta z rejestru.
4. **Odrzucenie kasuje wiersz-widmo**, a nie tylko wizytówkę — inaczej w bazie
   zostaje nazwa firmy (u jednoosobowej działalności: imię i nazwisko) bez
   niczego, co by ją pokazywało.

Test sprząta po sobie: konto testowe i wszystkie utworzone wiersze znikają.

Użycie:
    cd backend && python -m scripts.test_manual_business
"""
import asyncio
import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy import text  # noqa: E402
from sqlmodel import select  # noqa: E402

from src.database.connection import async_session, engine  # noqa: E402
from src.database.schema import (  # noqa: E402
    CEIDGBusiness, BusinessProfile, User, SQLModel,
)
from src.api.endpoints.business import (  # noqa: E402
    ManualBusinessRequest, add_manual_business, moderate_claim,
    apply_public_visibility,
)

TEST_EMAIL = "test-manual-business@rybnolive.local"
TEST_NAZWA = "Testowa Spółdzielnia Socjalna „Widmo”"

passed, failed = 0, 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✅ {label}")
    else:
        failed += 1
        print(f"  ❌ {label}" + (f" — {detail}" if detail else ""))


async def ensure_tables() -> None:
    """Tworzy tylko tabele potrzebne temu testowi (baza deweloperska bywa pusta)."""
    tables = [
        SQLModel.metadata.tables[t]
        for t in ("users", "business_profiles", "ceidg_businesses")
        if t in SQLModel.metadata.tables
    ]
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all, tables=tables)


async def cleanup(session) -> None:
    """Kasuje wszystko, co test mógł zostawić — także po przerwanym przebiegu."""
    await session.execute(text(
        "DELETE FROM business_profiles WHERE user_id IN "
        "(SELECT id FROM users WHERE email = :e)"
    ), {"e": TEST_EMAIL})
    await session.execute(text(
        "DELETE FROM ceidg_businesses WHERE ceidg_id LIKE 'manual-%' AND nazwa = :n"
    ), {"n": TEST_NAZWA})
    await session.execute(text("DELETE FROM users WHERE email = :e"), {"e": TEST_EMAIL})
    await session.commit()


async def main() -> int:
    await ensure_tables()

    async with async_session() as session:
        await cleanup(session)
        user = User(
            email=TEST_EMAIL,
            password_hash="!test!",
            full_name="Test Manual Business",
            is_admin=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    print("\n1. Zgłoszenie firmy spoza CEIDG")
    request = ManualBusinessRequest(
        nazwa=TEST_NAZWA,
        miasto="Hartowiec",
        branza="usługi opiekuńcze",
        telefon="123456789",
        note="szyld przy drodze na Rumian",
    )
    result = await add_manual_business(request, user=user)
    business_id = result["business_id"]
    claim_id = result["claim_id"]
    check("zgłoszenie przyjęte, status pending", result["status"] == "pending")

    async with async_session() as session:
        business = (await session.execute(
            select(CEIDGBusiness).where(CEIDGBusiness.id == business_id)
        )).scalar_one()
        check("wiersz ma source='manual'", business.source == "manual",
              f"jest '{business.source}'")
        check("ceidg_id ma prefiks 'manual-'", business.ceidg_id.startswith("manual-"))
        check("NIP pusty jest dozwolony", business.nip == "")

        # Branża MUSI wylądować na wizytówce, nie tylko w notatce dla admina.
        # Karta w katalogu liczy branżę z `pkd_main`, którego wpis ręczny nie ma —
        # 18.08 firma z branżą „Produkcja" weszła do katalogu z pustym podpisem
        profile_new = (await session.execute(
            select(BusinessProfile).where(BusinessProfile.id == claim_id)
        )).scalar_one()
        check("branża trafia na wizytówkę jako opis",
              profile_new.description == "usługi opiekuńcze",
              f"opis to {profile_new.description!r}")

        # 1. Niewidoczna publicznie przed akceptacją
        visible = (await session.execute(
            apply_public_visibility(select(CEIDGBusiness.id))
            .where(CEIDGBusiness.id == business_id)
        )).scalars().all()
        check("PRZED akceptacją firma jest niewidoczna publicznie", visible == [],
              f"widoczna: {visible}")

        # 2. Sync CEIDG jej nie widzi, więc nie oznaczy jako wykreślonej
        sync_scope = (await session.execute(
            select(CEIDGBusiness.id)
            .where(CEIDGBusiness.source == "ceidg")
            .where(CEIDGBusiness.id == business_id)
        )).scalars().all()
        check("sync CEIDG pomija wpis ręczny (nie oznaczy WYKRESLONY)", sync_scope == [])

    print("\n2. Akceptacja przez człowieka")
    await moderate_claim(claim_id, action="approve", user=user)

    async with async_session() as session:
        visible = (await session.execute(
            apply_public_visibility(select(CEIDGBusiness.id))
            .where(CEIDGBusiness.id == business_id)
        )).scalars().all()
        check("PO akceptacji firma jest widoczna publicznie", visible == [business_id],
              f"widoczne: {visible}")

        profile = (await session.execute(
            select(BusinessProfile).where(BusinessProfile.id == claim_id)
        )).scalar_one()
        check("wizytówka ma status verified", profile.claim_status == "verified")

    print("\n3. Odrzucenie kasuje wiersz-widmo")
    async with async_session() as session:
        profile = (await session.execute(
            select(BusinessProfile).where(BusinessProfile.id == claim_id)
        )).scalar_one()
        profile.claim_status = "pending"
        session.add(profile)
        await session.commit()

    reject = await moderate_claim(claim_id, action="reject", user=user)
    check("odrzucenie zgłasza usunięcie wpisu ręcznego",
          reject.get("business_deleted") is True, str(reject))

    async with async_session() as session:
        left = (await session.execute(
            select(CEIDGBusiness.id).where(CEIDGBusiness.id == business_id)
        )).scalars().all()
        check("wiersz-widmo zniknął z bazy", left == [], f"został: {left}")

        firms_from_registry = (await session.execute(
            select(CEIDGBusiness.id).where(CEIDGBusiness.source == "ceidg").limit(1)
        )).scalars().all()
        check("firmy z rejestru nietknięte", len(firms_from_registry) == 1)

    print("\n4. Bramki walidacji")
    for label, req, expect in [
        ("miejscowość spoza gminy odrzucona",
         ManualBusinessRequest(nazwa="Firma Testowa Spoza", miasto="Działdowo"), 400),
        ("nazwa krótsza niż 3 znaki odrzucona",
         ManualBusinessRequest(nazwa="AB", miasto="Rybno"), 400),
        ("NIP o złej długości odrzucony",
         ManualBusinessRequest(nazwa="Firma Testowa NIP", miasto="Rybno", nip="123"), 400),
    ]:
        try:
            await add_manual_business(req, user=user)
            check(label, False, "przeszło mimo błędnych danych")
        except Exception as exc:
            code = getattr(exc, "status_code", None)
            check(label, code == expect, f"kod {code}, oczekiwano {expect}")

    async with async_session() as session:
        await cleanup(session)

    print(f"\n{'=' * 52}")
    print(f"Wynik: {passed} zielonych, {failed} czerwonych")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
