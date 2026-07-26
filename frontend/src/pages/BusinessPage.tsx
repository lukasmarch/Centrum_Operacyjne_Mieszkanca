import React, { useState, useEffect, useCallback } from 'react';
import { AppSection, Business } from '../../types';
import { useAuth } from '../context/AuthContext';
import { Search, X, Info, Store, BarChart3, Phone, Globe, Clock, Star, BadgeCheck, Pencil, Megaphone, Tag } from 'lucide-react';
import {
    fetchCatalog, claimBusiness, fetchMyClaims, updateBusinessProfile, uploadBusinessLogo,
    trackBusinessView, fetchPendingClaims, moderateClaim,
    fetchActiveAnnouncements, fetchMyAnnouncements, createAnnouncement, deactivateAnnouncement,
    getAssetUrl, isOwnerBusiness,
    CatalogCard, MyClaim, PendingClaim, ActiveAnnouncement, BusinessAnnouncement, AnnouncementType,
} from '../services/businessApi';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

interface Locality {
    name: string;
    count: number;
}

interface Stats {
    total_count: number;
    active_count: number;
    last_sync: string;
}

interface Analytics {
    by_year: Record<string, number>;           // total registrations per year
    by_year_suspended: Record<string, number>; // suspended per registration year
    by_status: Record<string, number>;
    total: number;
}

interface CategoryItem {
    category: string;
    count: number;
}

// Emoji icons per category for visual appeal
const CATEGORY_ICONS: Record<string, string> = {
    'Handel i naprawy': '🛒',
    'Budownictwo': '🏗️',
    'Transport': '🚚',
    'Informacja i komunikacja': '💻',
    'Usługi profesjonalne': '⚖️',
    'Nauka i technika': '🔬',
    'Rolnictwo': '🌾',
    'Zakwaterowanie i gastronomia': '🍽️',
    'Opieka zdrowotna': '🏥',
    'Edukacja': '📚',
    'Finanse i ubezpieczenia': '💰',
    'Nieruchomości': '🏠',
    'Kultura i rekreacja': '🎭',
    'Pozostałe usługi': '🔧',
    'Przetwórstwo': '🏭',
    'Administracja i wsparcie': '📋',
    'Energetyka': '⚡',
    'Woda i odpady': '💧',
    'Administracja publiczna': '🏛️',
    'Górnictwo': '⛏️',
    'Gospodarstwa domowe': '🏡',
    'Organizacje eksterytorialne': '🌍',
};

