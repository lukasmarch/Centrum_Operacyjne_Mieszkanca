"""
Zapis konta na newsletter — jedno miejsce dla rejestracji i dla przełącznika w profilu.

Cennik obiecuje newsletter tygodniowy w planie darmowym i dzienny w Premium, więc
subskrypcja jest częścią zamówionej usługi, a nie zgodą marketingową. Do 20.08.2026
rejestracja nie zakładała jej wcale: pierwszy prawdziwy użytkownik zaznaczył zgodę
marketingową i nie dostał ani jednego maila, bo jedyną działającą drogą był
przełącznik w profilu, do którego nigdy nie zajrzał.

Moduł celowo nie zna FastAPI ani zależności auth — `newsletter/routes.py` importuje
`src.auth.dependencies`, więc sięganie po tamtejszą logikę z `auth/routes.py`
zawiązywałoby pętlę importów.
"""

import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import NewsletterSubscriber, NewsletterFrequency, NewsletterStatus, User, UserTier

PREMIUM_TIERS = (UserTier.PREMIUM.value, UserTier.BUSINESS.value)


def default_frequency(tier: str) -> str:
    """Dzienny briefing to dodatek Premium — plan darmowy dostaje tygodniowy."""
    return (
        NewsletterFrequency.DAILY.value
        if tier in PREMIUM_TIERS
        else NewsletterFrequency.WEEKLY.value
    )


def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


async def ensure_subscription(
    session: AsyncSession,
    user: User,
    frequency: Optional[str] = None,
) -> Optional[NewsletterSubscriber]:
    """Zakłada lub uzupełnia subskrypcję konta. Nie commituje — robi to wywołujący.

    Zwraca `None`, gdy użytkownik wcześniej się wypisał: wypis jest decyzją, której
    założenie konta nie może cofnąć.

    `confirmed_at` ustawiamy od razu, bez maila potwierdzającego. Adres pochodzi
    z konta, a nie z anonimowego formularza, i tak samo robi już przełącznik
    w profilu (`PUT /api/newsletter/my-subscription`).
    """
    result = await session.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == user.email)
    )
    subscriber = result.scalar_one_or_none()

    if subscriber is None:
        subscriber = NewsletterSubscriber(
            email=user.email,
            user_id=user.id,
            frequency=frequency or default_frequency(user.tier),
            location=user.location,
            status=NewsletterStatus.ACTIVE.value,
            confirmed_at=datetime.utcnow(),
            unsubscribe_token=generate_token(),
        )
        session.add(subscriber)
        return subscriber

    if subscriber.status == NewsletterStatus.UNSUBSCRIBED.value:
        # Ktoś świadomie zrezygnował — konto zakładane na ten sam adres tego nie odwraca.
        return None

    if subscriber.user_id is None:
        subscriber.user_id = user.id  # zapis sprzed rejestracji dostaje właściciela
    if frequency:
        subscriber.frequency = frequency
    if not subscriber.confirmed_at:
        subscriber.confirmed_at = datetime.utcnow()
    subscriber.updated_at = datetime.utcnow()
    session.add(subscriber)
    return subscriber
