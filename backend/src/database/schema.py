from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Column, JSON, ARRAY, String, Index
from sqlalchemy.dialects.postgresql import JSONB
from enum import Enum


# ======================
# Enums for User System
# ======================

class UserTier(str, Enum):
    FREE = "free"
    PREMIUM = "premium"
    BUSINESS = "business"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PENDING = "pending"


class NewsletterFrequency(str, Enum):
    WEEKLY = "weekly"
    DAILY = "daily"


class NewsletterStatus(str, Enum):
    ACTIVE = "active"
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"


# ======================
# User System Tables (Sprint 1)
# ======================

class User(SQLModel, table=True):
    """Użytkownicy systemu"""
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(max_length=255, unique=True, index=True)
    password_hash: str = Field(max_length=255)
    full_name: str = Field(max_length=100)
    location: str = Field(max_length=100, default="Rybno")  # Domyślna miejscowość
    tier: str = Field(default=UserTier.FREE.value, max_length=20)  # free, premium, business

    # Preferences (JSONB) - kategorie, powiadomienia, etc.
    preferences: Optional[dict] = Field(default_factory=dict, sa_column=Column(JSONB))

    # Status flags
    email_verified: bool = Field(default=False)
    is_active: bool = Field(default=True)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None


class Subscription(SQLModel, table=True):
    """Subskrypcje Premium/Business"""
    __tablename__ = "subscriptions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    tier: str = Field(max_length=20)  # premium, business
    status: str = Field(default=SubscriptionStatus.ACTIVE.value, max_length=20)  # active, cancelled, expired

    # Stripe integration (Sprint 4)
    stripe_subscription_id: Optional[str] = Field(default=None, max_length=100)
    stripe_customer_id: Optional[str] = Field(default=None, max_length=100)

    # Dates
    started_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ======================
# Newsletter Tables (Sprint 2)
# ======================

