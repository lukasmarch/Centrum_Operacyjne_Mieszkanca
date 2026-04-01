import { useState, useEffect, useRef } from 'react';
import { BusStatusResponse, BusTimetableResponse } from '../../types';

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api';

export function useBusStatus() {
  const [status, setStatus] = useState<BusStatusResponse | null>(null);
  const [timetable, setTimetable] = useState<BusTimetableResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch timetable once on mount (static data, rarely changes)
  useEffect(() => {
    fetch(`${API}/bus/timetable`)
      .then(r => r.json())
      .then(setTimetable)
      .catch(() => setError('Brak połączenia z API'));
  }, []);

  // Fetch status every 30 seconds
  useEffect(() => {
    const fetchStatus = () => {
      fetch(`${API}/bus/status`)
        .then(r => r.json())
        .then(setStatus)
        .catch(() => {/* status silently fails, timetable still works */});
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 30_000);
    return () => clearInterval(interval);
  }, []);

  return { status, timetable, error };
}
