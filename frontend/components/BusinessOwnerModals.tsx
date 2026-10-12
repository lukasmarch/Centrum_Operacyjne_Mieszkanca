/**
 * Panel właściciela wizytówki — edycja karty i ogłoszenia firmy.
 *
 * Wydzielone z `BusinessPage`, bo te same okna otwiera zakładka „Moja firma"
 * w profilu użytkownika. Do 19.08.2026 dostęp do edycji istniał WYŁĄCZNIE
 * przez kafelek w katalogu, a katalog ma limit 60 pozycji i pomija karty ukryte
 * na wniosek firmy — właściciel sześćdziesiątej pierwszej wizytówki nie miał
 * jak wejść w jej edycję.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Megaphone, Tag as TagIcon, X, Eye, Store, AlertTriangle } from 'lucide-react';
import { Tag } from './simple/tv';
import {
    updateBusinessProfile, uploadBusinessLogo, getAssetUrl,
    fetchMyAnnouncements, createAnnouncement, deactivateAnnouncement,
    CatalogCard, MyClaim, BusinessAnnouncement, AnnouncementType,
} from '../src/services/businessApi';

// ==================== Klocki okien (świat „Pasek informacyjny”) ====================

/** Pole formularza: obramowanie 2 px szwem, fokus papierem, 16 px — iOS nie powiększa. */
export const FIELD =
    'min-h-[48px] w-full border-2 border-tv-seam bg-tv-ink px-3 py-2.5 text-[16px] text-white outline-none transition-colors placeholder:text-tv-muted focus:border-tv-paper';

/** Przycisk główny: chaber, wąskie wersaliki, 52 px. */
export const PRIMARY_BTN =
    'font-cond inline-flex min-h-[52px] w-full items-center justify-center gap-2 bg-tv-blue px-4 text-[17px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff] disabled:opacity-50 disabled:hover:bg-tv-blue';

/** Błąd formularza — żółty pas z ikoną (czerwień jest zarezerwowana dla awarii). */
export const FormError: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <p role="alert" className="flex items-start gap-2 bg-tv-yellow px-3 py-2.5 text-[15px] leading-snug text-tv-ink">
        <AlertTriangle size={16} className="mt-0.5 shrink-0" aria-hidden />
        <span>{children}</span>
    </p>
);

/**
 * Płaski panel okna: krawędź 2 px w chabrze, tło przyciemnione jednolicie
 * (bez rozmycia), zamknięcie w kwadracie 44 px.
 */
export const ModalShell: React.FC<{
    title: React.ReactNode;
    sub?: React.ReactNode;
    onClose: () => void;
    wide?: boolean;
    children: React.ReactNode;
}> = ({ title, sub, onClose, wide = false, children }) => (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
        <div
            role="dialog"
            aria-modal="true"
            className={`max-h-[85vh] w-full overflow-y-auto border border-tv-seam border-t-2 border-t-tv-blue bg-tv-panel p-4 sm:p-6 ${wide ? 'max-w-xl' : 'max-w-lg'}`}
            onClick={e => e.stopPropagation()}
        >
            <div className="flex items-start justify-between gap-3">
                <h2 className="font-cond pt-1.5 text-[22px] font-extrabold leading-tight text-white">{title}</h2>
                <button
                    onClick={onClose}
                    aria-label="Zamknij"
                    className="flex h-11 w-11 shrink-0 items-center justify-center text-tv-muted transition-colors hover:bg-tv-panel2 hover:text-white"
                >
                    <X size={20} aria-hidden />
                </button>
            </div>
            {sub && <div className="mb-5 mt-1 text-[14px] leading-snug text-tv-muted">{sub}</div>}
            {!sub && <div className="mb-4" />}
            {children}
        </div>
    </div>
);

// ==================== Modal: edycja wizytówki (właściciel) ====================

