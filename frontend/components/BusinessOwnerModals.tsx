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
import { Megaphone, Tag } from 'lucide-react';
import {
    updateBusinessProfile, uploadBusinessLogo, getAssetUrl,
    fetchMyAnnouncements, createAnnouncement, deactivateAnnouncement,
    CatalogCard, MyClaim, BusinessAnnouncement, AnnouncementType,
} from '../src/services/businessApi';

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
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" onClick={onClose}>
            <div className="bg-gray-950 rounded-3xl border border-gray-800/50 max-w-lg w-full max-h-[85vh] overflow-y-auto shadow-2xl p-8" onClick={e => e.stopPropagation()}>
                <div className="flex items-center justify-between mb-1">
                    <h2 className="text-xl font-black text-neutral-100">Edytuj wizytówkę</h2>
                    <button onClick={onClose} className="w-9 h-9 rounded-full bg-gray-900 flex items-center justify-center text-neutral-400 hover:bg-gray-800 border border-gray-700/50">✕</button>
                </div>
                <p className="text-xs text-neutral-500 mb-5">{claim.nazwa} · 👁 {claim.views_count} wyświetleń</p>

                <div className="space-y-4">
                    <div className="flex items-center gap-4">
                        <div className="w-16 h-16 rounded-2xl bg-white/[0.06] border border-white/10 flex items-center justify-center overflow-hidden flex-shrink-0">
                            {logoUrl
                                ? <img src={getAssetUrl(logoUrl)} alt="Logo" className="w-full h-full object-cover" />
                                : <span className="text-neutral-500 text-2xl">🏪</span>}
                        </div>
                        <div className="flex-1">
                            <label className="inline-block px-4 py-2 bg-white/[0.06] border border-white/10 rounded-xl text-xs font-bold text-neutral-300 hover:bg-white/[0.1] cursor-pointer transition-all">
                                {uploadingLogo ? 'Wysyłam…' : logoUrl ? 'Zmień logo' : 'Dodaj logo'}
                                <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
                                    disabled={uploadingLogo}
                                    onChange={e => onLogoSelected(e.target.files?.[0])} />
                            </label>
                            <p className="text-[10px] text-neutral-500 mt-1.5">JPG, PNG lub WEBP, max 2MB</p>
                        </div>
                    </div>
                    <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} maxLength={600}
                        placeholder="Opis firmy — czym się zajmujecie, co Was wyróżnia (max 600 znaków)"
                        className="w-full px-3 py-2.5 bg-gray-900 border border-gray-700/50 rounded-xl text-sm text-neutral-200 focus:border-blue-500 outline-none placeholder:text-neutral-500 resize-none" />
                    <div className="grid grid-cols-2 gap-3">
                        <input type="tel" value={telefon} onChange={e => setTelefon(e.target.value)} placeholder="Telefon"
                            className="px-3 py-2.5 bg-gray-900 border border-gray-700/50 rounded-xl text-sm text-neutral-200 focus:border-blue-500 outline-none placeholder:text-neutral-500" />
                        <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="E-mail"
                            className="px-3 py-2.5 bg-gray-900 border border-gray-700/50 rounded-xl text-sm text-neutral-200 focus:border-blue-500 outline-none placeholder:text-neutral-500" />
                    </div>
                    <input type="text" value={www} onChange={e => setWww(e.target.value)} placeholder="Strona WWW"
                        className="w-full px-3 py-2.5 bg-gray-900 border border-gray-700/50 rounded-xl text-sm text-neutral-200 focus:border-blue-500 outline-none placeholder:text-neutral-500" />
                    <input type="text" value={godziny} onChange={e => setGodziny(e.target.value)} placeholder="Godziny otwarcia, np. pn-pt 8-17, sb 8-13"
                        className="w-full px-3 py-2.5 bg-gray-900 border border-gray-700/50 rounded-xl text-sm text-neutral-200 focus:border-blue-500 outline-none placeholder:text-neutral-500" />
                    {error && <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl p-3">⚠️ {error}</p>}
                    <button onClick={save} disabled={saving}
                        className="w-full py-3.5 bg-gradient-to-r from-blue-600 to-violet-600 text-white font-black rounded-xl hover:from-blue-500 hover:to-violet-500 disabled:opacity-50 transition-all">
                        {saving ? 'Zapisuję…' : 'Zapisz wizytówkę'}
                    </button>
                </div>
            </div>
        </div>
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
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" onClick={onClose}>
            <div className="bg-gray-950 rounded-3xl border border-gray-800/50 max-w-lg w-full max-h-[85vh] overflow-y-auto shadow-2xl p-8" onClick={e => e.stopPropagation()}>
                <div className="flex items-center justify-between mb-1">
                    <h2 className="text-xl font-black text-neutral-100">📣 Ogłoszenia firmy</h2>
                    <button onClick={onClose} className="w-9 h-9 rounded-full bg-gray-900 flex items-center justify-center text-neutral-400 hover:bg-gray-800 border border-gray-700/50">✕</button>
                </div>
                <p className="text-xs text-neutral-500 mb-5">{claim.nazwa}</p>

                {!claim.is_premium ? (
                    <div className="p-5 bg-amber-500/10 border border-amber-500/30 rounded-2xl text-center">
                        <p className="text-sm font-bold text-amber-300 mb-1">Funkcja planu „Firma lokalna"</p>
                        <p className="text-xs text-neutral-400 leading-relaxed">
                            Ogłoszenia i okazje publikują firmy z planem Firma lokalna (49 zł/mc):
                            2 ogłoszenia + 8 okazji miesięcznie, widoczne na stronie głównej,
                            w feedzie i newsletterze. Napisz do nas: biuro@lumargo.pl
                        </p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {/* Formularz publikacji */}
                        <div className="grid grid-cols-2 gap-2">
                            {(Object.keys(QUOTA_INFO) as AnnouncementType[]).map(t => (
                                <button key={t} onClick={() => setType(t)}
                                    className={`p-3 rounded-xl border text-left transition-all ${
                                        type === t ? 'bg-amber-500/15 border-amber-500/40' : 'bg-gray-900 border-gray-700/50 hover:border-gray-600'
                                    }`}>
                                    <p className={`text-xs font-bold ${type === t ? 'text-amber-300' : 'text-neutral-300'}`}>{QUOTA_INFO[t].label}</p>
                                    <p className="text-[10px] text-neutral-500 mt-0.5">{QUOTA_INFO[t].hint}</p>
                                    <p className="text-[10px] text-neutral-400 mt-1">
                                        {usedThisMonth(t)}/{QUOTA_INFO[t].limit} w tym miesiącu
                                    </p>
                                </button>
                            ))}
                        </div>
                        <input type="text" value={title} onChange={e => setTitle(e.target.value)} maxLength={120}
                            placeholder={type === 'okazja' ? 'Np. Truskawki 50% taniej do 16:00' : 'Tytuł ogłoszenia'}
                            className="w-full px-3 py-2.5 bg-gray-900 border border-gray-700/50 rounded-xl text-sm text-neutral-200 focus:border-amber-500 outline-none placeholder:text-neutral-500" />
                        <textarea value={body} onChange={e => setBody(e.target.value)} rows={3} maxLength={500}
                            placeholder="Treść (max 500 znaków)"
                            className="w-full px-3 py-2.5 bg-gray-900 border border-gray-700/50 rounded-xl text-sm text-neutral-200 focus:border-amber-500 outline-none placeholder:text-neutral-500 resize-none" />
                        {type === 'okazja' && (
                            <label className="block text-xs text-neutral-400">
                                Ważna do (maks. 7 dni):
                                <input type="datetime-local" value={validUntil} onChange={e => setValidUntil(e.target.value)}
                                    className="mt-1 w-full px-3 py-2.5 bg-gray-900 border border-gray-700/50 rounded-xl text-sm text-neutral-200 focus:border-amber-500 outline-none" />
                            </label>
                        )}
                        {error && <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl p-3">⚠️ {error}</p>}
                        <button onClick={publish} disabled={saving || !title.trim() || !body.trim()}
                            className="w-full py-3 bg-gradient-to-r from-amber-600 to-orange-600 text-white font-black rounded-xl hover:from-amber-500 hover:to-orange-500 disabled:opacity-50 transition-all">
                            {saving ? 'Publikuję…' : 'Opublikuj'}
                        </button>

                        {/* Lista ogłoszeń */}
                        {loading ? (
                            <p className="text-neutral-500 text-xs text-center py-3">Ładowanie…</p>
                        ) : items.length > 0 && (
                            <div className="space-y-2 pt-2 border-t border-white/8">
                                {items.map(a => (
                                    <div key={a.id} className="p-3 bg-white/[0.03] border border-white/8 rounded-xl">
                                        <div className="flex items-start justify-between gap-2">
                                            <div className="min-w-0">
                                                <p className="text-xs font-bold text-neutral-200 flex items-center gap-1.5">
                                                    {a.type === 'okazja' ? <Tag size={10} className="text-amber-400" /> : <Megaphone size={10} className="text-blue-400" />}
                                                    {a.title}
                                                </p>
                                                <p className="text-[11px] text-neutral-500 mt-0.5 line-clamp-2">{a.body}</p>
                                                <p className="text-[10px] text-neutral-600 mt-1">
                                                    {isLive(a) ? '🟢 aktywne' : '⚪ nieaktywne'}
                                                    {a.valid_until && ` · do ${new Date(a.valid_until).toLocaleString('pl-PL', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}`}
                                                </p>
                                            </div>
                                            {isLive(a) && (
                                                <button onClick={() => withdraw(a.id)}
                                                    className="text-[10px] text-red-400 hover:text-red-300 whitespace-nowrap flex-shrink-0">
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
            </div>
        </div>
    );
};
