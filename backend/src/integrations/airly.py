import os
import aiohttp
from typing import Optional, Dict, Any, List
from datetime import datetime

class AirlyClient:
    """Client for Airly API (Async)"""
    
    BASE_URL = "https://airapi.airly.eu/v2"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("AIRLY_API_KEY")
        if not self.api_key:
            raise ValueError("AIRLY_API_KEY is not set")
            
        self.headers = {
            "Accept": "application/json",
            "apikey": self.api_key
        }

    async def get_measurements(self, lat: float, lng: float) -> Dict[str, Any]:
        """Get measurements from nearest installation to coordinates."""
        async with aiohttp.ClientSession(headers=self.headers) as session:
            url = f"{self.BASE_URL}/measurements/nearest"
            params = {
                "lat": lat,
                "lng": lng,
                "maxDistanceKM": 25.0
            }
            
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Airly API error: {response.status} - {error_text}")
                
                return await response.json()

    def parse_measurements(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw API response into flat dictionary."""
        current = data.get("current", {})
        if not current:
            return {}
            
        # Extract values
        values = {v["name"]: v["value"] for v in current.get("values", [])}
        
        # Extract CAQI
        indexes = current.get("indexes", [])
        caqi = next((i for i in indexes if i["name"] == "AIRLY_CAQI"), {})
        
        return {
            "pm25": values.get("PM25"),
            "pm10": values.get("PM10"),
            "temperature": values.get("TEMPERATURE"),
            "humidity": values.get("HUMIDITY"),
            "pressure": values.get("PRESSURE"),
            "caqi": caqi.get("value"),
            "caqi_level": caqi.get("level"),
            "timestamp": datetime.fromisoformat(current["fromDateTime"].replace("Z", "+00:00"))
        }

# Singleton instance
airly_client = AirlyClient() if os.getenv("AIRLY_API_KEY") else None
