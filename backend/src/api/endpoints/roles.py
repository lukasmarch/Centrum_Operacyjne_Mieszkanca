"""
Role z zakresem: zaproszenia, przyjęcie roli, lista i odwołanie (admin).

Rejestracja jest JEDNA dla wszystkich (`/api/auth/register`). Rolę dokleja
zaproszenie: Łukasz dzwoni do sołtysa, generuje link dla jego sołectwa i wręcza
go SMS-em albo osobiście. Kto kliknie link, zakłada konto (albo loguje się na
istniejące) i od razu jest zweryfikowanym sołtysem — weryfikacja odbyła się
w rozmowie. Logika ról: `services/roles.py`.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import select

from src.auth.dependencies import get_admin_user, get_current_active_user
from src.database.connection import async_session
from src.database.schema import RoleInvitation, User, UserRole
from src.services import roles as role_service
from src.utils.logger import setup_logger

logger = setup_logger("Roles")

router = APIRouter(prefix="/api/roles", tags=["roles"])


class RoleOut(BaseModel):
    id: int
    role: str
    label: str
    scope: str
    scope_label: str
    signed_as: str
    permissions: List[str]
    verified_at: Optional[datetime] = None


def _role_out(row: UserRole) -> RoleOut:
    definition = role_service.ROLES.get(row.role)
    return RoleOut(
        id=row.id,
        role=row.role,
        label=definition.label if definition else row.role,
        scope=row.scope,
        scope_label=definition.scope_label if definition else "",
        signed_as=role_service.signed_as(row.role, row.scope) if definition else row.role,
        permissions=sorted(definition.permissions) if definition else [],
        verified_at=row.verified_at,
    )


async def send_role_welcome(user_id: int, role_id: int) -> None:
    """Instrukcja dla nowej roli — w tle, po zapisie. Rola ma zostać nadana także
    wtedy, gdy poczta leży (ta sama zasada co przy powitaniu po rejestracji)."""
    try:
        from src.newsletter.email_service import EmailService
        from src.newsletter.subscriptions import ensure_subscription

        async with async_session() as session:
            user = await session.get(User, user_id)
            row = await session.get(UserRole, role_id)
            if not user or not row or row.role != "soltys":
                return
            subscriber = await ensure_subscription(session, user)
            await session.commit()
            token = subscriber.unsubscribe_token if subscriber else None
            await EmailService().send_soltys_welcome(
                to_email=user.email,
                recipient_name=user.full_name,
                signed_as=role_service.signed_as(row.role, row.scope),
                unsubscribe_token=token,
            )
    except Exception as exc:  # noqa: BLE001 — rola już nadana, mail jest dodatkiem
        logger.error(f"Instrukcja roli {role_id} dla konta {user_id} nie wyszła: {exc}")


# ── Konto ────────────────────────────────────────────────────────────────

@router.get("/me", response_model=List[RoleOut])
async def my_roles(user=Depends(get_current_active_user)):
    async with async_session() as session:
        return [_role_out(r) for r in await role_service.live_roles(session, user.id)]


class InvitationPublic(BaseModel):
    state: str
    role: str
    role_label: str
    scope: str
    signed_as: str
    expires_at: datetime
    message: Optional[str] = None


@router.get("/invitation/{token}", response_model=InvitationPublic)
async def invitation_details(token: str):
    """Strona zaproszenia pokazuje, CZYM się stanie przyjmujący — zanim założy
    konto. Bez danych osobowych: `invitee_label` jest tylko dla admina."""
    async with async_session() as session:
        invitation = await role_service.find_invitation(session, token)
    if not invitation or invitation.role not in role_service.ROLES:
        raise HTTPException(status_code=404, detail="Nie znaleziono zaproszenia")
    state = role_service.invitation_state(invitation)
    return InvitationPublic(
        state=state,
        role=invitation.role,
        role_label=role_service.ROLES[invitation.role].label,
        scope=invitation.scope,
        signed_as=role_service.signed_as(invitation.role, invitation.scope),
        expires_at=invitation.expires_at,
        message=role_service.INVITATION_ERRORS.get(state),
    )


@router.post("/invitation/{token}/accept", response_model=RoleOut)
async def accept_invitation(
    token: str,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_active_user),
):
    """Przyjęcie zaproszenia na ISTNIEJĄCYM koncie. Nowe konto przyjmuje je
    w jednym kroku z rejestracją (`invite_token` w `/api/auth/register`)."""
    async with async_session() as session:
        invitation = await role_service.find_invitation(session, token)
        if not invitation:
            raise HTTPException(status_code=404, detail="Nie znaleziono zaproszenia")
        account = await session.get(User, user.id)
        row, created = await role_service.accept_invitation(session, invitation, account)
        await session.commit()
        await session.refresh(row)
        out = _role_out(row)
    if created:
        background_tasks.add_task(send_role_welcome, user.id, row.id)
    logger.info(f"Konto {user.id} przyjęło zaproszenie → {out.signed_as}")
    return out


# ── Admin ────────────────────────────────────────────────────────────────

class RoleDefinitionOut(BaseModel):
    role: str
    label: str
    scope_label: str
    scopes: List[str]
    grants_premium: bool


@router.get("/definitions", response_model=List[RoleDefinitionOut])
async def role_definitions(admin=Depends(get_admin_user)):
    return [
        RoleDefinitionOut(
            role=key, label=d.label, scope_label=d.scope_label,
            scopes=list(d.scopes), grants_premium=d.grants_premium,
        )
        for key, d in role_service.ROLES.items()
    ]


class AdminRoleOut(RoleOut):
    user_id: int
    user_email: str
    user_name: str
    method: str
    status: str


@router.get("/admin/list", response_model=List[AdminRoleOut])
async def list_roles(admin=Depends(get_admin_user)):
    async with async_session() as session:
        rows = (await session.execute(
            select(UserRole, User)
            .join(User, User.id == UserRole.user_id)
            .where(UserRole.status != role_service.REVOKED)
            .order_by(UserRole.role, UserRole.scope)
        )).all()
    return [
        AdminRoleOut(
            **_role_out(r).model_dump(),
            user_id=u.id, user_email=u.email, user_name=u.full_name,
            method=r.method, status=r.status,
        )
        for r, u in rows
    ]


@router.post("/admin/roles/{role_id}/revoke")
async def revoke_role(role_id: int, admin=Depends(get_admin_user)):
    async with async_session() as session:
        row = await session.get(UserRole, role_id)
        if not row or row.status == role_service.REVOKED:
            raise HTTPException(status_code=404, detail="Nie znaleziono roli")
        await role_service.revoke_role(session, row)
        await session.commit()
    logger.info(f"Admin {admin.email} odebrał rolę {role_id}")
    return {"success": True}


class InvitationCreate(BaseModel):
    role: str = "soltys"
    scope: str
    invitee_label: Optional[str] = Field(default=None, max_length=100)


class InvitationAdminOut(BaseModel):
    id: int
    role: str
    scope: str
    signed_as: str
    invitee_label: Optional[str]
    url: str
    state: str
    created_at: datetime
    expires_at: datetime
    used_at: Optional[datetime]
    used_by_email: Optional[str]


def _invitation_out(inv: RoleInvitation, used_by_email: Optional[str] = None) -> InvitationAdminOut:
    return InvitationAdminOut(
        id=inv.id,
        role=inv.role,
        scope=inv.scope,
        signed_as=role_service.signed_as(inv.role, inv.scope),
        invitee_label=inv.invitee_label,
        url=role_service.invitation_url(inv.token),
        state=role_service.invitation_state(inv),
        created_at=inv.created_at,
        expires_at=inv.expires_at,
        used_at=inv.used_at,
        used_by_email=used_by_email,
    )


@router.get("/admin/invitations", response_model=List[InvitationAdminOut])
async def list_invitations(admin=Depends(get_admin_user)):
    async with async_session() as session:
        rows = (await session.execute(
            select(RoleInvitation, User.email)
            .join(User, User.id == RoleInvitation.used_by_user_id, isouter=True)
            .order_by(RoleInvitation.created_at.desc())
            .limit(100)
        )).all()
    return [_invitation_out(inv, email) for inv, email in rows]


@router.post("/admin/invitations", response_model=InvitationAdminOut, status_code=201)
async def create_invitation(body: InvitationCreate, admin=Depends(get_admin_user)):
    async with async_session() as session:
        inv = await role_service.create_invitation(
            session, body.role, body.scope, body.invitee_label, admin.email,
        )
        await session.commit()
        await session.refresh(inv)
    logger.info(f"Admin {admin.email} wystawił zaproszenie {inv.role}/{inv.scope}")
    return _invitation_out(inv)


@router.delete("/admin/invitations/{invitation_id}")
async def revoke_invitation(invitation_id: int, admin=Depends(get_admin_user)):
    async with async_session() as session:
        inv = await session.get(RoleInvitation, invitation_id)
        if not inv:
            raise HTTPException(status_code=404, detail="Nie znaleziono zaproszenia")
        if inv.used_at:
            raise HTTPException(
                status_code=409,
                detail="Zaproszenie zostało już przyjęte — odbierz rolę na liście ról",
            )
        inv.revoked_at = datetime.utcnow()
        session.add(inv)
        await session.commit()
    return {"success": True}
