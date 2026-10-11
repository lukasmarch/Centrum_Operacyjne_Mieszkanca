import { wasteData } from '../data/wasteSchedule';

/**
 * Która pozycja harmonogramu odpadów należy do czytelnika — albo `null`,
 * gdy tego nie wiemy.
 *
 * „Rybno” ma DWA rejony (R1 i R2), różniące się o tydzień. Do 11.10.2026
 * front po cichu zamieniał „Rybno” na R1 (audyt F-039), więc mieszkaniec R2
 * i każdy anonim dostawali na stronie głównej cudzy termin wywozu, podany
 * pewnym tonem. Niepewność ma być widoczna: `null` = „wybierz miejscowość”.
 *
 * Kolejność: wybór zapamiętany na stronie odpadów → miejscowość z konta,
 * gdy jest dokładną pozycją harmonogramu → JEDYNA pozycja zaczynająca się
 * od tej nazwy. Dwie pasujące pozycje to brak odpowiedzi, nie pierwsza z nich.
 * Ta sama reguła co `waste_policy.match_towns` w backendzie (bez „zawiera”).
 */
const STORAGE_KEY = 'rl_waste_town';

export const wasteTowns = (): string[] =>
    Object.keys(wasteData).sort((a, b) => a.localeCompare(b, 'pl'));

export function storedWasteTown(): string | null {
    try {
        const saved = localStorage.getItem(STORAGE_KEY);
        return saved && saved in wasteData ? saved : null;
    } catch {
        return null; // tryb prywatny bez localStorage
    }
}

export function rememberWasteTown(town: string): void {
    try {
        localStorage.setItem(STORAGE_KEY, town);
    } catch {
        // bez pamięci wybór obowiązuje do końca wizyty
    }
}

export function resolveWasteTown(profileLocation?: string | null): string | null {
    const stored = storedWasteTown();
    if (stored) return stored;
    if (!profileLocation) return null;
    if (profileLocation in wasteData) return profileLocation;
    const matches = Object.keys(wasteData).filter(name => name.startsWith(profileLocation));
    return matches.length === 1 ? matches[0] : null;
}
