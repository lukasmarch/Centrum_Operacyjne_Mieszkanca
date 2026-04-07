"""
Trial Expiry Job — codziennie o 5:00

Sprawdza userów których 7-dniowy trial Premium wygasł i downgrade'uje do Free.
Logika: trial_ends_at < now AND tier = "premium" AND brak aktywnej subskrypcji.
"""
import asyncio
import logging
from datetime import datetime

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import async_session
from src.database.schema import User, Subscription, UserTier, SubscriptionStatus
from src.utils.logger import setup_logger

logger = setup_logger("TrialExpiryJob")


async def run_trial_expiry_async():
    """Downgrade userów po wygaśnięciu triala."""
    logger.info("=== Trial Expiry Job START ===")
    now = datetime.utcnow()
    downgraded = 0

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

        await session.commit()

    logger.info(f"=== Trial Expiry Job DONE: {downgraded} users downgraded ===")


def run_trial_expiry():
    """Wrapper synchroniczny dla APScheduler."""
    asyncio.run(run_trial_expiry_async())
