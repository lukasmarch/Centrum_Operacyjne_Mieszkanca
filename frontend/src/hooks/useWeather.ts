import { useState, useEffect } from 'react';
import { WeatherData } from '../../types';

// Backend API response
interface WeatherApiResponse {
  location: string;
  temperature: number;
  feels_like: number;
  description: string;
  humidity: number;
  wind_speed: number;
  icon: string;
  fetched_at: string;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useWeather(location: string = 'Rybno') {
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchWeather = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${API_URL}/api/weather/${location}`);

        if (!response.ok) {
          throw new Error('Nie udało się pobrać danych pogody');
        }

        const data: WeatherApiResponse = await response.json();

        // Map backend data to frontend format
        const mappedWeather: WeatherData = {
          temp: Math.round(data.temperature),
          condition: data.description,
          humidity: data.humidity,
          windSpeed: Math.round(data.wind_speed * 3.6), // m/s to km/h
          lakeTemp: undefined, // TODO: Add lake data
          lakeLevel: undefined,
          icon: data.icon
        };

        setWeather(mappedWeather);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Błąd pobierania pogody');
        setWeather(null);
      } finally {
        setLoading(false);
      }
    };

    fetchWeather();

    // Refresh every 15 minutes
    const interval = setInterval(fetchWeather, 15 * 60 * 1000);

    return () => clearInterval(interval);
  }, [location]);

  return { weather, loading, error };
}
