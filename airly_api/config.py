"""
Airly API Configuration
"""
import os
from dataclasses import dataclass


@dataclass
class Config:
    """Configuration for Airly API client."""
    
    # API Configuration
    API_KEY: str = os.getenv("AIRLY_API_KEY", "")
    BASE_URL: str = "https://airapi.airly.eu/v2"
    
    # Location: Rybno, powiat Działdowski, woj. Warmińsko-Mazurskie
    RYBNO_LAT: float = 53.3825
    RYBNO_LNG: float = 19.9278
    
    # Request settings
    MAX_DISTANCE_KM: float = 25.0  # Max distance to search for installations
    TIMEOUT_SECONDS: int = 30
    
    def __post_init__(self):
        if not self.API_KEY:
            raise ValueError(
                "AIRLY_API_KEY environment variable is required. "
                "Get your free API key at https://developer.airly.org/register"
            )


config = Config()
