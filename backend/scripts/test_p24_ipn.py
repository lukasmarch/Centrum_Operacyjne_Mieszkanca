"""
IPN Przelewy24 — pięć scenariuszy z audytu 11.10.2026 (F-023), na LOKALNEJ bazie.

P24 jest udawane (`verify_transaction` podmienione), mail potwierdzenia
przechwytywany. Baza jest prawdziwa, bo blokada wiersza (`FOR UPDATE`) i dwa
równoległe IPN-y nie dają się sprawdzić na atrapie sesji. Dlatego test NIE idzie
do CI (CI nie ma bazy) — uruchamia się go przed każdą zmianą płatności.

  1. nowy zakup: pending → active, okres 31 dni, jeden mail,
  2. przedłużenie przed końcem: nowy okres liczony od końca obecnego planu,
  3. powtórzony IPN: 200, bez zmian, bez drugiego maila,
  4. dwa IPN-y naraz: jedna aktywacja, jeden mail,
  5. P24 bez odpowiedzi → 503 i pending (P24 ponowi), potem sukces → active.
  +  kwota inna niż cena planu → bez aktywacji; odrzucony IPN nie gasi działającego planu.

Konto testowe ma WŁASNĄ domenę i jest kasowane na końcu (także po błędzie).

    cd backend && python -m scripts.test_p24_ipn
"""
import asyncio
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from fastapi import FastAPI
from sqlalchemy import delete, select

from src.api.endpoints import payments
from src.database.connection import async_session
from src.database.schema import Subscription, SubscriptionStatus, User
from src.services.p24_service import SUBSCRIPTION_PRICES, VerifyResult, p24_service

TEST_DOMAIN = "qa-p24.rybnolive.pl"
PRICE = SUBSCRIPTION_PRICES["premium"]["monthly"]

results: list[bool] = []


def check(label: str, ok: bool, detail="") -> None:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + str(detail)) if detail else ''}")
    results.append(bool(ok))


# --------------------------------------------------------------------------- atrapy P24 i maila

class FakeP24:
    def __init__(self):
        self.answers: list = []
        self.calls = 0
        self.delay = 0.0

    async def verify(self, session_id, order_id, amount, currency="PLN"):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.answers.pop(0) if self.answers else VerifyResult.VERIFIED


fake = FakeP24()
p24_service.verify_transaction = fake.verify
mails: list = []


async def _capture_mail(session, user, sub, period, amount):
    mails.append(sub.p24_session_id)


payments._send_purchase_confirmation = _capture_mail

app = FastAPI()
app.include_router(payments.router)


async def ipn(session_id: str, order_id: str, amount: int = PRICE) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        return await c.post("/api/payments/webhook", json={
            "sessionId": session_id, "orderId": int(order_id), "amount": amount, "currency": "PLN",
        })


# --------------------------------------------------------------------------- dane

async def make_user() -> int:
    async with async_session() as s:
        user = User(
            email=f"ipn-{uuid.uuid4().hex[:8]}@{TEST_DOMAIN}", full_name="Test IPN",
            password_hash="x", location="Rybno R1", tier="free",
        )
        s.add(user)
        await s.commit()
        return user.id


async def pending(user_id: int, period: str = "monthly") -> str:
    session_id = f"COM-{user_id}-premium-{period}-{uuid.uuid4().hex[:8]}"
    async with async_session() as s:
        s.add(Subscription(user_id=user_id, tier="premium",
                           status=SubscriptionStatus.PENDING.value, p24_session_id=session_id))
        await s.commit()
    return session_id


async def subs_of(session_id: str) -> list:
    async with async_session() as s:
        rows = await s.execute(select(Subscription).where(Subscription.p24_session_id == session_id))
        return rows.scalars().all()


async def cleanup() -> None:
    async with async_session() as s:
        ids = (await s.execute(select(User.id).where(User.email.like(f"%@{TEST_DOMAIN}")))).scalars().all()
        if ids:
            await s.execute(delete(Subscription).where(Subscription.user_id.in_(ids)))
            await s.execute(delete(User).where(User.id.in_(ids)))
            await s.commit()


# --------------------------------------------------------------------------- scenariusze

async def scenario_new_purchase(user_id: int) -> None:
    print("\n1️⃣  Nowy zakup")
    mails.clear()
    sid = await pending(user_id)
    r = await ipn(sid, "1001")
    [sub] = await subs_of(sid)
    check("200 dla P24", r.status_code == 200, r.status_code)
    check("subskrypcja aktywna", sub.status == "active", sub.status)
    days = (sub.expires_at - datetime.utcnow()).days
    check("okres 31 dni od dziś", days in (30, 31), days)
    check("jeden mail potwierdzenia", mails == [sid], mails)


