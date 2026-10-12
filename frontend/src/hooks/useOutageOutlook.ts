import { useEffect, useState } from 'react';

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api';

/** Pozycja przeglądu awarii — `backend/src/api/endpoints/outlook.py`. */
export interface OutageItem {
    id: number;
    title: string;
    kind: 'prad' | 'woda' | 'gaz' | 'pozar' | 'wypadek' | 'inne';
    label: string;
    places: string[];
    start: Date | null;
    end: Date | null;
    ongoing: boolean;
    reportedAt: Date | null;
    concernsVillage: boolean;
}

export interface OutageOutlook {
    items: OutageItem[];
    windowDays: number;
    /** Kiedy serwer sprawdził komunikaty — belka podaje to przy źródle */
    checkedAt: Date | null;
}

const toDate = (raw: string | null): Date | null => {
    if (!raw) return null;
    const d = new Date(raw);
    return isNaN(d.getTime()) ? null : d;
};

/**
 * Awarie w gminie: trwające i zapowiedziane na najbliższy tydzień.
 *
 * Trzy stany, bo każdy znaczy co innego dla belki: `undefined` — jeszcze nie
 * wiemy (belka się nie rysuje), `null` — zapytanie padło (belka mówi wprost,
 * że nie sprawdziła), obiekt — odpowiedź, także pusta. Pusta lista to „w
 * komunikatach nic nie zapowiedziano”, NIGDY „na pewno będzie prąd”.
 *
 * Odświeżanie co 10 min: zakładka pulpitu potrafi stać otwarta pół dnia,
 * a Energa dopisuje wyłączenia w ciągu dnia (okna 9/12/15/18/21).
 */
export function useOutageOutlook(village: string | null): OutageOutlook | null | undefined {
    const [outlook, setOutlook] = useState<OutageOutlook | null | undefined>(undefined);

    useEffect(() => {
        let cancelled = false;
        const load = () => {
            const query = village ? `?village=${encodeURIComponent(village)}` : '';
            fetch(`${API_URL}/alerts/outlook${query}`)
                .then(res => (res.ok ? res.json() : Promise.reject(res.status)))
                .then(data => {
                    if (cancelled) return;
                    setOutlook({
                        windowDays: data.window_days ?? 7,
                        checkedAt: toDate(data.checked_at),
                        items: (data.items ?? []).map((raw: any): OutageItem => ({
                            id: raw.id,
                            title: raw.title,
                            kind: raw.kind,
                            label: raw.label,
                            places: raw.places ?? [],
                            start: toDate(raw.start),
                            end: toDate(raw.end),
                            ongoing: Boolean(raw.ongoing),
                            reportedAt: toDate(raw.reported_at),
                            concernsVillage: Boolean(raw.concerns_village),
                        })),
                    });
                })
                .catch(() => { if (!cancelled) setOutlook(null); });
        };
        load();
        const timer = setInterval(load, 10 * 60_000);
        return () => { cancelled = true; clearInterval(timer); };
    }, [village]);

    return outlook;
}
