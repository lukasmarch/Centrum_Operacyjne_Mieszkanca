"""
Cinema Repertoire API - Database-First Architecture

Returns cinema showtimes from local database (cinema_showtimes table).
Data refreshed daily at 8:00 AM by scheduler.
"""
from fastapi import APIRouter, HTTPException, Query, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, delete
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from src.database import get_session
from src.database.schema import CinemaShowtime
from src.config import settings


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
    fetchedAt: Optional[str] = None  # kiedy dane były ostatnio pobrane


@router.get("/repertoire", response_model=CinemaRepertoire)
async def get_cinema_repertoire(
    location: str = Query(..., description="City name: 'Działdowo' or 'Lubawa'"),
    session: AsyncSession = Depends(get_session)
):
    """
    Get cinema repertoire for a specific location from database.

    Data is refreshed daily at 8:00 AM by scheduler.
    Returns latest available repertoire from database (fallback to most recent if today missing).
    """
    # Normalize location
    normalized_location = location.capitalize()
    if normalized_location == "Dzialdowo":
        normalized_location = "Działdowo"

    cinema_name_map = {
        "Działdowo": "Kino Działdowo",
        "Lubawa": "Kino Pokój Lubawa",
    }
    cinema_name = cinema_name_map.get(normalized_location, f"Kino {normalized_location}")

    today = datetime.now().strftime('%d.%m.%Y')

    # Najpierw spróbuj dzisiejszych danych
    stmt = select(CinemaShowtime).where(
        and_(
            CinemaShowtime.cinema_name == cinema_name,
            CinemaShowtime.date == today
        )
    )
    result = await session.execute(stmt)
    showtimes = result.scalars().all()

    # Fallback: zwróć ostatnie dostępne dane jeśli dziś brak
    if not showtimes:
        latest_date_stmt = select(func.max(CinemaShowtime.fetched_at)).where(
            CinemaShowtime.cinema_name == cinema_name
        )
        latest_result = await session.execute(latest_date_stmt)
        latest_fetched_at = latest_result.scalar()

        if latest_fetched_at:
            stmt = select(CinemaShowtime).where(
                and_(
                    CinemaShowtime.cinema_name == cinema_name,
                    CinemaShowtime.fetched_at == latest_fetched_at
                )
            )
            result = await session.execute(stmt)
            showtimes = result.scalars().all()

    if not showtimes:
        return CinemaRepertoire(
            cinemaName=cinema_name,
            date=today,
            movies=[],
            fetchedAt=None
        )

    # Wyznacz datę pobrania dla informacji o aktualności
    fetched_at_str = None
    if showtimes[0].fetched_at:
        fetched_at_str = showtimes[0].fetched_at.strftime('%d.%m.%Y')

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
        date=showtimes[0].date if showtimes else today,
        movies=movies,
        fetchedAt=fetched_at_str
    )


# ---------------------------------------------------------------------------
# Ingest endpoint — wywoływany przez GitHub Actions (omija Cloudflare na VPS)
# ---------------------------------------------------------------------------

class IngestMovie(BaseModel):
    title: str
    times: List[str]
    poster: str = ""
    link: str = ""
    genre: str = "Film"
    rating: str = "N/A"


class IngestPayload(BaseModel):
    cinema_name: str  # np. "Kino Działdowo"
    date: str         # DD.MM.YYYY — data scrape'a
    movies: List[IngestMovie]


@router.post("/ingest", status_code=200)
async def ingest_cinema_data(
    payload: IngestPayload,
    authorization: str = Header(...),
    session: AsyncSession = Depends(get_session)
):
    """
    Przyjmuje dane repertuaru od GitHub Actions.
    Autoryzacja: Bearer {CINEMA_INGEST_TOKEN}

    Wywoływane codziennie przez workflow .github/workflows/cinema_scrape.yml
    który scrape'uje biletyna.pl z IP GitHub (nieblokowanego przez Cloudflare).
    """
    # Weryfikacja tokenu
    expected = f"Bearer {settings.CINEMA_INGEST_TOKEN}"
    if not settings.CINEMA_INGEST_TOKEN or authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")

    now = datetime.utcnow()

    # Usuń stare rekordy dla tego kina + daty
    await session.execute(
        delete(CinemaShowtime).where(
            and_(
                CinemaShowtime.cinema_name == payload.cinema_name,
                CinemaShowtime.date == payload.date
            )
        )
    )

    # Zapisz nowe
    count = 0
    for movie in payload.movies:
        if not movie.times:
            continue
        showtime = CinemaShowtime(
            cinema_name=payload.cinema_name,
            date=payload.date,
            title=movie.title,
            genre=movie.genre,
            showtimes=movie.times,
            poster_url=movie.poster,
            rating=movie.rating,
            link=movie.link,
            fetched_at=now
        )
        session.add(showtime)
        count += 1

    await session.commit()
    return {"saved": count, "cinema": payload.cinema_name, "date": payload.date}