class NewsletterSubscriber(SQLModel, table=True):
    """Subskrybenci newslettera"""
    __tablename__ = "newsletter_subscribers"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(max_length=255, unique=True, index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")  # Może być NULL dla anonimowych
    frequency: str = Field(default=NewsletterFrequency.WEEKLY.value, max_length=20)  # weekly, daily
    status: str = Field(default=NewsletterStatus.ACTIVE.value, max_length=20)  # active, unsubscribed, bounced
    location: str = Field(default="Rybno", max_length=100)  # Lokalizacja dla spersonalizowanej treści

    # Confirmation
    confirmation_token: Optional[str] = Field(default=None, max_length=100)
    confirmed_at: Optional[datetime] = None

    # Unsubscribe
    unsubscribe_token: str = Field(max_length=100)  # Unique token for unsubscribe link
    unsubscribed_at: Optional[datetime] = None

    # Stats
    emails_sent: int = Field(default=0)
    emails_opened: int = Field(default=0)
    last_sent_at: Optional[datetime] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class NewsletterLog(SQLModel, table=True):
    """Log wysłanych newsletterów"""
    __tablename__ = "newsletter_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    subscriber_id: int = Field(foreign_key="newsletter_subscribers.id", index=True)
    newsletter_type: str = Field(max_length=20)  # weekly, daily
    subject: str = Field(max_length=255)
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    opened_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    status: str = Field(default="sent", max_length=20)  # sent, opened, bounced, failed


class Source(SQLModel, table=True):
    __tablename__ = "sources"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, index=True)
    type: str = Field(max_length=50)
    url: Optional[str] = None
    scraping_config: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    last_scraped: Optional[datetime] = None
    status: str = Field(default="active", max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Article(SQLModel, table=True):
    __tablename__ = "articles"

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.id", index=True)
    external_id: Optional[str] = Field(default=None, max_length=255, unique=True)
    title: str
    content: Optional[str] = None
    summary: Optional[str] = None
    url: str = Field(unique=True, index=True)
    image_url: Optional[str] = None
    author: Optional[str] = Field(default=None, max_length=255)
    published_at: Optional[datetime] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    category: Optional[str] = Field(default=None, max_length=100)
    tags: Optional[List[str]] = Field(default=None, sa_column=Column(ARRAY(String)))
    location_mentioned: Optional[List[str]] = Field(default=None, sa_column=Column(ARRAY(String)))
    processed: bool = Field(default=False)

class Event(SQLModel, table=True):
    __tablename__ = "events"
    __table_args__ = (
        Index('idx_event_unique', 'title', 'event_date', 'location', unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=500)
    description: Optional[str] = None
    short_description: Optional[str] = Field(default=None, max_length=300)
    event_date: datetime
    event_time: Optional[str] = Field(default=None, max_length=10)
    end_date: Optional[datetime] = None
    location: Optional[str] = Field(default=None, max_length=255)
    address: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=100)
    source_article_id: Optional[int] = Field(default=None, foreign_key="articles.id")
    external_url: Optional[str] = None
    image_url: Optional[str] = None
    organizer: Optional[str] = Field(default=None, max_length=255)
    price_info: Optional[str] = Field(default=None, max_length=255)
    contact_info: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_featured: bool = Field(default=False)
    views_count: int = Field(default=0)

class Weather(SQLModel, table=True):
    __tablename__ = "weather"

    id: Optional[int] = Field(default=None, primary_key=True)
    location: str = Field(max_length=100, index=True)  # "Rybno", "Działdowo"
    latitude: float
    longitude: float

    # Current weather
    temperature: float  # °C
    feels_like: float  # °C
    temp_min: float  # °C
    temp_max: float  # °C

    # Conditions
    description: str = Field(max_length=200)  # "pochmurno", "słonecznie"
    icon: str = Field(max_length=10)  # OpenWeather icon code
    main: str = Field(max_length=50)  # "Clouds", "Clear", "Rain"

    # Additional data
    humidity: int  # %
    pressure: int  # hPa
    wind_speed: float  # m/s
    wind_deg: Optional[int] = None  # degrees
    clouds: int  # %

    # Visibility & rain
    visibility: Optional[int] = None  # meters
    rain_1h: Optional[float] = None  # mm
    rain_3h: Optional[float] = None  # mm

    # Sun times
    sunrise: Optional[datetime] = None
    sunset: Optional[datetime] = None

    # Forecast (optional JSONB for 5-day forecast)
    forecast: Optional[dict] = Field(default=None, sa_column=Column(JSONB))

    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    is_current: bool = Field(default=True)  # flag for latest record

class DailySummary(SQLModel, table=True):
    """Dzienne podsumowania generowane przez AI"""
    __tablename__ = "daily_summaries"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: datetime = Field(unique=True, index=True)  # Data podsumowania
    headline: str  # Główny nagłówek dnia
    content: dict = Field(sa_column=Column(JSONB))  # Pełne podsumowanie (DailySummary model)
    generated_at: datetime = Field(default_factory=datetime.utcnow)  # Kiedy wygenerowano


class GUSStatistic(SQLModel, table=True):
    """Statystyki GUS (Bank Danych Lokalnych) - Demografia i Rynek Pracy"""
    __tablename__ = "gus_statistics"
    __table_args__ = (
        Index('idx_gus_category_year', 'category', 'year', unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    category: str = Field(max_length=50, index=True)  # "demographics" lub "employment"
    year: int = Field(index=True)  # Rok danych (np. 2025)
    data: dict = Field(sa_column=Column(JSONB))  # Wszystkie statystyki jako JSONB

    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow)  # Kiedy pobrano z API
    updated_at: datetime = Field(default_factory=datetime.utcnow)  # Ostatnia aktualizacja

    # Opcjonalnie: Szybki dostęp do kluczowych metryk (denormalizacja)
    # Demografia:
    population_total: Optional[int] = None  # Ludność ogółem
    unemployment_rate: Optional[float] = None  # Stopa bezrobocia (%)


class GUSGminaStats(SQLModel, table=True):
    """Cache danych GUS dla gmin - pobierane raz miesięcznie"""
    __tablename__ = "gus_gmina_stats"
    __table_args__ = (
        Index('idx_gus_gmina_unit_var_year', 'unit_id', 'var_id', 'year', unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Identyfikacja
    unit_id: str = Field(max_length=20, index=True)  # ID jednostki GUS (np. "042815403062")
    unit_name: str = Field(max_length=100)  # Nazwa gminy (np. "Rybno")
    var_id: str = Field(max_length=20, index=True)  # ID zmiennej GUS (np. "60530")
    var_name: str = Field(max_length=200)  # Nazwa zmiennej (np. "Podmioty REGON na 10k")
    
    # Dane
    year: int = Field(index=True)  # Rok danych
    value: Optional[float] = None  # Wartość
    
    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow)  # Kiedy pobrano z API GUS
    
    # Indeks dla szybkiego pobierania porównań
    category: str = Field(max_length=50, default="business", index=True)  # business, demographics, employment

