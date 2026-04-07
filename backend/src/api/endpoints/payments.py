"""
Płatności Przelewy24 + BLIK
POST /api/payments/create-transaction  — tworzy sesję płatności, zwraca redirect URL
POST /api/payments/webhook             — IPN webhook od P24 (server-to-server)
GET  /api/payments/verify              — weryfikacja po powrocie z P24
GET  /api/payments/subscription        — status subskrypcji zalogowanego usera
POST /api/payments/cancel              — anulowanie subskrypcji
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import settings
from src.database import get_session
from src.database.schema import User, Subscription, UserTier, SubscriptionStatus
from src.auth.dependencies import get_current_active_user
from src.services.p24_service import p24_service, SUBSCRIPTION_PRICES

logger = logging.getLogger("PaymentsAPI")

router = APIRouter(prefix="/api/payments", tags=["payments"])

# Mapowanie tierów na wyświetlane nazwy
TIER_NAMES = {
    "premium": "Premium",
    "business": "Pro",
}

# Czas trwania subskrypcji
PERIOD_DAYS = {
    "monthly": 31,
    "yearly": 366,
}


# =======================
# Request/Response Models
# =======================

class CreateTransactionRequest(BaseModel):
    tier: str            # "premium" | "business"
    period: str          # "monthly" | "yearly"


class CreateTransactionResponse(BaseModel):
    redirect_url: str
    session_id: str
    amount_pln: float


class SubscriptionStatusResponse(BaseModel):
    tier: str
    status: str
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    is_trial: bool = False


# =======================
# Helper: upgrade user tier
# =======================

async def _activate_subscription(
    session: AsyncSession,
    user: User,
    tier: str,
    period: str,
    p24_session_id: str,
    p24_order_id: str,
) -> Subscription:
    """Aktywuje subskrypcję po potwierdzeniu płatności przez P24."""
    # Anuluj poprzednią aktywną subskrypcję (jeśli istnieje)
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE.value,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.status = SubscriptionStatus.CANCELLED.value
        existing.cancelled_at = datetime.utcnow()
        existing.updated_at = datetime.utcnow()

    # Nowa subskrypcja
    expires_at = datetime.utcnow() + timedelta(days=PERIOD_DAYS[period])
    sub = Subscription(
        user_id=user.id,
        tier=tier,
        status=SubscriptionStatus.ACTIVE.value,
        p24_order_id=p24_order_id,
        p24_session_id=p24_session_id,
        started_at=datetime.utcnow(),
        expires_at=expires_at,
    )
    session.add(sub)

    # Upgrade user tier
    user.tier = tier
    user.trial_ends_at = None  # Koniec trialu po zakupie

    await session.commit()
    await session.refresh(sub)
    logger.info(f"Subscription activated: user_id={user.id}, tier={tier}, period={period}, expires={expires_at.date()}")
    return sub


# =======================
# Endpoints
# =======================

@router.post("/create-transaction", response_model=CreateTransactionResponse)
async def create_transaction(
    req: CreateTransactionRequest,
    request: Request,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Tworzy sesję płatności w Przelewy24 i zwraca URL do przekierowania.
    User musi być zalogowany.
    """
    if req.tier not in SUBSCRIPTION_PRICES:
        raise HTTPException(status_code=400, detail=f"Nieznany tier: {req.tier}")
    if req.period not in ("monthly", "yearly"):
        raise HTTPException(status_code=400, detail="Period musi być 'monthly' lub 'yearly'")

    amount = p24_service.get_price(req.tier, req.period)
    if amount == 0:
        raise HTTPException(status_code=400, detail="Brak ceny dla tego planu")

    session_id = p24_service.generate_session_id(user.id, req.tier, req.period)
    tier_name = TIER_NAMES.get(req.tier, req.tier.capitalize())
    period_label = "miesięczna" if req.period == "monthly" else "roczna"
    description = f"Centrum Operacyjne Rybna — subskrypcja {tier_name} ({period_label})"

    # URL-e zwrotne
    return_url = f"{settings.APP_URL}/payment/success?session={session_id}&tier={req.tier}"
    notify_url = f"{settings.APP_URL.replace('localhost:3000', 'localhost:8000')}/api/payments/webhook"

    # Zapis pending subscription
    pending_sub = Subscription(
        user_id=user.id,
        tier=req.tier,
        status=SubscriptionStatus.PENDING.value,
        p24_session_id=session_id,
    )
    session.add(pending_sub)
    await session.commit()

    try:
        result = p24_service.register_transaction(
            session_id=session_id,
            amount=amount,
            email=user.email,
            description=description,
            return_url=return_url,
            notify_url=notify_url,
            first_name=user.full_name.split()[0] if user.full_name else "",
            last_name=" ".join(user.full_name.split()[1:]) if user.full_name and " " in user.full_name else "",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return CreateTransactionResponse(
        redirect_url=result["redirect_url"],
        session_id=session_id,
        amount_pln=round(amount / 100, 2),
    )


@router.post("/webhook")
async def p24_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    IPN Webhook od Przelewy24 (server-to-server).
    P24 wysyła POST po potwierdzeniu/odrzuceniu płatności.
    Endpoint musi zwrócić HTTP 200 żeby P24 uznał że IPN dotarł.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    session_id = body.get("sessionId", "")
    order_id = str(body.get("orderId", ""))
    amount = int(body.get("amount", 0))
    currency = body.get("currency", "PLN")

    logger.info(f"P24 IPN received: session_id={session_id}, order_id={order_id}, amount={amount}")

    if not session_id or not order_id:
        logger.warning("P24 IPN: brak sessionId lub orderId")
        return {"status": "ok"}

    # Znajdź pending subscription po session_id
    result = await session.execute(
        select(Subscription).where(Subscription.p24_session_id == session_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        logger.warning(f"P24 IPN: brak subskrypcji dla session_id={session_id}")
        return {"status": "ok"}

    # Pobierz usera
    user_result = await session.execute(
        select(User).where(User.id == sub.user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        logger.error(f"P24 IPN: brak usera id={sub.user_id}")
        return {"status": "ok"}

    # Weryfikuj transakcję z P24
    verified = p24_service.verify_transaction(session_id, order_id, amount, currency)
    if not verified:
        logger.error(f"P24 IPN: weryfikacja nieudana dla session_id={session_id}")
        sub.status = SubscriptionStatus.EXPIRED.value
        sub.updated_at = datetime.utcnow()
        await session.commit()
        return {"status": "ok"}

    # Wyciągnij tier i period z session_id (format: COM-{user_id}-{tier}-{period}-{hex})
    parts = session_id.split("-")
    tier = parts[2] if len(parts) >= 4 else sub.tier
    period = parts[3] if len(parts) >= 5 else "monthly"

    # Aktywuj subskrypcję
    await _activate_subscription(session, user, tier, period, session_id, order_id)

    return {"status": "ok"}


@router.get("/verify")
async def verify_payment(
    session_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_active_user),
):
    """
    Weryfikacja statusu płatności po powrocie z P24.
    Frontend wywołuje po przekierowaniu z success URL.
    """
    result = await session.execute(
        select(Subscription).where(
            Subscription.p24_session_id == session_id,
            Subscription.user_id == user.id,
        )
    )
    sub = result.scalar_one_or_none()

    if not sub:
        raise HTTPException(status_code=404, detail="Transakcja nie znaleziona")

    await session.refresh(user)

    return {
        "status": sub.status,
        "tier": sub.tier,
        "expires_at": sub.expires_at,
        "user_tier": user.tier,
    }


@router.get("/subscription", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Status subskrypcji zalogowanego usera."""
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE.value,
        ).order_by(Subscription.expires_at.desc())
    )
    sub = result.scalar_one_or_none()

    is_trial = bool(
        user.trial_ends_at and
        user.trial_ends_at > datetime.utcnow() and
        user.tier in [UserTier.PREMIUM.value, UserTier.BUSINESS.value]
    )

    return SubscriptionStatusResponse(
        tier=user.tier,
        status=sub.status if sub else "free",
        started_at=sub.started_at if sub else None,
        expires_at=sub.expires_at if sub else None,
        trial_ends_at=user.trial_ends_at,
        is_trial=is_trial,
    )


@router.post("/cancel")
async def cancel_subscription(
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Anuluje aktywną subskrypcję usera."""
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE.value,
        )
    )
    sub = result.scalar_one_or_none()

    if not sub:
        raise HTTPException(status_code=404, detail="Brak aktywnej subskrypcji")

    sub.status = SubscriptionStatus.CANCELLED.value
    sub.cancelled_at = datetime.utcnow()
    sub.updated_at = datetime.utcnow()

    user.tier = UserTier.FREE.value

    await session.commit()
    logger.info(f"Subscription cancelled: user_id={user.id}")

    return {"status": "cancelled", "message": "Subskrypcja anulowana. Dostęp do końca okresu rozliczeniowego."}
