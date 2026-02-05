from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Optional

# Znajdź katalog backend (gdzie jest .env)
BACKEND_DIR = Path(__file__).parent.parent

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
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
    JWT_SECRET: str = "your-secret-key-min-32-chars-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Newsletter settings (Sprint 2)
    RESEND_API_KEY: Optional[str] = None
    NEWSLETTER_FROM_EMAIL: str = "newsletter@centrum-mieszkanca.pl"
    NEWSLETTER_FROM_NAME: str = "Centrum Operacyjne Mieszkańca"
    APP_URL: str = "http://localhost:3000"  # Frontend URL for links

    # Pydantic v2 syntax
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding='utf-8',
        case_sensitive=True
    )

settings = Settings()
