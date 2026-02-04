#!/usr/bin/env python3
"""
Fetch air quality data for Rybno from Airly API

Usage:
    export AIRLY_API_KEY="your-api-key"
    python -m airly_api.fetch_data
"""
import json
import sys
from datetime import datetime

from .config import config
from .client import AirlyClient, AirlyAPIError


def format_measurement(name: str, value: float, unit: str) -> str:
    """Format a measurement value for display."""
    if value is None:
        return f"  {name}: brak danych"
    return f"  {name}: {value:.1f} {unit}"


def main():
    """Main function to fetch and display air quality data."""
    print("=" * 60)
    print("🌬️  Jakość Powietrza - Rybno, powiat Działdowski")
    print("=" * 60)
    print()
    
    try:
        client = AirlyClient()
    except ValueError as e:
        print(f"❌ Błąd konfiguracji: {e}")
        sys.exit(1)
    
    lat, lng = config.RYBNO_LAT, config.RYBNO_LNG
    print(f"📍 Lokalizacja: {lat}°N, {lng}°E")
    print()
    
    try:
        # Find nearest installations
        print("🔍 Szukam najbliższych stacji pomiarowych...")
        installations = client.get_nearest_installations(lat, lng)
        
        if not installations:
            print("❌ Nie znaleziono stacji w pobliżu")
            sys.exit(1)
        
        print(f"✅ Znaleziono {len(installations)} stacji:")
        for inst in installations:
            print(f"   • ID {inst.id}: {inst.display_name}")
        print()
        
        # Get measurements from nearest station
        nearest = installations[0]
        print(f"📊 Pobieram dane z najbliższej stacji (ID: {nearest.id})...")
        measurements = client.get_measurements(nearest.id)
        
        if not measurements.current:
            print("❌ Brak aktualnych pomiarów")
            sys.exit(1)
        
        current = measurements.current
        print()
        print("-" * 40)
        print("📈 AKTUALNE POMIARY")
        print("-" * 40)
        
        # Air quality index
        caqi = current.caqi
        if caqi:
            print()
            print(f"🎯 Indeks jakości powietrza (CAQI): {caqi.value:.0f}")
            print(f"   Poziom: {caqi.level_pl}")
            if caqi.description:
                print(f"   {caqi.description}")
            if caqi.advice:
                print(f"   💡 {caqi.advice}")
        
        # Measurements
        print()
        print("📏 Zanieczyszczenia:")
        if current.pm25 is not None:
            print(format_measurement("PM2.5", current.pm25, "µg/m³"))
        if current.pm10 is not None:
            print(format_measurement("PM10", current.pm10, "µg/m³"))
        
        # Check for other pollutants
        for v in current.values:
            if v.name not in ["PM25", "PM10", "TEMPERATURE", "HUMIDITY", "PRESSURE", "PM1"]:
                print(format_measurement(v.name, v.value, v.unit))
        
        print()
        print("🌡️  Warunki atmosferyczne:")
        if current.temperature is not None:
            print(format_measurement("Temperatura", current.temperature, "°C"))
        if current.humidity is not None:
            print(format_measurement("Wilgotność", current.humidity, "%"))
        if current.pressure is not None:
            print(format_measurement("Ciśnienie", current.pressure, "hPa"))
        
        # Standards
        if current.standards:
            print()
            print("📋 Normy:")
            for std in current.standards:
                status = "✅" if std.percent <= 100 else "⚠️"
                print(f"   {status} {std.name} ({std.pollutant}): {std.percent:.0f}% normy")
        
        print()
        print("-" * 40)
        print(f"⏰ Dane z: {current.from_datetime.strftime('%Y-%m-%d %H:%M')}")
        print(f"   do: {current.till_datetime.strftime('%Y-%m-%d %H:%M')}")
        print()
        
        # Export as JSON
        export_data = {
            "location": {
                "name": "Rybno",
                "lat": lat,
                "lng": lng
            },
            "installation": {
                "id": nearest.id,
                "name": nearest.display_name,
                "lat": nearest.location.latitude,
                "lng": nearest.location.longitude
            },
            "timestamp": datetime.now().isoformat(),
            "measurements": {
                "pm25": current.pm25,
                "pm10": current.pm10,
                "temperature": current.temperature,
                "humidity": current.humidity,
                "pressure": current.pressure
            },
            "caqi": {
                "value": caqi.value if caqi else None,
                "level": caqi.level if caqi else None,
                "level_pl": caqi.level_pl if caqi else None,
                "color": caqi.color if caqi else None
            } if caqi else None
        }
        
        print("💾 Dane JSON:")
        print(json.dumps(export_data, indent=2, ensure_ascii=False))
        
    except AirlyAPIError as e:
        print(f"❌ Błąd API: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
