"""
Push Notifications Endpoints (Sprint 5C)

Endpointy:
- GET  /api/push/vapid-public-key  – publiczny klucz VAPID dla frontend
- POST /api/push/subscribe          – rejestracja subskrypcji
- DELETE /api/push/subscribe        – wypisanie (po endpoint URL)
- POST /api/push/test               – test wysyłki (tylko admin/business)
"""
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlmodel import select

from src.config import settings
from src.database.connection import async_session
from src.database.schema import PushSubscription
from src.auth.dependencies import get_optional_user, get_business_user
from src.services.push_service import push_service
from src.utils.logger import setup_logger

logger = setup_logger("PushAPI")

router = APIRouter(prefix="/api/push", tags=["push"])


# ==================== Request/Response Models ====================

class PushSubscribeRequest(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    categories: List[str] = ["alerty", "powietrze", "artykuly"]
    user_agent: Optional[str] = None


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


class PushTestRequest(BaseModel):
    title: str = "Test powiadomienia"
    body: str = "Centrum Operacyjne Mieszkańca – test push"
    url: str = "/"


# ==================== Endpoints ====================

@router.get("/vapid-public-key")
async def get_vapid_public_key():
    """Zwraca publiczny klucz VAPID dla frontend (do serviceWorker)."""
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(
            status_code=503,
            detail="Push notifications nie są skonfigurowane (brak VAPID_PUBLIC_KEY)"
        )
    return {"publicKey": settings.VAPID_PUBLIC_KEY}


@router.post("/subscribe", status_code=201)
async def subscribe_push(
    payload: PushSubscribeRequest,
    request: Request,
    current_user=Depends(get_optional_user),
):
    """
    Rejestruje subskrypcję push notification.
    Działa dla zalogowanych i niezalogowanych użytkowników.
    """
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(
            status_code=503,
            detail="Push notifications nie są skonfigurowane"
        )

    async with async_session() as session:
        # Sprawdź czy subskrypcja już istnieje (po endpoint)
        result = await session.execute(
            select(PushSubscription).where(
                PushSubscription.endpoint == payload.endpoint
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Zaktualizuj istniejącą subskrypcję
            existing.p256dh = payload.p256dh
            existing.auth = payload.auth
            existing.categories = payload.categories
            existing.active = True
            existing.last_used_at = datetime.utcnow()
            if current_user:
                existing.user_id = current_user.id
                existing.email = current_user.email
            session.add(existing)
            await session.commit()
            logger.info(f"Updated push subscription: {payload.endpoint[:50]}...")
            return {"status": "updated", "id": existing.id}

        # Nowa subskrypcja
        user_agent = payload.user_agent or request.headers.get("user-agent", "")
        subscription = PushSubscription(
            user_id=current_user.id if current_user else None,
            email=current_user.email if current_user else None,
            endpoint=payload.endpoint,
            p256dh=payload.p256dh,
            auth=payload.auth,
            categories=payload.categories,
            user_agent=user_agent[:500] if user_agent else None,
            active=True,
        )
        session.add(subscription)
        await session.commit()
        await session.refresh(subscription)
        logger.info(f"New push subscription: {payload.endpoint[:50]}... (user_id={subscription.user_id})")
        return {"status": "subscribed", "id": subscription.id}


@router.delete("/subscribe")
async def unsubscribe_push(payload: PushUnsubscribeRequest):
    """Wypisuje subskrypcję push (po endpoint URL)."""
    async with async_session() as session:
        result = await session.execute(
            select(PushSubscription).where(
                PushSubscription.endpoint == payload.endpoint
            )
        )
        subscription = result.scalar_one_or_none()

        if not subscription:
            raise HTTPException(status_code=404, detail="Subskrypcja nie znaleziona")

        subscription.active = False
        session.add(subscription)
        await session.commit()
        logger.info(f"Push subscription deactivated: {payload.endpoint[:50]}...")
        return {"status": "unsubscribed"}


@router.post("/test")
async def test_push(
    payload: PushTestRequest,
    current_user=Depends(get_business_user),
):
    """
    Test wysyłki push notification do wszystkich aktywnych subskrybentów.
    Wymaga konta Business.
    """
    async with async_session() as session:
        sent = await push_service.send_to_category(
            session=session,
            category="alerty",
            title=payload.title,
            body=payload.body,
            url=payload.url,
        )
    return {"status": "sent", "recipients": sent}


@router.get("/subscriptions/count")
async def get_subscriptions_count(current_user=Depends(get_business_user)):
    """Liczba aktywnych subskrypcji push (tylko Business)."""
    from sqlalchemy import func
    async with async_session() as session:
        result = await session.execute(
            select(func.count()).where(PushSubscription.active == True)
        )
        count = result.scalar()
    return {"active_subscriptions": count}
