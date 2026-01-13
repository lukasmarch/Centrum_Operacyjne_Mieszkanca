"""
Helper module dla notebooków - pozwala na import klas database bez problemu z 'src'
"""
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Column, ARRAY, String, create_engine, Session, select
from sqlalchemy.dialects.postgresql import JSONB


class Source(SQLModel, table=True):
    """Model dla źródeł danych"""
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
    """Model dla artykułów"""
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


def get_database_connection(database_url: str):
    """
    Zwraca połączenie z bazą danych (synchroniczne, dla Jupyter)
    
    Args:
        database_url: URL połączenia z bazą PostgreSQL
        
    Returns:
        SQLModel engine (synchroniczny)
        
    Note:
        Automatycznie konwertuje async URL (asyncpg) na sync URL (psycopg2)
        ponieważ Jupyter notebooks działają synchronicznie.
    """
    # Konwertuj async URL na sync URL
    # Backend używa postgresql+asyncpg, ale notebook potrzebuje postgresql (lub psycopg2)
    sync_url = database_url.replace('postgresql+asyncpg://', 'postgresql://')
    
    return create_engine(sync_url, echo=False)
