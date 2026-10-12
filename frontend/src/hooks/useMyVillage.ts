import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api';

/**
 * Wieś czytelnika — jedno pytanie, na którym stoi cały pulpit.
 *
 * Krytyka 11.10.2026: strona pytała o miejscowość w trzech miejscach naraz
 * (kafel odpadów „Wybierz miejscowość” bez wyboru, szara lista w prośbie
 * o push, profil), a gość nie dostawał w zamian nic. Teraz odpowiedź pada
 * raz i od razu działa w trzech miejscach: belka awarii, wywóz, push.
 *
 * Dwa reżimy (decyzja 11.10.2026):
 * - **Gość** wybiera dowolną wieś; wybór zostaje na urządzeniu (localStorage).
 * - **Zalogowany** zaczyna ZAWSZE od wsi z konta. Może przełączyć się na inną
 *   (sprawdza, co u rodziców), ale to podgląd na czas wizyty (sessionStorage),
 *   nie zmiana konta — ta zostaje w profilu. Wcześniej wieś wybrana jako gość
 *   wygrywała z kontem także po zalogowaniu, więc konto „Żabiny” oglądało Rybno,
 *   a główka i górny pasek pokazywały dwie różne wsie naraz.
 *
 * ⚠️ Lista wsi pochodzi z backendu (`alert_policy.GMINA_RYBNO_PLACES`, 22 nazwy),
 * NIE z harmonogramu odpadów (24 pozycje z „Rybno R1/R2”). To dwie różne listy
 * — patrz `wasteTown.ts`.
 */
const GUEST_KEY = 'rl_village';
const SESSION_KEY = 'rl_village_view';

const read = (store: () => Storage, key: string): string | null => {
    try {
        return store().getItem(key);
    } catch {
        return null;
    }
};

const write = (store: () => Storage, key: string, value: string | null) => {
    try {
        if (value) store().setItem(key, value);
        else store().removeItem(key);
    } catch {
        // bez pamięci wybór obowiązuje do końca wizyty
    }
};

const local = () => localStorage;
const session = () => sessionStorage;

/** „Rybno R1” z konta → „Rybno” (rejon wywozu to nie nazwa wsi). */
export const villageFromAccount = (location?: string | null): string | null =>
    location ? location.replace(/\s+R\d+$/i, '').trim() || null : null;

/** Wieś zapamiętana przez gościa — podpowiedź dla formularza rejestracji. */
export const guestVillage = (): string | null => read(local, GUEST_KEY);

export interface MyVillage {
    village: string | null;
    /** Wieś z konta (`null` dla gościa) */
    accountVillage: string | null;
    /** Zalogowany ogląda teraz inną wieś niż swoją */
    isPreview: boolean;
    places: string[];
    setVillage: (name: string | null) => void;
}

export function useMyVillage(): MyVillage {
    const { user, isAuthenticated } = useAuth();
    const accountVillage = isAuthenticated ? villageFromAccount(user?.location) : null;
    const [guest, setGuest] = useState<string | null>(() => read(local, GUEST_KEY));
    // Klucz z id konta: podgląd jednej osoby nie przechodzi na drugą przy przelogowaniu
    const viewKey = `${SESSION_KEY}_${user?.id ?? ''}`;
    const [view, setView] = useState<string | null>(() => read(session, viewKey));
    const [places, setPlaces] = useState<string[]>([]);

    useEffect(() => { setView(read(session, viewKey)); }, [viewKey]);

    useEffect(() => {
        let cancelled = false;
        fetch(`${API_URL}/business/gmina-localities`)
            .then(res => (res.ok ? res.json() : []))
            .then(data => { if (!cancelled && Array.isArray(data)) setPlaces(data); })
            .catch(() => { if (!cancelled) setPlaces([]); });
        return () => { cancelled = true; };
    }, []);

    const setVillage = useCallback((name: string | null) => {
        if (isAuthenticated) {
            // Powrót do wsi z konta kasuje podgląd — nie zostawiamy „wyboru” równego kontu
            const next = name && name !== accountVillage ? name : null;
            write(session, viewKey, next);
            setView(next);
        } else {
            write(local, GUEST_KEY, name);
            setGuest(name);
        }
    }, [isAuthenticated, accountVillage, viewKey]);

    if (isAuthenticated) {
        const village = view ?? accountVillage;
        return { village, accountVillage, isPreview: !!view && view !== accountVillage, places, setVillage };
    }
    return { village: guest, accountVillage: null, isPreview: false, places, setVillage };
}
