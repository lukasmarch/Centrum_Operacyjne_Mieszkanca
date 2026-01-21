"""
Users module - User profile management
Sprint 1: System Auth/Users
"""

from .service import UserService
from .routes import router

__all__ = ["UserService", "router"]
