"""
FastAPI dependencies for authentication
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.database import get_session, User, UserTier
from .jwt import verify_token

# Bearer token scheme
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    access_token: Optional[str] = Cookie(default=None),
    session: AsyncSession = Depends(get_session)
) -> User:
    """
    Get the current authenticated user from JWT token.

    Token can be provided either:
    - In Authorization header (Bearer token)
    - In 'access_token' cookie

    Raises:
        HTTPException 401: If token is missing or invalid
        HTTPException 401: If user not found
    """
    # Get token from header or cookie
    token = None
    if credentials:
        token = credentials.credentials
    elif access_token:
        token = access_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify token
    payload = verify_token(token, token_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user_email = payload.get("sub")
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await session.execute(
        select(User).where(User.email == user_email)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user and verify they are active.

    Raises:
        HTTPException 403: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    return current_user


async def get_premium_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current user and verify they have Premium or Business tier.

    Use this dependency to protect premium-only endpoints.

    Raises:
        HTTPException 403: If user doesn't have premium access
    """
    if current_user.tier not in [UserTier.PREMIUM.value, UserTier.BUSINESS.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium subscription required for this feature"
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    access_token: Optional[str] = Cookie(default=None),
    session: AsyncSession = Depends(get_session)
) -> Optional[User]:
    """
    Optionally get current user if authenticated.

    Returns None if no valid token provided (doesn't raise exception).
    Useful for endpoints that have different behavior for auth/non-auth users.
    """
    token = None
    if credentials:
        token = credentials.credentials
    elif access_token:
        token = access_token

    if not token:
        return None

    payload = verify_token(token, token_type="access")
    if not payload:
        return None

    user_email = payload.get("sub")
    if not user_email:
        return None

    result = await session.execute(
        select(User).where(User.email == user_email)
    )
    return result.scalar_one_or_none()
