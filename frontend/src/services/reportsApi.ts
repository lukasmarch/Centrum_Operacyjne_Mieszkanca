/**
 * Zgłoszenie24 – Reports API Service
 * Frontend client for /api/reports/* endpoints
 */
import type { Report, ReportListResponse, ReportMapItem, ReportCategory } from '../../types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Fetch paginated list of reports
 */
export async function fetchReports(params: {
    page?: number;
    limit?: number;
    category?: ReportCategory;
    status?: string;
    sort?: 'newest' | 'popular' | 'severity';
} = {}): Promise<ReportListResponse> {
    const searchParams = new URLSearchParams();
    if (params.page) searchParams.set('page', String(params.page));
    if (params.limit) searchParams.set('limit', String(params.limit));
    if (params.category) searchParams.set('category', params.category);
    if (params.status) searchParams.set('status', params.status);
    if (params.sort) searchParams.set('sort', params.sort);

    const res = await fetch(`${API_BASE}/api/reports?${searchParams}`);
    if (!res.ok) throw new Error(`Failed to fetch reports: ${res.status}`);
    return res.json();
}

/**
 * Fetch a single report by ID
 */
export async function fetchReport(id: number): Promise<Report> {
    const res = await fetch(`${API_BASE}/api/reports/${id}`);
    if (!res.ok) throw new Error(`Failed to fetch report: ${res.status}`);
    return res.json();
}

/**
 * Fetch reports with GPS coordinates for map display
 */
export async function fetchReportsForMap(params: {
    category?: ReportCategory;
    status?: string;
    limit?: number;
} = {}): Promise<ReportMapItem[]> {
    const searchParams = new URLSearchParams();
    if (params.category) searchParams.set('category', params.category);
    if (params.status) searchParams.set('status', params.status);
    if (params.limit) searchParams.set('limit', String(params.limit));

    const res = await fetch(`${API_BASE}/api/reports/map?${searchParams}`);
    if (!res.ok) throw new Error(`Failed to fetch map reports: ${res.status}`);
    return res.json();
}

/**
 * Create a new report (multipart form with optional image upload)
 */
export async function createReport(data: {
    title: string;
    description: string;
    author_name?: string;
    author_email?: string;
    author_phone?: string;
    latitude?: number;
    longitude?: number;
    address?: string;
    location_name?: string;
    image?: File;
}): Promise<Report> {
    const formData = new FormData();
    formData.append('title', data.title);
    formData.append('description', data.description);
    if (data.author_name) formData.append('author_name', data.author_name);
    if (data.author_email) formData.append('author_email', data.author_email);
    if (data.author_phone) formData.append('author_phone', data.author_phone);
    if (data.latitude != null) formData.append('latitude', String(data.latitude));
    if (data.longitude != null) formData.append('longitude', String(data.longitude));
    if (data.address) formData.append('address', data.address);
    if (data.location_name) formData.append('location_name', data.location_name);
    if (data.image) formData.append('image', data.image);

    const res = await fetch(`${API_BASE}/api/reports`, {
        method: 'POST',
        body: formData,
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(err.detail || `Failed to create report: ${res.status}`);
    }
    return res.json();
}

/**
 * Upvote (confirm problem) a report
 */
export async function upvoteReport(id: number): Promise<Report> {
    const res = await fetch(`${API_BASE}/api/reports/${id}/upvote`, {
        method: 'PATCH',
    });
    if (!res.ok) throw new Error(`Failed to upvote: ${res.status}`);
    return res.json();
}

/**
 * Get report statistics
 */
export async function fetchReportsStats(): Promise<{
    total: number;
    by_status: Record<string, number>;
    by_category: Record<string, number>;
}> {
    const res = await fetch(`${API_BASE}/api/reports/stats/summary`);
    if (!res.ok) throw new Error(`Failed to fetch stats: ${res.status}`);
    return res.json();
}

/**
 * Helper: build full image URL
 */
export function getImageUrl(path: string | undefined): string | undefined {
    if (!path) return undefined;
    if (path.startsWith('http')) return path;
    return `${API_BASE}${path}`;
}

/**
 * Category labels & icons (Polish)
 */
export const CATEGORY_CONFIG: Record<string, { label: string; emoji: string; color: string }> = {
    emergency: { label: 'Alarm / Wypadek', emoji: '🚨', color: '#c0392b' },
    fire: { label: 'Pożar', emoji: '🔥', color: '#d35400' },
    infrastructure: { label: 'Infrastruktura', emoji: '🏗️', color: '#e67e22' },
    waste: { label: 'Odpady', emoji: '🗑️', color: '#27ae60' },
    greenery: { label: 'Zieleń', emoji: '🌳', color: '#2ecc71' },
    safety: { label: 'Bezpieczeństwo', emoji: '⚠️', color: '#8e44ad' },
    water: { label: 'Woda / Kanalizacja', emoji: '💧', color: '#3498db' },
    other: { label: 'Inne', emoji: '📋', color: '#95a5a6' },
};

export const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
    new: { label: 'Nowe', color: '#3498db' },
    verified: { label: 'Zweryfikowane', color: '#9b59b6' },
    in_progress: { label: 'W realizacji', color: '#f39c12' },
    resolved: { label: 'Rozwiązane', color: '#27ae60' },
    rejected: { label: 'Odrzucone', color: '#e74c3c' },
};

export const SEVERITY_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
    low: { label: 'Niski', color: '#27ae60', icon: 'ℹ️' },
    medium: { label: 'Średni', color: '#f39c12', icon: '⚡' },
    high: { label: 'Wysoki', color: '#e67e22', icon: '🔶' },
    critical: { label: 'KRYTYCZNY', color: '#e74c3c', icon: '🚨' },
};
