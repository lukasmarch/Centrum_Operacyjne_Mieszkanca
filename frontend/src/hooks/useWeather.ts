import { useState, useEffect } from 'react';
import { useDataCache } from '../context/DataCacheContext';

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api';

/**
 * Full API response from /api/weather/current
 * All fields now returned by the backend including sunrise/sunset/temp_min/temp_max.
 */
export interface WeatherFull {
  location: string;
  temperature: number;
  feels_like: number;
  temp_min: number;
  temp_max: number;
  description: string;
  icon: string;
  main: string;
  humidity: number;
  pressure: number;
  wind_speed: number;  // m/s
  wind_deg: number | null;
  clouds: number;      // %
  visibility: number | null;
  rain_1h: number | null;
  rain_3h: number | null;
  sunrise: string | null;  // ISO string
  sunset: string | null;   // ISO string
  fetched_at: string;
  // Derived UI helpers
  windKmh: number;
}

export function useWeather(location: string = 'Rybno') {
  const { getWeather, setWeather } = useDataCache();
  const [weather, setWeatherState] = useState<WeatherFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchWeather = async () => {
      // Check legacy cache (WeatherData type) – skip if we have fresh WeatherFull in sessionStorage
      const cacheKey = `weather_full_${location}`;
      const cached = sessionStorage.getItem(cacheKey);
      if (cached) {
        try {
          const parsed: WeatherFull = JSON.parse(cached);
          const age = Date.now() - new Date(parsed.fetched_at).getTime();
          if (age < 30 * 60 * 1000) { // 30 min
            setWeatherState(parsed);
            setLoading(false);
            return;
          }
        } catch { /* ignore */ }
      }

      try {
        setLoading(true);
        const response = await fetch(`${API_URL}/weather/current?location=${encodeURIComponent(location)}`);

        if (!response.ok) {
          throw new Error('Nie udało się pobrać danych pogody');
        }

        const data = await response.json();

        const mapped: WeatherFull = {
          ...data,
          windKmh: Math.round((data.wind_speed ?? 0) * 3.6),
        };

        setWeatherState(mapped);
        sessionStorage.setItem(cacheKey, JSON.stringify(mapped));
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Błąd pobierania pogody');
      } finally {
        setLoading(false);
      }
    };

    fetchWeather();
    const interval = setInterval(fetchWeather, 30 * 60 * 1000); // refresh every 30 min
    return () => clearInterval(interval);
  }, [location]);

  return { weather, loading, error };
}
