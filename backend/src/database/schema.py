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
    embedded: bool = Field(default=False)  # True when RAG embeddings generated (Sprint 6)

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

class AirQuality(SQLModel, table=True):
    """Jakość powietrza z Airly"""
    __tablename__ = "air_quality"

    id: Optional[int] = Field(default=None, primary_key=True)
    location: str = Field(max_length=100, index=True)  # "Rybno"
    
    # Indexes
    pm25: float  # µg/m³
    pm10: float  # µg/m³
    caqi: float  # Airly CAQI index
    caqi_level: str = Field(max_length=50) # VERY_LOW, LOW, etc.
    
    # Weather conditions from sensor
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    
    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    is_current: bool = Field(default=True)

class DailySummary(SQLModel, table=True):
    """Dzienne podsumowania generowane przez AI"""
    __tablename__ = "daily_summaries"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: datetime = Field(unique=True, index=True)  # Data podsumowania
    headline: str  # Główny nagłówek dnia
    content: dict = Field(sa_column=Column(JSONB))  # Pełne podsumowanie (DailySummary model)
    generated_at: datetime = Field(default_factory=datetime.utcnow)  # Kiedy wygenerowano


class CinemaShowtime(SQLModel, table=True):
    """Repertuar kin - Dzialdowo i Lubawa (scraped daily)"""
    __tablename__ = "cinema_showtimes"
    __table_args__ = (
        Index('idx_cinema_date_title', 'cinema_name', 'date', 'title'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Cinema & Schedule
    cinema_name: str = Field(max_length=100, index=True)  # "Kino Dzialdowo", "Kino Lubawa"
    date: str = Field(max_length=10, index=True)  # "DD.MM.YYYY" format (matches scraper)

    # Movie Details
    title: str = Field(max_length=200)  # Film title
    genre: str = Field(max_length=50, default="Film")  # Genre
    showtimes: List[str] = Field(sa_column=Column(ARRAY(String)))  # ["16:50", "20:30"]
    poster_url: str = Field(max_length=500)  # Poster image URL
    rating: str = Field(max_length=10, default="N/A")  # Rating (usually "N/A")
    link: Optional[str] = Field(default=None, max_length=500)  # Link to movie page

    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class TrafficCache(SQLModel, table=True):
    """Cache danych o ruchu drogowym - Gemini Grounding API (refreshed every 4h)"""
    __tablename__ = "traffic_cache"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Traffic data (JSONB for flexibility)
    # Structure: {"roads": [...], "sources": [...]}
    data: dict = Field(sa_column=Column(JSONB))

    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    is_current: bool = Field(default=True)  # Flag for latest record
    ttl_seconds: int = Field(default=14400)  # TTL: 4 hours


# Legacy GUSStatistic model removed (2026-02-17)
# Replaced by: GUSGminaStats, GUSNationalAverages, GUSDataRefreshLog
# See: backend/src/api/endpoints/gus.py for new database-first architecture

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
    category: Optional[str] = Field(default=None, max_length=50, index=True)  # Kategoria (demografia, finanse_gminy, etc.)

    # Dane
    year: int = Field(index=True)  # Rok danych
    value: Optional[float] = None  # Wartość

    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow)  # Kiedy pobrano z API GUS


# ======================
# CEIDG Business Tables
# ======================

class CEIDGBusiness(SQLModel, table=True):
    """Firmy z rejestru CEIDG dla Gminy Rybno"""
    __tablename__ = "ceidg_businesses"
    __table_args__ = (
        Index('idx_ceidg_nip', 'nip'),
        Index('idx_ceidg_miasto', 'miasto'),
        Index('idx_ceidg_gmina_powiat', 'gmina', 'powiat'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    ceidg_id: str = Field(max_length=50, unique=True, index=True)  # UUID from CEIDG API
    
    # Business data
    nazwa: str = Field(max_length=500)
    nip: str = Field(max_length=20, index=True)
    regon: Optional[str] = Field(default=None, max_length=20)
    
    # PKD codes
    pkd_main: Optional[str] = Field(default=None, max_length=20, index=True)
    pkd_list: Optional[List[dict]] = Field(default=None, sa_column=Column(JSONB))

    status: str = Field(max_length=30, default="AKTYWNY")  # AKTYWNY, ZAWIESZONY, WYKRESLONY
    data_rozpoczecia: Optional[datetime] = None
    
    # Owner
    wlasciciel_imie: Optional[str] = Field(default=None, max_length=100)
    wlasciciel_nazwisko: Optional[str] = Field(default=None, max_length=100)
    
    # Address (denormalized for quick queries)
    ulica: Optional[str] = Field(default=None, max_length=200)
    budynek: Optional[str] = Field(default=None, max_length=20)
    lokal: Optional[str] = Field(default=None, max_length=20)
    miasto: str = Field(max_length=100, index=True)
    kod_pocztowy: str = Field(max_length=10)
    gmina: str = Field(max_length=100)
    powiat: str = Field(max_length=100)
    wojewodztwo: Optional[str] = Field(default=None, max_length=100)
    
    # Full data as JSON for future extensibility
    raw_data: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    
    # External link
    ceidg_link: Optional[str] = Field(default=None, max_length=500)
    
    # Detailed Data (fetched from /firma/{id})
    adres_korespondencyjny: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    spolki: Optional[List[dict]] = Field(default=None, sa_column=Column(JSONB))
    obywatelstwa: Optional[List[dict]] = Field(default=None, sa_column=Column(JSONB))
    email: Optional[str] = Field(default=None, max_length=255)
    www: Optional[str] = Field(default=None, max_length=500)
    telefon: Optional[str] = Field(default=None, max_length=50)
    
    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CEIDGSyncStats(SQLModel, table=True):
    """Statystyki synchronizacji CEIDG"""
    __tablename__ = "ceidg_sync_stats"

    id: Optional[int] = Field(default=None, primary_key=True)
    gmina: str = Field(max_length=100, unique=True, index=True)
    powiat: str = Field(max_length=100)

    # Counts
    total_count: int = Field(default=0)
    active_count: int = Field(default=0)

    # Breakdown by locality (JSONB)
    by_miejscowosc: dict = Field(default_factory=dict, sa_column=Column(JSONB))

    # Sync metadata
    last_sync: datetime = Field(default_factory=datetime.utcnow)
    sync_status: str = Field(max_length=20, default="success")  # success, failed, in_progress


# ======================
# GUS Database-First Tables (2026-02-06)
# ======================

class GUSDataRefreshLog(SQLModel, table=True):
    """
    Tracking odświeżania danych GUS - kiedy ostatnio zaktualizowano każdą zmienną.
    Używane przez scheduler do monitorowania monthly refresh jobs.
    """
    __tablename__ = "gus_data_refresh_log"
    __table_args__ = (
        Index('idx_gus_refresh_var_key', 'var_key', unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Variable identification
    var_key: str = Field(max_length=100, unique=True, index=True)  # Key from gus_variables.py
    var_id: str = Field(max_length=20)  # GUS BDL variable ID

    # Refresh tracking
    last_refresh: datetime = Field(default_factory=datetime.utcnow)  # Ostatni successful refresh
    records_updated: int = Field(default=0)  # Liczba zaktualizowanych rekordów

    # Status
    status: str = Field(max_length=20, default="success")  # success, failed, in_progress
    error_message: Optional[str] = Field(default=None, max_length=500)  # Jeśli failed

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GUSNationalAverages(SQLModel, table=True):
    """
    Średnie krajowe i wojewódzkie dla zmiennych GUS.
    Używane do porównań: "Rybno: 6,837 PLN (79.2% średniej krajowej)".
    Populowane przez scheduler wraz z danymi gminnymi.
    """
    __tablename__ = "gus_national_averages"
    __table_args__ = (
        Index('idx_gus_avg_var_year_level', 'var_id', 'year', 'level', unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Variable identification
    var_id: str = Field(max_length=20, index=True)  # GUS BDL variable ID
    var_key: str = Field(max_length=100, index=True)  # Key from gus_variables.py

    # Data
    year: int = Field(index=True)  # Rok danych
    level: str = Field(max_length=20, index=True)  # "national" | "voivodeship"
    value: Optional[float] = None  # Wartość średniej

    # Metadata
    fetched_at: datetime = Field(default_factory=datetime.utcnow)  # Kiedy pobrano z API


class GUSInsight(SQLModel, table=True):
    """
    AI-generowane analizy statystyk GUS dla Business tier.
    Generowane raz w miesiącu przez scheduler + GPT-4o-mini.

    UWAGA: Niższy priorytet - implementacja w późniejszym sprincie.
    """
    __tablename__ = "gus_insights"
    __table_args__ = (
        Index('idx_gus_insight_category', 'category'),
    )

    id: Optional[int] = Field(default=None, primary_key=True)

    # Classification
    category: str = Field(max_length=50, index=True)  # demografia, rynek_pracy, etc.
    insight_type: str = Field(max_length=50)  # trend, comparison, recommendation

    # Content
    content: str = Field(max_length=2000)  # Treść insightu po polsku (3-5 bullet points)
    data_context: dict = Field(default_factory=dict, sa_column=Column(JSONB))  # Dane źródłowe

    # Validity
    generated_at: datetime = Field(default_factory=datetime.utcnow)  # Kiedy wygenerowano
    valid_until: datetime  # Do kiedy aktualny (typically +1 month)


# ======================
# Zgłoszenie24 – Centrum Powiadamiania (Sprint Reports)
# ======================

class ReportStatus(str, Enum):
    NEW = "new"
    VERIFIED = "verified"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class ReportCategory(str, Enum):
    EMERGENCY = "emergency"            # Wypadki, tonięcie, zawalenie
    FIRE = "fire"                      # Pożary
    INFRASTRUCTURE = "infrastructure"  # Roads, sidewalks, lighting
    WASTE = "waste"                    # Waste, trash, overflowing bins
    GREENERY = "greenery"              # Greenery, parks
    SAFETY = "safety"                  # Safety, road signs, barriers
    WATER = "water"                    # Water, sewage, leaks
    OTHER = "other"                    # Other issues


class Report(SQLModel, table=True):
    """Zgłoszenia mieszkańców – usterki, awarie, zdarzenia"""
    __tablename__ = "reports"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Autor (opcjonalnie zalogowany)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    author_name: Optional[str] = Field(default=None, max_length=100)
    author_email: Optional[str] = Field(default=None, max_length=255)
    author_phone: Optional[str] = Field(default=None, max_length=50)

    # Treść
    title: str = Field(max_length=200)
    description: str
    ai_summary: Optional[str] = None

    # Kategoryzacja (AI)
    category: str = Field(default=ReportCategory.OTHER.value, max_length=50, index=True)
    ai_detected_objects: Optional[dict] = Field(default=None, sa_column=Column(JSONB))
    ai_condition_assessment: Optional[str] = Field(default=None, max_length=500)
    ai_severity: Optional[str] = Field(default=None, max_length=20)  # low, medium, high, critical

    # Media
    image_url: Optional[str] = Field(default=None, max_length=500)
    generated_image_url: Optional[str] = Field(default=None, max_length=500)

    # Geolokalizacja
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = Field(default=None, max_length=300)
    location_name: Optional[str] = Field(default=None, max_length=100)

    # Status
    status: str = Field(default=ReportStatus.NEW.value, max_length=20, index=True)
    is_spam: bool = Field(default=False)

    # Interakcja
    upvotes: int = Field(default=0)
    views_count: int = Field(default=0)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


# ======================
# Push Notifications (Sprint 5C)
# ======================

class PushSubscription(SQLModel, table=True):
    """Subskrypcje Web Push Notifications"""
    __tablename__ = "push_subscriptions"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Powiązanie z użytkownikiem (opcjonalne)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", index=True)
    email: Optional[str] = Field(default=None, max_length=255)  # dla niezalogowanych

    # Web Push Protocol fields
    endpoint: str = Field(max_length=1000, unique=True, index=True)  # URL push service
    p256dh: str = Field(max_length=200)   # klucz szyfrowania
    auth: str = Field(max_length=100)     # auth secret

    # Kategorie powiadomień: alerty, powietrze, artykuly, wydarzenia
    categories: list = Field(default_factory=list, sa_column=Column(JSONB))

    # Metadata urządzenia
    user_agent: Optional[str] = Field(default=None, max_length=500)

    # Status
    active: bool = Field(default=True)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
