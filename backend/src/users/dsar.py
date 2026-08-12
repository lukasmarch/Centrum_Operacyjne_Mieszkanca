"""
DSAR (Data Subject Access Request) — realizacja praw osób z RODO.

- export_user_data():    art. 15 (dostęp) + art. 20 (przenoszenie) — pełny zrzut
                         danych użytkownika w formacie JSON
- delete_user_account(): art. 17 (usunięcie) — kasuje dane osobowe i artefakty;
                         rekord users jest anonimizowany (nie kasowany), bo
                         subscriptions/referrals muszą pozostać dla rozliczeń
                         (art. 17 ust. 3 lit. b — obowiązek prawny)
"""

import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import delete, update, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database.schema import (
    User, Subscription, NewsletterSubscriber, Report, PushSubscription,
    BusinessProfile, BusinessAnnouncement,
)
from src.database.vectors import Conversation, ChatMessage, APICostLog
from src.utils.logger import setup_logger

logger = setup_logger("DSAR")


async def export_user_data(session: AsyncSession, user: User) -> dict:
    """Zbiera wszystkie dane osobowe użytkownika w jeden słownik (JSON-owalny)."""

    # Profil + zgody
    profile = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "location": user.location,
        "tier": user.tier,
        "preferences": user.preferences,
        "email_verified": user.email_verified,
        "created_at": _iso(user.created_at),
        "last_login": _iso(user.last_login),
        "consents": {
            "terms_accepted_at": _iso(user.consent_terms_at),
            "marketing": user.consent_marketing,
            "privacy_policy_version": user.consent_privacy_version,
        },
    }

    # Subskrypcje (płatności)
    subs = (await session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )).scalars().all()
    subscriptions = [{
        "tier": s.tier,
        "status": s.status,
        "started_at": _iso(s.started_at),
        "expires_at": _iso(s.expires_at),
        "p24_order_id": s.p24_order_id,
    } for s in subs]

    # Rozmowy z AI
    convs = (await session.execute(
        select(Conversation).where(Conversation.user_id == user.id)
        .order_by(Conversation.created_at)
    )).scalars().all()
    conversations = []
    for conv in convs:
        msgs = (await session.execute(
            select(ChatMessage).where(ChatMessage.conversation_id == conv.id)
            .order_by(ChatMessage.created_at)
        )).scalars().all()
        conversations.append({
            "title": conv.title,
            "agent": conv.agent_name,
            "created_at": _iso(conv.created_at),
            "messages": [{
                "role": m.role,
                "content": m.content,
                "agent": m.agent_name,
                "created_at": _iso(m.created_at),
            } for m in msgs],
        })

    # Zgłoszenia (autorstwa użytkownika — po koncie lub e-mailu)
    reps = (await session.execute(
        select(Report).where(
            or_(Report.user_id == user.id, Report.author_email == user.email)
        ).order_by(Report.created_at)
    )).scalars().all()
    reports = [{
        "title": r.title,
        "description": r.description,
        "category": r.category,
        "status": r.status,
        "address": r.address,
        "location_name": r.location_name,
        "author_name": r.author_name,
        "author_email": r.author_email,
        "author_phone": r.author_phone,
        "image_url": r.image_url,
        "created_at": _iso(r.created_at),
    } for r in reps]

    # Powiadomienia push
    pushes = (await session.execute(
        select(PushSubscription).where(
            or_(PushSubscription.user_id == user.id, PushSubscription.email == user.email)
        )
    )).scalars().all()
    push_subscriptions = [{
        "endpoint": p.endpoint,
        "categories": p.categories,
        "active": p.active,
        "user_agent": p.user_agent,
        "created_at": _iso(p.created_at),
    } for p in pushes]

    # Newsletter
    nl = (await session.execute(
        select(NewsletterSubscriber).where(NewsletterSubscriber.email == user.email)
    )).scalar_one_or_none()
    newsletter = {
        "subscribed": nl is not None and nl.status == "active",
        "frequency": nl.frequency if nl else None,
        "confirmed_at": _iso(nl.confirmed_at) if nl else None,
        "emails_sent": nl.emails_sent if nl else 0,
    } if nl else {"subscribed": False}

    # Zagregowane użycie AI (telemetria powiązana z kontem)
    usage = (await session.execute(
        select(
            func.count(APICostLog.id),
            func.coalesce(func.sum(APICostLog.tokens_input + APICostLog.tokens_output), 0),
        ).where(APICostLog.user_id == user.id)
    )).one()
    ai_usage = {"total_requests": usage[0], "total_tokens": int(usage[1])}

    return {
        "format": "RODO art. 15/20 data export",
        "service": "rybnolive.pl",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "profile": profile,
        "subscriptions": subscriptions,
        "conversations": conversations,
        "reports": reports,
        "push_subscriptions": push_subscriptions,
        "newsletter": newsletter,
        "ai_usage": ai_usage,
    }


