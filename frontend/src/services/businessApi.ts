/**
 * Wizytówki firm — API katalogu (sprint B)
 * Model 3 poziomów: rejestrowa → przejęta (0 zł) → Firma lokalna (49 zł/mc)
 */
import { getAccessToken } from './authApi';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

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

/** Licznik wyświetleń wizytówki (fire-and-forget) */
export function trackBusinessView(businessId: number): void {
    fetch(`${API_BASE}/business/${businessId}/view`, { method: 'POST' }).catch(() => {});
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
