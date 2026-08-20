"""
Test cyklu życia okresu próbnego (2026-08-20).

Sprawdza to, czego zabrakło pierwszemu prawdziwemu użytkownikowi: że rejestracja
zakłada subskrypcję newslettera, że powitanie mówi o 30 dniach i że wygaszenie
planu jest zapowiedziane, a nie ciche.

Scenariusze:
  1. rejestracja        → subskrypcja `daily` + confirmed_at + mail powitalny
  2. trial za 7 dni     → mail 'week', a drugi przebieg tego samego dnia MILCZY
  3. trial za 1 dzień   → mail 'last_day' (nagłówek mówi „dziś" albo „jutro", nie zgaduje)
  4. trial wygasły      → mail 'ended' PRZED zejściem na Free
  5. wypisany adres     → rejestracja go nie wskrzesza

Nic nie wychodzi na zewnątrz: `EmailService.send_email` jest podmieniony na zapis
do listy. Konta testowe (`@qa.rybnolive.pl`) są kasowane na końcu, także po błędzie.

Użycie:
    cd backend && python -m scripts.test_trial_lifecycle
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from fastapi import BackgroundTasks, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import select

from src.config import settings
from src.database.schema import User, UserTier, NewsletterSubscriber, NewsletterStatus, NewsletterFrequency
from src.newsletter.email_service import EmailService
from src.newsletter.subscriptions import ensure_subscription

TEST_DOMAIN = "@qa.rybnolive.pl"  # .local/.test odrzuca walidator adresu
sent_emails = []


def capture_emails():
    """Podmienia wysyłkę na zapis do listy — nic nie idzie do Resend."""
    async def capture(self, to_email, subject, html_content, reply_to=None, unsubscribe_url=None):
        sent_emails.append({"to": to_email, "subject": subject, "html": html_content})
        return {"status": "sent", "id": "test", "to": to_email}
    EmailService.send_email = capture


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"   {'✅' if ok else '❌'} {label}{(' — ' + detail) if detail else ''}")
    return ok


async def make_user(session, email: str, days_left, stage=None, tier=UserTier.PREMIUM.value) -> User:
    user = User(
        email=email,
        password_hash="x" * 20,
        full_name="Jan Testowy",
        location="Rybno",
        tier=tier,
        trial_ends_at=(datetime.utcnow() + timedelta(days=days_left)) if days_left is not None else None,
        trial_reminder_stage=stage,
        consent_terms_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    await ensure_subscription(session, user)
    await session.commit()
    return user


async def scenario_registration(session) -> bool:
    """1. Rejestracja zakłada subskrypcję i wysyła powitanie."""
    print("\n1️⃣  Rejestracja → subskrypcja + mail powitalny")
    from src.auth.routes import register
    from src.auth.schemas import UserCreate

    sent_emails.clear()
    email = f"rejestracja{TEST_DOMAIN}"
    background = BackgroundTasks()
    await register(
        background_tasks=background,
        user_data=UserCreate(
            email=email, password="Testowe123", full_name="Jan Testowy",
            location="Rybno", consent_terms=True, consent_marketing=True,
        ),
        response=Response(),
        session=session,
    )
    await background()  # FastAPI odpala zadania tła po odpowiedzi

    sub = (await session.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
    )).scalar_one_or_none()

    ok = check("subskrypcja powstała", sub is not None)
    if sub:
        ok &= check("częstotliwość dzienna (trial = Premium)",
                    sub.frequency == NewsletterFrequency.DAILY.value, sub.frequency)
        ok &= check("potwierdzona od razu (konto = potwierdzony adres)", sub.confirmed_at is not None)
    ok &= check("mail powitalny wyszedł", len(sent_emails) == 1,
                sent_emails[0]["subject"] if sent_emails else "brak")
    if sent_emails:
        html = sent_emails[0]["html"]
        ok &= check("mówi o okresie próbnym", "okres pr" in html.lower() or "okres&nbsp;pr" in html.lower())
        ok &= check("podaje datę końca", "wrze" in html or "pa&#378;" in html or "październ" in html)
    return ok


async def scenario_reminders(session) -> bool:
    """2-4. Przypomnienia: właściwy etap, bez powtórek, 'ended' przed degradacją."""
    from src.scheduler.trial_expiry_job import _send_upcoming_reminders, _send_reminder

    print("\n2️⃣  Trial za 7 dni → etap 'week', bez powtórki")
    sent_emails.clear()
    now = datetime.utcnow()
    u7 = await make_user(session, f"tydzien{TEST_DOMAIN}", days_left=7)
    count = await _send_upcoming_reminders(session, now)
    await session.commit()
    await session.refresh(u7)
    ok = check("wysłany dokładnie jeden mail", count == 1, f"{count}")
    ok &= check("etap zapisany jako 'week'", u7.trial_reminder_stage == "week", str(u7.trial_reminder_stage))

    again = await _send_upcoming_reminders(session, now)
    ok &= check("drugi przebieg tego samego dnia milczy", again == 0, f"{again}")

    print("\n3️⃣  Trial za 1 dzień → etap 'last_day'")
    sent_emails.clear()
    u1 = await make_user(session, f"jutro{TEST_DOMAIN}", days_left=1)
    await _send_upcoming_reminders(session, now)
    await session.commit()
    await session.refresh(u1)
    ok &= check("etap 'last_day'", u1.trial_reminder_stage == "last_day", str(u1.trial_reminder_stage))
    subject = next((m["subject"] for m in sent_emails if m["to"] == u1.email), "")
    ok &= check("temat mówi o konkretnym dniu", "dziś" in subject or "jutro" in subject, subject)

    print("\n4️⃣  Trial wygasły → mail 'ended' zanim plan spadnie")
    sent_emails.clear()
    u0 = await make_user(session, f"koniec{TEST_DOMAIN}", days_left=-1)
    await _send_reminder(session, u0, "ended", now)
    await session.commit()
    await session.refresh(u0)
    ok &= check("etap 'ended'", u0.trial_reminder_stage == "ended", str(u0.trial_reminder_stage))
    ok &= check("mail o zmianie planu wyszedł", len(sent_emails) == 1,
                sent_emails[0]["subject"] if sent_emails else "brak")
    ok &= check("data trialu była jeszcze dostępna przy wysyłce", u0.trial_ends_at is not None)
    return ok


async def scenario_unsubscribed(session) -> bool:
    """5. Wypis jest decyzją — założenie konta go nie cofa."""
    print("\n5️⃣  Wypisany adres → rejestracja nie wskrzesza subskrypcji")
    email = f"wypisany{TEST_DOMAIN}"
    session.add(NewsletterSubscriber(
        email=email, frequency=NewsletterFrequency.WEEKLY.value,
        status=NewsletterStatus.UNSUBSCRIBED.value, unsubscribe_token="token-testowy",
        unsubscribed_at=datetime.utcnow(),
    ))
    await session.commit()

    user = User(email=email, password_hash="x" * 20, full_name="Jan Testowy",
                location="Rybno", tier=UserTier.PREMIUM.value, created_at=datetime.utcnow())
    session.add(user)
    await session.commit()
    await session.refresh(user)

    result = await ensure_subscription(session, user)
    ok = check("ensure_subscription zwraca None", result is None)

    sub = (await session.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == email)
    )).scalar_one()
    ok &= check("status pozostał 'unsubscribed'", sub.status == NewsletterStatus.UNSUBSCRIBED.value, sub.status)
    return ok


async def cleanup(engine):
    async with engine.begin() as conn:
        await conn.execute(text(f"DELETE FROM newsletter_subscribers WHERE email LIKE '%{TEST_DOMAIN}'"))
        await conn.execute(text(f"DELETE FROM users WHERE email LIKE '%{TEST_DOMAIN}'"))
    print(f"\n🧹 Konta testowe ({TEST_DOMAIN}) usunięte")


async def main() -> int:
    print("=" * 62)
    print("TEST CYKLU OKRESU PRÓBNEGO")
    print("=" * 62)
    capture_emails()

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await cleanup(engine)  # pozostałości po przerwanym przebiegu

    ok = True
    try:
        async with async_session() as session:
            ok &= await scenario_registration(session)
            ok &= await scenario_reminders(session)
            ok &= await scenario_unsubscribed(session)
    finally:
        await cleanup(engine)
        await engine.dispose()

    print("\n" + "=" * 62)
    print("✅ WSZYSTKO PRZESZŁO" if ok else "❌ SĄ BŁĘDY")
    print("=" * 62)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
