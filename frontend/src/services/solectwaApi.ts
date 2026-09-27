/**
 * Role z zakresem (sołtys) i ogłoszenia sołectw — klient API.
 * Backend: backend/src/api/endpoints/roles.py, backend/src/api/endpoints/solectwa.py
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

async function ok<T>(res: Response): Promise<T> {
    if (!res.ok) {
        let detail = `Błąd ${res.status}`;
        try {
            const body = await res.json();
            if (typeof body.detail === 'string') detail = body.detail;
        } catch {
            // odpowiedź bez JSON — zostaje kod błędu
        }
        throw new Error(detail);
    }
    return res.json();
}

export const PERM_SOLECTWO_POST = 'solectwo.post';

export interface MyRole {
    id: number;
    role: string;
    label: string;
    scope: string;
    scope_label: string;
    signed_as: string;
    permissions: string[];
    verified_at: string | null;
}

export interface InvitationPublic {
    state: 'active' | 'used' | 'revoked' | 'expired';
    role: string;
    role_label: string;
    scope: string;
    signed_as: string;
    expires_at: string;
    message: string | null;
}

export type PostStatus = 'processing' | 'pending' | 'published' | 'rejected' | 'failed';

export interface MyPost {
    id: number;
    solectwo: string;
    signed_as: string;
    status: PostStatus;
    title: string | null;
    summary: string | null;
    created_at: string;
    published_at: string | null;
    reject_reason: string | null;
    url: string | null;
}

export interface AdminPost extends MyPost {
    transcript: string | null;
    doc_type: string | null;
    note: string | null;
    event_at: string | null;
    event_until: string | null;
    personal_data: string[] | null;
    illegible: string[] | null;
    ai_error: string | null;
    image_count: number;
    author_email: string | null;
    author_name: string | null;
}

export interface PublicPost {
    id: number;
    solectwo: string;
    signed_as: string;
    title: string;
    summary: string | null;
    transcript: string | null;
    doc_type: string | null;
    event_at: string | null;
    event_until: string | null;
    published_at: string | null;
}

export interface RoleDefinition {
    role: string;
    label: string;
    scope_label: string;
    scopes: string[];
    grants_premium: boolean;
}

export interface AdminRole extends MyRole {
    user_id: number;
    user_email: string;
    user_name: string;
    method: string;
    status: string;
}

export interface AdminInvitation {
    id: number;
    role: string;
    scope: string;
    signed_as: string;
    invitee_label: string | null;
    url: string;
    state: 'active' | 'used' | 'revoked' | 'expired';
    created_at: string;
    expires_at: string;
    used_at: string | null;
    used_by_email: string | null;
}

export const STATUS_LABELS: Record<PostStatus, { label: string; tone: string }> = {
    processing: { label: 'Odczytujemy pismo…', tone: 'text-sky-300 bg-sky-500/10 border-sky-500/30' },
    pending: { label: 'Czeka na redakcję', tone: 'text-amber-300 bg-amber-500/10 border-amber-500/30' },
    published: { label: 'Opublikowane', tone: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30' },
    rejected: { label: 'Nieopublikowane', tone: 'text-neutral-300 bg-white/5 border-white/15' },
    failed: { label: 'Czeka na redakcję', tone: 'text-amber-300 bg-amber-500/10 border-amber-500/30' },
};

/** Backend oddaje naiwny UTC bez strefy (poza polami, które dostają „Z")
 *  — bez sufiksu przeglądarka czytałaby go jako czas lokalny. */
export function parseUtc(value: string | null | undefined): Date | null {
    if (!value) return null;
    const iso = /[Zz]|[+-]\d{2}:\d{2}$/.test(value) ? value : `${value}Z`;
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? null : d;
}

// ── Konto ──

export async function fetchMyRoles(): Promise<MyRole[]> {
    const res = await fetch(`${API_BASE}/roles/me`, { headers: authHeaders() });
    if (!res.ok) return [];
    return res.json();
}

export async function fetchInvitation(token: string): Promise<InvitationPublic> {
    return ok(await fetch(`${API_BASE}/roles/invitation/${encodeURIComponent(token)}`));
}

