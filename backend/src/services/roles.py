"""
Role z zakresem — jedno miejsce na to, kim jest konto i co mu wolno.

Rola jest warstwą NAD kontem (`user_roles`), a nie rodzajem konta. Rejestracja
jest jedna dla wszystkich; rolę dokleja zaproszenie albo decyzja admina.
Dzięki temu sołtys jest też zwykłym mieszkańcem, a koniec kadencji odbiera
rolę, nie konto.

Definicje ról (`ROLES`) mieszkają w KODZIE, nie w bazie: to, co wolno sołtysowi,
jest decyzją projektową, a nie daną do edycji. Nowa rola (urzędnik, redaktor)
to jeden wpis w słowniku — reszta mechanizmu (zaproszenia, odwołanie, DSAR)
działa bez zmian.

Firmy świadomie zostają przy `business_profiles`: tamten przepływ działa i jest
spięty z płatnościami P24. Admin zostaje przy `users.is_admin`.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import settings
from src.database.schema import (
    RoleInvitation, Subscription, SubscriptionStatus, User, UserRole, UserTier,
)
from src.services.gmina_facts import SOLECTWA

VERIFIED = "verified"
PENDING = "pending"
REVOKED = "revoked"

# Ważność linku z zaproszenia. Dwa tygodnie: sołtys dostaje link po rozmowie
# telefonicznej i ma czas usiąść do komputera, ale link nie wisi bez końca.
INVITATION_DAYS = 14

# Uprawnienia — nazwy czynności, o które pytają endpointy
PERM_SOLECTWO_POST = "solectwo.post"


@dataclass(frozen=True)
class RoleDef:
    label: str
    scope_label: str
    scopes: tuple[str, ...]
    # Podpis przy publikacji — „Sołtys sołectwa Żabiny"
    signature: str
    permissions: frozenset[str] = field(default_factory=frozenset)
    # Plan Premium bez terminu, dopóki rola trwa (decyzja Łukasza z 27.09:
    # sołtys tak, urzędnik na razie nic)
    grants_premium: bool = False


ROLES: dict[str, RoleDef] = {
    "soltys": RoleDef(
        label="Sołtys",
        scope_label="sołectwo",
        scopes=SOLECTWA,
        signature="Sołtys sołectwa {scope}",
        permissions=frozenset({PERM_SOLECTWO_POST}),
        grants_premium=True,
    ),
}


def role_def(role: str) -> RoleDef:
    definition = ROLES.get(role)
    if definition is None:
        raise HTTPException(status_code=400, detail=f"Nieznana rola: {role}")
    return definition


def validate_scope(role: str, scope: str) -> str:
    """Zakres musi pochodzić z zamkniętej listy roli — literówka w nazwie
    sołectwa dałaby sołtysa czegoś, czego nie ma."""
    definition = role_def(role)
    if scope not in definition.scopes:
        raise HTTPException(
            status_code=400,
            detail=f"Nieznany zakres „{scope}” dla roli {definition.label}",
        )
    return scope


def signed_as(role: str, scope: str) -> str:
    return role_def(role).signature.format(scope=scope)


def invitation_url(token: str) -> str:
    return f"{settings.APP_URL.rstrip('/')}/zaproszenie?kod={token}"


async def live_roles(session: AsyncSession, user_id: int) -> list[UserRole]:
    rows = await session.execute(
        select(UserRole)
        .where(UserRole.user_id == user_id, UserRole.status == VERIFIED)
        .order_by(UserRole.created_at)
    )
    return list(rows.scalars().all())


async def has_premium_role(session: AsyncSession, user_id: int) -> bool:
    """Czy konto ma Premium z tytułu roli. Pytają o to joby wygaszania planu —
    bez tego wygasła płatna subskrypcja zdjęłaby Premium aktywnemu sołtysowi."""
    return any(ROLES.get(r.role) and ROLES[r.role].grants_premium
               for r in await live_roles(session, user_id))


async def role_with_permission(
    session: AsyncSession, user: User, permission: str,
) -> list[UserRole]:
    return [
        r for r in await live_roles(session, user.id)
        if r.role in ROLES and permission in ROLES[r.role].permissions
    ]


def _apply_premium(user: User) -> None:
    """Premium bez terminu: `trial_ends_at = None`, więc job triala konta nie
    widzi. Plan „business" jest wyższy — nie schodzimy z niego."""
    if user.tier != UserTier.BUSINESS.value:
        user.tier = UserTier.PREMIUM.value
    user.trial_ends_at = None