export const EditProfileModal: React.FC<{
    claim: MyClaim;
    card?: CatalogCard;
    onClose: () => void;
    onSaved: () => void;
}> = ({ claim, card, onClose, onSaved }) => {
    // Wartości startowe: karta z katalogu, a gdy okno otwarto spoza katalogu
    // (zakładka „Moja firma") — dane z `/my-claims`. Pusty formularz nie jest
    // tu neutralny: zapis wysyła puste stringi, które backend rozumie jako
    // „wyczyść pole".
    const current = card?.profile ?? claim.profile;
    const [description, setDescription] = useState(current?.description || '');
    const [telefon, setTelefon] = useState(current?.telefon || '');
    const [email, setEmail] = useState(current?.email || '');
    const [www, setWww] = useState(current?.www || '');
    const [godziny, setGodziny] = useState(current?.godziny || '');
    const [logoUrl, setLogoUrl] = useState(current?.logo_url || '');
    const [uploadingLogo, setUploadingLogo] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const onLogoSelected = async (file: File | undefined) => {
        if (!file) return;
        if (file.size > 2 * 1024 * 1024) {
            setError('Logo jest za duże. Maksymalny rozmiar: 2MB');
            return;
        }
        setUploadingLogo(true);
        setError(null);
        try {
            const url = await uploadBusinessLogo(claim.business_id, file);
            setLogoUrl(url);
            onSaved(); // upload zapisuje się od razu w bazie — odśwież katalog w tle
        } catch (err: any) {
            setError(err.message);
        } finally {
            setUploadingLogo(false);
        }
    };

    const save = async () => {
        setSaving(true);
        setError(null);
        try {
            await updateBusinessProfile(claim.business_id, {
                description: description,
                telefon: telefon,
                email: email,
                www: www,
                godziny: godziny,
            });
            onSaved();
            onClose();
        } catch (err: any) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    };

    return (
        <ModalShell
            title="Edytuj wizytówkę"
            onClose={onClose}
            sub={<span className="inline-flex flex-wrap items-center gap-x-1.5">{claim.nazwa} · <Eye size={14} aria-hidden /> <span className="tabular">{claim.views_count}</span> wyświetleń</span>}
        >
            <div className="space-y-4">
                <div className="flex items-center gap-4">
                    <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden bg-tv-panel2">
                        {logoUrl
                            ? <img src={getAssetUrl(logoUrl)} alt="Logo" className="h-full w-full object-cover" />
                            : <Store size={26} className="text-tv-muted" aria-hidden />}
                    </div>
                    <div className="flex-1">
                        <label className="font-cond inline-flex min-h-[44px] cursor-pointer items-center bg-tv-paper px-4 text-[15px] font-extrabold uppercase tracking-wide text-tv-ink transition-colors hover:bg-white focus-within:outline focus-within:outline-2 focus-within:outline-tv-yellow">
                            {uploadingLogo ? 'Wysyłam…' : logoUrl ? 'Zmień logo' : 'Dodaj logo'}
                            <input type="file" accept="image/jpeg,image/png,image/webp" className="sr-only"
                                disabled={uploadingLogo}
                                onChange={e => onLogoSelected(e.target.files?.[0])} />
                        </label>
                        <p className="mt-1.5 text-[13px] text-tv-muted">JPG, PNG lub WEBP, max 2MB</p>
                    </div>
                </div>
                <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} maxLength={600}
                    placeholder="Opis firmy — czym się zajmujecie, co Was wyróżnia (max 600 znaków)"
                    className={`${FIELD} resize-none`} />
                <div className="grid gap-3 sm:grid-cols-2">
                    <input type="tel" value={telefon} onChange={e => setTelefon(e.target.value)} placeholder="Telefon"
                        className={FIELD} />
                    <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="E-mail"
                        className={FIELD} />
                </div>
                <input type="text" value={www} onChange={e => setWww(e.target.value)} placeholder="Strona WWW"
                    className={FIELD} />
                <input type="text" value={godziny} onChange={e => setGodziny(e.target.value)} placeholder="Godziny otwarcia, np. pn-pt 8-17, sb 8-13"
                    className={FIELD} />
                {error && <FormError>{error}</FormError>}
                <button onClick={save} disabled={saving} className={PRIMARY_BTN}>
                    {saving ? 'Zapisuję…' : 'Zapisz wizytówkę'}
                </button>
            </div>
        </ModalShell>
    );
};

// ==================== Modal: ogłoszenia firmy (plan Firma lokalna) ====================

const QUOTA_INFO: Record<AnnouncementType, { label: string; limit: number; hint: string }> = {
    ogloszenie: { label: 'Ogłoszenie', limit: 2, hint: 'widoczne w feedzie aktualności i newsletterze' },
    okazja: { label: 'Okazja „tu i teraz"', limit: 8, hint: 'krótka promocja (maks. 7 dni) — strona główna i wizytówka' },
};

