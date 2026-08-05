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

/**
 * `generated_at` przychodzi z backendu jako naiwny UTC (`datetime.utcnow()`
 * w `DailySummary`), czyli napis BEZ oznaczenia strefy. `new Date("2026-08-05T11:30:23")`
 * czyta taki napis jako czas LOKALNY, więc briefing odświeżony o 13:30 wyglądał
 * na wygenerowany o 11:30 — dwie godziny starszy, niż jest naprawdę.
 */
function parseUtc(raw: string): Date | null {
    if (!raw) return null;
    const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(raw);
    const parsed = new Date(hasZone ? raw : `${raw}Z`);
    return isNaN(parsed.getTime()) ? null : parsed;
}

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
                setSummaryState(cachedSummary.data);
                setLastUpdated(cachedSummary.generatedAt);
                setLoading(false);
                setError(null);
                return;
            }

            try {
                setLoading(true);
                const response = await fetch(`${API_URL}/summary/daily`);

                if (!response.ok) {
                    throw new Error('Nie udało się pobrać podsumowania');
                }

                const data: DailySummaryApiResponse = await response.json();

                // The content field contains the actual summary structure
                const generatedAt = parseUtc(data.generated_at);
                setSummaryState(data.content);
                setSummary(data.content, generatedAt); // Store in cache
                setLastUpdated(generatedAt);
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

