"""
Authentication routes: register, login, logout, refresh
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import get_session, User
from src.database.schema import Referral, SiteEvent, UserTier
from src.config import settings
from src.auth.dependencies import get_current_active_user
from src.newsletter.subscriptions import ensure_subscription
from src.services import roles as role_service
from src.services.rate_limit import DailyLimit, client_key
from .jwt import (
    get_password_hash, verify_password,
    create_access_token, create_refresh_token, verify_token,
    session_claims, token_matches_password,
    create_password_reset_token, read_password_reset_token, password_fingerprint,
)
from .schemas import (
    UserCreate, UserLogin, UserResponse, Token, AuthResponse,
    MessageResponse, RefreshTokenRequest, ForgotPasswordRequest, ResetPasswordRequest,
)

# Cookie security: False for localhost (HTTP), True for production (HTTPS)
COOKIE_SECURE = not settings.APP_URL.startswith("http://localhost")

# Wersja dokumentów prawnych akceptowanych przy rejestracji.
# Podbij przy każdej istotnej zmianie regulaminu/polityki prywatności.
PRIVACY_POLICY_VERSION = "2026-09-29"  # = PRIVACY_VERSION i TERMS_VERSION we froncie

logger = logging.getLogger("Auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


# Limity kont (audyt 11.10.2026, F-028). Liczniki w pamięci, doba lokalna —
# ta sama klasa co Whisper i Zgłoszenia 24 (`services/rate_limit`).
# ⚠️ Nieudane logowania liczymy per para IP + adres i per IP, NIGDY per sam adres:
# licznik na adres pozwoliłby obcemu zablokować komuś konto złymi hasłami.
LOGIN_FAILS_PAIR = DailyLimit(
    "Logowanie (IP+adres)", per_key=10, total=100_000,
    message="Zbyt wiele nieudanych prób logowania. Spróbuj jutro albo ustaw nowe hasło.",
)
LOGIN_FAILS_IP = DailyLimit(
    "Logowanie (IP)", per_key=50, total=100_000,
    message="Zbyt wiele nieudanych prób logowania. Spróbuj jutro albo ustaw nowe hasło.",
)
RESET_BY_IP = DailyLimit(
    "Reset hasła (IP)", per_key=5, total=100,
    message="Zbyt wiele próśb o nowe hasło. Spróbuj jutro.",
)
RESET_BY_EMAIL = DailyLimit(
    "Reset hasła (adres)", per_key=3, total=100,
    message="Zbyt wiele próśb o nowe hasło. Spróbuj jutro.",
)

# Jedna odpowiedź dla każdego adresu — nie zdradzamy, czy konto istnieje
RESET_REQUESTED_MESSAGE = (
    "Jeśli to konto istnieje, wysłaliśmy na nie link do ustawienia nowego hasła. "
    "Link działa przez godzinę."
)


def _issue_session(user: User, response: Response) -> Token:
    """Tokeny i ciasteczka sesji — jedno miejsce dla rejestracji, logowania,
    odświeżania i ustawienia nowego hasła. Tokeny niosą odcisk hasła (`pwv`),
    więc zmiana hasła kończy wszystkie wcześniejsze sesje."""
    claims = session_claims(user)
    access_token = create_access_token(claims)
    refresh_token = create_refresh_token(claims)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,  # False dla localhost (HTTP)
        samesite="lax",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


def _login_pair_key(request: Request, email: str) -> str:
    return client_key(request) + ":" + email.strip().lower()


async def _send_welcome_email(
    email: str,
    full_name: Optional[str],
    trial_ends_at: Optional[datetime],
    unsubscribe_token: str,
) -> None:
    """Powitanie leci w tle — rejestracja ma się udać także wtedy, gdy Resend milczy."""
    try:
        from src.newsletter.email_service import EmailService
        await EmailService().send_welcome_email(
            to_email=email,
            recipient_name=full_name,
            trial_ends_at=trial_ends_at,
            unsubscribe_token=unsubscribe_token,
        )
    except Exception as exc:  # noqa: BLE001 — konto już istnieje, mail jest dodatkiem
        logger.error(f"Nie udało się wysłać powitania do {email}: {exc}")


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    background_tasks: BackgroundTasks,
    user_data: UserCreate,
    response: Response,
    session: AsyncSession = Depends(get_session)
):
    """
    Register a new user account.

    - **email**: Valid email address (must be unique)
    - **password**: Min 8 chars, must contain uppercase and digit
    - **full_name**: User's display name
    - **location**: User's town (default: Rybno)
    - **consent_terms**: required acceptance of Terms of Service and Privacy Policy
    """
    # Akceptacja regulaminu jest warunkiem zawarcia umowy (art. 8 UŚUDE, RODO art. 6 ust. 1 lit. b)
    if not user_data.consent_terms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rejestracja wymaga akceptacji Regulaminu i Polityki prywatności"
        )

    # Check if email already exists
    result = await session.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Zaproszenie sprawdzamy PRZED założeniem konta: nieważny link ma dać
    # komunikat, a nie konto zwykłego mieszkańca, które sołtys uzna za swoje.
    invitation = None
    if user_data.invite_token:
        invitation = await role_service.find_invitation(session, user_data.invite_token)
        if not invitation:
            raise HTTPException(status_code=404, detail="Nie znaleziono zaproszenia")
        state = role_service.invitation_state(invitation)
        if state != "active":
            raise HTTPException(status_code=410, detail=role_service.INVITATION_ERRORS[state])

    # Sprawdź polecającego (referral)
    referrer = None
    if user_data.referral_code:
        ref_result = await session.execute(
            select(User).where(User.referral_code == user_data.referral_code)
        )
        referrer = ref_result.scalar_one_or_none()

    # Create new user z 30-dniowym triałem Premium (bez karty — rekomendacja raportu 07.2026)
    trial_ends = datetime.utcnow() + timedelta(days=30)
    new_user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        location=user_data.location,
        tier=UserTier.PREMIUM.value,         # Trial Premium od razu
        trial_ends_at=trial_ends,
        referral_code=secrets.token_hex(4),  # 8-znakowy unikalny kod
        referred_by=referrer.id if referrer else None,
        consent_terms_at=datetime.utcnow(),
        consent_marketing=user_data.consent_marketing,
        consent_privacy_version=PRIVACY_POLICY_VERSION,
        # Skąd przyszedł ten człowiek. Zapisywane RAZ, przy zakładaniu konta —
        # `site_events` kasuje retencja po 180 dniach, a odpowiedź na „który post
        # dowiózł tego klienta" ma przeżyć dłużej niż log.
        acq_session_id=(user_data.acq.session_id if user_data.acq else None),
        acq_utm_campaign=(user_data.acq.utm_campaign if user_data.acq else None),
        acq_landing=(user_data.acq.landing if user_data.acq else None),
        acq_first_seen=(user_data.acq.first_seen if user_data.acq else None),
        created_at=datetime.utcnow()
    )

    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)

    # Zdarzenie w lejku. Dopisuje je SERWER, nie przeglądarka: z przeglądarki
    # `register_done` przyszłoby też od kogoś, kto konta nie założył.
    session.add(SiteEvent(
        session_id=new_user.acq_session_id,
        user_id=new_user.id,
        event="register_done",
        utm_campaign=new_user.acq_utm_campaign,
        path=new_user.acq_landing,
    ))
    await session.commit()

    # Rola z zaproszenia. Sołtys dostaje Premium bez terminu (`grant_role`
    # zeruje `trial_ends_at`), więc mail o 30-dniowym triale byłby nieprawdą —
    # zamiast niego idzie instrukcja dla sołtysa.
    granted_role = None
    if invitation:
        granted_role, _ = await role_service.accept_invitation(session, invitation, new_user)
        await session.commit()
        await session.refresh(new_user)

    # Jeśli jest polecający — zapisz referral i nagrodź +14 dni (jeśli polecający ma Premium)
    if referrer:
        referral = Referral(
            referrer_id=referrer.id,
            referred_id=new_user.id,
        )
        session.add(referral)
        # Nagrodź polecającego: +14 dni do trial lub extends subscription
        if referrer.trial_ends_at and referrer.trial_ends_at > datetime.utcnow():
            referrer.trial_ends_at = referrer.trial_ends_at + timedelta(days=14)
        else:
            referrer.trial_ends_at = datetime.utcnow() + timedelta(days=14)
        if referrer.tier == UserTier.FREE.value:
            referrer.tier = UserTier.PREMIUM.value
        referral.rewarded_at = datetime.utcnow()
        session.add(referrer)
        await session.commit()
        await session.refresh(new_user)

    # Newsletter: cennik obiecuje tygodniowy w planie darmowym i dzienny w Premium,
    # więc subskrypcja powstaje razem z kontem. Wcześniej trzeba było ją odkryć
    # samemu w profilu — pierwszy prawdziwy użytkownik nie dostał żadnego maila.
    subscriber = await ensure_subscription(session, new_user)
    if subscriber is not None:
        await session.commit()
        await session.refresh(subscriber)

        if granted_role is None:
            # Jedyny moment, w którym mówimy wprost, że Premium jest na 30 dni.
            background_tasks.add_task(
                _send_welcome_email,
                new_user.email,
                new_user.full_name,
                new_user.trial_ends_at,
                subscriber.unsubscribe_token,
            )

    # Instrukcja sołtysa to mail transakcyjny — idzie także do kogoś, kto kiedyś
    # wypisał się z newslettera (wtedy `subscriber` jest None)
    if granted_role is not None:
        from src.api.endpoints.roles import send_role_welcome
        background_tasks.add_task(send_role_welcome, new_user.id, granted_role.id)

    tokens = _issue_session(new_user, response)

    return AuthResponse(user=UserResponse.model_validate(new_user), tokens=tokens)


@router.post("/login", response_model=AuthResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session)
):
    """
    Login with email and password.

    Returns JWT tokens for authentication.
    """
    pair_key = _login_pair_key(request, credentials.email)
    ip_key = client_key(request)
    # Limit sprawdzamy PRZED hasłem — po wyczerpaniu nawet trafne hasło czeka do jutra,
    # inaczej limit nie zatrzymywałby zgadywania
    if LOGIN_FAILS_PAIR.used(pair_key) >= LOGIN_FAILS_PAIR.per_key:
        raise HTTPException(status_code=429, detail=LOGIN_FAILS_PAIR.message)
    if LOGIN_FAILS_IP.used(ip_key) >= LOGIN_FAILS_IP.per_key:
        raise HTTPException(status_code=429, detail=LOGIN_FAILS_IP.message)

    result = await session.execute(
        select(User).where(User.email == credentials.email)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.password_hash):
        LOGIN_FAILS_PAIR.count(pair_key)
        LOGIN_FAILS_IP.count(ip_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowy e-mail lub hasło"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="To konto jest nieaktywne"
        )

    # Update last login
    user.last_login = datetime.utcnow()
    await session.commit()
    await session.refresh(user)

    tokens = _issue_session(user, response)
    return AuthResponse(user=UserResponse.model_validate(user), tokens=tokens)


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response):
    """
    Logout user by clearing auth cookies.
    """
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")

    return MessageResponse(message="Successfully logged out")


@router.post("/refresh", response_model=Token)
async def refresh_tokens(
    refresh_request: RefreshTokenRequest,
    response: Response,
    session: AsyncSession = Depends(get_session)
):
    """
    Refresh access token using refresh token.
    """
    payload = verify_token(refresh_request.refresh_token, token_type="refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesja wygasła — zaloguj się ponownie"
        )

    result = await session.execute(
        select(User).where(User.email == payload.get("sub"))
    )
    user = result.scalar_one_or_none()

    # Token odświeżania sprzed zmiany hasła nie odnawia sesji — inaczej przejęta
    # sesja przeżyłaby zmianę hasła o kolejne 7 dni (F-028)
    if not user or not user.is_active or not token_matches_password(payload, user):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesja wygasła — zaloguj się ponownie"
        )

    return _issue_session(user, response)


async def _send_password_reset(email: str, full_name: Optional[str], reset_url: str) -> None:
    """Mail w tle — odpowiedź trasy nie może zależeć od tego, czy konto istnieje,
    a czas wysyłki przez Resend by to zdradzał."""
    try:
        from src.newsletter.email_service import EmailService
        await EmailService().send_password_reset(
            to_email=email, recipient_name=full_name, reset_url=reset_url,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Nie udało się wysłać linku resetu hasła: {exc}")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """Link do ustawienia nowego hasła (ważny 1 h, jednorazowy).

    Odpowiedź jest TA SAMA dla istniejącego i nieistniejącego adresu (F-028) —
    formularz nie może służyć do sprawdzania, kto ma u nas konto.
    """
    RESET_BY_IP.hit(client_key(request))
    RESET_BY_EMAIL.hit(data.email.strip().lower())

    result = await session.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if user is not None and user.is_active:
        token = create_password_reset_token(user)
        reset_url = f"{settings.APP_URL.rstrip('/')}/nowe-haslo?token={token}"
        background_tasks.add_task(_send_password_reset, user.email, user.full_name, reset_url)
        logger.info(f"Reset hasła: link wysłany do user_id={user.id}")

    return MessageResponse(message=RESET_REQUESTED_MESSAGE)


@router.post("/reset-password", response_model=AuthResponse)
async def reset_password(
    data: ResetPasswordRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """Nowe hasło z linku. Kończy wszystkie wcześniejsze sesje i loguje od razu."""
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Link wygasł albo został już użyty. Poproś o nowy.",
    )
    payload = read_password_reset_token(data.token)
    if payload is None:
        raise invalid

    user = await session.get(User, int(payload["sub"]))
    # Odcisk innego hasła = link już użyty (albo hasło zmieniono inną drogą)
    if user is None or not user.is_active or payload["pwv"] != password_fingerprint(user.password_hash):
        raise invalid

    user.password_hash = get_password_hash(data.new_password)
    await session.commit()
    await session.refresh(user)
    logger.info(f"Reset hasła: nowe hasło ustawione dla user_id={user.id}")

    tokens = _issue_session(user, response)
    return AuthResponse(user=UserResponse.model_validate(user), tokens=tokens)


@router.get("/referral")
async def get_referral_info(
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Pobierz swój kod referralny i statystyki.
    Link do polecania: {APP_URL}/register?ref={referral_code}
    """
    from sqlalchemy import func
    from src.database.schema import Referral

    # Generuj kod jeśli user go nie ma (legacy accounts)
    if not user.referral_code:
        import secrets
        user.referral_code = secrets.token_hex(4)
        await session.commit()
        await session.refresh(user)

    # Policz ile osób dołączyło przez ten kod
    count_result = await session.execute(
        select(func.count()).where(Referral.referrer_id == user.id)
    )
    referral_count = count_result.scalar() or 0

    referral_link = f"{settings.APP_URL}/register?ref={user.referral_code}"

    return {
        "referral_code": user.referral_code,
        "referral_link": referral_link,
        "referrals_count": referral_count,
        "reward_per_referral": "14 dni Premium dla Ciebie i osoby zaproszonej",
        "trial_ends_at": user.trial_ends_at,
    }