export async function acceptInvitation(token: string): Promise<MyRole> {
    return ok(await fetch(`${API_BASE}/roles/invitation/${encodeURIComponent(token)}/accept`, {
        method: 'POST',
        headers: authHeaders(),
    }));
}

// ── Sołtys ──

export async function createPost(images: File[], note: string, roleId?: number): Promise<MyPost> {
    const form = new FormData();
    images.forEach((file) => form.append('images', file));
    if (note.trim()) form.append('note', note.trim());
    if (roleId !== undefined) form.append('role_id', String(roleId));
    return ok(await fetch(`${API_BASE}/solectwa/posts`, {
        method: 'POST',
        headers: authHeaders(),
        body: form,
    }));
}

export async function fetchMyPosts(): Promise<MyPost[]> {
    const res = await fetch(`${API_BASE}/solectwa/posts/mine`, { headers: authHeaders() });
    if (!res.ok) return [];
    return res.json();
}

// ── Publicznie ──

export async function fetchPublicPost(id: number): Promise<PublicPost> {
    return ok(await fetch(`${API_BASE}/solectwa/posts/${id}`));
}

// ── Redakcja ──

export async function fetchAdminPosts(status?: string): Promise<AdminPost[]> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : '';
    return ok(await fetch(`${API_BASE}/solectwa/admin/posts${qs}`, { headers: authHeaders() }));
}

/** Oryginał zdjęcia — `<img src>` nie wyśle nagłówka autoryzacji, więc pobieramy
 *  blob i pokazujemy przez URL.createObjectURL (zwolnić revokeObjectURL). */
export async function fetchPostImage(postId: number, index: number): Promise<string> {
    const res = await fetch(`${API_BASE}/solectwa/admin/posts/${postId}/images/${index}`, {
        headers: authHeaders(),
    });
    if (!res.ok) throw new Error(`Błąd ${res.status}`);
    return URL.createObjectURL(await res.blob());
}

export async function editPost(
    postId: number, data: { title?: string; summary?: string; transcript?: string },
): Promise<MyPost> {
    return ok(await fetch(`${API_BASE}/solectwa/admin/posts/${postId}`, {
        method: 'PATCH',
        headers: authHeaders(true),
        body: JSON.stringify(data),
    }));
}

export async function approvePost(postId: number): Promise<MyPost> {
    return ok(await fetch(`${API_BASE}/solectwa/admin/posts/${postId}/approve`, {
        method: 'POST',
        headers: authHeaders(),
    }));
}

export async function rejectPost(postId: number, reason: string): Promise<MyPost> {
    return ok(await fetch(`${API_BASE}/solectwa/admin/posts/${postId}/reject`, {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify({ reason: reason.trim() || null }),
    }));
}

export async function rereadPost(postId: number): Promise<MyPost> {
    return ok(await fetch(`${API_BASE}/solectwa/admin/posts/${postId}/reread`, {
        method: 'POST',
        headers: authHeaders(),
    }));
}

export async function fetchRoleDefinitions(): Promise<RoleDefinition[]> {
    return ok(await fetch(`${API_BASE}/roles/definitions`, { headers: authHeaders() }));
}

export async function fetchAdminRoles(): Promise<AdminRole[]> {
    return ok(await fetch(`${API_BASE}/roles/admin/list`, { headers: authHeaders() }));
}

export async function revokeRole(roleId: number): Promise<void> {
    await ok(await fetch(`${API_BASE}/roles/admin/roles/${roleId}/revoke`, {
        method: 'POST',
        headers: authHeaders(),
    }));
}

export async function fetchInvitations(): Promise<AdminInvitation[]> {
    return ok(await fetch(`${API_BASE}/roles/admin/invitations`, { headers: authHeaders() }));
}

export async function createInvitation(
    role: string, scope: string, inviteeLabel: string,
): Promise<AdminInvitation> {
    return ok(await fetch(`${API_BASE}/roles/admin/invitations`, {
        method: 'POST',
        headers: authHeaders(true),
        body: JSON.stringify({ role, scope, invitee_label: inviteeLabel.trim() || null }),
    }));
}

export async function revokeInvitation(invitationId: number): Promise<void> {
    await ok(await fetch(`${API_BASE}/roles/admin/invitations/${invitationId}`, {
        method: 'DELETE',
        headers: authHeaders(),
    }));
}
