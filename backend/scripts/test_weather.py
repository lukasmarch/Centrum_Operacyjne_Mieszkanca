#!/usr/bin/env python3
"""
Test weather integration - fetch weather for Rybno and Działdowo
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Load environment
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.integrations.weather import WeatherService, LOCATIONS
from src.database.schema import Weather


async def test_weather_integration():
    """Test fetching and saving weather data"""

    print("🌤️  Weather Integration Test\n")

    # Check API key
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("❌ OPENWEATHER_API_KEY not set in .env")
        print("   Get free API key from: https://openweathermap.org/api")
        return

    print(f"✓ API Key found: {api_key[:10]}...")

    # Database connection
    database_url = os.getenv("DATABASE_URL")
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Initialize service
    weather_service = WeatherService(api_key=api_key)

    async with async_session() as session:
        print(f"\n📍 Configured locations: {len(LOCATIONS)}")
        for name, coords in LOCATIONS.items():
            print(f"   - {name}: {coords['lat']}, {coords['lon']}")

        print("\n🌐 Fetching weather data...")

        # Update all locations
        results = await weather_service.update_all_locations(session)

        print(f"\n✅ Successfully updated {len(results)}/{len(LOCATIONS)} locations\n")

        # Display results
        print("=" * 60)
        for weather in results:
            print(f"\n📍 {weather.location}")
            print(f"   🌡️  Temperature: {weather.temperature}°C (feels like {weather.feels_like}°C)")
            print(f"   ☁️  Conditions: {weather.description}")
            print(f"   💧 Humidity: {weather.humidity}%")
            print(f"   🌬️  Wind: {weather.wind_speed} m/s")
            print(f"   🔻 Pressure: {weather.pressure} hPa")
            if weather.rain_1h:
                print(f"   🌧️  Rain (1h): {weather.rain_1h} mm")
            print(f"   📅 Fetched: {weather.fetched_at}")
        print("\n" + "=" * 60)

        # Test retrieving current weather
        print("\n🔄 Testing database retrieval...")
        for location in LOCATIONS.keys():
            current = await weather_service.get_current_weather(session, location)
            if current:
                print(f"   ✓ {location}: {current.temperature}°C")
            else:
                print(f"   ✗ {location}: No data found")

        # Count total weather records
        result = await session.execute(select(Weather))
        total_records = len(result.scalars().all())
        print(f"\n📊 Total weather records in DB: {total_records}")

    await engine.dispose()

    print("\n✅ Weather integration test completed!")


if __name__ == "__main__":
    asyncio.run(test_weather_integration())
