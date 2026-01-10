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

    SCRAPER_USER_AGENT: str = "Mozilla/5.0 (compatible; CentrumOperacyjneBot/1.0)"
    SCRAPER_TIMEOUT: int = 30
    SCRAPER_RATE_LIMIT: float = 1.0
    SCRAPER_MAX_RETRIES: int = 3

    # Pydantic v2 syntax
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding='utf-8',
        case_sensitive=True
    )

settings = Settings()