export const AnnouncementsModal: React.FC<{
    claim: MyClaim;
    onClose: () => void;
    onChanged: () => void;
}> = ({ claim, onClose, onChanged }) => {
    const [items, setItems] = useState<BusinessAnnouncement[]>([]);
    const [loading, setLoading] = useState(true);
    const [type, setType] = useState<AnnouncementType>('okazja');
    const [title, setTitle] = useState('');
    const [body, setBody] = useState('');
    const [validUntil, setValidUntil] = useState('');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(() => {
        fetchMyAnnouncements(claim.business_id).then(setItems).finally(() => setLoading(false));
    }, [claim.business_id]);

    useEffect(() => { load(); }, [load]);

    const monthStart = new Date();
    monthStart.setDate(1); monthStart.setHours(0, 0, 0, 0);
    const usedThisMonth = (t: AnnouncementType) =>
        items.filter(i => i.type === t && new Date(i.created_at) >= monthStart).length;

    const publish = async () => {
        setSaving(true);
        setError(null);
        try {
            await createAnnouncement(claim.business_id, {
                type,
                title: title.trim(),
                body: body.trim(),
                valid_until: type === 'okazja' && validUntil ? new Date(validUntil).toISOString() : undefined,
            });
            setTitle(''); setBody(''); setValidUntil('');
            load();
            onChanged();
        } catch (err: any) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    };

    const withdraw = async (id: number) => {
        try {
            await deactivateAnnouncement(id);
            setItems(prev => prev.map(i => i.id === id ? { ...i, is_active: false } : i));
            onChanged();
        } catch (err) {
            console.error('Announcement withdraw failed:', err);
        }
    };

    const now = new Date();
    const isLive = (a: BusinessAnnouncement) =>
        a.is_active && (!a.valid_until || new Date(a.valid_until) > now);

    return (
        <ModalShell title="Ogłoszenia firmy" sub={claim.nazwa} onClose={onClose}>
            {!claim.is_premium ? (
                <div className="bg-tv-panel2 p-4">
                    <Tag tone="paper">Funkcja planu „Firma lokalna"</Tag>
                    <p className="mt-3 text-[15px] leading-relaxed text-[#d7dbe8]">
                        Ogłoszenia i okazje publikują firmy z planem Firma lokalna (49 zł/mc):
                        2 ogłoszenia + 8 okazji miesięcznie, widoczne na stronie głównej,
                        w feedzie i newsletterze. Napisz do nas: biuro@lumargo.pl
                    </p>
                </div>
            ) : (
                <div className="space-y-4">
                    {/* Formularz publikacji */}
                    <div role="group" aria-label="Rodzaj wpisu" className="grid grid-cols-1 gap-px bg-tv-seam sm:grid-cols-2">
                        {(Object.keys(QUOTA_INFO) as AnnouncementType[]).map(t => (
                            <button key={t} onClick={() => setType(t)} aria-pressed={type === t}
                                className={`min-h-[44px] p-3 text-left transition-colors ${
                                    type === t ? 'bg-tv-paper text-tv-ink' : 'bg-tv-panel2 text-white hover:bg-tv-seam'
                                }`}>
                                <p className="font-cond text-[16px] font-extrabold uppercase tracking-wide">{QUOTA_INFO[t].label}</p>
                                <p className={`mt-0.5 text-[13px] leading-snug ${type === t ? 'text-tv-ink/75' : 'text-tv-muted'}`}>{QUOTA_INFO[t].hint}</p>
                                <p className={`tabular mt-1 text-[13px] font-semibold ${type === t ? 'text-tv-ink' : 'text-tv-paper'}`}>
                                    {usedThisMonth(t)}/{QUOTA_INFO[t].limit} w tym miesiącu
                                </p>
                            </button>
                        ))}
                    </div>
                    <input type="text" value={title} onChange={e => setTitle(e.target.value)} maxLength={120}
                        placeholder={type === 'okazja' ? 'Np. Truskawki 50% taniej do 16:00' : 'Tytuł ogłoszenia'}
                        className={FIELD} />
                    <textarea value={body} onChange={e => setBody(e.target.value)} rows={3} maxLength={500}
                        placeholder="Treść (max 500 znaków)"
                        className={`${FIELD} resize-none`} />
                    {type === 'okazja' && (
                        <label className="block text-[14px] text-tv-muted">
                            Ważna do (maks. 7 dni):
                            <input type="datetime-local" value={validUntil} onChange={e => setValidUntil(e.target.value)}
                                className={`${FIELD} mt-1 [color-scheme:dark]`} />
                        </label>
                    )}
                    {error && <FormError>{error}</FormError>}
                    <button onClick={publish} disabled={saving || !title.trim() || !body.trim()} className={PRIMARY_BTN}>
                        {saving ? 'Publikuję…' : 'Opublikuj'}
                    </button>

                    {/* Lista ogłoszeń */}
                    {loading ? (
                        <p className="py-3 text-center text-[14px] text-tv-muted">Wczytuję…</p>
                    ) : items.length > 0 && (
                        <div className="grid grid-cols-1 gap-px border-t border-tv-seam bg-tv-seam">
                            {items.map(a => (
                                <div key={a.id} className="bg-tv-panel py-3">
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="min-w-0">
                                            <p className="flex items-center gap-1.5 text-[15px] font-bold text-white">
                                                {a.type === 'okazja'
                                                    ? <TagIcon size={14} className="shrink-0 text-tv-muted" aria-hidden />
                                                    : <Megaphone size={14} className="shrink-0 text-tv-muted" aria-hidden />}
                                                {a.title}
                                            </p>
                                            <p className="mt-0.5 line-clamp-2 text-[14px] text-[#d7dbe8]">{a.body}</p>
                                            <p className="tabular mt-1 text-[13px] text-tv-muted">
                                                {isLive(a)
                                                    ? <span className="font-bold text-tv-paper">aktywne</span>
                                                    : 'nieaktywne'}
                                                {a.valid_until && ` · do ${new Date(a.valid_until).toLocaleString('pl-PL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}`}
                                            </p>
                                        </div>
                                        {isLive(a) && (
                                            <button onClick={() => withdraw(a.id)}
                                                className="min-h-[44px] shrink-0 whitespace-nowrap px-2 text-[14px] font-bold text-tv-bluesoft underline-offset-4 hover:text-white hover:underline">
                                                Wycofaj
                                            </button>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </ModalShell>
    );
};
