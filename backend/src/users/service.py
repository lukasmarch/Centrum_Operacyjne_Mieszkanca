"""
User service - CRUD operations for users
"""

from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import User, Subscription, UserTier, SubscriptionStatus
from src.auth.jwt import verify_password, get_password_hash


class UserService:
    """Service class for user operations"""

    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
        """Get user by ID"""
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
        """Get user by email"""
        result = await session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_user_profile(
        session: AsyncSession,
        user: User,
        full_name: Optional[str] = None,
        location: Optional[str] = None,
        preferences: Optional[dict] = None
    ) -> User:
        """Update user profile fields"""
        if full_name is not None:
            user.full_name = full_name
        if location is not None:
            user.location = location
        if preferences is not None:
            # Merge preferences
            current_prefs = user.preferences or {}
            current_prefs.update(preferences)
            user.preferences = current_prefs

        await session.commit()
        await session.refresh(user)
        return user

    @staticmethod
    async def change_password(
        session: AsyncSession,
        user: User,
        current_password: str,
        new_password: str
    ) -> bool:
        """
        Change user password.

        Returns:
            True if password changed successfully
            False if current password is incorrect
        """
        if not verify_password(current_password, user.password_hash):
            return False

        user.password_hash = get_password_hash(new_password)
        await session.commit()
        return True

    @staticmethod
    async def get_user_subscription(
        session: AsyncSession,
        user_id: int
    ) -> Optional[Subscription]:
        """Get active subscription for user"""
        result = await session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE.value
            )
            .order_by(Subscription.expires_at.desc())
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def upgrade_to_premium(
        session: AsyncSession,
        user: User,
        stripe_subscription_id: Optional[str] = None,
        stripe_customer_id: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> Subscription:
        """
        Upgrade user to Premium tier.

        Creates a new subscription record and updates user tier.
        """
        # Create subscription
        subscription = Subscription(
            user_id=user.id,
            tier=UserTier.PREMIUM.value,
            status=SubscriptionStatus.ACTIVE.value,
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=stripe_customer_id,
            expires_at=expires_at
        )
        session.add(subscription)

        # Update user tier
        user.tier = UserTier.PREMIUM.value

        await session.commit()
        await session.refresh(subscription)
        await session.refresh(user)

        return subscription

    @staticmethod
    async def cancel_subscription(
        session: AsyncSession,
        subscription: Subscription
    ) -> Subscription:
        """Cancel a subscription"""
        subscription.status = SubscriptionStatus.CANCELLED.value
        subscription.cancelled_at = datetime.utcnow()
        subscription.updated_at = datetime.utcnow()

        # Get user and downgrade to free
        result = await session.execute(
            select(User).where(User.id == subscription.user_id)
        )
        user = result.scalar_one()
        user.tier = UserTier.FREE.value

        await session.commit()
        await session.refresh(subscription)

        return subscription

    @staticmethod
    async def deactivate_user(session: AsyncSession, user: User) -> User:
        """Deactivate user account"""
        user.is_active = False
        await session.commit()
        await session.refresh(user)
        return user

    @staticmethod
    async def verify_email(session: AsyncSession, user: User) -> User:
        """Mark user email as verified"""
        user.email_verified = True
        await session.commit()
        await session.refresh(user)
        return user
