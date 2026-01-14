import { useState, useEffect } from 'react';
import { DailySummary } from '../../types';

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
    const [summary, setSummary] = useState<DailySummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

    useEffect(() => {
        const fetchSummary = async () => {
            try {
                setLoading(true);
                const response = await fetch(`${API_URL}/api/summary/daily`);

                if (!response.ok) {
                    throw new Error('Nie udało się pobrać podsumowania');
                }

                const data: DailySummaryApiResponse = await response.json();

                // The content field contains the actual summary structure
                setSummary(data.content);
                setLastUpdated(new Date(data.generated_at));
                setError(null);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Błąd pobierania podsumowania');
                setSummary(null);
            } finally {
                setLoading(false);
            }
        };

        fetchSummary();

        // Refresh every 15 minutes
        const interval = setInterval(fetchSummary, 15 * 60 * 1000);

        return () => clearInterval(interval);
    }, []);

    return { summary, loading, error, lastUpdated };
}
