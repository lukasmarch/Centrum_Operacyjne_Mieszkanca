"""
Newsletter API routes
"""

import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from src.database import (
    get_session, NewsletterSubscriber, NewsletterLog, User,
    NewsletterFrequency, NewsletterStatus, UserTier
)
from src.auth.dependencies import get_current_active_user, get_optional_user
from .schemas import (
    NewsletterSubscribe, NewsletterUnsubscribe, NewsletterConfirm,
    NewsletterPreferencesUpdate, SubscriberResponse, SubscriptionStats, MessageResponse
)
from .email_service import EmailService

router = APIRouter(prefix="/api/newsletter", tags=["newsletter"])


def generate_token(length: int = 32) -> str:
    """Generate a secure random token"""
    return secrets.token_urlsafe(length)


@router.post("/subscribe", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def subscribe(
    data: NewsletterSubscribe,
    current_user: User = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Subscribe to the newsletter.

    - Free users can only subscribe to weekly
    - Premium users can subscribe to daily
    - Sends confirmation email
    """
    # Check if already subscribed
    result = await session.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == data.email)
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.status == NewsletterStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already subscribed to newsletter"
            )
        else:
            # Reactivate existing subscription
            existing.status = NewsletterStatus.ACTIVE.value
            existing.unsubscribed_at = None
            existing.frequency = data.frequency
            existing.location = data.location
            existing.updated_at = datetime.utcnow()
            await session.commit()
            return MessageResponse(message="Newsletter subscription reactivated")

    # Check if daily is allowed (Premium only)
    if data.frequency == NewsletterFrequency.DAILY.value:
        if not current_user or current_user.tier not in [UserTier.PREMIUM.value, UserTier.BUSINESS.value]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Daily newsletter requires Premium subscription"
            )

    # Create new subscriber
    confirmation_token = generate_token()
    unsubscribe_token = generate_token()

    subscriber = NewsletterSubscriber(
        email=data.email,
        user_id=current_user.id if current_user else None,
        frequency=data.frequency,
        location=data.location,
        confirmation_token=confirmation_token,
        unsubscribe_token=unsubscribe_token
    )

    session.add(subscriber)
    await session.commit()

    # Send confirmation email
    email_service = EmailService()
    await email_service.send_confirmation_email(
        to_email=data.email,
        confirmation_token=confirmation_token
    )

    return MessageResponse(
        message="Check your email to confirm subscription"
    )


@router.post("/confirm", response_model=MessageResponse)
async def confirm_subscription(
    data: NewsletterConfirm,
    session: AsyncSession = Depends(get_session)
):
    """
    Confirm newsletter subscription via token from email.
    """
    result = await session.execute(
        select(NewsletterSubscriber)
        .where(NewsletterSubscriber.confirmation_token == data.token)
    )
    subscriber = result.scalar_one_or_none()

    if not subscriber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid confirmation token"
        )

    if subscriber.confirmed_at:
        return MessageResponse(message="Subscription already confirmed")

    subscriber.confirmed_at = datetime.utcnow()
    subscriber.confirmation_token = None  # Invalidate token
    subscriber.updated_at = datetime.utcnow()

    await session.commit()

    return MessageResponse(message="Newsletter subscription confirmed!")


@router.post("/unsubscribe", response_model=MessageResponse)
async def unsubscribe(
    data: NewsletterUnsubscribe,
    session: AsyncSession = Depends(get_session)
):
    """
    Unsubscribe from newsletter via token.
    """
    result = await session.execute(
        select(NewsletterSubscriber)
        .where(NewsletterSubscriber.unsubscribe_token == data.token)
    )
    subscriber = result.scalar_one_or_none()

    if not subscriber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid unsubscribe token"
        )

    if subscriber.status == NewsletterStatus.UNSUBSCRIBED.value:
        return MessageResponse(message="Already unsubscribed")

    subscriber.status = NewsletterStatus.UNSUBSCRIBED.value
    subscriber.unsubscribed_at = datetime.utcnow()
    subscriber.updated_at = datetime.utcnow()

    await session.commit()

    return MessageResponse(message="Successfully unsubscribed from newsletter")


@router.get("/preferences", response_model=SubscriberResponse)
async def get_preferences(
    token: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Get current subscription preferences by unsubscribe token.
    """
    result = await session.execute(
        select(NewsletterSubscriber)
        .where(NewsletterSubscriber.unsubscribe_token == token)
    )
    subscriber = result.scalar_one_or_none()

    if not subscriber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid token"
        )

    return SubscriberResponse.model_validate(subscriber)


@router.put("/preferences", response_model=SubscriberResponse)
async def update_preferences(
    token: str,
    data: NewsletterPreferencesUpdate,
    session: AsyncSession = Depends(get_session)
):
    """
    Update subscription preferences (location, frequency).
    """
    result = await session.execute(
        select(NewsletterSubscriber)
        .where(NewsletterSubscriber.unsubscribe_token == token)
    )
    subscriber = result.scalar_one_or_none()

    if not subscriber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid token"
        )

    # Check if trying to upgrade to daily
    if data.frequency == NewsletterFrequency.DAILY.value:
        # Check if user has premium
        if subscriber.user_id:
            user_result = await session.execute(
                select(User).where(User.id == subscriber.user_id)
            )
            user = user_result.scalar_one_or_none()
            if not user or user.tier not in [UserTier.PREMIUM.value, UserTier.BUSINESS.value]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Daily newsletter requires Premium subscription"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Daily newsletter requires Premium subscription"
            )

    if data.location:
        subscriber.location = data.location
    if data.frequency:
        subscriber.frequency = data.frequency

    subscriber.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(subscriber)

    return SubscriberResponse.model_validate(subscriber)


