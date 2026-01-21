"""
Newsletter module - Weekly and Daily newsletters
Sprint 2: Newsletter System
"""

from .generator import NewsletterGenerator
from .email_service import EmailService
from .routes import router

__all__ = ["NewsletterGenerator", "EmailService", "router"]
