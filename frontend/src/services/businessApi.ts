/**
 * Wizytówki firm — API katalogu (sprint B)
 * Model 3 poziomów: rejestrowa → przejęta (0 zł) → Firma lokalna (49 zł/mc)
 */
import { getAccessToken } from './authApi';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const API_ORIGIN = API_BASE.replace(/\/api\/?$/, '');

/** Zamienia ścieżkę względną (np. logo_url z backendu) na pełny URL do api.rybnolive.pl */
export function getAssetUrl(path?: string | null): string {
    if (!path) return '';
    if (/^https?:\/\//.test(path)) return path;
    return `${API_ORIGIN}${path}`;
}

function authHeaders(json = false): Record<string, string> {
    const headers: Record<string, string> = {};
    const token = getAccessToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (json) headers['Content-Type'] = 'application/json';
    return headers;
}

export interface BusinessProfilePublic {
    description?: string | null;
    telefon?: string | null;
    email?: string | null;
    www?: string | null;
    godziny?: string | null;
    logo_url?: string | null;
    is_premium: boolean;
}

export interface CatalogCard {
    id: number;
    nazwa: string;
    miasto: string;
    branza?: string | null;
    status: string;
    data_rozpoczecia?: string | null;
    profile: BusinessProfilePublic;
}

/**
 * Firma właściciela portalu — nie pokazujemy jej jako „Polecane w Rybnie".
 *
 * Dopóki katalog jest pusty, wyróżniona wizytówka właściciela czyta się jako reklama
 * samego siebie — a to pierwsza rzecz, którą zobaczy przedsiębiorca, któremu sprzedajemy
 * plan Firma lokalna. Wizytówka zostaje w katalogu jako zwykła; traci tylko status
 * promowanej. Regułę usuwamy, gdy w katalogu będzie kilka realnych firm.
 */
const OWNER_BUSINESS_PATTERNS = ['lu-mar-go', 'lumargo', 'lu mar go'];

export function isOwnerBusiness(nazwa?: string | null): boolean {
    if (!nazwa) return false;
    const normalized = nazwa.toLowerCase();
    return OWNER_BUSINESS_PATTERNS.some(pattern => normalized.includes(pattern));
}

/** Wizytówki nadające się do ekspozycji „Polecane" — premium i nie należące do właściciela. */
export function promotableCards(cards: CatalogCard[]): CatalogCard[] {
    return cards.filter(c => c.profile.is_premium && !isOwnerBusiness(c.nazwa));
}

export interface MyClaim {
    claim_id: number;
    business_id: number;
    nazwa: string;
    claim_status: 'pending' | 'verified' | 'rejected';
    is_premium: boolean;
    views_count: number;
}

export interface PendingClaim {
    claim_id: number;
    business_id: number;
    nazwa: string;
    miasto: string;
    nip: string;
    user_email: string;
    note?: string | null;
    telefon?: string | null;
    email?: string | null;
    created_at: string;
    /** 'ceidg' — dane potwierdza rejestr, sprawdzamy tylko właściciela.
     *  'manual' — firma dopisana ręcznie, trzeba potwierdzić też jej istnienie. */
    source?: 'ceidg' | 'manual';
}

/** Firma spoza CEIDG — dopisywana przez właściciela (spółka, oddział, KGW) */
export interface ManualBusinessInput {
    nazwa: string;
    miasto: string;
    nip?: string;
    ulica?: string;
    budynek?: string;
    kod_pocztowy?: string;
    branza?: string;
    telefon?: string;
    email?: string;
    www?: string;
    note?: string;
}

/** Katalog wizytówek (strona główna zakładki) — premium na górze */
export async function fetchCatalog(): Promise<CatalogCard[]> {
    const res = await fetch(`${API_BASE}/business/catalog`);
    if (!res.ok) throw new Error(`Failed to fetch catalog: ${res.status}`);
    return res.json();
}

/** Przejmij wizytówkę (wymaga zalogowania) */
export async function claimBusiness(businessId: number, data: {
    telefon?: string;
    email?: string;
    www?: string;
    note?: string;
}): Promise<{ status: string; message: string }> {
    const res = await fetch(`${API_BASE}/business/${businessId}/claim`, {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify(data),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Wystąpił błąd' }));
        throw new Error(err.detail || `Błąd: ${res.status}`);
    }
    return res.json();
}

/** Miejscowości gminy Rybno — jedyna lista dopuszczalna przy wpisie ręcznym.
 *  Pobierana z backendu, bo tam stoi oryginał (AVAILABLE_LOCATIONS w types.ts
 *  to pozycje harmonogramu odpadów, nie miejscowości). */
export async function fetchGminaLocalities(): Promise<string[]> {
    const res = await fetch(`${API_BASE}/business/gmina-localities`);
    if (!res.ok) return [];
    return res.json();
}

/** Dodaj firmę, której nie ma w CEIDG (wymaga zalogowania).
 *  Wpis jest niewidoczny publicznie, dopóki nie zatwierdzi go człowiek. */
export async function addManualBusiness(
    data: ManualBusinessInput,
): Promise<{ status: string; claim_id: number; business_id: number; message: string }> {
    const res = await fetch(`${API_BASE}/business/manual`, {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify(data),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Wystąpił błąd' }));
        throw new Error(err.detail || `Błąd: ${res.status}`);
    }
    return res.json();
}

/** Moje przejęte wizytówki */
export async function fetchMyClaims(): Promise<MyClaim[]> {
    const res = await fetch(`${API_BASE}/business/my-claims`, { headers: authHeaders() });
    if (!res.ok) return [];
    return res.json();
}

/** Edycja wizytówki (zweryfikowany właściciel) */
export async function updateBusinessProfile(businessId: number, data: {
    description?: string;
    telefon?: string;
    email?: string;
    www?: string;
    godziny?: string;
}): Promise<void> {
    const res = await fetch(`${API_BASE}/business/${businessId}/profile`, {
        method: 'PATCH',
        headers: authHeaders(true),
        body: JSON.stringify(data),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Wystąpił błąd' }));
        throw new Error(err.detail || `Błąd: ${res.status}`);
    }
}

/** Upload logo wizytówki (max 2MB, jpg/png/webp) — zwraca nowy logo_url */
export async function uploadBusinessLogo(businessId: number, file: File): Promise<string> {
    const form = new FormData();
    form.append('logo', file);
    const res = await fetch(`${API_BASE}/business/${businessId}/logo`, {
        method: 'POST',
        headers: authHeaders(), // bez Content-Type — przeglądarka ustawi boundary multipart
        body: form,
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Wystąpił błąd' }));
        throw new Error(err.detail || `Błąd: ${res.status}`);
    }
    const data = await res.json();
    return data.logo_url;
}

// ── Ogłoszenia firm (Radar Lokalnego Biznesu, plan Firma lokalna) ──

export type AnnouncementType = 'ogloszenie' | 'okazja';

export interface BusinessAnnouncement {
    id: number;
    business_id: number;
    type: AnnouncementType;
    title: string;
    body: string;
    valid_until?: string | null;
    is_active: boolean;
    created_at: string;
}

export interface ActiveAnnouncement {
    id: number;
    business_id: number;
    type: AnnouncementType;
    title: string;
    body: string;
    valid_until?: string | null;
    created_at: string;
    nazwa: string;
    miasto: string;
    branza?: string | null;
    telefon?: string | null;
    logo_url?: string | null;
}

/** Aktywne ogłoszenia/okazje — kafel na stronie głównej, feed, newsletter */
export async function fetchActiveAnnouncements(limit = 10): Promise<ActiveAnnouncement[]> {
    const res = await fetch(`${API_BASE}/business/announcements/active?limit=${limit}`);
    if (!res.ok) return [];
    return res.json();
}

/** Ogłoszenia właściciela wizytówki (panel firmy) */
export async function fetchMyAnnouncements(businessId: number): Promise<BusinessAnnouncement[]> {
    const res = await fetch(`${API_BASE}/business/${businessId}/announcements`, { headers: authHeaders() });
    if (!res.ok) return [];
    return res.json();
}

/** Publikacja ogłoszenia/okazji (limity: 2 ogłoszenia/mc, 8 okazji/mc) */
export async function createAnnouncement(businessId: number, data: {
    type: AnnouncementType;
    title: string;
    body: string;
    valid_until?: string;
}): Promise<BusinessAnnouncement> {
    const res = await fetch(`${API_BASE}/business/${businessId}/announcements`, {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify(data),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Wystąpił błąd' }));
        throw new Error(err.detail || `Błąd: ${res.status}`);
    }
    return res.json();
}

/** Wycofanie ogłoszenia (soft delete) */
export async function deactivateAnnouncement(announcementId: number): Promise<void> {
    const res = await fetch(`${API_BASE}/business/announcements/${announcementId}`, {
        method: 'DELETE',
        headers: authHeaders(),
    });
    if (!res.ok) throw new Error(`Błąd wycofania: ${res.status}`);
}

/**
 * Licznik wizytówki (fire-and-forget). DWIE różne miary — nie mieszać:
 *
 * `impression` — karta pojawiła się na ekranie. Mówi tylko tyle, ile „ktoś
 *   przeszedł obok wystawy": jedno wejście do katalogu to pokaz dla KAŻDEJ
 *   widocznej firmy.
 * `contact` — ktoś kliknął telefon, www albo e-mail. Dopiero to znaczy,
 *   że się zatrzymał, i tylko tę liczbę wolno sprzedawać firmie.
 *
 * Do 12.08.2026 istniała jedna funkcja wołana przy renderowaniu karty, a jej
 * wynik szedł do klienta jako „wyświetlenia wizytówki".
 */
export function trackBusinessImpression(businessId: number): void {
    fetch(`${API_BASE}/business/${businessId}/view?kind=impression`, { method: 'POST' })
        .catch(() => {});
}

export function trackBusinessContact(businessId: number): void {
    fetch(`${API_BASE}/business/${businessId}/view?kind=contact`, { method: 'POST' })
        .catch(() => {});
}

// ── Admin ──

export async function fetchPendingClaims(): Promise<PendingClaim[]> {
    const res = await fetch(`${API_BASE}/business/claims/pending`, { headers: authHeaders() });
    if (!res.ok) return [];
    return res.json();
}

export async function moderateClaim(claimId: number, action: 'approve' | 'reject'): Promise<void> {
    const res = await fetch(`${API_BASE}/business/claims/${claimId}?action=${action}`, {
        method: 'PATCH',
        headers: authHeaders(),
    });
    if (!res.ok) throw new Error(`Błąd moderacji: ${res.status}`);
}