@router.get("/my-subscription", response_model=SubscriberResponse)
async def get_my_subscription(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Get current user's newsletter subscription.
    Requires authentication.
    """
    result = await session.execute(
        select(NewsletterSubscriber)
        .where(NewsletterSubscriber.user_id == current_user.id)
        .where(NewsletterSubscriber.status == NewsletterStatus.ACTIVE.value)
    )
    subscriber = result.scalar_one_or_none()

    if not subscriber:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active newsletter subscription"
        )

    return SubscriberResponse.model_validate(subscriber)


@router.put("/my-subscription")
async def update_my_subscription(
    data: dict,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Upsert newsletter subscription for the logged-in user.
    Body: {"frequency": "daily"|"weekly", "weekly": bool, "daily": bool}
    """
    # Validate daily requires premium
    frequency = data.get("frequency")
    if frequency == NewsletterFrequency.DAILY.value:
        if current_user.tier not in [UserTier.PREMIUM.value, UserTier.BUSINESS.value]:
            raise HTTPException(status_code=403, detail="Daily newsletter requires Premium")

    result = await session.execute(
        select(NewsletterSubscriber)
        .where(NewsletterSubscriber.user_id == current_user.id)
        .where(NewsletterSubscriber.status == NewsletterStatus.ACTIVE.value)
    )
    subscriber = result.scalar_one_or_none()

    if not subscriber:
        # Create new subscriber
        subscriber = NewsletterSubscriber(
            email=current_user.email,
            user_id=current_user.id,
            frequency=frequency or NewsletterFrequency.WEEKLY.value,
            status=NewsletterStatus.ACTIVE.value,
            confirmed_at=datetime.utcnow(),
            unsubscribe_token=generate_token(),
        )
        session.add(subscriber)
    else:
        if frequency:
            subscriber.frequency = frequency
        if not subscriber.confirmed_at:
            subscriber.confirmed_at = datetime.utcnow()
        subscriber.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(subscriber)
    return {"status": "ok", "frequency": subscriber.frequency, "email": subscriber.email}


@router.get("/stats", response_model=SubscriptionStats)
async def get_newsletter_stats(
    session: AsyncSession = Depends(get_session)
):
    """
    Get newsletter subscription statistics.
    Public endpoint.
    """
    # Total subscribers
    total_result = await session.execute(
        select(func.count(NewsletterSubscriber.id))
    )
    total = total_result.scalar() or 0

    # Active subscribers
    active_result = await session.execute(
        select(func.count(NewsletterSubscriber.id))
        .where(NewsletterSubscriber.status == NewsletterStatus.ACTIVE.value)
    )
    active = active_result.scalar() or 0

    # Weekly subscribers
    weekly_result = await session.execute(
        select(func.count(NewsletterSubscriber.id))
        .where(NewsletterSubscriber.status == NewsletterStatus.ACTIVE.value)
        .where(NewsletterSubscriber.frequency == NewsletterFrequency.WEEKLY.value)
    )
    weekly = weekly_result.scalar() or 0

    # Daily subscribers
    daily_result = await session.execute(
        select(func.count(NewsletterSubscriber.id))
        .where(NewsletterSubscriber.status == NewsletterStatus.ACTIVE.value)
        .where(NewsletterSubscriber.frequency == NewsletterFrequency.DAILY.value)
    )
    daily = daily_result.scalar() or 0

    return SubscriptionStats(
        total_subscribers=total,
        active_subscribers=active,
        weekly_subscribers=weekly,
        daily_subscribers=daily
    )
