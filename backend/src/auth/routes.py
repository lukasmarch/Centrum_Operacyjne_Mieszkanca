"""
Authentication routes: register, login, logout, refresh
"""

import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import get_session, User
from src.database.schema import Referral, UserTier
from src.config import settings
from src.auth.dependencies import get_current_active_user
from .jwt import (
    get_password_hash, verify_password,
    create_access_token, create_refresh_token, verify_token
)
from .schemas import (
    UserCreate, UserLogin, UserResponse, Token, AuthResponse,
    MessageResponse, RefreshTokenRequest
)

# Cookie security: False for localhost (HTTP), True for production (HTTPS)
COOKIE_SECURE = not settings.APP_URL.startswith("http://localhost")

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
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
    """
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

    # Sprawdź polecającego (referral)
    referrer = None
    if user_data.referral_code:
        ref_result = await session.execute(
            select(User).where(User.referral_code == user_data.referral_code)
        )
        referrer = ref_result.scalar_one_or_none()

    # Create new user z 7-dniowym triałem Premium
    trial_ends = datetime.utcnow() + timedelta(days=7)
    new_user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        location=user_data.location,
        tier=UserTier.PREMIUM.value,         # Trial Premium od razu
        trial_ends_at=trial_ends,
        referral_code=secrets.token_hex(4),  # 8-znakowy unikalny kod
        referred_by=referrer.id if referrer else None,
        created_at=datetime.utcnow()
    )

    session.add(new_user)
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

    # Generate tokens
    token_data = {
        "sub": new_user.email,
        "user_id": new_user.id,
        "tier": new_user.tier
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Set cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,  # Set to False for localhost development
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

    return AuthResponse(
        user=UserResponse.model_validate(new_user),
        tokens=Token(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    credentials: UserLogin,
    response: Response,
    session: AsyncSession = Depends(get_session)
):
    """
    Login with email and password.

    Returns JWT tokens for authentication.
    """
    # Find user
    result = await session.execute(
        select(User).where(User.email == credentials.email)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    # Update last login
    user.last_login = datetime.utcnow()
    await session.commit()
    await session.refresh(user)

    # Generate tokens
    token_data = {
        "sub": user.email,
        "user_id": user.id,
        "tier": user.tier
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Set cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
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

    return AuthResponse(
        user=UserResponse.model_validate(user),
        tokens=Token(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    )


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
    # Verify refresh token
    payload = verify_token(refresh_request.refresh_token, token_type="refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    # Get user
    user_email = payload.get("sub")
    result = await session.execute(
        select(User).where(User.email == user_email)
    )
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Generate new tokens
    token_data = {
        "sub": user.email,
        "user_id": user.id,
        "tier": user.tier
    }
    access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    # Update cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    )

    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


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
