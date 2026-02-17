import { useState, useEffect } from 'react';
import { Event } from '../../types';

// Backend API response
// Event model from schema.py: 
// id, title, description, event_date, location, category, image_url...
const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';

export function useEvents(limit: number = 50) {
    const [events, setEvents] = useState<Event[] | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchEvents = async () => {
            try {
                setLoading(true);
                const response = await fetch(`${API_URL}/events?limit=${limit}`);

                if (!response.ok) {
                    throw new Error('Nie udało się pobrać wydarzeń');
                }

                const data: any[] = await response.json();

                // Map backend data to frontend Event interface
                // Frontend Event: id, title, date, location, category, isPromoted?
                const mappedEvents: Event[] = data.map(item => ({
                    id: String(item.id),
                    title: item.title,
                    date: item.event_date, // Keep as ISO string for proper parsing
                    location: item.location || 'Brak lokalizacji',
                    category: item.category || 'Inne',
                    isPromoted: item.is_featured,
                    imageUrl: item.image_url || undefined,
                    description: item.short_description || item.description || undefined,
                    externalUrl: item.external_url || undefined
                }));

                setEvents(mappedEvents);
                setError(null);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Błąd pobierania wydarzeń');
                setEvents(null);
            } finally {
                setLoading(false);
            }
        };

        fetchEvents();

        // Refresh every 5 minutes
        const interval = setInterval(fetchEvents, 5 * 60 * 1000);

        return () => clearInterval(interval);
    }, [limit]);

    return { events, loading, error };
}
