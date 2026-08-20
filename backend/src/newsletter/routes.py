"""
Newsletter API routes
"""

import html
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from src.config import settings
from src.database import (
    get_session, NewsletterSubscriber, NewsletterLog, User,
    NewsletterFrequency, NewsletterStatus, UserTier
)
from src.auth.dependencies import get_current_active_user, get_optional_user
from .schemas import (
    NewsletterSubscribe, NewsletterConfirm,
    NewsletterPreferencesUpdate, SubscriberResponse, SubscriptionStats, MessageResponse
)
from .email_service import EmailService
from .subscriptions import ensure_subscription

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


def _unsubscribe_page(title: str, body: str, form_token: Optional[str] = None) -> HTMLResponse:
    """Strona wypisu w kolorystyce newslettera — bez logowania i bez frontendu."""
    button = ""
    if form_token:
        button = f"""
      <form method="post" action="/api/newsletter/unsubscribe">
        <input type="hidden" name="token" value="{html.escape(form_token)}">
        <button type="submit" style="margin-top:22px; padding:13px 26px; background:#3a81f6; color:#fff; border:0; border-radius:12px; font-size:15px; font-weight:700; cursor:pointer;">Potwierdzam wypisanie</button>
      </form>"""

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RybnoLive — newsletter</title></head>
<body style="margin:0; background:#020617; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif; color:#fafafa;">
  <div style="max-width:520px; margin:0 auto; padding:64px 24px;">
    <div style="font-size:21px; font-weight:800; letter-spacing:-0.4px;">Rybno<span style="color:#91c5ff;">Live</span></div>
    <div style="margin-top:32px; background:#0d1117; border:1px solid #1f2937; border-radius:20px; padding:28px;">
      <h1 style="margin:0; font-size:22px; line-height:29px;">{html.escape(title)}</h1>
      <p style="margin:10px 0 0; font-size:15px; line-height:23px; color:#a1a1a1;">{html.escape(body)}</p>{button}
    </div>
    <p style="margin-top:24px; font-size:13px; color:#525252;">
      <a href="{settings.APP_URL}" style="color:#91c5ff; text-decoration:none;">Wróć do rybnolive.pl</a>
    </p>
  </div>
</body></html>""")


@router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe_page(token: str):
    """
    Strona wypisu otwierana z linku w stopce newslettera.

    Sam GET niczego nie zmienia — skanery antyspamowe i podglądy linków w klientach
    pocztowych odwiedzają adresy z maila, więc wypis następuje dopiero po kliknięciu
    przycisku (POST).
    """
    return _unsubscribe_page(
        "Wypisać Cię z newslettera?",
        "Przestaniemy wysyłać briefing i podsumowanie tygodnia. Konto w serwisie zostaje bez zmian.",
        form_token=token,
    )


@router.post("/unsubscribe")
async def unsubscribe(
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    """
    Unsubscribe from newsletter via token.

    Token przyjmujemy trzema drogami, bo ten sam adres obsługuje:
    - JSON `{"token": ...}` — wywołania z aplikacji (odpowiedź JSON),
    - formularz ze strony wypisu,
    - one-click z nagłówka List-Unsubscribe (Gmail/Outlook wysyłają POST na adres
      z maila, token siedzi w query stringu).
    """
    token = request.query_params.get("token")
    wants_json = False
    content_type = request.headers.get("content-type", "")

    if not token and content_type.startswith("application/json"):
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        token = payload.get("token")
        wants_json = True
    elif not token:
        form = await request.form()
        token = form.get("token")

    if not token:
        if wants_json:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing token")
        return _unsubscribe_page("Brak tokenu", "Link jest niekompletny. Otwórz go ponownie z wiadomości e-mail.")

    result = await session.execute(
        select(NewsletterSubscriber)
        .where(NewsletterSubscriber.unsubscribe_token == token)
    )
    subscriber = result.scalar_one_or_none()

    if not subscriber:
        if wants_json:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invalid unsubscribe token"
            )
        return _unsubscribe_page(
            "Nie znaleźliśmy tej subskrypcji",
            "Link wygasł albo został już użyty. Jeśli nadal dostajesz wiadomości, napisz na biuro@lumargo.pl.",
        )

    if subscriber.status == NewsletterStatus.UNSUBSCRIBED.value:
        if wants_json:
            return MessageResponse(message="Already unsubscribed")
        return _unsubscribe_page("Już Cię wypisaliśmy", "Ten adres nie otrzymuje newslettera RybnoLive.")

    subscriber.status = NewsletterStatus.UNSUBSCRIBED.value
    subscriber.unsubscribed_at = datetime.utcnow()
    subscriber.updated_at = datetime.utcnow()

    await session.commit()

    if wants_json:
        return MessageResponse(message="Successfully unsubscribed from newsletter")

    return _unsubscribe_page(
        "Wypisaliśmy Cię z newslettera",
        "Nie wyślemy już briefingu ani podsumowania tygodnia. Możesz zapisać się ponownie w każdej chwili w serwisie.",
    )


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

    # Ta sama ścieżka co przy rejestracji — jedno miejsce decyduje, jak wygląda
    # subskrypcja konta (patrz newsletter/subscriptions.py).
    subscriber = await ensure_subscription(session, current_user, frequency=frequency)
    if subscriber is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ten adres został wypisany z newslettera — zapisz się ponownie przez formularz",
        )

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
