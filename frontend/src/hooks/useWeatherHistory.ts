import { useState, useEffect, useCallback } from 'react';

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api';

export interface WeatherHistoryPoint {
  temperature: number;
  humidity: number;
  wind_speed: number; // m/s from API
  fetched_at: string;
}

export function useWeatherHistory(location = 'Rybno', days = 1) {
  const [history, setHistory] = useState<WeatherHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch_ = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/weather/history?location=${location}&days=${days}`);
      if (res.ok) {
        const raw: WeatherHistoryPoint[] = await res.json();
        // Sample to at most 24 points for charts
        const step = Math.max(1, Math.floor(raw.length / 24));
        const sampled: WeatherHistoryPoint[] = [];
        for (let i = 0; i < raw.length; i += step) {
          sampled.push(raw[i]);
          if (sampled.length >= 24) break;
        }
        setHistory(sampled);
      }
    } catch {
      // silent – chart will just be empty
    } finally {
      setLoading(false);
    }
  }, [location, days]);

  useEffect(() => {
    fetch_();
    const id = setInterval(fetch_, 60 * 60 * 1000); // refresh every hour
    return () => clearInterval(id);
  }, [fetch_]);

  return { history, loading };
}
