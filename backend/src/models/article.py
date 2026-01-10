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
    title: str
    summary: Optional[str] = None
    url: str
    image_url: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    scraped_at: datetime

    class Config:
        from_attributes = True
