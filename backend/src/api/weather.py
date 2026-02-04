from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List, Optional
from datetime import datetime, timedelta

from ..database.connection import get_session
from ..database.schema import Weather, AirQuality
from ..integrations.weather import WeatherService

router = APIRouter(prefix="/api/weather", tags=["Weather"])

# --- OpenWeatherMap Endpoints ---

@router.get("")
async def get_all_weather(session: AsyncSession = Depends(get_session)):
    """Get current weather for all locations"""
    result = await session.execute(
        select(Weather)
        .where(Weather.is_current == True)
        .order_by(Weather.fetched_at.desc())
    )
    weather_data = result.scalars().all()
    return {"weather": weather_data, "count": len(weather_data)}

@router.get("/current")
async def get_current_weather(
    location: str = "Rybno",
    session: AsyncSession = Depends(get_session)
):
    """Get current weather data for a specific location."""
    weather_service = WeatherService()
    weather = await weather_service.get_current_weather(session, location)

    if not weather:
        raise HTTPException(
            status_code=404,
            detail=f"Weather data not found for location: {location}"
        )

    return weather

@router.get("/history")
async def get_weather_history(
    location: str = "Rybno",
    days: int = 7,
    session: AsyncSession = Depends(get_session)
):
    """Get historical weather data (temperature)."""
    since = datetime.utcnow() - timedelta(days=days)
    statement = select(Weather).where(
        Weather.location == location,
        Weather.fetched_at >= since
    ).order_by(Weather.fetched_at)
    
    result = await session.execute(statement)
    return result.scalars().all()

@router.post("/update")
async def update_weather(session: AsyncSession = Depends(get_session)):
    """Manually trigger weather update for all locations"""
    weather_service = WeatherService()
    results = await weather_service.update_all_locations(session)

    return {
        "message": "Weather updated successfully",
        "locations_updated": len(results),
        "data": results
    }

# --- Airly Endpoints ---

@router.get("/air-quality/current")
async def get_current_air_quality(
    location: str = "Rybno",
    session: AsyncSession = Depends(get_session)
):
    """Get current air quality data."""
    statement = select(AirQuality).where(
        AirQuality.location == location,
        AirQuality.is_current == True
    )
    result = await session.execute(statement)
    record = result.scalar_one_or_none()
    
    if not record:
        # Fallback to last known if "current" flag issue
        statement = select(AirQuality).where(
            AirQuality.location == location
        ).order_by(AirQuality.fetched_at.desc())
        result = await session.execute(statement)
        record = result.scalars().first()
        
    if not record:
        raise HTTPException(status_code=404, detail="Air quality data not found")
        
    return record

@router.get("/air-quality/history")
async def get_air_quality_history(
    location: str = "Rybno",
    days: int = 7,
    session: AsyncSession = Depends(get_session)
):
    """Get historical air quality data."""
    since = datetime.utcnow() - timedelta(days=days)
    statement = select(AirQuality).where(
        AirQuality.location == location,
        AirQuality.fetched_at >= since
    ).order_by(AirQuality.fetched_at)
    
    result = await session.execute(statement)
    return result.scalars().all()

# Legacy endpoint support (optional, can be removed if frontend strictly uses /current)
@router.get("/{location}")
async def get_weather_by_location(
    location: str,
    session: AsyncSession = Depends(get_session)
):
    """Get current weather for a specific location (Legacy)"""
    return await get_current_weather(location, session)
