"""
Airly API Data Models
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Location:
    """Geographic location."""
    latitude: float
    longitude: float


@dataclass
class Address:
    """Address information."""
    country: str = ""
    city: str = ""
    street: str = ""
    number: str = ""
    display_address1: str = ""
    display_address2: str = ""


@dataclass
class Installation:
    """Airly sensor installation."""
    id: int
    location: Location
    address: Address
    elevation: float = 0.0
    airly: bool = True
    sponsor: Optional[dict] = None
    
    @property
    def display_name(self) -> str:
        """Human-readable installation name."""
        if self.address.display_address1:
            return f"{self.address.display_address1}, {self.address.display_address2}"
        return f"{self.address.city}, {self.address.street} {self.address.number}"


@dataclass
class MeasurementValue:
    """Single measurement value."""
    name: str
    value: float
    
    @property
    def unit(self) -> str:
        """Get unit for measurement type."""
        units = {
            "PM1": "µg/m³",
            "PM25": "µg/m³",
            "PM10": "µg/m³",
            "TEMPERATURE": "°C",
            "HUMIDITY": "%",
            "PRESSURE": "hPa",
            "NO2": "µg/m³",
            "O3": "µg/m³",
            "CO": "µg/m³",
            "SO2": "µg/m³",
        }
        return units.get(self.name, "")


@dataclass
class Index:
    """Air quality index (CAQI)."""
    name: str
    value: float
    level: str
    description: str
    advice: str
    color: str
    
    @property
    def level_pl(self) -> str:
        """Polish translation of level."""
        levels = {
            "VERY_LOW": "Bardzo niski",
            "LOW": "Niski",
            "MEDIUM": "Średni",
            "HIGH": "Wysoki",
            "VERY_HIGH": "Bardzo wysoki",
            "EXTREME": "Ekstremalny",
            "AIRMAGEDDON": "Katastrofalny",
        }
        return levels.get(self.level, self.level)


@dataclass
class Standard:
    """Air quality standard."""
    name: str
    pollutant: str
    limit: float
    percent: float
    averaging: str = ""


@dataclass
class MeasurementData:
    """Measurement data for a time period."""
    from_datetime: datetime
    till_datetime: datetime
    values: list[MeasurementValue] = field(default_factory=list)
    indexes: list[Index] = field(default_factory=list)
    standards: list[Standard] = field(default_factory=list)
    
    def get_value(self, name: str) -> Optional[float]:
        """Get measurement value by name."""
        for v in self.values:
            if v.name == name:
                return v.value
        return None
    
    @property
    def pm25(self) -> Optional[float]:
        return self.get_value("PM25")
    
    @property
    def pm10(self) -> Optional[float]:
        return self.get_value("PM10")
    
    @property
    def temperature(self) -> Optional[float]:
        return self.get_value("TEMPERATURE")
    
    @property
    def humidity(self) -> Optional[float]:
        return self.get_value("HUMIDITY")
    
    @property
    def pressure(self) -> Optional[float]:
        return self.get_value("PRESSURE")
    
    @property
    def caqi(self) -> Optional[Index]:
        """Get CAQI index."""
        for idx in self.indexes:
            if idx.name == "AIRLY_CAQI":
                return idx
        return None


@dataclass
class Measurements:
    """Complete measurements response."""
    current: Optional[MeasurementData] = None
    history: list[MeasurementData] = field(default_factory=list)
    forecast: list[MeasurementData] = field(default_factory=list)
