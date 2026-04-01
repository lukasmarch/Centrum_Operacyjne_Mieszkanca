import { useState, useEffect, useCallback } from 'react';

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api';

/**
 * Single 3-hour forecast slot from OWM /forecast stored in Weather.forecast JSONB.
 */
export interface ForecastSlot {
  dt: number;          // Unix timestamp
  dt_txt: string;      // "2026-04-01 15:00:00"
  temp: number;        // °C
  feels_like: number;
  temp_min: number;
  temp_max: number;
  humidity: number;
  pressure: number;
  pop: number;         // probability of precipitation 0–1
  rain_3h: number | null;
  clouds: number;      // %
  wind_speed: number;  // m/s
  wind_deg: number | null;
  icon: string;        // OWM icon code e.g. "01d"
  description: string;
  main: string;        // "Clear", "Clouds", "Rain"…
}

export interface WeatherForecast {
  hourly: ForecastSlot[];
  uv_index: number | null;
}

export function useWeatherForecast(location = 'Rybno') {
  const [forecast, setForecast] = useState<WeatherForecast | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_URL}/weather/forecast?location=${encodeURIComponent(location)}`
      );
      if (res.ok) {
        const data: WeatherForecast = await res.json();
        setForecast(data);
        setError(null);
      } else if (res.status === 404) {
        // Forecast JSONB not yet populated - will populate on next weather update
        setForecast(null);
        setError('no_data');
      } else {
        setError('fetch_error');
      }
    } catch {
      setError('network_error');
    } finally {
      setLoading(false);
    }
  }, [location]);

  useEffect(() => {
    fetchData();
    // Forecast data good for 3h (OWM free tier refresh rate)
    const id = setInterval(fetchData, 3 * 60 * 60 * 1000);
    return () => clearInterval(id);
  }, [fetchData]);

  return { forecast, loading, error };
}
