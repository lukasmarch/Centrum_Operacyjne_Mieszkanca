"""
JWT Token utilities for authentication
"""

from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext

from src.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token

    Args:
        data: Payload data (should include 'sub' with user email/id)
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({
        "exp": expire,
        "type": "access"
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )

    return encoded_jwt


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token (longer lived)

    Args:
        data: Payload data (should include 'sub' with user email/id)
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )

    to_encode.update({
        "exp": expire,
        "type": "refresh"
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )

    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    """
    Verify and decode a JWT token

    Args:
        token: JWT token string
        token_type: Expected token type ("access" or "refresh")

    Returns:
        Decoded payload dict if valid, None if invalid

    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )

        # Check token type
        if payload.get("type") != token_type:
            return None

        return payload

    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Sesja związana z hasłem i reset hasła (audyt 11.10.2026, F-028)
#
# Do 11.10.2026 zmiana hasła nie kończyła żadnej sesji: token logowania (8 h)
# i odświeżania (7 dni) działały dalej, więc ktoś, kto przejął sesję, zostawał
# w środku także po tym, jak właściciel zmienił hasło. Resetu hasła nie było wcale.
#
# Zamiast tabeli sesji — ODCISK hasła w tokenie (`pwv`): HMAC z bieżącego
# skrótu hasła. Nowe hasło = nowy skrót (bcrypt ma sól, więc nawet to samo hasło
# daje inny) = wszystkie wcześniejsze tokeny przestają pasować. Ten sam odcisk
# czyni token resetu JEDNORAZOWYM: po ustawieniu hasła link sam się unieważnia.
# ---------------------------------------------------------------------------
import hashlib
import hmac

PASSWORD_RESET_TTL = timedelta(hours=1)


def password_fingerprint(password_hash: str) -> str:
    """Odcisk bieżącego hasła — nie da się z niego odtworzyć skrótu ani hasła."""
    return hmac.new(
        settings.JWT_SECRET.encode(), password_hash.encode(), hashlib.sha256
    ).hexdigest()[:16]


def session_claims(user) -> dict:
    """Zawartość tokenów logowania i odświeżania dla konta."""
    return {
        "sub": user.email,
        "user_id": user.id,
        "tier": user.tier,
        "pwv": password_fingerprint(user.password_hash),
    }


def token_matches_password(payload: dict, user) -> bool:
    """Czy token został wydany dla BIEŻĄCEGO hasła konta.

    ⚠️ Token bez `pwv` (wydany przed 11.10.2026) przechodzi — inaczej wdrożenie
    wylogowałoby wszystkich naraz. Wygasa sam, najpóźniej po 7 dniach.
    """
    pwv = payload.get("pwv")
    if pwv is None:
        return True
    return hmac.compare_digest(pwv, password_fingerprint(user.password_hash))


def create_password_reset_token(user, now: Optional[datetime] = None) -> str:
    now = now or datetime.utcnow()
    return jwt.encode(
        {
            "sub": str(user.id),
            "type": "password_reset",
            "pwv": password_fingerprint(user.password_hash),
            "exp": now + PASSWORD_RESET_TTL,
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def read_password_reset_token(token: str) -> Optional[dict]:
    """Treść tokenu resetu albo None (zły podpis, wygasły, inny typ).
    Zgodność z bieżącym hasłem sprawdza wołający — wymaga wiersza konta."""
    payload = verify_token(token, token_type="password_reset")
    if not payload or not payload.get("pwv") or not str(payload.get("sub", "")).isdigit():
        return None
    return payload
