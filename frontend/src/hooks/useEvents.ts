import { useState, useEffect, useRef } from 'react';
import { TimedEvent } from '../utils/eventTime';

// Backend API response
// Event model from schema.py: 
// id, title, description, event_date, location, category, image_url...
// Fallback musi zawierać /api — endpointy doklejają samą ścieżkę („/events").
// Bez tego `npm run dev` bez jawnej zmiennej trafiał w :8000/events → 404:
// vite.config ma envDir wskazujący ../backend, więc frontend/.env NIE jest
// wczytywany, a produkcja działa tylko dlatego, że deploy-frontend.sh podaje
// VITE_API_URL w linii poleceń.
const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api';

export function useEvents(limit: number = 50) {
    const [events, setEvents] = useState<TimedEvent[] | null>(null);
    // `loading` tylko przy PIERWSZYM ładowaniu; odświeżenie w tle i błąd nie
    // kasują listy — ta sama zasada co w `useArticles` (audyt F-035)
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [fetchedAt, setFetchedAt] = useState<Date | null>(null);
    const hasData = useRef(false);

    useEffect(() => {
        const controller = new AbortController();
        hasData.current = false;
        setLoading(true);

        const fetchEvents = async () => {
            try {
                const response = await fetch(`${API_URL}/events?limit=${limit}`, { signal: controller.signal });

                if (!response.ok) {
                    throw new Error('Nie udało się pobrać wydarzeń');
                }

                const data: any[] = await response.json();

                // Map backend data to frontend Event interface
                // Frontend Event: id, title, date, location, category, isPromoted?
                const mappedEvents: TimedEvent[] = data.map(item => ({
                    id: String(item.id),
                    title: item.title,
                    date: item.event_date, // Keep as ISO string for proper parsing
                    // Brak miejsca to brak treści, nie napis „Brak lokalizacji” z pinezką
                    location: item.location || '',
                    category: item.category || 'Inne',
                    isPromoted: item.is_featured,
                    imageUrl: item.image_url || undefined,
                    description: item.short_description || item.description || undefined,
                    // Pełny opis obok skróconego: kafel Rady wyciąga z niego
                    // porządek obrad, którego `short_description` nie niesie
                    details: item.description || undefined,
                    externalUrl: item.external_url || undefined,
                    organizer: item.organizer || undefined,
                    sourceName: item.source_name || undefined,
                    // Koniec wydarzenia — bez niego kafle na stronie głównej nie
                    // mają jak odróżnić „trwa teraz" od „już było" i zapraszały
                    // na poranne posiedzenie komisji przez cały dzień
                    endDate: item.end_date || undefined,
                }));

                setEvents(mappedEvents);
                setFetchedAt(new Date());
                setError(null);
                hasData.current = true;
            } catch (err) {
                if (controller.signal.aborted) return;
                setError(err instanceof Error ? err.message : 'Błąd pobierania wydarzeń');
                if (!hasData.current) setEvents(null);
            } finally {
                if (!controller.signal.aborted) setLoading(false);
            }
        };

        fetchEvents();

        // Refresh every 5 minutes
        const interval = setInterval(fetchEvents, 5 * 60 * 1000);

        return () => {
            clearInterval(interval);
            controller.abort();
        };
    }, [limit]);

    return { events, loading, error, fetchedAt };
}
