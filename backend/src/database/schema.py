from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Column, JSON, ARRAY, String, Index
from sqlalchemy.dialects.postgresql import JSONB

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
