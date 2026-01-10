"""
Pydantic Models dla AI Agents

Response models dla strukturyzowanych odpowiedzi z Pydantic AI
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ArticleCategory(BaseModel):
    """Response z kategoryzacji artykułu"""

    primary_category: str = Field(
        description="Główna kategoria z listy 8 modułów"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Pewność klasyfikacji (0-1)"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tagi tematyczne (3-5 słów kluczowych)"
    )
    locations_mentioned: List[str] = Field(
        default_factory=list,
        description="Wymienione miejscowości z Powiatu Działdowskiego"
    )
    key_entities: List[str] = Field(
        default_factory=list,
        description="Kluczowe podmioty (osoby, instytucje, firmy)"
    )
    summary: str = Field(
        max_length=500,
        description="Podsumowanie 2-3 zdania po polsku"
    )


class ExtractedEvent(BaseModel):
    """Wydarzenie wyekstrahowane z artykułu"""

    is_event: bool = Field(
        description="Czy artykuł opisuje konkretne wydarzenie"
    )
    title: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = Field(
        max_length=300,
        default=None
    )
    event_date: Optional[datetime] = None
    event_time: Optional[str] = Field(
        max_length=10,
        default=None,
        description="Format HH:MM"
    )
    end_date: Optional[datetime] = None
    location: Optional[str] = None
    address: Optional[str] = None
    organizer: Optional[str] = None
    price_info: Optional[str] = None
    contact_info: Optional[str] = None


class DailySummary(BaseModel):
    """Dzienne podsumowanie wiadomości"""

    date: str = Field(description="Data w formacie YYYY-MM-DD")
    headline: str = Field(
        max_length=200,
        description="Główny nagłówek dnia"
    )
    highlights: List[str] = Field(
        min_length=3,
        max_length=5,
        description="Top 3-5 najważniejszych wiadomości"
    )
    summary_by_category: dict[str, str] = Field(
        description="Podsumowanie per moduł (klucz: kategoria, wartość: opis)"
    )
    upcoming_events: List[str] = Field(
        default_factory=list,
        description="Nadchodzące wydarzenia"
    )
    weather_summary: str = Field(
        description="Podsumowanie pogody"
    )
