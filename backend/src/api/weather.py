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
    """Get current weather data for a specific location – full fields including
    sunrise, sunset, temp_min, temp_max, feels_like, clouds, rain_1h."""
    weather_service = WeatherService()
    weather = await weather_service.get_current_weather(session, location)

    if not weather:
        raise HTTPException(
            status_code=404,
            detail=f"Weather data not found for location: {location}"
        )

    # Return all DB fields as dict (including sunrise/sunset/temp_min/temp_max)
    return {
        "location": weather.location,
        "temperature": weather.temperature,
        "feels_like": weather.feels_like,
        "temp_min": weather.temp_min,
        "temp_max": weather.temp_max,
        "description": weather.description,
        "icon": weather.icon,
        "main": weather.main,
        "humidity": weather.humidity,
        "pressure": weather.pressure,
        "wind_speed": weather.wind_speed,      # m/s
        "wind_deg": weather.wind_deg,
        "clouds": weather.clouds,              # %
        "visibility": weather.visibility,
        "rain_1h": weather.rain_1h,
        "rain_3h": weather.rain_3h,
        "sunrise": weather.sunrise.isoformat() if weather.sunrise else None,
        "sunset": weather.sunset.isoformat() if weather.sunset else None,
        "fetched_at": weather.fetched_at.isoformat() if weather.fetched_at else None,
    }


@router.get("/forecast")
async def get_weather_forecast(
    location: str = "Rybno",
    session: AsyncSession = Depends(get_session)
):
    """
    Get 5-day/3h hourly forecast + UV index stored in Weather.forecast JSONB.
    Returns:
        {
          "hourly": [ {dt, dt_txt, temp, pop, icon, description, wind_speed, humidity, ...}, ... ],
          "uv_index": float | null
        }
    """
    weather_service = WeatherService()
    weather = await weather_service.get_current_weather(session, location)

    if not weather or not weather.forecast:
        raise HTTPException(
            status_code=404,
            detail=f"Forecast data not yet available for {location}. Trigger /api/weather/update first."
        )

    return weather.forecast

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


@router.post("/air-quality/update")
async def update_air_quality_manual():
    """Manually trigger air quality update from Airly API"""
    from src.scheduler.air_quality_job import update_air_quality
    
    try:
        await update_air_quality()
        return {"message": "Air quality update triggered successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

# Legacy endpoint support (optional, can be removed if frontend strictly uses /current)
@router.get("/{location}")
async def get_weather_by_location(
    location: str,
    session: AsyncSession = Depends(get_session)
):
    """Get current weather for a specific location (Legacy)"""
    return await get_current_weather(location, session)
