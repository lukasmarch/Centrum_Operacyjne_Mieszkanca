"""
Trial/Subscription Expiry Job — codziennie o 5:00

1. Downgrade userów z wygasłym 30-dniowym trialem Premium (brak aktywnej subskrypcji).
2. Wygaszanie opłaconych subskrypcji po expires_at (status → expired, tier → free).
3. Wyłączanie wyróżnienia wizytówek (is_premium) po premium_until (plan Firma lokalna).
"""
import asyncio
import logging
from datetime import datetime

from sqlmodel import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.database.schema import User, Subscription, UserTier, SubscriptionStatus, BusinessProfile
from src.utils.logger import setup_logger

logger = setup_logger("TrialExpiryJob")


async def run_trial_expiry_async():
    """Downgrade userów po wygaśnięciu triala."""
    logger.info("=== Trial Expiry Job START ===")
    now = datetime.utcnow()
    downgraded = 0

    # Tworzymy własny engine dla tego event loopa (nie reużywamy globalnego z uvloop FastAPI)
    engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Znajdź userów z wygasłym trialem (tier=premium, trial_ends_at < now)
        result = await session.execute(
            select(User).where(
                User.tier == UserTier.PREMIUM.value,
                User.trial_ends_at != None,
                User.trial_ends_at < now,
                User.is_active == True,
            )
        )
        trial_expired_users = result.scalars().all()

        for user in trial_expired_users:
            # Sprawdź czy ma aktywną (płatną) subskrypcję
            sub_result = await session.execute(
                select(Subscription).where(
                    Subscription.user_id == user.id,
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                    Subscription.expires_at > now,
                )
            )
            active_sub = sub_result.scalar_one_or_none()

            if active_sub:
                # Ma płatną subskrypcję — wyczyść trial, zostaw tier
                user.trial_ends_at = None
                session.add(user)
                logger.info(f"User {user.id} has paid subscription, clearing trial flag")
            else:
                # Brak subskrypcji — downgrade do Free
                user.tier = UserTier.FREE.value
                user.trial_ends_at = None
                session.add(user)
                downgraded += 1
                logger.info(f"User {user.id} ({user.email}) trial expired → downgraded to Free")

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

        await session.commit()

    logger.info(
        f"=== Trial Expiry Job DONE: {downgraded} triali wygaszonych, "
        f"{expired_subs} subskrypcji expired, {premium_off} wizytówek premium off ==="
    )


def run_trial_expiry():
    """Wrapper synchroniczny dla APScheduler."""
    asyncio.run(run_trial_expiry_async())
