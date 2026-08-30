"""
Pydantic schemas for authentication
"""

from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator
from src.database import UserTier


# ======================
# Request Schemas
# ======================

class Acquisition(BaseModel):
    """
    Skąd przyszedł ten, kto zakłada konto — z pierwszej wizyty zapamiętanej
    w przeglądarce (`localStorage.rl_acq`, patrz `frontend/src/services/analytics.ts`).

    Pole jest opcjonalne i nigdy nie może zablokować rejestracji: przeglądarka
    z wyczyszczoną pamięcią albo wejście prosto z adresu po prostu go nie przyśle.
    """
    session_id: Optional[str] = Field(default=None, max_length=36)
    utm_campaign: Optional[str] = Field(default=None, max_length=100)
    landing: Optional[str] = Field(default=None, max_length=200)
    first_seen: Optional[datetime] = None

    @field_validator("first_seen")
    @classmethod
    def strip_timezone(cls, v: Optional[datetime]) -> Optional[datetime]:
        """
        Przeglądarka wysyła `toISOString()`, czyli czas ZE STREFĄ („…Z”), a cały
        projekt trzyma naiwny UTC. Bez tego asyncpg odrzuca zapis do kolumny
        TIMESTAMP („can't subtract offset-naive and offset-aware datetimes”)
        i rejestracja kończy się błędem 500 — przy KAŻDYM nowym koncie.
        """
        if v is None or v.tzinfo is None:
            return v
        return v.astimezone(timezone.utc).replace(tzinfo=None)


class UserCreate(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    full_name: str = Field(min_length=2, max_length=100)
    location: str = Field(default="Rybno", max_length=100)
    referral_code: Optional[str] = Field(default=None, max_length=20)  # Kod polecającego
    consent_terms: bool = Field(default=False)      # akceptacja regulaminu + polityki prywatności (wymagana)
    consent_marketing: bool = Field(default=False)  # zgoda marketingowa (opcjonalna)
    acq: Optional[Acquisition] = None               # źródło wizyty (pomiar, nie warunek rejestracji)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Ensure password has minimum complexity"""
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


class PasswordChange(BaseModel):
    """Schema for password change"""
    current_password: str
    new_password: str = Field(min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v


class UserPreferences(BaseModel):
    """Schema for user preferences"""
    categories: Optional[List[str]] = None  # Preferred news categories
    notifications: Optional[dict] = None  # Notification settings
    newsletter_frequency: Optional[str] = None  # "none", "weekly", "daily"
    dashboard_layout: Optional[str] = None  # Dashboard layout preset ID


class UserUpdate(BaseModel):
    """Schema for updating user profile"""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    location: Optional[str] = Field(None, max_length=100)
    preferences: Optional[UserPreferences] = None


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request"""
    refresh_token: str


# ======================
# Response Schemas
# ======================

class UserResponse(BaseModel):
    """Schema for user data in responses"""
    id: int
    email: str
    full_name: str
    location: str
    tier: str
    is_admin: bool = False
    email_verified: bool
    preferences: Optional[dict] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    # Bez tego pola front nie ma skąd wiedzieć, że Premium jest na 30 dni — pokazywał
    # sam plan i użytkownik dowiadywał się o końcu okresu próbnego dopiero po fakcie.
    trial_ends_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class TokenPayload(BaseModel):
    """Schema for decoded JWT token payload"""
    sub: str  # User email
    user_id: int
    tier: str
    exp: datetime
    type: str  # "access" or "refresh"


class AuthResponse(BaseModel):
    """Schema for authentication response (login/register)"""
    user: UserResponse
    tokens: Token


class MessageResponse(BaseModel):
    """Schema for simple message responses"""
    message: str
    success: bool = True


# ======================
# Location Options
# ======================

AVAILABLE_LOCATIONS = [
    "Rybno R1",
    "Rybno R2",
    "Dębień",
    "Domki letniskowe",
    "Grabacz",
    "Gralewo Stacja",
    "Gronowo",
    "Groszki",
    "Grądy",
    "Hartowiec",
    "Jeglia",
    "Kopaniarze",
    "Koszelewki",
    "Koszelewy",
    "Naguszewo",
    "Nowa Wieś",
    "Prusy",
    "Rapaty",
    "Rumian",
    "Szczupliny",
    "Truszczyny",
    "Tuczki",
    "Wery",
    "Żabiny",
]