async def grant_role(
    session: AsyncSession,
    user: User,
    role: str,
    scope: str,
    method: str,
    verified_by: Optional[str] = None,
) -> tuple[UserRole, bool]:
    """Nadaj zweryfikowaną rolę. Zwraca (rola, czy_nowa).

    Idempotentna: druga próba nadania tej samej roli zwraca istniejący wiersz
    (dwukrotne kliknięcie w link, admin i zaproszenie naraz).
    """
    validate_scope(role, scope)
    existing = (await session.execute(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role == role,
            UserRole.scope == scope,
            UserRole.status != REVOKED,
        )
    )).scalar_one_or_none()

    now = datetime.utcnow()
    if existing:
        if existing.status != VERIFIED:
            existing.status = VERIFIED
            existing.verified_at = now
            existing.verified_by = verified_by
            session.add(existing)
            if ROLES[role].grants_premium:
                _apply_premium(user)
                session.add(user)
            return existing, True
        return existing, False

    row = UserRole(
        user_id=user.id, role=role, scope=scope, status=VERIFIED,
        method=method, verified_by=verified_by, verified_at=now,
    )
    session.add(row)
    if ROLES[role].grants_premium:
        _apply_premium(user)
        session.add(user)
    await session.flush()
    return row, True


async def revoke_role(session: AsyncSession, row: UserRole) -> None:
    """Odbierz rolę. Premium z tytułu roli znika, chyba że konto ma inną rolę
    z Premium albo opłaconą subskrypcję."""
    row.status = REVOKED
    row.revoked_at = datetime.utcnow()
    session.add(row)
    await session.flush()

    definition = ROLES.get(row.role)
    if not (definition and definition.grants_premium):
        return
    if await has_premium_role(session, row.user_id):
        return
    paid = (await session.execute(
        select(Subscription).where(
            Subscription.user_id == row.user_id,
            Subscription.status == SubscriptionStatus.ACTIVE.value,
            Subscription.expires_at > datetime.utcnow(),
        )
    )).scalars().first()
    if paid:
        return
    user = await session.get(User, row.user_id)
    if user and user.tier == UserTier.PREMIUM.value and not user.trial_ends_at:
        user.tier = UserTier.FREE.value
        session.add(user)


async def create_invitation(
    session: AsyncSession,
    role: str,
    scope: str,
    invitee_label: Optional[str],
    created_by: Optional[str],
) -> RoleInvitation:
    validate_scope(role, scope)
    invitation = RoleInvitation(
        token=secrets.token_urlsafe(24),
        role=role,
        scope=scope,
        invitee_label=(invitee_label or "").strip() or None,
        created_by=created_by,
        expires_at=datetime.utcnow() + timedelta(days=INVITATION_DAYS),
    )
    session.add(invitation)
    await session.flush()
    return invitation


def invitation_state(invitation: RoleInvitation, now: Optional[datetime] = None) -> str:
    """`active` / `used` / `revoked` / `expired` — jedno źródło odpowiedzi
    dla strony zaproszenia i dla listy admina."""
    now = now or datetime.utcnow()
    if invitation.used_at:
        return "used"
    if invitation.revoked_at:
        return "revoked"
    if invitation.expires_at <= now:
        return "expired"
    return "active"


async def find_invitation(session: AsyncSession, token: str) -> Optional[RoleInvitation]:
    if not token:
        return None
    return (await session.execute(
        select(RoleInvitation).where(RoleInvitation.token == token)
    )).scalar_one_or_none()


INVITATION_ERRORS = {
    "used": "To zaproszenie zostało już wykorzystane.",
    "revoked": "To zaproszenie zostało wycofane.",
    "expired": "To zaproszenie wygasło — poproś o nowe.",
}


async def accept_invitation(
    session: AsyncSession, invitation: RoleInvitation, user: User,
) -> tuple[UserRole, bool]:
    """Przyjęcie zaproszenia = zweryfikowana rola. Weryfikacja odbyła się
    w rozmowie, po której admin wręczył link."""
    state = invitation_state(invitation)
    if state != "active":
        raise HTTPException(status_code=410, detail=INVITATION_ERRORS[state])

    row, created = await grant_role(
        session, user, invitation.role, invitation.scope,
        method="invitation", verified_by=invitation.created_by,
    )
    invitation.used_at = datetime.utcnow()
    invitation.used_by_user_id = user.id
    session.add(invitation)
    return row, created
