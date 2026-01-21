"""
Pydantic schemas for newsletter endpoints
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from src.database import NewsletterFrequency, NewsletterStatus


class NewsletterSubscribe(BaseModel):
    """Request schema for newsletter subscription"""
    email: EmailStr
    location: str = Field(default="Rybno", max_length=100)
    frequency: str = Field(default=NewsletterFrequency.WEEKLY.value)  # weekly or daily


class NewsletterUnsubscribe(BaseModel):
    """Request schema for unsubscribe (by token)"""
    token: str


class NewsletterConfirm(BaseModel):
    """Request schema for subscription confirmation"""
    token: str


class NewsletterPreferencesUpdate(BaseModel):
    """Request schema for updating preferences"""
    location: Optional[str] = Field(None, max_length=100)
    frequency: Optional[str] = None  # weekly or daily


class SubscriberResponse(BaseModel):
    """Response schema for subscriber info"""
    id: int
    email: str
    frequency: str
    status: str
    location: str
    created_at: datetime
    emails_sent: int
    last_sent_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SubscriptionStats(BaseModel):
    """Stats for newsletter subscriptions"""
    total_subscribers: int
    active_subscribers: int
    weekly_subscribers: int
    daily_subscribers: int


class MessageResponse(BaseModel):
    """Simple message response"""
    message: str
    success: bool = True
