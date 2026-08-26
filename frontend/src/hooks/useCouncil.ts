import { useCallback, useEffect, useState } from 'react';

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api';

/**
 * Skróty obrad Rady Gminy.
 *
 * Dwa zapytania zamiast jednego, bo lista i skrót mają różne rozmiary: punkty
 * jednej sesji to kilka kilobajtów i na liście nie mają czego robić. Endpoint
 * listy zwraca sam nagłówek i lead, pełny skrót dochodzi przy rozwinięciu.
 *
 * ⚠️ API wydaje **wyłącznie sesje w stanie `published`** — to ta sama bramka
 * akceptacji, przez którą przechodzi człowiek. Pusta lista przy działającym
 * backendzie nie jest awarią: znaczy, że żaden skrót nie został jeszcze
 * zatwierdzony.
 */

export interface CouncilPoint {
    title: string;
    description: string;
    timestamp: string;
    quote?: string | null;
    speaker?: string | null;
    /** Link do nagrania przewinięty na minutę, w której sprawa padła */
    watch_url?: string | null;
}

export interface CouncilResolution {
    subject: string;
    number?: string | null;
    outcome?: string | null;
    timestamp?: string | null;
    watch_url?: string | null;
}

export interface CouncilSummary {
    headline?: string;
    lead?: string;
    points?: CouncilPoint[];
    resolutions?: CouncilResolution[];
    is_substantive?: boolean;
}

export interface CouncilSession {
    id: number;
    title: string;
    session_number: string | null;
    session_date: string | null;
    page_url: string;
    video_url: string | null;
    duration_min: number | null;
    published_at: string | null;
    headline?: string | null;
    lead?: string | null;
    summary?: CouncilSummary;
}

export function useCouncilSessions() {
    const [sessions, setSessions] = useState<CouncilSession[] | null>(null);
    const [failed, setFailed] = useState(false);

    useEffect(() => {
        let alive = true;
        fetch(`${API_URL}/council/sessions`)
            .then(r => (r.ok ? r.json() : Promise.reject(r.status)))
            .then(data => alive && setSessions(data.sessions ?? []))
            .catch(() => alive && setFailed(true));
        return () => { alive = false; };
    }, []);

    return { sessions, failed, loading: sessions === null && !failed };
}

/**
 * Pełny skrót jednej sesji, pobierany dopiero przy rozwinięciu i pamiętany.
 * Mieszkaniec otwiera zwykle jedną sesję — ściąganie wszystkich punktów z góry
 * byłoby kilkudziesięcioma kilobajtami na zapas.
 */
export function useCouncilDetails() {
    const [details, setDetails] = useState<Record<number, CouncilSession>>({});
    const [pending, setPending] = useState<number | null>(null);

    const load = useCallback((id: number) => {
        if (details[id]) return;
        setPending(id);
        fetch(`${API_URL}/council/sessions/${id}`)
            .then(r => (r.ok ? r.json() : Promise.reject(r.status)))
            .then(data => setDetails(prev => ({ ...prev, [id]: data })))
            .catch(() => undefined)
            .finally(() => setPending(current => (current === id ? null : current)));
    }, [details]);

    return { details, pending, load };
}
