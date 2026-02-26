"""
Waste Schedule API — harmonogram wywozu śmieci dla Gminy Rybno

GET /api/waste/towns            → lista miejscowości
GET /api/waste/schedule?town=X&days=60  → nadchodzące odbiory
"""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_session

router = APIRouter(prefix="/api/waste", tags=["waste"])


@router.get("/towns")
async def get_towns(session: AsyncSession = Depends(get_session)):
    """Zwraca listę wszystkich miejscowości w harmonogramie śmieci."""
    result = await session.execute(
        text("SELECT DISTINCT town FROM waste_schedule ORDER BY town")
    )
    towns = [row[0] for row in result]
    return {"towns": towns}


@router.get("/schedule")
async def get_schedule(
    town: str = Query(default="Rybno R1", description="Nazwa miejscowości"),
    days: int = Query(default=60, ge=1, le=365, description="Liczba dni do przodu"),
    session: AsyncSession = Depends(get_session),
):
    """
    Zwraca nadchodzące terminy wywozu śmieci dla danej miejscowości.

    Parametry:
    - town: nazwa miejscowości (np. "Rybno R1", "Jeglia")
    - days: liczba dni do przodu (domyślnie 60)
    """
    today = date.today()
    end_date = today + timedelta(days=days)

    result = await session.execute(
        text("""
            SELECT waste_type, collection_date
            FROM waste_schedule
            WHERE town = :town
              AND collection_date >= :today
              AND collection_date <= :end_date
            ORDER BY collection_date, waste_type
        """),
        {"town": town, "today": today, "end_date": end_date},
    )

    rows = result.fetchall()
    events = []
    for row in rows:
        waste_type, col_date = row
        days_remaining = (col_date - today).days
        events.append(
            {
                "waste_type": waste_type,
                "date": col_date.strftime("%d.%m.%Y"),
                "days_remaining": days_remaining,
            }
        )

    return {
        "town": town,
        "days_requested": days,
        "events": events,
        "count": len(events),
    }
