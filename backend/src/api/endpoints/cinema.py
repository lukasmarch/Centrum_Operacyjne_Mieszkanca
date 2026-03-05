"""
Cinema Repertoire API - Database-First Architecture

Returns cinema showtimes from local database (cinema_showtimes table).
Data refreshed daily at 8:00 AM by scheduler.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from src.database import get_session
from src.database.schema import CinemaShowtime


router = APIRouter()


# Response models (match frontend expectations)
class Movie(BaseModel):
    title: str
    genre: str
    time: List[str]  # List of showtimes like ["16:50", "20:30"]
    posterUrl: str
    rating: str
    link: Optional[str] = None


class CinemaRepertoire(BaseModel):
    cinemaName: str
    date: str
    movies: List[Movie]


@router.get("/repertoire", response_model=CinemaRepertoire)
async def get_cinema_repertoire(
    location: str = Query(..., description="City name: 'Działdowo' or 'Lubawa'"),
    session: AsyncSession = Depends(get_session)
):
    """
    Get cinema repertoire for a specific location from database.

    Data is refreshed daily at 8:00 AM by scheduler.
    Returns latest repertoire (today's date) from database.

    Args:
        location: City name (Działdowo or Lubawa)

    Returns:
        CinemaRepertoire with list of movies and showtimes
    """
    # Normalize location
    normalized_location = location.capitalize()
    if normalized_location == "Dzialdowo":
        normalized_location = "Działdowo"

    # Map location to cinema_name (must match scraper output!)
    # Scraper uses city_slug without Polish chars: f"Kino {city_slug}" -> "Kino Dzialdowo"
    cinema_name_map = {
        "Działdowo": "Kino Działdowo",
        "Lubawa": "Kino Pokój Lubawa",
    }
    cinema_name = cinema_name_map.get(normalized_location, f"Kino {normalized_location}")

    # Get today's date in DD.MM.YYYY format (matches scraper format)
    today = datetime.now().strftime('%d.%m.%Y')

    # Query database for today's showtimes
    stmt = select(CinemaShowtime).where(
        and_(
            CinemaShowtime.cinema_name == cinema_name,
            CinemaShowtime.date == today
        )
    )
    result = await session.execute(stmt)
    showtimes = result.scalars().all()

    if not showtimes:
        # No data found - return empty repertoire
        return CinemaRepertoire(
            cinemaName=cinema_name,
            date=today,
            movies=[]
        )

    # Build response
    movies = [
        Movie(
            title=showtime.title,
            genre=showtime.genre,
            time=showtime.showtimes,
            posterUrl=showtime.poster_url,
            rating=showtime.rating,
            link=showtime.link
        )
        for showtime in showtimes
    ]

    return CinemaRepertoire(
        cinemaName=cinema_name,
        date=today,
        movies=movies
    )
