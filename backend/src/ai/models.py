"""
Pydantic Models dla AI Agents

Response models dla strukturyzowanych odpowiedzi z Pydantic AI
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

# Dozwolone kategorie - Literal wymusza walidację przez Pydantic AI
ArticleCategoryName = Literal[
    'Awaria', 'Urząd', 'Zdrowie', 'Edukacja', 'Biznes',
    'Transport', 'Kultura', 'Sport', 'Rekreacja', 'Nieruchomości'
]


class ArticleCategory(BaseModel):
    """Response z kategoryzacji artykułu"""

    primary_category: ArticleCategoryName = Field(
        description="JEDNA z dozwolonych kategorii: Awaria, Urząd, Zdrowie, Edukacja, Biznes, Transport, Kultura, Sport, Rekreacja, Nieruchomości. NIE używaj innych nazw."
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
        description="Główny nagłówek dnia - chwytliwy, przyciągający uwagę"
    )
    highlights: str = Field(
        max_length=1000,
        description="Akapit opisowy (4-6 zdań) z najważniejszymi wiadomościami, pogodą i wydarzeniami. Najważniejsze info w **bold** (markdown)"
    )
    summary_by_category: dict[str, str] = Field(
        default_factory=dict,
        description="Podsumowanie per moduł (klucz: kategoria, wartość: opis)"
    )
    upcoming_events: List[str] = Field(
        default_factory=list,
        description="Nadchodzące wydarzenia"
    )
    air_quality_summary: str = Field(
        description="Podsumowanie jakości powietrza i warunków pogodowych (dane z czujnika w Rybnie)"
    )
    cited_article_ids: List[int] = Field(
        default_factory=list,
        description="IDs artykułów (z pola [ID:xxx]) które są cytowane lub stanowią podstawę headline i highlights. Max 5 najważniejszych."
    )
