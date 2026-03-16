import { useState, useEffect } from 'react';
import { HealthTodayResponse } from '../../types';

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';

export function useHealthToday() {
  const [data, setData] = useState<HealthTodayResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        setLoading(true);
        const response = await fetch(`${API_URL}/health/today`);

        if (!response.ok) {
          throw new Error('Nie udało się pobrać danych zdrowotnych');
        }

        const result: HealthTodayResponse = await response.json();
        setData(result);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Błąd pobierania danych');
        setData(null);
      } finally {
        setLoading(false);
      }
    };

    fetchHealth();

    // Refresh every 4 hours
    const interval = setInterval(fetchHealth, 4 * 60 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  return { data, loading, error };
}
