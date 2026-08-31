"""
Trial/Subscription Expiry Job — codziennie o 5:00

1. Przypomnienia o kończącym się trialu: 7 dni przed, dzień przed i po zmianie planu.
2. Downgrade userów z wygasłym 30-dniowym trialem Premium (brak aktywnej subskrypcji).
3. Wygaszanie opłaconych subskrypcji po expires_at (status → expired, tier → free).
4. Wyłączanie wyróżnienia wizytówek (is_premium) po premium_until (plan Firma lokalna).

Do 20.08.2026 punkt 2 odbierał dostęp bez słowa — użytkownik widział to jak awarię
albo wycofanie obietnicy. `users.trial_reminder_stage` pilnuje, żeby codzienny
przebieg nie wysłał tego samego maila siedem razy z rzędu.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from datetime import timedelta

from src.database.schema import (
    User, Subscription, UserTier, SubscriptionStatus, BusinessProfile,
    NewsletterSubscriber,
)
from src.utils.logger import setup_logger

logger = setup_logger("TrialExpiryJob")


# Kolejność etapów — mail wychodzi tylko wtedy, gdy jest dalszy niż ostatnio wysłany
REMINDER_ORDER = {None: 0, "": 0, "week": 1, "last_day": 2, "ended": 3}

# Ile dni czekamy z odebraniem planu, gdy mail „ended" nie wyszedł. Powód odmowy
# bywa trwały (konto bez rekordu subskrybenta nie ma jak dostać stopki z wypisem),
# więc czekanie musi mieć koniec — inaczej jedna dziura w danych fundowałaby
# komuś Premium bez końca.
ENDED_GRACE_DAYS = 3


async def _unsubscribe_token(session: AsyncSession, user: User) -> Optional[str]:
    """Token wypisu z rekordu subskrybenta — stopka maila musi mieć działający link."""
    result = await session.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == user.email)
    )
    subscriber = result.scalar_one_or_none()
    return subscriber.unsubscribe_token if subscriber else None


async def _send_reminder(session: AsyncSession, user: User, stage: str, now: datetime) -> bool:
    """Wysyła jeden etap przypomnienia i zapisuje znacznik. Zwraca True, gdy poszło."""
    if REMINDER_ORDER.get(stage, 0) <= REMINDER_ORDER.get(user.trial_reminder_stage, 0):
        return False

    token = await _unsubscribe_token(session, user)
    if not token:
        # Bez rekordu subskrybenta nie mamy jak dać działającego wypisu w stopce.
        logger.warning(f"User {user.id} bez subskrypcji newslettera — pomijam mail '{stage}'")
        return False

    from src.newsletter.email_service import EmailService

    try:
        result = await EmailService().send_trial_reminder(
            to_email=user.email,
            recipient_name=user.full_name,
            stage=stage,
            trial_ends_at=user.trial_ends_at,
            unsubscribe_token=token,
            now=now,
        )
    except Exception as exc:  # noqa: BLE001 — wygaszenie planu ma się odbyć niezależnie od poczty
        logger.error(f"Mail '{stage}' do {user.email} nie wyszedł: {exc}")
        return False

    # Znacznik stawiamy WYŁĄCZNIE po realnej wysyłce. „skipped" (brak klucza Resend)
    # albo „failed" nie może zużyć etapu — inaczej jedna godzina złej konfiguracji
    # kasuje przypomnienie na zawsze, bo job nigdy nie wróci do tego samego progu.
    if result.get("status") != "sent":
        logger.error(
            f"Mail '{stage}' do {user.email} nie został wysłany "
            f"(status: {result.get('status')}, {result.get('error', 'brak klucza?')})"
        )
        return False

    user.trial_reminder_stage = stage
    user.trial_reminder_sent_at = now
    session.add(user)
    logger.info(f"Mail '{stage}' → {user.email}")
    return True


async def _send_upcoming_reminders(session: AsyncSession, now: datetime) -> int:
    """Przypomnienia dla kont, którym trial jeszcze trwa: −7 dni i dzień przed."""
    result = await session.execute(
        select(User).where(
            User.tier.in_([UserTier.PREMIUM.value, UserTier.BUSINESS.value]),
            User.trial_ends_at != None,  # noqa: E711 — SQLAlchemy wymaga porównania
            User.trial_ends_at > now,
            User.is_active == True,  # noqa: E712
        )
    )

    sent = 0
    for user in result.scalars().all():
        remaining = user.trial_ends_at - now
        # Progi są o dobę szersze niż nazwa etapu: job rusza o 5:00, a trial wygasa
        # o godzinie rejestracji, więc przy progu równym 7 dniom mail „za tydzień"
        # wychodziłby dopiero szóstego dnia przed końcem.
        if remaining <= timedelta(days=2):
            stage = "last_day"
        elif remaining <= timedelta(days=8):
            stage = "week"
        else:
            continue
        if await _send_reminder(session, user, stage, now):
            sent += 1
    return sent



async def _send_subscription_reminder(
    session: AsyncSession, sub: Subscription, user: User, stage: str, now: datetime
) -> bool:
    """Jeden etap przypomnienia o kończącym się OPŁACONYM okresie. True, gdy poszło.

    Znacznik siedzi na subskrypcji, nie na użytkowniku: kolejny zakup zakłada nowy
    rekord, więc kolejne przypomnienia startują od zera — inaczej klient dostałby
    komplet maili tylko za pierwszym razem.
    """
    if REMINDER_ORDER.get(stage, 0) <= REMINDER_ORDER.get(sub.reminder_stage, 0):
        return False

    token = await _unsubscribe_token(session, user)
    if not token:
        logger.warning(f"User {user.id} bez subskrypcji newslettera — pomijam mail '{stage}'")
        return False

    from src.newsletter.email_service import EmailService

    try:
        result = await EmailService().send_subscription_reminder(
            to_email=user.email,
            recipient_name=user.full_name,
            stage=stage,
            expires_at=sub.expires_at,
            unsubscribe_token=token,
            tier=sub.tier,
            now=now,
        )
    except Exception as exc:  # noqa: BLE001 — wygaszenie planu ma się odbyć niezależnie od poczty
        logger.error(f"Mail subskrypcji '{stage}' do {user.email} nie wyszedł: {exc}")
        return False

    if result.get("status") != "sent":
        logger.error(
            f"Mail subskrypcji '{stage}' do {user.email} nie został wysłany "
            f"(status: {result.get('status')}, {result.get('error', 'brak klucza?')})"
        )
        return False

    sub.reminder_stage = stage
    sub.reminder_sent_at = now
    session.add(sub)
    logger.info(f"Mail subskrypcji '{stage}' → {user.email}")
    return True


async def _send_paid_reminders(session: AsyncSession, now: datetime) -> int:
    """Przypomnienia dla OPŁACONYCH subskrypcji: −7 dni i dzień przed wygaśnięciem.

    Do 21.08.2026 ta ścieżka nie istniała. Przypomnienia zbudowane dzień wcześniej
    patrzyły wyłącznie na `users.trial_ends_at`, a zakup Premium czyści to pole —
    klient, który ZAPŁACIŁ, był jedynym, którego nikt nie uprzedzał. Plan nie
    odnawia się automatycznie (regulamin §6.5), więc bez tego maila dostęp znikał
    w środku miesiąca bez słowa.

    Anulowane subskrypcje też tu wchodzą: `cancelled` zachowuje dostęp do końca
    opłaconego okresu, więc data wygaśnięcia obowiązuje tak samo.
    """
    result = await session.execute(
        select(Subscription, User)
        .join(User, Subscription.user_id == User.id)
        .where(
            Subscription.status.in_(
                [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.CANCELLED.value]
            ),
            Subscription.expires_at != None,  # noqa: E711
            Subscription.expires_at > now,
            User.is_active == True,  # noqa: E712
        )
    )

    sent = 0
    for sub, user in result.all():
        remaining = sub.expires_at - now
        # Progi o dobę szersze niż nazwa etapu — job rusza o 5:00, a subskrypcja
        # wygasa o godzinie zakupu (patrz ten sam komentarz przy trialu).
        if remaining <= timedelta(days=2):
            stage = "last_day"
        elif remaining <= timedelta(days=8):
            stage = "week"
        else:
            continue
        if await _send_subscription_reminder(session, sub, user, stage, now):
            sent += 1
    return sent


async def _downgrade_expired_trials(session: AsyncSession, now: datetime) -> int:
    """Zejście na plan darmowy po wygaśnięciu okresu próbnego. Zwraca liczbę zejść.

    Osobna funkcja, bo `run_trial_expiry_async` buduje własny engine pod event loop
    APSchedulera i nie da się jej podać sesji testowej — a to jest ten moment,
    w którym człowiek traci dostęp, więc musi być sprawdzalny testem.
    """
    result = await session.execute(
        select(User).where(
            User.tier == UserTier.PREMIUM.value,
            User.trial_ends_at != None,  # noqa: E711
            User.trial_ends_at < now,
            User.is_active == True,  # noqa: E712
        )
    )

    downgraded = 0
    for user in result.scalars().all():
        # Aktywna (płatna) subskrypcja bije wygasły trial
        sub_result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.status == SubscriptionStatus.ACTIVE.value,
                Subscription.expires_at > now,
            )
        )
        if sub_result.scalar_one_or_none():
            user.trial_ends_at = None
            session.add(user)
            logger.info(f"User {user.id} has paid subscription, clearing trial flag")
            continue

        # Mail idzie PRZED wyzerowaniem trial_ends_at — po zmianie planu nie ma już
        # z czego złożyć daty, a użytkownik ma się dowiedzieć, co się właśnie stało.
        announced = await _send_reminder(session, user, "ended", now)

        # Poczta padła? Dostęp zostaje do jutra. Wyzerowane `trial_ends_at` wypycha
        # konto ze WSZYSTKICH zapytań tego jobu, więc mail nigdy by nie wrócił,
        # a plan zniknąłby w ciszy — dokładnie to, przed czym etap 'ended' miał
        # chronić. Etapy 'week' i 'last_day' są odporne same z siebie (znacznik
        # stawiamy dopiero po realnej wysyłce, a próg obowiązuje nazajutrz);
        # 'ended' wypada tylko raz, więc potrzebuje tej klamry. 31.08.2026 Resend
        # odrzucał wszystko przez niezweryfikowaną domenę — dzień takiej awarii
        # wystarczy, żeby trafić w ten jeden przebieg.
        if not announced and now - user.trial_ends_at < timedelta(days=ENDED_GRACE_DAYS):
            logger.warning(
                f"User {user.id} ({user.email}): mail 'ended' nie wyszedł — "
                f"downgrade odłożony, spróbuję jutro"
            )
            continue

        user.tier = UserTier.FREE.value
        user.trial_ends_at = None
        session.add(user)
        downgraded += 1
        logger.info(f"User {user.id} ({user.email}) trial expired → downgraded to Free")

    return downgraded


async def _close_abandoned_payments(session: AsyncSession, now: datetime) -> int:
    """Zamyka wpisy `pending` po porzuconej płatności (starsze niż doba).

    Rekord `pending` powstaje przy `/create-transaction`, a płatność potwierdza
    dopiero IPN. Kto rozmyśli się na stronie P24, zostawia po sobie wpis, który
    nigdy nie doczeka potwierdzenia — 20.08 były w bazie dwa takie sieroty.
    Same z siebie nie szkodzą, ale zaśmiecają każdą odpowiedź na pytanie
    „co ten użytkownik ma", a `/verify` musi je omijać.

    Doba, nie godzina: BLIK i przelew potrafią zejść klientowi dłużej niż sesja
    w przeglądarce, a P24 przyjmuje potwierdzenie z opóźnieniem.
    """
    result = await session.execute(
        select(Subscription).where(
            Subscription.status == SubscriptionStatus.PENDING.value,
            Subscription.created_at < now - timedelta(days=1),
        )
    )
    closed = 0
    for sub in result.scalars().all():
        sub.status = SubscriptionStatus.EXPIRED.value
        sub.updated_at = now
        session.add(sub)
        closed += 1
        logger.info(f"Porzucona płatność: subskrypcja {sub.id} (user {sub.user_id}) → expired")
    return closed


async def run_trial_expiry_async():
    """Downgrade userów po wygaśnięciu triala."""
    logger.info("=== Trial Expiry Job START ===")
    now = datetime.utcnow()

    # Tworzymy własny engine dla tego event loopa (nie reużywamy globalnego z uvloop FastAPI)
    engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Uprzedzenie: mail wychodzi ZANIM cokolwiek zabierzemy — osobno dla
        # okresu próbnego i osobno dla opłaconej subskrypcji (inna treść, inny znacznik)
        reminded = await _send_upcoming_reminders(session, now)
        reminded_paid = await _send_paid_reminders(session, now)
        await session.commit()

        # 1b. Zejście na plan darmowy po wygaśnięciu okresu próbnego
        downgraded = await _downgrade_expired_trials(session, now)

        # 2. Wygaś opłacone subskrypcje po expires_at
        expired_subs = 0
        # ACTIVE i CANCELLED — anulowane zachowują dostęp do końca opłaconego okresu
        sub_result = await session.execute(
            select(Subscription).where(
                Subscription.status.in_(
                    [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.CANCELLED.value]
                ),
                Subscription.expires_at != None,
                Subscription.expires_at < now,
            )
        )
        for sub in sub_result.scalars().all():
            sub.status = SubscriptionStatus.EXPIRED.value
            sub.updated_at = now
            session.add(sub)
            expired_subs += 1

            user_result = await session.execute(select(User).where(User.id == sub.user_id))
            sub_user = user_result.scalar_one_or_none()

            # Mail o zmianie planu idzie zawsze, gdy opłacony okres się skończył —
            # także wtedy, gdy konto ma jeszcze inną aktywną subskrypcję i tieru nie
            # tracimy. Klient ma wiedzieć, że to, za co zapłacił, właśnie się zamknęło.
            if sub_user and sub_user.is_active:
                await _send_subscription_reminder(session, sub, sub_user, "ended", now)

            if sub_user and sub_user.tier != UserTier.FREE.value and not sub_user.trial_ends_at:
                # Czy user ma inną wciąż aktywną subskrypcję?
                other_result = await session.execute(
                    select(Subscription).where(
                        Subscription.user_id == sub.user_id,
                        Subscription.status == SubscriptionStatus.ACTIVE.value,
                        Subscription.expires_at > now,
                        Subscription.id != sub.id,
                    )
                )
                if not other_result.scalars().first():
                    sub_user.tier = UserTier.FREE.value
                    session.add(sub_user)
                    logger.info(f"Subscription expired: user {sub_user.id} ({sub_user.email}) → downgraded to Free")

        # 3. Wyłącz wyróżnienie wizytówek po premium_until (regulamin §11: powrót do postaci podstawowej)
        premium_off = 0
        profile_result = await session.execute(
            select(BusinessProfile).where(
                BusinessProfile.is_premium == True,
                BusinessProfile.premium_until != None,
                BusinessProfile.premium_until < now,
            )
        )
        for profile in profile_result.scalars().all():
            profile.is_premium = False
            profile.updated_at = now
            session.add(profile)
            premium_off += 1
            logger.info(f"Business profile premium expired: profile_id={profile.id}")

        # 4. Porzucone płatności — wpisy `pending`, których IPN nigdy nie potwierdził
        abandoned = await _close_abandoned_payments(session, now)

        await session.commit()

    logger.info(
        f"=== Trial Expiry Job DONE: {reminded} przypomnień o trialu, "
        f"{reminded_paid} przypomnień o subskrypcji, "
        f"{downgraded} triali wygaszonych, "
        f"{expired_subs} subskrypcji expired, {premium_off} wizytówek premium off, "
        f"{abandoned} porzuconych płatności zamkniętych ==="
    )


def run_trial_expiry():
    """Wrapper synchroniczny dla APScheduler."""
    asyncio.run(run_trial_expiry_async())
