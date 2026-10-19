"""
Dane pozyskania i pomiar strony: retencja oraz prawa osób (audyt 11.10.2026, E8).

Luki, które ten test zamyka:
  • `users.acq_*` i `push_subscriptions.acq_session_id` nie wygasały nigdy
  • usunięcie konta (art. 17) anonimizowało rekord, ale zostawiało `acq_session_id` — „usunięte"
    konto dalej wskazywało swoje wiersze w `site_events` — i nie kasowało samych zdarzeń
  • eksport (art. 15/20) nie zawierał ani danych pozyskania, ani zdarzeń użytkownika

Sprawdza:
  1. retencja: 89 dni → nic się nie zmienia; 91 dni → znika identyfikator wizyty (konto i push),
     kampania i strona wejścia zostają; > 24 miesiące → znika wszystko; konto bez `acq_first_seen`
     liczy wiek od założenia
  2. retencja nie rusza cudzych wierszy (liczone w transakcji, którą wycofujemy)
  3. eksport zawiera blok `acquisition` i zdarzenia powiązane przez `user_id` ORAZ przez identyfikator
     wizyty (także te sprzed rejestracji), ale nie cudze
  4. usunięcie konta kasuje te zdarzenia, czyści `acq_*` na zanonimizowanym rekordzie, a cudze
     zdarzenia zostają

Test na bazie (w CI: job db-tests). Własne rekordy mają prefiks `test-priv` i są kasowane na końcu.

Użycie: cd backend && python -m scripts.test_privacy_retention
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select

from src.database.connection import async_session
from src.database.schema import PushSubscription, SiteEvent, User, UserTier
from src.scheduler import retention_job as rj
from src.users.dsar import delete_user_account, export_user_data

PREFIX = "test-priv"
DOMAIN = "@test-privacy.rybnolive.pl"
results: list[bool] = []
created_user_ids: list[int] = []


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))
    return ok


async def make_user(tag: str, base: datetime, with_first_seen: bool = True) -> User:
    async with async_session() as session:
        user = User(
            email=f"{PREFIX}-{tag}{DOMAIN}", password_hash="x" * 20, full_name="Test Prywatność",
            location="Rybno", tier=UserTier.FREE.value, consent_terms_at=base,
            acq_session_id=f"{PREFIX}-sess-{tag}", acq_utm_campaign=f"{PREFIX}-kampania",
            acq_landing="/sesje", acq_first_seen=base if with_first_seen else None,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        created_user_ids.append(user.id)
        return user


async def state(session, user_id: int, push_id: int) -> dict:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    push = (await session.execute(select(PushSubscription).where(PushSubscription.id == push_id))).scalar_one()
    return {"sess": user.acq_session_id, "camp": user.acq_utm_campaign, "land": user.acq_landing,
            "first": user.acq_first_seen, "push": push.acq_session_id}


async def purged_state(user_id: int, push_id: int, now: datetime) -> tuple[dict, dict]:
    """Stan po retencji w `now` — w transakcji, którą WYCOFUJEMY (cudze dane nietknięte)."""
    async with async_session() as session:
        counts = await rj.purge_acquisition(session, now)
        after = await state(session, user_id, push_id)
        await session.rollback()
    return after, counts


async def cleanup() -> None:
    async with async_session() as session:
        await session.execute(delete(SiteEvent).where(SiteEvent.session_id.like(f"{PREFIX}-%")))
        await session.execute(delete(SiteEvent).where(SiteEvent.user_id.in_(created_user_ids or [0])))
        await session.execute(delete(PushSubscription).where(PushSubscription.endpoint.like(f"https://{PREFIX}.invalid/%")))
        await session.execute(delete(User).where(User.email.like(f"{PREFIX}-%{DOMAIN}")))
        if created_user_ids:
            await session.execute(delete(User).where(User.id.in_(created_user_ids)))
        await session.commit()


async def run() -> None:
    base = datetime.utcnow()
    a = await make_user("a", base)
    b = await make_user("b", base, with_first_seen=False)  # bez daty pierwszej wizyty → wiek od założenia konta

    async with async_session() as session:
        push = PushSubscription(
            user_id=None, email=a.email, endpoint=f"https://{PREFIX}.invalid/a", p256dh="x", auth="y",
            categories=[], acq_session_id=f"{PREFIX}-sess-push",
        )
        session.add(push)
        # zdarzenia: po user_id, po identyfikatorze wizyty z konta, po wizycie z subskrypcji push, cudze
        session.add_all([
            SiteEvent(occurred_at=base, session_id=f"{PREFIX}-sess-zalogowany", user_id=a.id,
                      event="register_done", path="/moje-po-user-id"),
            SiteEvent(occurred_at=base, session_id=a.acq_session_id, user_id=None,
                      event="view", section="sesje", path="/moje-przed-rejestracja"),
            SiteEvent(occurred_at=base, session_id=f"{PREFIX}-sess-push", user_id=None,
                      event="view", section="feed", path="/moje-z-push"),
            SiteEvent(occurred_at=base, session_id=f"{PREFIX}-sess-cudza", user_id=None,
                      event="view", section="feed", path="/cudze"),
        ])
        await session.commit()
        await session.refresh(push)
        push_id = push.id

    print("\n1️⃣  Retencja danych pozyskania")
    s, _ = await purged_state(a.id, push_id, base + timedelta(days=89))
    check("89 dni: nic nie wygasa", all(v is not None for v in s.values()), s)
    s, c = await purged_state(a.id, push_id, base + timedelta(days=91))
    check("91 dni: identyfikator wizyty znika z konta i z subskrypcji push", s["sess"] is None and s["push"] is None, s)
    check("91 dni: kampania, strona wejścia i data pierwszej wizyty zostają",
          s["camp"] and s["land"] and s["first"], s)
    s, _ = await purged_state(a.id, push_id, base + timedelta(days=700))
    check("700 dni: kampania nadal jest (próg 24 miesiące = 730)", s["camp"] is not None, s)
    s, c = await purged_state(a.id, push_id, base + timedelta(days=731))
    check("731 dni: znika wszystko", not any([s["sess"], s["camp"], s["land"], s["first"], s["push"]]), s)
    check("liczniki z retencji zgodne ze stanem", c["attribution"] >= 1 and c["sessions"] >= 1, c)

    print("\n2️⃣  Konto bez `acq_first_seen`")
    async with async_session() as session:
        await rj.purge_acquisition(session, base + timedelta(days=91))
        b_user = (await session.execute(select(User).where(User.id == b.id))).scalar_one()
        check("wiek liczony od założenia konta → identyfikator wizyty też znika po 90 dniach",
              b_user.acq_session_id is None, b_user.acq_session_id)
        await session.rollback()

    print("\n3️⃣  Retencja nie rusza cudzych danych i niczego nie zostawia po wycofaniu")
    async with async_session() as session:
        a_now = (await session.execute(select(User).where(User.id == a.id))).scalar_one()
        check("po wycofaniu transakcji dane testowe w bazie są nietknięte",
              a_now.acq_session_id == f"{PREFIX}-sess-a" and a_now.acq_utm_campaign == f"{PREFIX}-kampania")

    print("\n4️⃣  Eksport (art. 15/20)")
    async with async_session() as session:
        account = await session.get(User, a.id)
        export = await export_user_data(session, account)
    acq = export["acquisition"]
    check("blok `acquisition` z danymi pozyskania",
          acq["session_id"] == f"{PREFIX}-sess-a" and acq["utm_campaign"] == f"{PREFIX}-kampania"
          and acq["landing"] == "/sesje" and acq["first_seen"], acq)
    paths = sorted(e["path"] for e in export["site_events"])
    check("zdarzenia po user_id, po wizycie z konta (sprzed rejestracji) i po wizycie z subskrypcji push",
          paths == ["/moje-po-user-id", "/moje-przed-rejestracja", "/moje-z-push"], paths)
    check("cudze zdarzenie NIE trafia do eksportu", "/cudze" not in paths, paths)
    check("eksport zdarzeń nie niesie identyfikatorów wizyt ani cudzych kont",
          all("session_id" not in e and "user_id" not in e for e in export["site_events"]))

    print("\n5️⃣  Usunięcie konta (art. 17)")
    async with async_session() as session:
        account = await session.get(User, a.id)
        await delete_user_account(session, account)
    async with async_session() as session:
        left = (await session.execute(
            select(SiteEvent.session_id).where(SiteEvent.session_id.like(f"{PREFIX}-%"))
        )).scalars().all()
        gone = (await session.execute(select(User).where(User.id == a.id))).scalar_one()
        pushes = (await session.execute(
            select(PushSubscription).where(PushSubscription.endpoint == f"https://{PREFIX}.invalid/a")
        )).scalars().all()
    check("zdarzenia osoby skasowane (po user_id i po obu identyfikatorach wizyt)",
          left == [f"{PREFIX}-sess-cudza"], left)
    check("cudze zdarzenie zostało", f"{PREFIX}-sess-cudza" in left)
    check("zanonimizowany rekord nie niesie danych pozyskania",
          not any([gone.acq_session_id, gone.acq_utm_campaign, gone.acq_landing, gone.acq_first_seen]),
          (gone.acq_session_id, gone.acq_utm_campaign))
    check("rekord users zanonimizowany, nie skasowany", gone.email.startswith("usuniete-") and gone.is_active is False)
    check("subskrypcja push skasowana", not pushes)


async def main() -> int:
    await cleanup()
    try:
        await run()
    finally:
        await cleanup()
    failed = results.count(False)
    print(f"\n{'✅' if not failed else '❌'} {len(results) - failed}/{len(results)} sprawdzeń")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
