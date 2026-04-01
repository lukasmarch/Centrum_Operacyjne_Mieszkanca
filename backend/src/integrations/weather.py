"""
OpenWeatherMap API Integration
Fetches weather data for specific locations (Rybno, Działdowo)
API Docs: https://openweathermap.org/current, /forecast, /uvi
"""
import asyncio
import httpx
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from src.config import settings
from src.database.schema import Weather
from src.utils.logger import setup_logger

logger = setup_logger("WeatherIntegration")

# Locations in Powiat Działdowski
LOCATIONS = {
    "Rybno": {
        "lat": 53.1386,
        "lon": 19.8956
    },
    "Działdowo": {
        "lat": 53.2347,
        "lon": 20.1861
    }
}


class WeatherService:
    """Service for fetching and storing weather data from OpenWeatherMap"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENWEATHER_API_KEY
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"
        self.forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
        self.uvi_url = "https://api.openweathermap.org/data/2.5/uvi"

    async def fetch_weather(self, location: str, lat: float, lon: float) -> dict:
        """
        Fetch current weather from OpenWeatherMap API

        Args:
            location: Location name (e.g., "Rybno")
            lat: Latitude
            lon: Longitude

        Returns:
            Weather data dictionary
        """
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",  # Celsius
            "lang": "pl"  # Polish descriptions
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                logger.info(f"Fetching weather for {location} ({lat}, {lon})")
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()

                logger.info(f"Successfully fetched weather for {location}")
                return data

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error fetching weather for {location}: {e}")
                raise
            except Exception as e:
                logger.error(f"Error fetching weather for {location}: {e}")
                raise

    async def fetch_forecast(self, lat: float, lon: float) -> list:
        """
        Fetch 5-day / 3-hour forecast from OWM /forecast.
        Returns a list of slots with: dt, temp, pop (precipitation probability),
        icon, description, wind_speed, humidity, clouds, feels_like.
        """
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",
            "lang": "pl",
            "cnt": 40,  # 5 days × 8 slots per day
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                logger.info(f"Fetching forecast for ({lat}, {lon})")
                response = await client.get(self.forecast_url, params=params)
                response.raise_for_status()
                data = response.json()
                items = []
                for slot in data.get("list", []):
                    main = slot.get("main", {})
                    weather = slot.get("weather", [{}])[0]
                    wind = slot.get("wind", {})
                    items.append({
                        "dt": slot.get("dt"),
                        "dt_txt": slot.get("dt_txt", ""),
                        "temp": main.get("temp"),
                        "feels_like": main.get("feels_like"),
                        "temp_min": main.get("temp_min"),
                        "temp_max": main.get("temp_max"),
                        "humidity": main.get("humidity"),
                        "pressure": main.get("pressure"),
                        "pop": slot.get("pop", 0.0),       # probability of precipitation 0–1
                        "rain_3h": slot.get("rain", {}).get("3h"),
                        "clouds": slot.get("clouds", {}).get("all", 0),
                        "wind_speed": wind.get("speed"),
                        "wind_deg": wind.get("deg"),
                        "icon": weather.get("icon", ""),
                        "description": weather.get("description", ""),
                        "main": weather.get("main", ""),
                    })
                logger.info(f"Fetched {len(items)} forecast slots")
                return items
            except Exception as e:
                logger.warning(f"Forecast fetch failed: {e}")
                return []

    async def fetch_uvi(self, lat: float, lon: float) -> Optional[float]:
        """Fetch current UV index from OWM /uvi endpoint."""
        params = {"lat": lat, "lon": lon, "appid": self.api_key}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(self.uvi_url, params=params)
                response.raise_for_status()
                uvi = response.json().get("value")
                logger.info(f"Fetched UV index: {uvi}")
                return uvi
            except Exception as e:
                logger.warning(f"UV index fetch failed: {e}")
                return None

    def parse_weather_response(self, data: dict, location: str, lat: float, lon: float) -> dict:
        """
        Parse OpenWeatherMap API response into Weather model format

        Args:
            data: API response
            location: Location name
            lat: Latitude
            lon: Longitude

        Returns:
            Dictionary ready for Weather model
        """
        main = data.get("main", {})
        weather = data.get("weather", [{}])[0]
        wind = data.get("wind", {})
        rain = data.get("rain", {})
        sys = data.get("sys", {})

        return {
            "location": location,
            "latitude": lat,
            "longitude": lon,
            "temperature": main.get("temp", 0.0),
            "feels_like": main.get("feels_like", 0.0),
            "temp_min": main.get("temp_min", 0.0),
            "temp_max": main.get("temp_max", 0.0),
            "description": weather.get("description", ""),
            "icon": weather.get("icon", ""),
            "main": weather.get("main", ""),
            "humidity": main.get("humidity", 0),
            "pressure": main.get("pressure", 0),
            "wind_speed": wind.get("speed", 0.0),
            "wind_deg": wind.get("deg"),
            "clouds": data.get("clouds", {}).get("all", 0),
            "visibility": data.get("visibility"),
            "rain_1h": rain.get("1h"),
            "rain_3h": rain.get("3h"),
            "sunrise": datetime.fromtimestamp(sys.get("sunrise")) if sys.get("sunrise") else None,
            "sunset": datetime.fromtimestamp(sys.get("sunset")) if sys.get("sunset") else None,
            "fetched_at": datetime.utcnow(),
            "is_current": True
        }

    async def save_weather(self, session: AsyncSession, weather_data: dict) -> Weather:
        """
        Save weather data to database

        Args:
            session: Database session
            weather_data: Parsed weather data

        Returns:
            Saved Weather object
        """
        location = weather_data["location"]

        # Mark previous records as not current
        await session.execute(
            update(Weather)
            .where(Weather.location == location)
            .values(is_current=False)
        )

        # Create new weather record
        weather = Weather(**weather_data)
        session.add(weather)
        await session.commit()
        await session.refresh(weather)

        logger.info(f"Saved weather for {location}: {weather.temperature}°C, {weather.description}")
        return weather

    async def update_weather_for_location(
        self,
        session: AsyncSession,
        location: str,
        lat: float,
        lon: float
    ) -> Weather:
        """
        Fetch current weather + 5-day forecast + UV index, then save to DB.

        Args:
            session: Database session
            location: Location name
            lat: Latitude
            lon: Longitude

        Returns:
            Saved Weather object
        """
        # Fetch all three in parallel
        raw_data, forecast_items, uvi = await asyncio.gather(
            self.fetch_weather(location, lat, lon),
            self.fetch_forecast(lat, lon),
            self.fetch_uvi(lat, lon),
            return_exceptions=True,
        )

        if isinstance(raw_data, Exception):
            raise raw_data

        weather_data = self.parse_weather_response(raw_data, location, lat, lon)

        # Build JSONB forecast payload
        forecast_payload: dict = {}
        if not isinstance(forecast_items, Exception) and forecast_items:
            forecast_payload["hourly"] = forecast_items
        if not isinstance(uvi, Exception) and uvi is not None:
            forecast_payload["uv_index"] = uvi

        if forecast_payload:
            weather_data["forecast"] = forecast_payload

        return await self.save_weather(session, weather_data)

    async def update_all_locations(self, session: AsyncSession) -> list[Weather]:
        """
        Update weather for all configured locations

        Args:
            session: Database session

        Returns:
            List of saved Weather objects
        """
        results = []

        for location, coords in LOCATIONS.items():
            try:
                weather = await self.update_weather_for_location(
                    session,
                    location,
                    coords["lat"],
                    coords["lon"]
                )
                results.append(weather)

            except Exception as e:
                logger.error(f"Failed to update weather for {location}: {e}")

        logger.info(f"Updated weather for {len(results)}/{len(LOCATIONS)} locations")
        return results

    async def get_current_weather(self, session: AsyncSession, location: str) -> Optional[Weather]:
        """
        Get current weather from database for a location

        Args:
            session: Database session
            location: Location name

        Returns:
            Current Weather object or None
        """
        result = await session.execute(
            select(Weather)
            .where(Weather.location == location, Weather.is_current == True)
            .order_by(Weather.fetched_at.desc())
        )
        return result.scalar_one_or_none()
