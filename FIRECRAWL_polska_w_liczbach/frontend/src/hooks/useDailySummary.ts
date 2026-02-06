import { useState, useEffect } from 'react';
import { DailySummary } from '../../types';
import { useDataCache } from '../context/DataCacheContext';

// Backend API response
interface DailySummaryApiResponse {
    id: number;
    date: string;
    headline: string;
    content: DailySummary;
    generated_at: string;
}

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';

export function useDailySummary() {
    const { getSummary, setSummary } = useDataCache();
    const [summary, setSummaryState] = useState<DailySummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

    useEffect(() => {
        const fetchSummary = async () => {
            // Check cache first
            const cachedSummary = getSummary();
            if (cachedSummary) {
                setSummaryState(cachedSummary);
                setLoading(false);
                setError(null);
                return;
            }

            try {
                setLoading(true);
                const response = await fetch(`${API_URL}/api/summary/daily`);

                if (!response.ok) {
                    throw new Error('Nie udało się pobrać podsumowania');
                }

                const data: DailySummaryApiResponse = await response.json();

                // The content field contains the actual summary structure
                setSummaryState(data.content);
                setSummary(data.content); // Store in cache
                setLastUpdated(new Date(data.generated_at));
                setError(null);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Błąd pobierania podsumowania');
                setSummaryState(null);
            } finally {
                setLoading(false);
            }
        };

        fetchSummary();

        // Refresh every 2 hours (cache duration)
        const interval = setInterval(fetchSummary, 2 * 60 * 60 * 1000);

        return () => clearInterval(interval);
    }, [getSummary, setSummary]);

    return { summary, loading, error, lastUpdated };
}

