from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, HttpUrl

class ArticleInput(BaseModel):
    source_id: int
    external_id: Optional[str] = None
    title: str
    content: Optional[str] = None
    url: str
    image_url: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None

class ArticleOutput(BaseModel):
    id: int
    source_id: int
    source_name: Optional[str] = None  # Added for frontend
    source_label: Optional[str] = None  # nazwa źródła do pokazania w UI; None → neutralne „źródło ↗"
    title: str
    display_title: Optional[str] = None  # nagłówek AI — frontend pokazuje go zamiast title
    summary: Optional[str] = None
    url: str
    image_url: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    event_at: Optional[datetime] = None      # termin zdarzenia (wyłączenie prądu)
    event_until: Optional[datetime] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    scraped_at: datetime
    # Awaria będąca sprawą najbliższych godzin (feed_policy.is_pinned_alert) —
    # frontend nie ma jak tego policzyć sam, bo progi czasu żyją w backendzie
    is_pinned: bool = False
    # Miejscowości z gminy Rybno wymienione w komunikacie oraz odpowiedź na
    # pytanie „czy to dotyczy MOJEJ wsi" (parametr `location` zapytania).
    # Bez `location` zawsze True — patrz `alert_policy.concerns`.
    alert_places: List[str] = []
    concerns_location: bool = True
    # Zasięg dla układu strony: „gmina" / „okolice" (powiat) / „region".
    # Liczony z oceny kategoryzacji (`locality`), dla wpisów bez oceny —
    # z `feed_policy.article_scope`. Dopisany 3.09.2026, gdy zakładka
    # Wiadomości grupowała po DACIE publikacji: wszystko lokalne wchodzi rano
    # z wczorajszą datą (Apify raz dziennie), więc sekcję „Dzisiaj" otwierały
    # zawsze trzy RSS-y z powiatu, choć ranking miał je na 5., 11. i 15. miejscu.
    scope: str = "region"

    class Config:
        from_attributes = True
