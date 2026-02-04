"""
Airly API Client
"""
import requests
from datetime import datetime
from typing import Optional

from .config import config
from .models import (
    Location, Address, Installation, 
    MeasurementValue, Index, Standard, 
    MeasurementData, Measurements
)


class AirlyAPIError(Exception):
    """Custom exception for Airly API errors."""
    pass


class AirlyClient:
    """Client for Airly API."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize client with API key."""
        self.api_key = api_key or config.API_KEY
        self.base_url = config.BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "apikey": self.api_key
        })
    
    def _request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make API request."""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.get(
                url, 
                params=params, 
                timeout=config.TIMEOUT_SECONDS
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                raise AirlyAPIError("Invalid API key")
            elif response.status_code == 429:
                raise AirlyAPIError("API rate limit exceeded")
            raise AirlyAPIError(f"HTTP error: {e}")
        except requests.exceptions.RequestException as e:
            raise AirlyAPIError(f"Request failed: {e}")
    
    def _parse_installation(self, data: dict) -> Installation:
        """Parse installation from API response."""
        loc_data = data.get("location", {})
        addr_data = data.get("address", {})
        
        return Installation(
            id=data["id"],
            location=Location(
                latitude=loc_data.get("latitude", 0),
                longitude=loc_data.get("longitude", 0)
            ),
            address=Address(
                country=addr_data.get("country", ""),
                city=addr_data.get("city", ""),
                street=addr_data.get("street", ""),
                number=addr_data.get("number", ""),
                display_address1=addr_data.get("displayAddress1", ""),
                display_address2=addr_data.get("displayAddress2", "")
            ),
            elevation=data.get("elevation", 0.0),
            airly=data.get("airly", True),
            sponsor=data.get("sponsor")
        )
    
    def _parse_measurement_data(self, data: dict) -> MeasurementData:
        """Parse measurement data from API response."""
        values = [
            MeasurementValue(name=v["name"], value=v["value"])
            for v in data.get("values", [])
        ]
        
        indexes = [
            Index(
                name=idx["name"],
                value=idx.get("value", 0),
                level=idx.get("level", ""),
                description=idx.get("description", ""),
                advice=idx.get("advice", ""),
                color=idx.get("color", "#999999")
            )
            for idx in data.get("indexes", [])
        ]
        
        standards = [
            Standard(
                name=std["name"],
                pollutant=std["pollutant"],
                limit=std["limit"],
                percent=std["percent"],
                averaging=std.get("averaging", "")
            )
            for std in data.get("standards", [])
        ]
        
        from_dt = datetime.fromisoformat(
            data["fromDateTime"].replace("Z", "+00:00")
        )
        till_dt = datetime.fromisoformat(
            data["tillDateTime"].replace("Z", "+00:00")
        )
        
        return MeasurementData(
            from_datetime=from_dt,
            till_datetime=till_dt,
            values=values,
            indexes=indexes,
            standards=standards
        )
    
    def _parse_measurements(self, data: dict) -> Measurements:
        """Parse full measurements response."""
        current = None
        if data.get("current"):
            current = self._parse_measurement_data(data["current"])
        
        history = [
            self._parse_measurement_data(h) 
            for h in data.get("history", [])
        ]
        
        forecast = [
            self._parse_measurement_data(f) 
            for f in data.get("forecast", [])
        ]
        
        return Measurements(
            current=current,
            history=history,
            forecast=forecast
        )
    
    def get_nearest_installations(
        self, 
        lat: float, 
        lng: float, 
        max_distance_km: float = 25.0,
        max_results: int = 3
    ) -> list[Installation]:
        """Get nearest installations to a location."""
        data = self._request("installations/nearest", {
            "lat": lat,
            "lng": lng,
            "maxDistanceKM": max_distance_km,
            "maxResults": max_results
        })
        return [self._parse_installation(inst) for inst in data]
    
    def get_installation(self, installation_id: int) -> Installation:
        """Get installation by ID."""
        data = self._request(f"installations/{installation_id}")
        return self._parse_installation(data)
    
    def get_measurements(self, installation_id: int) -> Measurements:
        """Get measurements for an installation."""
        data = self._request("measurements/installation", {
            "installationId": installation_id
        })
        return self._parse_measurements(data)
    
    def get_nearest_measurements(
        self, 
        lat: float, 
        lng: float,
        max_distance_km: float = 25.0
    ) -> Measurements:
        """Get measurements from nearest installation."""
        data = self._request("measurements/nearest", {
            "lat": lat,
            "lng": lng,
            "maxDistanceKM": max_distance_km
        })
        return self._parse_measurements(data)
    
    def get_point_measurements(self, lat: float, lng: float) -> Measurements:
        """Get interpolated measurements for any point."""
        data = self._request("measurements/point", {
            "lat": lat,
            "lng": lng
        })
        return self._parse_measurements(data)
