from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Optional

# Znajdź katalog backend (gdzie jest .env)
BACKEND_DIR = Path(__file__).parent.parent

class Settings(BaseSettings):
    DATABASE_URL: str
    # REDIS_URL removed (2026-02-17): Not used - all cache in PostgreSQL
    OPENAI_API_KEY: str
    OPENWEATHER_API_KEY: str
    APIFY_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    AIRLY_API_KEY: Optional[str] = None
    CEIDG_API_TOKEN: Optional[str] = None  # Token do API CEIDG v3
    REGON_API_KEY: Optional[str] = "b220c4e85a1b4e1da8b8"  # Klucz do API REGON (GUS)

    SCRAPER_USER_AGENT: str = "Mozilla/5.0 (compatible; CentrumOperacyjneBot/1.0)"
    SCRAPER_TIMEOUT: int = 30
    SCRAPER_RATE_LIMIT: float = 1.0
    SCRAPER_MAX_RETRIES: int = 3

    # Auth settings (Sprint 1)
    JWT_SECRET: str  # REQUIRED: Min 32 chars, set in .env
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Newsletter settings (Sprint 2)
    RESEND_API_KEY: Optional[str] = None
    NEWSLETTER_FROM_EMAIL: str = "newsletter@centrum-mieszkanca.pl"
    NEWSLETTER_FROM_NAME: str = "Centrum Operacyjne Mieszkańca"
    APP_URL: str = "http://localhost:3000"  # Frontend URL for links

    # CORS settings
    CORS_ORIGINS: str = "http://localhost:3001,http://localhost:3002,http://localhost:5173"  # Comma-separated list

    # Push Notifications (Sprint 5C) - VAPID keys
    VAPID_PUBLIC_KEY: Optional[str] = None
    VAPID_PRIVATE_KEY: Optional[str] = None
    VAPID_CLAIMS_EMAIL: str = "push@centrum-mieszkanca.pl"

    # BIP Scraper / Firecrawl (Sprint 5D)
    FIRECRAWL_API_KEY: Optional[str] = None

    # Przelewy24 payments
    P24_MERCHANT_ID: Optional[int] = None         # Numer konta P24 (z panelu)
    P24_POS_ID: Optional[int] = None              # ID sklepu (zwykle = merchant_id)
    P24_CRC_KEY: Optional[str] = None             # Klucz CRC do podpisu (z panelu P24)
    P24_API_KEY: Optional[str] = None             # Klucz API (z panelu P24)
    P24_SANDBOX: bool = True                       # True = sandbox, False = produkcja

    # AI Chat + RAG (Sprint 6)
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    CHAT_MODEL: str = "gpt-4o"
    CHAT_MAX_CONTEXT_TOKENS: int = 8000

    # Token do autoryzacji endpointu /api/cinema/ingest (GitHub Actions → backend)
    CINEMA_INGEST_TOKEN: Optional[str] = None

    # Pydantic v2 syntax
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding='utf-8',
        case_sensitive=True
    )

settings = Settings()