async def scenario_renewal(user_id: int) -> None:
    print("\n2️⃣  Przedłużenie przed końcem planu")
    async with async_session() as s:
        current = (await s.execute(
            select(Subscription).where(Subscription.user_id == user_id, Subscription.status == "active")
        )).scalars().first()
        # obecny plan kończy się za 10 dni
        current.expires_at = datetime.utcnow() + timedelta(days=10)
        await s.commit()
        old_end = current.expires_at
    sid = await pending(user_id)
    await ipn(sid, "1002")
    [sub] = await subs_of(sid)
    expected = old_end + timedelta(days=31)
    drift = abs((sub.expires_at - expected).total_seconds())
    check("nowy okres liczony od końca obecnego (10 + 31 dni)", drift < 120,
          f"{sub.expires_at:%Y-%m-%d} vs {expected:%Y-%m-%d}")


async def scenario_duplicate(user_id: int) -> None:
    print("\n3️⃣  Powtórzony IPN")
    mails.clear()
    sid = await pending(user_id)
    await ipn(sid, "1003")
    [before] = await subs_of(sid)
    calls = fake.calls
    r = await ipn(sid, "1003")
    [after] = await subs_of(sid)
    check("200 dla powtórki", r.status_code == 200, r.status_code)
    check("data końca bez zmian", before.expires_at == after.expires_at)
    check("powtórka nie pyta P24 ponownie", fake.calls == calls, fake.calls - calls)
    check("jeden mail, nie dwa", mails == [sid], mails)


async def scenario_parallel(user_id: int) -> None:
    print("\n4️⃣  Dwa IPN-y naraz")
    mails.clear()
    sid = await pending(user_id)
    fake.delay = 0.5  # weryfikacja trwa — drugi IPN wchodzi w trakcie pierwszego
    calls = fake.calls
    r1, r2 = await asyncio.gather(ipn(sid, "1004"), ipn(sid, "1004"))
    fake.delay = 0.0
    subs = await subs_of(sid)
    check("oba dostają 200", (r1.status_code, r2.status_code) == (200, 200), (r1.status_code, r2.status_code))
    check("jedna weryfikacja w P24", fake.calls - calls == 1, fake.calls - calls)
    check("jeden mail", mails == [sid], mails)
    check("jeden aktywny wiersz", [s.status for s in subs] == ["active"], [s.status for s in subs])


async def scenario_timeout(user_id: int) -> None:
    print("\n5️⃣  P24 bez odpowiedzi, potem sukces")
    mails.clear()
    sid = await pending(user_id)
    fake.answers = [VerifyResult.ERROR]
    r = await ipn(sid, "1005")
    [sub] = await subs_of(sid)
    check("503 — P24 ponowi IPN", r.status_code == 503, r.status_code)
    check("płatność NIE wygasła (do 11.10 → expired)", sub.status == "pending", sub.status)
    check("bez maila", mails == [], mails)
    r = await ipn(sid, "1005")
    [sub] = await subs_of(sid)
    check("ponowiony IPN aktywuje", r.status_code == 200 and sub.status == "active", (r.status_code, sub.status))


async def scenario_guards(user_id: int) -> None:
    print("\n➕ Bezpieczniki")
    sid = await pending(user_id)
    calls = fake.calls
    r = await ipn(sid, "1006", amount=1)
    [sub] = await subs_of(sid)
    check("kwota ≠ cena planu → bez aktywacji", r.status_code == 200 and sub.status == "pending", sub.status)
    check("…i bez pytania P24", fake.calls == calls)

    sid = await pending(user_id)
    await ipn(sid, "1007")
    fake.answers = [VerifyResult.REJECTED]
    await ipn(sid, "9999")  # inny order_id dla tej samej sesji, P24 odrzuca
    [sub] = await subs_of(sid)
    check("odrzucony IPN nie gasi działającego planu", sub.status == "active", sub.status)

    sid = await pending(user_id)
    fake.answers = [VerifyResult.REJECTED]
    await ipn(sid, "1008")
    [sub] = await subs_of(sid)
    check("odrzucona oczekująca płatność → expired", sub.status == "expired", sub.status)


async def main() -> int:
    await cleanup()
    try:
        user_id = await make_user()
        await scenario_new_purchase(user_id)
        await scenario_renewal(user_id)
        await scenario_duplicate(user_id)
        await scenario_parallel(user_id)
        await scenario_timeout(user_id)
        await scenario_guards(user_id)
    finally:
        await cleanup()
    passed = sum(results)
    print(f"\n{'✅' if passed == len(results) else '❌'} {passed}/{len(results)} sprawdzeń")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