const STATUS_COLORS: Record<string, { bg: string; text: string; border: string; label: string }> = {
    'AKTYWNY': { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500/30', label: 'Aktywne' },
    'ZAWIESZONY': { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/30', label: 'Zawieszone' },
    'WYKRESLONY': { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30', label: 'Wykreślone' },
};

// Interactive dual-bar chart: blue = total registrations, amber = suspended
const CHART_HEIGHT_PX = 80;

const YearBarChart: React.FC<{
    data: Record<string, number>;
    dataSuspended: Record<string, number>;
    selectedYear: number | null;
    onYearClick: (year: number | null) => void;
}> = ({ data, dataSuspended, selectedYear, onYearClick }) => {
    const entries: [string, number][] = (Object.entries(data) as [string, number][]).sort(
        ([a], [b]) => Number(a) - Number(b)
    );
    if (entries.length === 0) return null;

    const maxVal: number = Math.max(...entries.map(([, v]) => v as number));

    return (
        <div className="w-full">
            {/* Chart area */}
            <div className="relative w-full flex items-end gap-px" style={{ height: `${CHART_HEIGHT_PX}px` }}>
                {entries.map(([year, count]) => {
                    const totalBar = maxVal > 0 ? Math.max(2, Math.round((count / maxVal) * CHART_HEIGHT_PX)) : 2;
                    const suspendedCount = (dataSuspended[year] as number) || 0;
                    const suspendedBar = maxVal > 0 ? Math.max(0, Math.round((suspendedCount / maxVal) * CHART_HEIGHT_PX)) : 0;
                    const isSelected = selectedYear === Number(year);

                    return (
                        <div
                            key={year}
                            className={`flex-1 relative group h-full flex flex-col justify-end cursor-pointer transition-all
                                ${isSelected ? 'opacity-100' : selectedYear ? 'opacity-40 hover:opacity-80' : 'hover:opacity-90'}`}
                            onClick={() => onYearClick(isSelected ? null : Number(year))}
                            title={`${year}: ${count} firm${suspendedCount > 0 ? ` (${suspendedCount} zaw.)` : ''}`}
                        >
                            {/* Stacked: blue total bar */}
                            <div
                                className={`w-full rounded-t-sm transition-colors ${isSelected ? 'bg-blue-400' : 'bg-blue-500/70 group-hover:bg-blue-400'
                                    }`}
                                style={{ height: `${totalBar}px` }}
                            />
                            {/* Amber overlay: suspended count */}
                            {suspendedBar > 0 && (
                                <div
                                    className="w-full absolute bottom-0 left-0 right-0 bg-amber-500/60 rounded-t-sm"
                                    style={{ height: `${suspendedBar}px` }}
                                />
                            )}
                            {/* Selection ring */}
                            {isSelected && (
                                <div className="absolute inset-0 ring-1 ring-blue-400 ring-inset rounded-t-sm" />
                            )}
                        </div>
                    );
                })}
            </div>
            {/* X-axis labels: show every 5th year */}
            <div className="flex items-start gap-px mt-1">
                {entries.map(([year]) => (
                    <div key={year} className="flex-1 text-center text-[8px] text-neutral-600 leading-none">
                        {Number(year) % 5 === 0 ? year : ''}
                    </div>
                ))}
            </div>
        </div>
    );
};

// ==================== Karta wizytówki (katalog) ====================

const CatalogBusinessCard: React.FC<{
    card: CatalogCard;
    isOwner?: boolean;
    onEdit?: () => void;
    onAnnouncements?: () => void;
    announcements?: ActiveAnnouncement[];
}> = ({ card, isOwner, onEdit, onAnnouncements, announcements }) => {
    // Wizytówka właściciela portalu nie dostaje odznaki „Polecane w Rybnie" —
    // katalog polecający wyłącznie firmę właściciela podważa całą ofertę B2B
    const premium = card.profile.is_premium && !isOwnerBusiness(card.nazwa);

    useEffect(() => {
        trackBusinessView(card.id);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [card.id]);

    return (
        <div className={`group p-5 rounded-2xl border transition-all duration-300 flex flex-col gap-3 ${
            premium
                ? 'bg-gradient-to-b from-amber-500/10 to-white/[0.03] border-amber-500/40 hover:border-amber-400/60 shadow-lg shadow-amber-900/10'
                : 'bg-white/[0.04] border-white/8 hover:border-white/15'
        }`}>
            <div className="flex justify-between items-start">
                {premium ? (
                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider bg-amber-500/15 text-amber-300 border border-amber-500/30">
                        <Star size={10} className="fill-amber-300" /> Polecane w Rybnie
                    </span>
                ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider bg-blue-500/10 text-blue-300 border border-blue-500/25">
                        <BadgeCheck size={11} /> Zweryfikowana
                    </span>
                )}
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-xs font-bold overflow-hidden ${
                    premium ? 'bg-gradient-to-br from-amber-500 to-orange-600 text-white' : 'bg-white/[0.06] border border-white/10 text-neutral-300'
                }`}>
                    {card.profile.logo_url
                        ? <img src={getAssetUrl(card.profile.logo_url)} alt="" className="w-full h-full object-cover" />
                        : card.nazwa.substring(0, 2).toUpperCase()}
                </div>
            </div>

            <h3 className="font-bold text-neutral-100 text-sm leading-snug">{card.nazwa}</h3>

            {card.profile.description && (
                <p className={`text-xs leading-relaxed line-clamp-3 ${premium ? 'text-neutral-300' : 'text-neutral-400'}`}>
                    {card.profile.description}
                </p>
            )}

            {/* Aktywne ogłoszenia/okazje firmy (plan Firma lokalna) */}
            {announcements && announcements.length > 0 && announcements.map(a => (
                <div key={a.id} className={`rounded-xl px-3 py-2 border text-xs ${
                    a.type === 'okazja'
                        ? 'bg-amber-500/10 border-amber-500/30'
                        : 'bg-white/[0.04] border-white/10'
                }`}>
                    <p className={`font-bold flex items-center gap-1.5 ${a.type === 'okazja' ? 'text-amber-300' : 'text-neutral-200'}`}>
                        {a.type === 'okazja' ? <Tag size={11} /> : <Megaphone size={11} />}
                        {a.title}
                        {a.type === 'okazja' && a.valid_until && (
                            <span className="ml-auto text-[10px] font-medium text-amber-400 whitespace-nowrap">
                                do {new Date(a.valid_until).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' })}
                            </span>
                        )}
                    </p>
                    <p className="text-neutral-400 mt-0.5 line-clamp-2">{a.body}</p>
                </div>
            ))}

            <div className="space-y-1.5 text-xs text-neutral-400 mt-auto">
                <p className="flex items-center gap-2"><span className="text-neutral-500">📍</span>{card.miasto}{card.branza ? ` · ${card.branza}` : ''}</p>
                {card.profile.godziny && (
                    <p className="flex items-center gap-2"><Clock size={12} className="text-neutral-500" />{card.profile.godziny}</p>
                )}
            </div>

            <div className="flex gap-2 pt-2 border-t border-white/8">
                {card.profile.telefon && (
                    <a
                        href={`tel:${card.profile.telefon.replace(/\s/g, '')}`}
                        className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-bold transition-all ${
                            premium
                                ? 'bg-gradient-to-r from-amber-600 to-orange-600 text-white hover:from-amber-500 hover:to-orange-500'
                                : 'bg-blue-600 text-white hover:bg-blue-500'
                        }`}
                    >
                        <Phone size={12} /> Zadzwoń
                    </a>
                )}
                {card.profile.www && (
                    <a
                        href={card.profile.www.startsWith('http') ? card.profile.www : `https://${card.profile.www}`}
                        target="_blank" rel="noopener noreferrer"
                        className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-bold bg-white/[0.06] text-neutral-300 border border-white/10 hover:bg-white/[0.1] transition-all"
                    >
                        <Globe size={12} /> WWW
                    </a>
                )}
                {isOwner && (
                    <>
                        <button
                            onClick={onEdit}
                            className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold bg-white/[0.06] text-neutral-300 border border-white/10 hover:bg-white/[0.1] transition-all"
                        >
                            <Pencil size={12} /> Edytuj
                        </button>
                        <button
                            onClick={onAnnouncements}
                            className="flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold bg-amber-500/10 text-amber-300 border border-amber-500/25 hover:bg-amber-500/20 transition-all"
                        >
                            <Megaphone size={12} /> Ogłoszenia
                        </button>
                    </>
                )}
            </div>
        </div>
    );
};

// ==================== Modal: przejmij wizytówkę ====================

const ClaimModal: React.FC<{
    onClose: () => void;
    onClaimed: () => void;
    onNavigate?: (section: AppSection) => void;
    isAuthenticated: boolean;
}> = ({ onClose, onClaimed, onNavigate, isAuthenticated }) => {
    const [step, setStep] = useState(1);
    const [search, setSearch] = useState('');
    const [results, setResults] = useState<Business[]>([]);
    const [searching, setSearching] = useState(false);
    const [selected, setSelected] = useState<Business | null>(null);
    const [telefon, setTelefon] = useState('');
    const [email, setEmail] = useState('');
    const [www, setWww] = useState('');
    const [note, setNote] = useState('');
    const [consent, setConsent] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [done, setDone] = useState(false);

    useEffect(() => {
        if (search.length < 2) { setResults([]); return; }
        const t = setTimeout(async () => {
            setSearching(true);
            try {
                const res = await fetch(`${API_URL}/business/search?nazwa=${encodeURIComponent(search)}&limit=8&status=`);
                const data = await res.json();
                setResults(Array.isArray(data) ? data : []);
            } catch { setResults([]); }
            finally { setSearching(false); }
        }, 300);
        return () => clearTimeout(t);
    }, [search]);

    const submit = async () => {
        if (!selected || !consent) return;
        setSubmitting(true);
        setError(null);
        try {
            await claimBusiness(selected.id, {
                telefon: telefon.trim() || undefined,
                email: email.trim() || undefined,
                www: www.trim() || undefined,
                note: note.trim() || undefined,
            });
            setDone(true);
            onClaimed();
        } catch (err: any) {
            setError(err.message);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" onClick={onClose}>
            <div className="bg-gray-950 rounded-3xl border border-gray-800/50 max-w-lg w-full max-h-[85vh] overflow-y-auto shadow-2xl p-8" onClick={e => e.stopPropagation()}>
                {done ? (
                    <div className="text-center py-8">
                        <div className="text-5xl mb-4">🎉</div>
                        <h2 className="text-xl font-black text-neutral-100 mb-2">Zgłoszenie przyjęte!</h2>
                        <p className="text-neutral-400 text-sm leading-relaxed">
                            Zweryfikujemy przejęcie wizytówki <strong className="text-neutral-200">{selected?.nazwa}</strong> w
                            ciągu 2 dni roboczych. Po zatwierdzeniu uzupełnisz opis i godziny otwarcia.
                        </p>
                        <button onClick={onClose} className="mt-6 px-8 py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-500 transition-colors">
                            Zamknij
                        </button>
                    </div>
                ) : (
                    <>
                        <div className="flex items-center justify-between mb-2">
                            <h2 className="text-xl font-black text-neutral-100">Przejmij wizytówkę</h2>
                            <button onClick={onClose} className="w-9 h-9 rounded-full bg-gray-900 flex items-center justify-center text-neutral-400 hover:bg-gray-800 border border-gray-700/50">✕</button>
                        </div>
                        <p className="text-xs text-neutral-500 mb-6">
                            Krok {step} z 2 — {step === 1 ? 'znajdź swoją firmę w rejestrze' : 'dane kontaktowe do wizytówki'}
                        </p>

                        {!isAuthenticated ? (
                            <div className="text-center py-6">
                                <p className="text-neutral-300 text-sm mb-4">
                                    Do przejęcia wizytówki potrzebujesz bezpłatnego konta —
                                    będzie służyć do zarządzania kartą Twojej firmy.
                                </p>
                                <button
                                    onClick={() => { onClose(); onNavigate?.('login'); }}
                                    className="px-8 py-3 bg-gradient-to-r from-blue-600 to-violet-600 text-white font-bold rounded-xl hover:from-blue-500 hover:to-violet-500 transition-all"
                                >
                                    Zaloguj się / Załóż konto
                                </button>
                            </div>
                        ) : step === 1 ? (
                            <div className="space-y-3">
                                <div className="relative">
                                    <Search className="absolute left-3 top-3 w-4 h-4 text-neutral-500" />
                                    <input
                                        type="text"
                                        value={search}
                                        onChange={e => setSearch(e.target.value)}
                                        placeholder="Nazwa firmy lub NIP…"
                                        className="w-full pl-10 pr-4 py-2.5 bg-gray-900 border border-gray-700/50 rounded-xl text-sm text-neutral-200 focus:border-blue-500 outline-none placeholder:text-neutral-500"
                                        autoFocus
                                    />
                                </div>
                                {searching && <p className="text-xs text-neutral-500">Szukam…</p>}
                                <div className="space-y-2 max-h-72 overflow-y-auto">
                                    {results.map(b => (
                                        <button
                                            key={b.id}
                                            onClick={() => { setSelected(b); setStep(2); }}
                                            className="w-full text-left p-3 rounded-xl bg-white/[0.03] border border-white/8 hover:border-blue-500/40 hover:bg-blue-500/5 transition-all"
                                        >
                                            <p className="text-sm font-bold text-neutral-200">{b.nazwa}</p>
                                            <p className="text-xs text-neutral-500 mt-0.5">📍 {b.miasto} · NIP {b.nip}</p>
                                        </button>
                                    ))}
                                    {search.length >= 2 && !searching && results.length === 0 && (
                                        <p className="text-xs text-neutral-500 text-center py-4">
                                            Nie znaleziono firmy. Napisz do nas: biuro@lumargo.pl
                                        </p>
                                    )}
                                </div>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                <div className="p-3 rounded-xl bg-blue-500/5 border border-blue-500/15">
                                    <p className="text-sm font-bold text-neutral-200">{selected?.nazwa}</p>
                                    <p className="text-xs text-neutral-500">📍 {selected?.miasto} · NIP {selected?.nip}</p>
                                    <button onClick={() => setStep(1)} className="text-[11px] text-blue-400 hover:underline mt-1">← zmień firmę</button>
                                </div>
                                <div className="grid grid-cols-2 gap-3">
                                    <input type="tel" value={telefon} onChange={e => setTelefon(e.target.value)} placeholder="Telefon firmowy"
                                        className="px-3 py-2.5 bg-gray-900 border border-gray-700/50 rounded-xl text-sm text-neutral-200 focus:border-blue-500 outline-none placeholder:text-neutral-500" />
                                    <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="E-mail firmowy"
                                        className="px-3 py-2.5 bg-gray-900 border border-gray-700/50 rounded-xl text-sm text-neutral-200 focus:border-blue-500 outline-none placeholder:text-neutral-500" />
                                </div>
                                <input type="text" value={www} onChange={e => setWww(e.target.value)} placeholder="Strona WWW (opcjonalnie)"
                                    className="w-full px-3 py-2.5 bg-gray-900 border border-gray-700/50 rounded-xl text-sm text-neutral-200 focus:border-blue-500 outline-none placeholder:text-neutral-500" />
                                <textarea value={note} onChange={e => setNote(e.target.value)} rows={2}
                                    placeholder="Jak możemy potwierdzić, że to Twoja firma? (np. oddzwonimy na numer z szyldu/strony)"
                                    className="w-full px-3 py-2.5 bg-gray-900 border border-gray-700/50 rounded-xl text-sm text-neutral-200 focus:border-blue-500 outline-none placeholder:text-neutral-500 resize-none" />
                                <label className="flex items-start gap-2.5 cursor-pointer">
                                    <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} className="mt-0.5 accent-blue-500 shrink-0" />
                                    <span className="text-[11px] text-neutral-400 leading-relaxed">
                                        Oświadczam, że reprezentuję tę firmę, i wyrażam zgodę na publikację podanych
                                        danych kontaktowych na wizytówce w katalogu firm RybnoLive. <span className="text-red-400">*</span>
                                    </span>
                                </label>
                                {error && <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl p-3">⚠️ {error}</p>}
                                <button
                                    onClick={submit}
                                    disabled={submitting || !consent}
                                    className="w-full py-3.5 bg-gradient-to-r from-blue-600 to-violet-600 text-white font-black rounded-xl hover:from-blue-500 hover:to-violet-500 disabled:opacity-50 transition-all"
                                >
                                    {submitting ? 'Wysyłam…' : 'Przejmij wizytówkę (0 zł)'}
                                </button>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
};

// ==================== Modal: edycja wizytówki (właściciel) ====================

const EditProfileModal: React.FC<{
    claim: MyClaim;
    card?: CatalogCard;
    onClose: () => void;
    onSaved: () => void;
}> = ({ claim, card, onClose, onSaved }) => {
    const [description, setDescription] = useState(card?.profile.description || '');
    const [telefon, setTelefon] = useState(card?.profile.telefon || '');
    const [email, setEmail] = useState(card?.profile.email || '');
    const [www, setWww] = useState(card?.profile.www || '');
    const [godziny, setGodziny] = useState(card?.profile.godziny || '');
    const [logoUrl, setLogoUrl] = useState(card?.profile.logo_url || '');
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

const AnnouncementsModal: React.FC<{
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

// ==================== Modal: weryfikacja przejęć (admin) ====================

const ClaimsModerationModal: React.FC<{
    onClose: () => void;
    onModerated: () => void;
}> = ({ onClose, onModerated }) => {
    const [claims, setClaims] = useState<PendingClaim[]>([]);
    const [loading, setLoading] = useState(true);
    const [busyId, setBusyId] = useState<number | null>(null);

    useEffect(() => {
        fetchPendingClaims().then(setClaims).finally(() => setLoading(false));
    }, []);

    const decide = async (claimId: number, action: 'approve' | 'reject') => {
        setBusyId(claimId);
        try {
            await moderateClaim(claimId, action);
            setClaims(prev => prev.filter(c => c.claim_id !== claimId));
            onModerated();
        } catch (err) {
            console.error('Claim moderation failed:', err);
        } finally {
            setBusyId(null);
        }
    };

    return (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" onClick={onClose}>
            <div className="bg-gray-950 rounded-3xl border border-gray-800/50 max-w-xl w-full max-h-[85vh] overflow-y-auto shadow-2xl p-8" onClick={e => e.stopPropagation()}>
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-black text-neutral-100">🛡️ Weryfikacja wizytówek</h2>
                    <button onClick={onClose} className="w-9 h-9 rounded-full bg-gray-900 flex items-center justify-center text-neutral-400 hover:bg-gray-800 border border-gray-700/50">✕</button>
                </div>
                {loading ? (
                    <p className="text-neutral-400 text-center py-6">Ładowanie…</p>
                ) : claims.length === 0 ? (
                    <p className="text-neutral-400 text-center py-6">✅ Brak przejęć do weryfikacji</p>
                ) : (
                    <div className="space-y-4">
                        {claims.map(c => (
                            <div key={c.claim_id} className="p-4 bg-white/[0.03] border border-white/8 rounded-2xl">
                                <p className="font-bold text-neutral-100 text-sm">{c.nazwa}</p>
                                <p className="text-xs text-neutral-500 mt-0.5">📍 {c.miasto} · NIP {c.nip}</p>
                                <p className="text-xs text-neutral-400 mt-1.5">
                                    👤 {c.user_email}
                                    {c.telefon && <> · 📞 {c.telefon}</>}
                                    {c.email && <> · ✉️ {c.email}</>}
                                </p>
                                {c.note && <p className="text-xs text-neutral-400 mt-1.5 italic">„{c.note}"</p>}
                                <div className="flex gap-2 mt-3">
                                    <button
                                        disabled={busyId === c.claim_id}
                                        onClick={() => decide(c.claim_id, 'approve')}
                                        className="flex-1 py-2 rounded-xl bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 text-xs font-bold hover:bg-emerald-500/25 transition-all disabled:opacity-50"
                                    >
                                        ✓ Zatwierdź
                                    </button>
                                    <button
                                        disabled={busyId === c.claim_id}
                                        onClick={() => decide(c.claim_id, 'reject')}
                                        className="flex-1 py-2 rounded-xl bg-red-500/10 text-red-400 border border-red-500/20 text-xs font-bold hover:bg-red-500/20 transition-all disabled:opacity-50"
                                    >
                                        ✕ Odrzuć
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

interface BusinessPageProps {
    onNavigate?: (section: AppSection) => void;
}

const BusinessPage: React.FC<BusinessPageProps> = ({ onNavigate }) => {
    const { isAuthenticated, user } = useAuth();
    const isAdmin = !!user?.is_admin;

    // Widok: katalog wizytówek (front) | dane rejestrowe i statystyki (schowane głębiej)
    const [view, setView] = useState<'katalog' | 'dane'>('katalog');
    const [catalog, setCatalog] = useState<CatalogCard[]>([]);
    const [catalogLoading, setCatalogLoading] = useState(true);
    const [myClaims, setMyClaims] = useState<MyClaim[]>([]);
    const [pendingClaimsCount, setPendingClaimsCount] = useState(0);
    const [showClaim, setShowClaim] = useState(false);
    const [showClaimsModeration, setShowClaimsModeration] = useState(false);
    const [editClaim, setEditClaim] = useState<MyClaim | null>(null);
    const [annClaim, setAnnClaim] = useState<MyClaim | null>(null);
    const [activeAnns, setActiveAnns] = useState<ActiveAnnouncement[]>([]);

    const loadCatalog = useCallback(() => {
        fetchCatalog()
            .then(setCatalog)
            .catch(() => setCatalog([]))
            .finally(() => setCatalogLoading(false));
        fetchActiveAnnouncements(20).then(setActiveAnns).catch(() => {});
        if (isAuthenticated) fetchMyClaims().then(setMyClaims).catch(() => {});
        if (isAdmin) fetchPendingClaims().then(c => setPendingClaimsCount(c.length)).catch(() => {});
    }, [isAuthenticated, isAdmin]);

    useEffect(() => { loadCatalog(); }, [loadCatalog]);

    const myVerifiedByBusinessId = new Map(
        myClaims.filter(c => c.claim_status === 'verified').map(c => [c.business_id, c])
    );
    const myPendingClaim = myClaims.find(c => c.claim_status === 'pending');

    const [businesses, setBusinesses] = useState<Business[]>([]);
    const [localities, setLocalities] = useState<Locality[]>([]);
    const [stats, setStats] = useState<Stats | null>(null);
    const [analytics, setAnalytics] = useState<Analytics | null>(null);
    const [categories, setCategories] = useState<CategoryItem[]>([]);

    const [selectedLocality, setSelectedLocality] = useState<string | null>(null);
    const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
    const [selectedYear, setSelectedYear] = useState<number | null>(null);  // Chart year filter
    const [searchTerm, setSearchTerm] = useState('');
    const [searchResults, setSearchResults] = useState<Business[] | null>(null);
    const [searchLoading, setSearchLoading] = useState(false);

    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const [loading, setLoading] = useState(false);

    // Fetch metadata on mount
    useEffect(() => {
        const fetchMetadata = async () => {
            try {
                const [statsRes, locRes, analyticsRes, categoriesRes] = await Promise.all([
                    fetch(`${API_URL}/business/stats`),
                    fetch(`${API_URL}/business/localities`),
                    fetch(`${API_URL}/business/analytics`),
                    fetch(`${API_URL}/business/categories`),
                ]);

                if (statsRes.ok) setStats(await statsRes.json());
                if (locRes.ok) setLocalities(await locRes.json());
                if (analyticsRes.ok) setAnalytics(await analyticsRes.json());
                if (categoriesRes.ok) setCategories(await categoriesRes.json());
            } catch (error) {
                console.error('Error fetching metadata:', error);
            }
        };
        fetchMetadata();
    }, []);

    // Debounced search effect
    useEffect(() => {
        if (searchTerm.length === 0) {
            setSearchResults(null);
            return;
        }
        if (searchTerm.length < 2) return;

        const timer = setTimeout(async () => {
            setSearchLoading(true);
            try {
                const res = await fetch(
                    `${API_URL}/business/search?nazwa=${encodeURIComponent(searchTerm)}&limit=50`
                );
                const data = await res.json();
                setSearchResults(Array.isArray(data) ? data : []);
            } catch {
                setSearchResults([]);
            } finally {
                setSearchLoading(false);
            }
        }, 300);

        return () => clearTimeout(timer);
    }, [searchTerm]);

    // Fetch businesses list when locality/category/year filter changes
    useEffect(() => {
        if (searchTerm.length >= 2) return; // in search mode, don't load list
        setBusinesses([]);
        setPage(1);
        setHasMore(true);
        fetchBusinesses(1, true);
    }, [selectedLocality, selectedCategory, selectedYear]);

    const fetchBusinesses = async (pageParam = 1, reset = false) => {
        if (loading) return;
        setLoading(true);

        try {
            let url = `${API_URL}/business/list?page=${pageParam}&limit=24`;
            if (selectedLocality) url += `&miasto=${encodeURIComponent(selectedLocality)}`;
            if (selectedCategory) url += `&category=${encodeURIComponent(selectedCategory)}`;
            if (selectedYear) url += `&year=${selectedYear}&status=`; // year filter: no status restriction

            const response = await fetch(url);
            const data = await response.json();

            if (data.businesses) {
                setBusinesses(prev => reset ? data.businesses : [...prev, ...data.businesses]);
                setHasMore(data.businesses.length === 24);
            } else {
                setHasMore(false);
            }
        } catch (error) {
            console.error('Error fetching businesses:', error);
        } finally {
            setLoading(false);
        }
    };

    const loadMore = () => {
        if (!loading && hasMore) {
            const nextPage = page + 1;
            setPage(nextPage);
            fetchBusinesses(nextPage, false);
        }
    };

    const handleLocalitySelect = (loc: string | null) => {
        setSelectedLocality(loc);
        setSelectedYear(null);
        setSearchTerm('');
        setSearchResults(null);
    };

    const handleCategorySelect = (cat: string | null) => {
        setSelectedCategory(cat);
        setSelectedYear(null);
        setSearchTerm('');
        setSearchResults(null);
    };

    const handleYearClick = (year: number | null) => {
        setSelectedYear(year);
        setSearchTerm('');
        setSearchResults(null);
    };

    const clearSearch = () => {
        setSearchTerm('');
        setSearchResults(null);
    };

    // Displayed businesses: search results or paginated list
    const displayedBusinesses = searchResults !== null ? searchResults : businesses;
    const isSearchMode = searchResults !== null;

    // Suspended count from analytics
    const suspendedCount = analytics?.by_status?.['ZAWIESZONY'] ?? 0;
    const deletedCount = analytics?.by_status?.['WYKRESLONY'] ?? 0;
    const spolkaCount = analytics?.by_status?.['WYLACZNIE_W_FORMIE_SPOLKI'] ?? 0;
    const activeCount = analytics?.by_status?.['AKTYWNY'] ?? stats?.active_count ?? 0;
    // Wpisy istniejące dziś — bez wykreślonych. Wcześniej kafel pokazywał total
    // z rejestru (660), w którym połowa to firmy wykreślone z CEIDG; czytelnik
    // odbierał to jako liczbę firm działających w gminie.
    const registeredCount = activeCount + suspendedCount + spolkaCount;

    return (
        <div className="space-y-8 pb-12">
            {/* ── Hero + przełącznik widoków ── */}
            <header className="bg-white/[0.04] backdrop-blur-xl rounded-3xl p-8 border border-white/5">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
                    <div>
                        <h2 className="text-3xl font-black text-neutral-100 tracking-tight">
                            {view === 'katalog' ? 'Katalog Firm' : 'Firmy — dane i statystyki'}
                        </h2>
                        <p className="text-neutral-400 mt-2">
                            {view === 'katalog'
                                // Liczba mnoga przy jednej wizytówce obiecuje więcej, niż katalog ma do pokazania
                                ? (catalog.length > 2
                                    ? 'Sprawdzone lokalne firmy z Gminy Rybno — z kontaktem i godzinami otwarcia'
                                    : 'Katalog firm z Gminy Rybno właśnie startuje — przejmij wizytówkę swojej firmy za darmo')
                                : 'Rejestr CEIDG: statystyki, sołectwa, branże i trendy rejestracji firm'}
                        </p>
                    </div>
                    <div className="flex gap-2 items-center flex-wrap">
                        <button
                            onClick={() => onNavigate?.('stats')}
                            className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-bold border bg-white/[0.04] text-neutral-400 border-white/10 hover:bg-white/[0.08] hover:text-neutral-200 transition-all"
                        >
                            <BarChart3 size={13} /> Statystyki GUS
                        </button>
                        {isAdmin && (
                            <button
                                onClick={() => setShowClaimsModeration(true)}
                                className={`px-4 py-2.5 rounded-xl text-xs font-bold border transition-all ${
                                    pendingClaimsCount > 0
                                        ? 'bg-amber-500/15 text-amber-300 border-amber-500/30 hover:bg-amber-500/25'
                                        : 'bg-white/[0.04] text-neutral-400 border-white/10 hover:bg-white/[0.08]'
                                }`}
                            >
                                🛡️ Weryfikacja{pendingClaimsCount > 0 ? ` (${pendingClaimsCount})` : ''}
                            </button>
                        )}
                        <div className="flex bg-white/[0.04] border border-white/10 rounded-xl p-1">
                            <button
                                onClick={() => setView('katalog')}
                                className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                                    view === 'katalog' ? 'bg-blue-600 text-white shadow' : 'text-neutral-400 hover:text-neutral-200'
                                }`}
                            >
                                <Store size={13} /> Katalog
                            </button>
                            <button
                                onClick={() => setView('dane')}
                                className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                                    view === 'dane' ? 'bg-blue-600 text-white shadow' : 'text-neutral-400 hover:text-neutral-200'
                                }`}
                            >
                                <BarChart3 size={13} /> Dane
                            </button>
                        </div>
                    </div>
                </div>
            </header>

            {/* ══════════ WIDOK: KATALOG WIZYTÓWEK ══════════ */}
            {view === 'katalog' && (
                <>
                    {/* Status mojego przejęcia */}
                    {myPendingClaim && (
                        <div className="bg-blue-500/5 border border-blue-500/15 rounded-2xl p-4 text-sm text-neutral-300">
                            ⏳ Twoje przejęcie wizytówki <strong>{myPendingClaim.nazwa}</strong> czeka
                            na weryfikację — zwykle do 2 dni roboczych.
                        </div>
                    )}

                    {catalogLoading ? (
                        <div className="text-center py-16 text-neutral-500">Ładowanie katalogu…</div>
                    ) : catalog.length > 0 ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                            {catalog.map(card => (
                                <CatalogBusinessCard
                                    key={card.id}
                                    card={card}
                                    isOwner={myVerifiedByBusinessId.has(card.id)}
                                    onEdit={() => setEditClaim(myVerifiedByBusinessId.get(card.id) || null)}
                                    onAnnouncements={() => setAnnClaim(myVerifiedByBusinessId.get(card.id) || null)}
                                    announcements={activeAnns.filter(a => a.business_id === card.id).slice(0, 2)}
                                />
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-14 bg-white/[0.03] border border-white/5 rounded-3xl">
                            <p className="text-4xl mb-3">🏪</p>
                            <h3 className="text-lg font-bold text-neutral-200 mb-2">Bądź pierwszy i przejmij swoją wizytówkę</h3>
                            <p className="text-sm text-neutral-500 max-w-md mx-auto">
                                Katalog wizytówek właśnie startuje. Przejmij kartę swojej firmy za darmo
                                i bądź widoczny dla mieszkańców całej gminy.
                            </p>
                        </div>
                    )}

                    {/* Sekcja "Dla firm" — lejek przejęcia wizytówki */}
                    <section className="bg-gradient-to-br from-blue-500/10 via-white/[0.03] to-violet-500/10 border border-blue-500/20 rounded-3xl p-8">
                        <div className="max-w-2xl">
                            <h3 className="text-2xl font-black text-neutral-100 mb-2">Prowadzisz firmę w gminie?</h3>
                            <p className="text-sm text-neutral-400 leading-relaxed mb-6">
                                Twoja firma prawdopodobnie już jest w naszym rejestrze — ale jej karta jest pusta.
                                Przejmij wizytówkę <strong className="text-neutral-200">za darmo</strong>: dodasz telefon,
                                godziny otwarcia i opis, a mieszkańcy znajdą Cię w katalogu.
                            </p>
                            <div className="grid sm:grid-cols-3 gap-3 mb-6 text-xs">
                                <div className="p-4 bg-white/[0.04] border border-white/8 rounded-2xl">
                                    <p className="font-bold text-neutral-200 mb-1">1 · Rejestrowa</p>
                                    <p className="text-neutral-500">Podstawowe dane z CEIDG — bez kontaktu</p>
                                </div>
                                <div className="p-4 bg-blue-500/8 border border-blue-500/25 rounded-2xl">
                                    <p className="font-bold text-blue-300 mb-1">2 · Przejęta — 0 zł</p>
                                    <p className="text-neutral-400">Kontakt, godziny, opis + odznaka „Zweryfikowana"</p>
                                </div>
                                <div className="p-4 bg-amber-500/10 border border-amber-500/30 rounded-2xl">
                                    <p className="font-bold text-amber-300 mb-1">3 · Firma lokalna — 49 zł/mc</p>
                                    <p className="text-neutral-400">„Polecane w Rybnie", top pozycji, ogłoszenia, statystyki</p>
                                </div>
                            </div>
                            <button
                                onClick={() => setShowClaim(true)}
                                className="px-8 py-4 bg-gradient-to-r from-blue-600 to-violet-600 text-white font-black rounded-2xl hover:from-blue-500 hover:to-violet-500 transition-all shadow-lg shadow-blue-900/30"
                            >
                                Przejmij wizytówkę swojej firmy →
                            </button>
                            <p className="text-[11px] text-neutral-500 mt-3">
                                Szukasz firmy, której tu nie ma? Pełny rejestr znajdziesz w zakładce „Dane".
                            </p>
                        </div>
                    </section>
                </>
            )}

            {/* ══════════ WIDOK: DANE REJESTROWE I STATYSTYKI ══════════ */}
            {view === 'dane' && (
                <>
            {/* Header / Stats */}
            <header className="bg-white/[0.04] backdrop-blur-xl rounded-3xl p-8 border border-white/5">

                {/* Key stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    <div className="bg-white/[0.04] p-4 rounded-xl border border-white/8">
                        <p className="text-xs text-neutral-400 font-bold uppercase tracking-wider mb-1">Firmy w rejestrze</p>
                        <p className="text-2xl font-black text-neutral-100">{registeredCount}</p>
                    </div>
                    <div className="bg-green-500/10 p-4 rounded-xl border border-green-500/20">
                        <p className="text-xs text-green-400 font-bold uppercase tracking-wider mb-1">Aktywne</p>
                        <p className="text-2xl font-black text-green-400">{activeCount}</p>
                    </div>
                    <div className="bg-amber-500/10 p-4 rounded-xl border border-amber-500/20">
                        <p className="text-xs text-amber-400 font-bold uppercase tracking-wider mb-1">Zawieszone</p>
                        <p className="text-2xl font-black text-amber-400">{suspendedCount}</p>
                    </div>
                    <div className="bg-blue-500/10 p-4 rounded-xl border border-blue-500/20">
                        <p className="text-xs text-blue-400 font-bold uppercase tracking-wider mb-1">Miejscowości</p>
                        <p className="text-2xl font-black text-blue-400">{localities.length}</p>
                    </div>
                </div>

                {/* Year chart */}
                {analytics && Object.keys(analytics.by_year).length > 0 && (
                    <div className="bg-white/[0.03] rounded-2xl p-5 border border-white/5">
                        <div className="flex items-start justify-between mb-4 flex-wrap gap-3">
                            {/* Left: title + description + legend */}
                            <div>
                                <h3 className="text-sm font-bold text-neutral-200 uppercase tracking-wider">
                                    📈 Firmy w rejestrze wg roku założenia
                                </h3>
                                <p className="text-xs text-neutral-500 mt-0.5 mb-2">
                                    Wpisy istniejące dziś (bez wykreślonych) — kliknij słupek, aby przefiltrować karty
                                </p>
                                <div className="flex gap-4 text-xs">
                                    <span className="flex items-center gap-1.5 text-neutral-400">
                                        <span className="w-3 h-2 rounded-sm bg-blue-500/70 inline-block" />
                                        W rejestrze
                                    </span>
                                    <span className="flex items-center gap-1.5 text-amber-400">
                                        <span className="w-3 h-2 rounded-sm bg-amber-500/60 inline-block" />
                                        Zawieszone
                                    </span>
                                </div>
                            </div>

                            {/* Right: selected year details */}
                            {selectedYear && (
                                <div className="flex items-start gap-3">
                                    <div className="bg-white/[0.06] border border-blue-500/30 rounded-xl px-4 py-3 text-right min-w-[130px]">
                                        <p className="text-[10px] text-neutral-500 uppercase tracking-wider font-bold mb-1">
                                            📅 Rok {selectedYear}
                                        </p>
                                        <div className="flex flex-col gap-1">
                                            <span className="text-sm font-black text-blue-400">
                                                {analytics.by_year[String(selectedYear)] ?? 0}
                                                <span className="text-xs font-normal text-neutral-500 ml-1">zarejestrowanych</span>
                                            </span>
                                            <span className="text-sm font-black text-amber-400">
                                                {(analytics.by_year_suspended ?? {})[String(selectedYear)] ?? 0}
                                                <span className="text-xs font-normal text-neutral-500 ml-1">zawieszonych</span>
                                            </span>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => handleYearClick(null)}
                                        className="mt-1 text-neutral-500 hover:text-neutral-300 transition-colors"
                                        title="Wyczyść filtr roku"
                                    >
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                            )}
                        </div>
                        <YearBarChart
                            data={analytics.by_year}
                            dataSuspended={analytics.by_year_suspended ?? {}}
                            selectedYear={selectedYear}
                            onYearClick={handleYearClick}
                        />
                    </div>
                )}
            </header>

            {/* Search bar */}
            <div className="relative">
                <div className="relative">
                    <Search className="absolute left-4 top-3.5 w-5 h-5 text-neutral-500 pointer-events-none" />
                    <input
                        type="text"
                        placeholder="Szukaj firmy po nazwie..."
                        value={searchTerm}
                        onChange={e => setSearchTerm(e.target.value)}
                        className="w-full pl-12 pr-12 py-3.5 bg-white/[0.05] backdrop-blur border border-white/8 rounded-2xl text-neutral-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder:text-neutral-500 transition-all"
                    />
                    {searchTerm && (
                        <button
                            onClick={clearSearch}
                            className="absolute right-4 top-3.5 text-neutral-500 hover:text-neutral-300 transition-colors"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    )}
                </div>
                {isSearchMode && (
                    <p className="text-xs text-neutral-500 mt-1.5 ml-1">
                        {searchLoading ? 'Szukam...' : `Znaleziono: ${searchResults?.length ?? 0} firm`}
                        {' '}— <button onClick={clearSearch} className="text-blue-400 hover:text-blue-300 underline">wyczyść</button>
                    </p>
                )}
            </div>

            {/* Filters: not shown in search mode */}
            {!isSearchMode && (
                <>
                    {/* Category pills */}
                    {categories.length > 0 && (
                        <div>
                            <p className="text-xs text-neutral-500 uppercase tracking-wider font-bold mb-2 ml-1">Branża</p>
                            <div className="flex flex-wrap gap-2">
                                <button
                                    onClick={() => handleCategorySelect(null)}
                                    className={`px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider whitespace-nowrap transition-all ${selectedCategory === null
                                        ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/30'
                                        : 'bg-white/[0.04] text-neutral-400 hover:bg-white/[0.07] border border-white/8 hover:text-neutral-200'
                                        }`}
                                >
                                    Wszystkie branże
                                </button>
                                {categories.map(cat => (
                                    <button
                                        key={cat.category}
                                        onClick={() => handleCategorySelect(cat.category)}
                                        className={`px-3 py-1.5 rounded-full text-xs font-bold whitespace-nowrap transition-all flex items-center gap-1.5 ${selectedCategory === cat.category
                                            ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/30'
                                            : 'bg-white/[0.04] text-neutral-400 hover:bg-white/[0.07] border border-white/8 hover:text-neutral-200'
                                            }`}
                                    >
                                        <span>{CATEGORY_ICONS[cat.category] ?? '📌'}</span>
                                        {cat.category}
                                        <span className="opacity-60 font-normal">({cat.count})</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Locality tabs */}
                    <div>
                        <p className="text-xs text-neutral-500 uppercase tracking-wider font-bold mb-2 ml-1">Miejscowość</p>
                        <div className="flex flex-wrap gap-2">
                            <button
                                onClick={() => handleLocalitySelect(null)}
                                className={`px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider whitespace-nowrap transition-colors ${selectedLocality === null
                                    ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/30'
                                    : 'bg-white/[0.04] text-neutral-400 hover:bg-white/[0.07] border border-white/8 hover:text-neutral-200'
                                    }`}
                            >
                                Wszystkie
                            </button>
                            {localities.map(loc => (
                                <button
                                    key={loc.name}
                                    onClick={() => handleLocalitySelect(loc.name)}
                                    className={`px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider whitespace-nowrap transition-colors ${selectedLocality === loc.name
                                        ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/30'
                                        : 'bg-white/[0.04] text-neutral-400 hover:bg-white/[0.07] border border-white/8 hover:text-neutral-200'
                                        }`}
                                >
                                    {loc.name} <span className="ml-1 opacity-60">({loc.count})</span>
                                </button>
                            ))}
                        </div>
                    </div>
                </>
            )}

            {/* Active filter info */}
            {(selectedLocality || selectedCategory) && !isSearchMode && (
                <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-neutral-500">Filtrowanie:</span>
                    {selectedLocality && (
                        <span className="flex items-center gap-1 text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20 px-3 py-1 rounded-full font-semibold">
                            📍 {selectedLocality}
                            <button onClick={() => setSelectedLocality(null)} className="ml-1 hover:text-blue-200"><X className="w-3 h-3" /></button>
                        </span>
                    )}
                    {selectedCategory && (
                        <span className="flex items-center gap-1 text-xs bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-3 py-1 rounded-full font-semibold">
                            {CATEGORY_ICONS[selectedCategory] ?? '📌'} {selectedCategory}
                            <button onClick={() => setSelectedCategory(null)} className="ml-1 hover:text-indigo-200"><X className="w-3 h-3" /></button>
                        </span>
                    )}
                </div>
            )}

            {/* Business Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
                {displayedBusinesses.map((business) => {
                    return (
                        <div
                            key={business.id}
                            className="group bg-white/[0.04] backdrop-blur-sm p-5 rounded-2xl border border-white/5 hover:border-white/10 shadow-sm hover:shadow-xl hover:shadow-black/20 transition-all duration-300 flex flex-col"
                        >
                            {/* Top row: status badge + initials */}
                            <div className="flex justify-between items-start mb-3">
                                <span className={`px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider ${business.status === 'AKTYWNY'
                                    ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                                    : business.status === 'ZAWIESZONY'
                                        ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                        : 'bg-white/[0.04] text-neutral-500 border border-white/8'
                                    }`}>
                                    {business.status === 'AKTYWNY' ? '● Aktywna'
                                        : business.status === 'ZAWIESZONY' ? '⏸ Zawieszona'
                                            : business.status}
                                </span>
                                <div className="w-9 h-9 rounded-xl bg-white/[0.06] border border-white/8 flex items-center justify-center text-xs font-bold text-neutral-400 group-hover:bg-blue-600 group-hover:text-white group-hover:border-blue-500 transition-all">
                                    {business.nazwa.substring(0, 2).toUpperCase()}
                                </div>
                            </div>

                            {/* Business name */}
                            <h3 className="font-bold text-neutral-100 mb-3 min-h-[2.5rem] line-clamp-2 group-hover:text-blue-400 transition-colors text-sm leading-snug">
                                {business.nazwa}
                            </h3>

                            {/* Details */}
                            <div className="space-y-2 text-sm text-neutral-400 flex-1">
                                <p className="flex items-start gap-2 text-xs">
                                    <span className="text-neutral-500 mt-0.5 shrink-0">📍</span>
                                    <span className="leading-tight">
                                        {business.ulica ? `${business.ulica} ${business.budynek}` : business.miasto}{business.lokal ? `/${business.lokal}` : ''}{' — '}
                                        {business.miasto}
                                    </span>
                                </p>
                            </div>

                            {/* Category badge */}
                            {business.branza && (
                                <div className="mt-3 pt-3 border-t border-white/5">
                                    <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-1 rounded-lg">
                                        {CATEGORY_ICONS[business.branza] ?? '📌'} {business.branza}
                                    </span>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            {/* Empty state */}
            {displayedBusinesses.length === 0 && !loading && !searchLoading && (
                <div className="text-center py-20">
                    <p className="text-neutral-500 text-4xl mb-4">🏢</p>
                    <p className="text-neutral-400 font-semibold">
                        {isSearchMode ? 'Brak firm pasujących do wyszukiwania' : 'Brak firm w tej kategorii'}
                    </p>
                    {isSearchMode && (
                        <button onClick={clearSearch} className="mt-3 text-blue-400 hover:text-blue-300 text-sm underline">
                            Wyczyść wyszukiwanie
                        </button>
                    )}
                </div>
            )}

            {/* Load More – only in list mode */}
            {!isSearchMode && hasMore && (
                <div className="text-center pt-4">
                    <button
                        onClick={loadMore}
                        disabled={loading}
                        className="px-8 py-3 bg-white/[0.04] border border-white/8 text-neutral-300 rounded-xl font-bold hover:bg-white/[0.07] disabled:opacity-50 transition-colors"
                    >
                        {loading ? 'Ładowanie...' : 'Pokaż więcej firm'}
                    </button>
                </div>
            )}
                </>
            )}

            {/* Nota prawna — klauzula informacyjna art. 14 RODO */}
            <div className="bg-white/[0.03] border border-white/5 rounded-2xl p-5 flex gap-3 items-start">
                <Info className="w-4 h-4 text-neutral-500 shrink-0 mt-0.5" />
                <p className="text-xs text-neutral-500 leading-relaxed">
                    Dane firm pochodzą z publicznego rejestru <strong className="text-neutral-400">CEIDG</strong> i
                    obejmują nazwę, adres wykonywania działalności, NIP, REGON, branżę, status wpisu
                    i rok rozpoczęcia działalności. Danych kontaktowych z rejestru nie pobieramy —
                    telefon i e-mail widać tylko tam, gdzie firma podała je sama.
                    Szczegóły w{' '}
                    <button
                        onClick={() => onNavigate?.('privacy')}
                        className="text-blue-400 hover:text-blue-300 underline"
                    >
                        polityce prywatności (art. 14 RODO)
                    </button>.
                    {' '}Prowadzisz tę firmę i chcesz zaktualizować lub ukryć swoją kartę?
                    Napisz:{' '}
                    <a href="mailto:biuro@lumargo.pl?subject=Katalog%20firm%20RybnoLive" className="text-blue-400 hover:text-blue-300 underline">
                        biuro@lumargo.pl
                    </a>{' '}— żądania rozpatrujemy w ciągu 7 dni.
                </p>
            </div>

            {/* ── Modale wizytówek ── */}
            {showClaim && (
                <ClaimModal
                    isAuthenticated={isAuthenticated}
                    onNavigate={onNavigate}
                    onClose={() => setShowClaim(false)}
                    onClaimed={loadCatalog}
                />
            )}
            {editClaim && (
                <EditProfileModal
                    claim={editClaim}
                    card={catalog.find(c => c.id === editClaim.business_id)}
                    onClose={() => setEditClaim(null)}
                    onSaved={loadCatalog}
                />
            )}
            {annClaim && (
                <AnnouncementsModal
                    claim={annClaim}
                    onClose={() => setAnnClaim(null)}
                    onChanged={loadCatalog}
                />
            )}
            {showClaimsModeration && (
                <ClaimsModerationModal
                    onClose={() => setShowClaimsModeration(false)}
                    onModerated={loadCatalog}
                />
            )}
        </div>
    );
};

export default BusinessPage;