async def delete_user_account(session: AsyncSession, user: User) -> None:
    """
    Realne usunięcie danych (art. 17):
    - kasuje rozmowy z AI, subskrypcje push i wpis newslettera,
    - anonimizuje zgłoszenia (treść zostaje — dane autora znikają),
    - anonimizuje rekord users (subscriptions/referrals zostają dla rozliczeń).
    """
    user_email = user.email

    # 1. Rozmowy z AI + wiadomości
    conv_ids = (await session.execute(
        select(Conversation.id).where(Conversation.user_id == user.id)
    )).scalars().all()
    if conv_ids:
        await session.execute(
            delete(ChatMessage).where(ChatMessage.conversation_id.in_(conv_ids))
        )
        await session.execute(
            delete(Conversation).where(Conversation.id.in_(conv_ids))
        )

    # 2. Zgłoszenia — anonimizacja autora (treść zgłoszenia zostaje)
    await session.execute(
        update(Report)
        .where(or_(Report.user_id == user.id, Report.author_email == user_email))
        .values(user_id=None, author_name=None, author_email=None, author_phone=None)
    )

    # 3. Subskrypcje push
    await session.execute(
        delete(PushSubscription).where(
            or_(PushSubscription.user_id == user.id, PushSubscription.email == user_email)
        )
    )

    # 4. Newsletter
    await session.execute(
        delete(NewsletterSubscriber).where(NewsletterSubscriber.email == user_email)
    )

    # 5. Wizytówki firm — kasowane RAZEM z kontem.
    #
    # Podstawą prawną publikacji telefonu, adresu e-mail i godzin otwarcia jest
    # ZGODA właściciela wyrażona przy przejęciu wizytówki. Konto znika, więc znika
    # zgoda — a bez niej kontakt nie może zostać w katalogu. Do 12.08.2026 nie
    # kasowaliśmy tych wierszy wcale: wizytówka zostawała „przejęta" przez konto,
    # które już nie istniało, z danymi kontaktowymi wystawionymi publicznie,
    # a firma była zablokowana przed ponownym przejęciem przez kogokolwiek.
    #
    # Ogłoszenia idą pierwsze, bo wskazują na tę samą firmę i po skasowaniu
    # profilu zostałyby w tablicy jako reklama bez właściciela.
    business_ids = (await session.execute(
        select(BusinessProfile.business_id).where(BusinessProfile.user_id == user.id)
    )).scalars().all()
    if business_ids:
        await session.execute(
            delete(BusinessAnnouncement).where(
                BusinessAnnouncement.business_id.in_(business_ids)
            )
        )
        await session.execute(
            delete(BusinessProfile).where(BusinessProfile.user_id == user.id)
        )

    # 6. Anonimizacja rekordu users (FK z subscriptions/referrals pozostaje spójne)
    user.email = f"usuniete-{user.id}@anonimizacja.rybnolive.pl"
    user.full_name = "Konto usunięte"
    user.password_hash = "!deleted!" + secrets.token_hex(24)
    user.location = ""
    user.preferences = {}
    user.is_active = False
    user.email_verified = False
    user.consent_marketing = False
    user.referral_code = None
    user.trial_ends_at = None
    session.add(user)

    await session.commit()
    logger.info(f"DSAR delete: user {user.id} anonymized, artifacts purged "
                f"({len(conv_ids)} conversations, {len(business_ids)} wizytówek)")


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None
