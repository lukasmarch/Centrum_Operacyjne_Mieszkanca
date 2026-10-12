import React, { useState, useEffect, useCallback } from 'react';
import { AppSection, Business } from '../../types';
import { useAuth } from '../context/AuthContext';
import {
    Search, X, Info, Store, BarChart3, Phone, Globe, Clock, Star, BadgeCheck, Pencil, Megaphone,
    Tag as TagIcon, MapPin, ArrowRight, ChevronLeft, CheckCircle2, ShieldCheck, User, Mail, Check,
} from 'lucide-react';
import { Tag, PageHead, Chip, Skeleton } from '../../components/simple/tv';
import {
    fetchCatalog, claimBusiness, fetchMyClaims,
    trackBusinessImpression, trackBusinessContact, fetchPendingClaims, moderateClaim,
    fetchActiveAnnouncements,
    getAssetUrl, isOwnerBusiness, addManualBusiness, fetchGminaLocalities,
    CatalogCard, MyClaim, PendingClaim, ActiveAnnouncement,
} from '../services/businessApi';
// Okna właściciela są wspólne z zakładką „Moja firma" w profilu
import {
    EditProfileModal, AnnouncementsModal, ModalShell, FormError, FIELD, PRIMARY_BTN,
} from '../../components/BusinessOwnerModals';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

/** Odmiana rzeczownika przez liczbę — polski ma trzy formy, nie dwie.
 *  Bez tego kolejka admina pokazywała „prowadzi 6 wizytówki". */
const pluralPL = (n: number, one: string, few: string, many: string): string => {
    if (n === 1) return one;
    const last = n % 10;
    const lastTwo = n % 100;
    return last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14) ? few : many;
};

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

// Etykiety znanych statusów CEIDG. Kolor statusu nie jest ozdobą: na karcie
// wyróżnia się wyłącznie „Zawieszona” (żółć = „sprawdź, zanim zadzwonisz”).
const STATUS_LABELS: Record<string, string> = {
    'AKTYWNY': 'Aktywne',
    'ZAWIESZONY': 'Zawieszone',
    'WYKRESLONY': 'Wykreślone',
    'WYLACZNIE_W_FORMIE_SPOLKI': 'Tylko w spółce',
    'OCZEKUJE_NA_ROZPOCZECIE_DZIALANOSCI': 'Przed startem',
};

/**
 * Etykieta statusu firmy. Słownik statusów CEIDG jest OTWARTY — 13.09.2026
 * rejestr przysłał szósty (`OCZEKUJE_NA_ROZPOCZECIE_DZIALANOSCI`), a karta
 * pokazywała wtedy surowy ciąg z podkreśleniami. Nieznanej wartości nie
 * ukrywamy: firma z rejestru ma być widoczna, choćby pod zgrubną nazwą.
 */
const statusLabel = (status: string | null | undefined): string => {
    if (!status) return 'Nieznany';
    const known = STATUS_LABELS[status];
    if (known) return known;
    const words = status.toLowerCase().split('_').join(' ');
    return words.charAt(0).toUpperCase() + words.slice(1);
};

// Wykres słupkowy: chaber = wpisy w rejestrze, żółć = zawieszone (kolor = stan)
const CHART_HEIGHT_PX = 96;

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
            <div className="relative flex w-full items-end gap-px" style={{ height: `${CHART_HEIGHT_PX}px` }}>
                {entries.map(([year, count]) => {
                    const totalBar = maxVal > 0 ? Math.max(2, Math.round((count / maxVal) * CHART_HEIGHT_PX)) : 2;
                    const suspendedCount = (dataSuspended[year] as number) || 0;
                    const suspendedBar = maxVal > 0 ? Math.max(0, Math.round((suspendedCount / maxVal) * CHART_HEIGHT_PX)) : 0;
                    const isSelected = selectedYear === Number(year);

                    return (
                        <button
                            key={year}
                            type="button"
                            aria-pressed={isSelected}
                            aria-label={`${year}: ${count} firm${suspendedCount > 0 ? `, ${suspendedCount} zawieszonych` : ''}`}
                            className={`group relative flex h-full flex-1 flex-col justify-end transition-opacity
                                ${isSelected ? 'opacity-100' : selectedYear ? 'opacity-40 hover:opacity-80' : 'hover:opacity-90'}`}
                            onClick={() => onYearClick(isSelected ? null : Number(year))}
                            title={`${year}: ${count} firm${suspendedCount > 0 ? ` (${suspendedCount} zaw.)` : ''}`}
                        >
                            <span
                                className={`block w-full transition-colors ${isSelected ? 'bg-tv-paper' : 'bg-tv-blue group-hover:bg-[#3a63ff]'}`}
                                style={{ height: `${totalBar}px` }}
                            />
                            {suspendedBar > 0 && (
                                <span
                                    className="absolute bottom-0 left-0 right-0 block bg-tv-yellow"
                                    style={{ height: `${suspendedBar}px` }}
                                />
                            )}
                        </button>
                    );
                })}
            </div>
            {/* Oś lat: co piąty rok; etykieta wystaje poza wąski słupek, stąd overflow-visible */}
            <div className="mt-1.5 flex items-start gap-px" aria-hidden>
                {entries.map(([year]) => (
                    <div key={year} className="relative h-4 flex-1 overflow-visible">
                        {Number(year) % 5 === 0 && (
                            <span className="tabular absolute left-1/2 -translate-x-1/2 whitespace-nowrap text-[13px] leading-none text-tv-muted">{year}</span>
                        )}
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
    span?: boolean;
}> = ({ card, isOwner, onEdit, onAnnouncements, announcements, span = false }) => {
    // Wizytówka właściciela portalu nie dostaje odznaki „Polecane w Rybnie" —
    // katalog polecający wyłącznie firmę właściciela podważa całą ofertę B2B
    const premium = card.profile.is_premium && !isOwnerBusiness(card.nazwa);
    const [logoBroken, setLogoBroken] = useState(false);

    useEffect(() => {
        trackBusinessImpression(card.id);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [card.id]);

    return (
        <article className={`flex flex-col gap-3 bg-tv-panel p-4 lg:p-5 ${span ? 'lg:col-span-2' : ''}`}>
            <div className="flex items-start gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden bg-tv-panel2 font-cond text-[15px] font-extrabold text-tv-paper">
                    {/* Plik logo bywa skasowany albo nieosiągalny — wtedy inicjały, nie ikona zepsutego obrazka */}
                    {card.profile.logo_url && !logoBroken
                        ? <img src={getAssetUrl(card.profile.logo_url)} alt="" onError={() => setLogoBroken(true)} className="h-full w-full object-cover" />
                        : card.nazwa.substring(0, 2).toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                    {/* Wyróżnienie planu Firma lokalna = plakietka papierowa, nie złoto:
                        w tym świecie kolor niesie stan, a reklama nie jest stanem */}
                    {premium ? (
                        <Tag tone="paper"><span className="inline-flex items-center gap-1"><Star size={12} aria-hidden /> Polecane w Rybnie</span></Tag>
                    ) : (
                        <span className="inline-flex items-center gap-1 text-[13px] font-semibold text-tv-muted">
                            <BadgeCheck size={14} aria-hidden /> Zweryfikowana
                        </span>
                    )}
                    <h3 className="mt-1.5 text-[17px] font-semibold leading-snug text-white">{card.nazwa}</h3>
                </div>
            </div>

            {card.profile.description && (
                <p className="line-clamp-3 max-w-[70ch] text-[15px] leading-relaxed text-[#d7dbe8]">
                    {card.profile.description}
                </p>
            )}

            {/* Aktywne ogłoszenia/okazje firmy (plan Firma lokalna) */}
            {announcements && announcements.length > 0 && (
                <div className="grid grid-cols-1 gap-px bg-tv-seam">
                    {announcements.map(a => (
                        <div key={a.id} className="bg-tv-panel2 px-3 py-2.5">
                            <p className="flex items-start gap-1.5 text-[15px] font-bold leading-snug text-white">
                                {a.type === 'okazja'
                                    ? <TagIcon size={14} className="mt-1 shrink-0 text-tv-muted" aria-hidden />
                                    : <Megaphone size={14} className="mt-1 shrink-0 text-tv-muted" aria-hidden />}
                                <span className="min-w-0 flex-1">{a.title}</span>
                                {a.type === 'okazja' && a.valid_until && (
                                    <span className="font-cond tabular shrink-0 whitespace-nowrap bg-tv-yellow px-2 py-1 text-[13px] font-extrabold uppercase leading-none text-tv-ink">
                                        do {new Date(a.valid_until).toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' })}
                                    </span>
                                )}
                            </p>
                            <p className="mt-0.5 line-clamp-2 text-[14px] text-[#d7dbe8]">{a.body}</p>
                        </div>
                    ))}
                </div>
            )}

            <div className="mt-auto space-y-1 text-[14px] text-tv-muted">
                <p className="flex items-center gap-2"><MapPin size={14} className="shrink-0" aria-hidden />{card.miasto}{card.branza ? ` · ${card.branza}` : ''}</p>
                {card.profile.godziny && (
                    <p className="flex items-center gap-2"><Clock size={14} className="shrink-0" aria-hidden />{card.profile.godziny}</p>
                )}
            </div>

            <div className="flex flex-wrap gap-2 border-t border-tv-seam pt-3">
                {card.profile.telefon && (
                    <a
                        href={`tel:${card.profile.telefon.replace(/\s/g, '')}`}
                        // Kliknięcie w kontakt to JEDYNA liczba, którą wolno pokazać
                        // firmie jako „ktoś się Tobą zainteresował". Renderowanie
                        // karty (wyżej, `trackBusinessImpression`) mówi tylko tyle,
                        // że ktoś przeszedł obok wystawy
                        onClick={() => trackBusinessContact(card.id)}
                        className="font-cond inline-flex min-h-[44px] flex-1 items-center justify-center gap-1.5 bg-tv-blue px-3 text-[16px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff]"
                    >
                        <Phone size={15} aria-hidden /> Zadzwoń
                    </a>
                )}
                {card.profile.www && (
                    <a
                        href={card.profile.www.startsWith('http') ? card.profile.www : `https://${card.profile.www}`}
                        target="_blank" rel="noopener noreferrer"
                        onClick={() => trackBusinessContact(card.id)}
                        className="font-cond inline-flex min-h-[44px] flex-1 items-center justify-center gap-1.5 bg-tv-paper px-3 text-[16px] font-extrabold uppercase tracking-wide text-tv-ink transition-colors hover:bg-white"
                    >
                        <Globe size={15} aria-hidden /> WWW
                        <span className="sr-only">(otwiera się w nowej karcie)</span>
                    </a>
                )}
                {isOwner && (
                    <>
                        <button
                            onClick={onEdit}
                            className="font-cond inline-flex min-h-[44px] items-center justify-center gap-1.5 bg-tv-panel2 px-3 text-[16px] font-bold uppercase tracking-wide text-tv-paper transition-colors hover:bg-tv-seam hover:text-white"
                        >
                            <Pencil size={15} aria-hidden /> Edytuj
                        </button>
                        <button
                            onClick={onAnnouncements}
                            className="font-cond inline-flex min-h-[44px] items-center justify-center gap-1.5 bg-tv-panel2 px-3 text-[16px] font-bold uppercase tracking-wide text-tv-paper transition-colors hover:bg-tv-seam hover:text-white"
                        >
                            <Megaphone size={15} aria-hidden /> Ogłoszenia
                        </button>
                    </>
                )}
            </div>
        </article>
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

    // Tryb ręczny — firma, której nie ma w CEIDG (spółka, oddział, KGW).
    // Ta sama ścieżka, nie druga pozycja w menu: człowiek, który nie znalazł
    // swojej firmy, jest już tutaj i szuka. Odesłanie go do formularza
    // kontaktowego kończyło wizytę.
    const [manual, setManual] = useState(false);
    const [mNazwa, setMNazwa] = useState('');
    const [mMiasto, setMMiasto] = useState('');
    const [mNip, setMNip] = useState('');
    const [mUlica, setMUlica] = useState('');
    const [mBranza, setMBranza] = useState('');
    const [localities, setLocalities] = useState<string[]>([]);

    useEffect(() => {
        if (manual && localities.length === 0) {
            fetchGminaLocalities().then(setLocalities).catch(() => setLocalities([]));
        }
    }, [manual, localities.length]);

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
        if (!consent) return;
        if (manual ? !(mNazwa.trim() && mMiasto) : !selected) return;
        setSubmitting(true);
        setError(null);
        try {
            if (manual) {
                await addManualBusiness({
                    nazwa: mNazwa.trim(),
                    miasto: mMiasto,
                    nip: mNip.trim() || undefined,
                    ulica: mUlica.trim() || undefined,
                    branza: mBranza.trim() || undefined,
                    telefon: telefon.trim() || undefined,
                    email: email.trim() || undefined,
                    www: www.trim() || undefined,
                    note: note.trim() || undefined,
                });
            } else {
                await claimBusiness(selected!.id, {
                    telefon: telefon.trim() || undefined,
                    email: email.trim() || undefined,
                    www: www.trim() || undefined,
                    note: note.trim() || undefined,
                });
            }
            setDone(true);
            onClaimed();
        } catch (err: any) {
            setError(err.message);
        } finally {
            setSubmitting(false);
        }
    };

    if (done) {
        return (
            <ModalShell title="Zgłoszenie przyjęte" onClose={onClose}>
                <div className="flex items-start gap-3">
                    <CheckCircle2 size={24} className="mt-0.5 shrink-0 text-tv-green" aria-hidden />
                    <p className="text-[15px] leading-relaxed text-[#d7dbe8]">
                        {manual ? (
                            <>
                                Sprawdzimy wpis <strong className="text-white">{mNazwa}</strong> w ciągu
                                2 dni roboczych — firmy nie ma w rejestrze, więc potwierdzamy ją u źródła.
                                Do tego czasu jest widoczna tylko dla Ciebie.
                            </>
                        ) : (
                            <>
                                Zweryfikujemy przejęcie wizytówki <strong className="text-white">{selected?.nazwa}</strong> w
                                ciągu 2 dni roboczych. Po zatwierdzeniu uzupełnisz opis i godziny otwarcia.
                            </>
                        )}
                    </p>
                </div>
                <button onClick={onClose} className={`${PRIMARY_BTN} mt-6`}>
                    Zamknij
                </button>
            </ModalShell>
        );
    }

    return (
        <ModalShell
            title={manual ? 'Dodaj swoją firmę' : 'Przejmij wizytówkę'}
            onClose={onClose}
            sub={<>Krok <span className="tabular">{step}</span> z 2 — {step === 1
                ? 'znajdź swoją firmę w rejestrze'
                : manual ? 'dane firmy i kontakt' : 'dane kontaktowe do wizytówki'}</>}
        >
            {!isAuthenticated ? (
                <div>
                    <p className="mb-4 text-[15px] leading-relaxed text-[#d7dbe8]">
                        Do przejęcia wizytówki potrzebujesz bezpłatnego konta —
                        będzie służyć do zarządzania kartą Twojej firmy.
                    </p>
                    <button
                        onClick={() => { onClose(); onNavigate?.('login'); }}
                        className={PRIMARY_BTN}
                    >
                        Zaloguj się / Załóż konto
                    </button>
                </div>
            ) : step === 1 ? (
                <div className="space-y-3">
                    <div className="flex min-h-[52px] items-center gap-3 border-2 border-tv-seam bg-tv-ink pl-3 transition-colors focus-within:border-tv-paper">
                        <Search size={18} className="shrink-0 text-tv-muted" aria-hidden />
                        <input
                            type="text"
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            placeholder="Nazwa firmy lub NIP…"
                            aria-label="Nazwa firmy lub NIP"
                            className="min-w-0 flex-1 bg-transparent py-3 pr-3 text-[16px] text-white outline-none placeholder:text-tv-muted focus-visible:outline-none"
                            autoFocus
                        />
                    </div>
                    {searching && <p className="text-[14px] text-tv-muted">Szukam…</p>}
                    {results.length > 0 && (
                        <div className="grid max-h-72 grid-cols-1 gap-px overflow-y-auto bg-tv-seam">
                            {results.map(b => (
                                <button
                                    key={b.id}
                                    onClick={() => { setSelected(b); setStep(2); }}
                                    className="w-full bg-tv-ink p-3 text-left transition-colors hover:bg-tv-panel2"
                                >
                                    <p className="text-[16px] font-semibold text-white">{b.nazwa}</p>
                                    <p className="mt-0.5 flex items-center gap-1.5 text-[13px] text-tv-muted">
                                        <MapPin size={13} aria-hidden /> {b.miasto} · NIP <span className="tabular">{b.nip}</span>
                                    </p>
                                </button>
                            ))}
                        </div>
                    )}
                    {search.length >= 2 && !searching && results.length === 0 && (
                        <p className="py-3 text-[15px] text-tv-muted">
                            Nie znaleziono firmy o tej nazwie.
                        </p>
                    )}
                    {/* Wyjście dla firm spoza CEIDG: spółek, oddziałów, kół gospodyń.
                        Rejestr obejmuje wyłącznie jednoosobowe działalności, więc
                        „nie ma jej w wyszukiwarce" nie znaczy „nie istnieje" */}
                    <div className="mt-1 border-t border-tv-seam pt-3">
                        <p className="mb-2 text-[14px] leading-relaxed text-tv-muted">
                            Nie ma tu Twojej firmy? Rejestr CEIDG nie obejmuje spółek,
                            oddziałów ani kół gospodyń — dopisz ją ręcznie, sprawdzimy zgłoszenie.
                        </p>
                        <button
                            onClick={() => { setManual(true); setSelected(null); setStep(2); }}
                            className="font-cond inline-flex min-h-[48px] w-full items-center justify-center bg-tv-paper px-4 text-[16px] font-extrabold uppercase tracking-wide text-tv-ink transition-colors hover:bg-white"
                        >
                            Dodaj firmę ręcznie
                        </button>
                    </div>
                </div>
            ) : (
                <div className="space-y-4">
                    {manual ? (
                        <div className="space-y-3">
                            <input type="text" value={mNazwa} onChange={e => setMNazwa(e.target.value)}
                                placeholder="Pełna nazwa firmy *" autoFocus
                                className={FIELD} />
                            <div className="grid gap-3 sm:grid-cols-2">
                                <select value={mMiasto} onChange={e => setMMiasto(e.target.value)}
                                    aria-label="Miejscowość"
                                    className={`${FIELD} [color-scheme:dark]`}>
                                    <option value="">Miejscowość *</option>
                                    {localities.map(loc => <option key={loc} value={loc}>{loc}</option>)}
                                </select>
                                <input type="text" value={mUlica} onChange={e => setMUlica(e.target.value)}
                                    placeholder="Ulica i numer"
                                    className={FIELD} />
                            </div>
                            <div className="grid gap-3 sm:grid-cols-2">
                                <input type="text" value={mNip} onChange={e => setMNip(e.target.value)}
                                    placeholder="NIP (jeśli firma go ma)" inputMode="numeric"
                                    className={FIELD} />
                                {/* Trafia na wizytówkę jako opis — wpis ręczny nie ma kodu PKD,
                                    z którego katalog liczy branżę firmom z rejestru */}
                                <input type="text" value={mBranza} onChange={e => setMBranza(e.target.value)}
                                    placeholder="Czym się zajmujecie? (pokażemy na wizytówce)"
                                    className={FIELD} />
                            </div>
                            <button onClick={() => { setManual(false); setStep(1); }} className="inline-flex min-h-[44px] items-center gap-1 text-[15px] font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline">
                                <ChevronLeft size={16} aria-hidden /> wróć do wyszukiwarki
                            </button>
                        </div>
                    ) : (
                        <div className="bg-tv-panel2 px-3 pt-3">
                            <p className="text-[16px] font-semibold text-white">{selected?.nazwa}</p>
                            <p className="mt-0.5 flex items-center gap-1.5 text-[13px] text-tv-muted">
                                <MapPin size={13} aria-hidden /> {selected?.miasto} · NIP <span className="tabular">{selected?.nip}</span>
                            </p>
                            <button onClick={() => setStep(1)} className="inline-flex min-h-[44px] items-center gap-1 text-[15px] font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline">
                                <ChevronLeft size={16} aria-hidden /> zmień firmę
                            </button>
                        </div>
                    )}
                    <div className="grid gap-3 sm:grid-cols-2">
                        <input type="tel" value={telefon} onChange={e => setTelefon(e.target.value)} placeholder="Telefon firmowy"
                            className={FIELD} />
                        <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="E-mail firmowy"
                            className={FIELD} />
                    </div>
                    <input type="text" value={www} onChange={e => setWww(e.target.value)} placeholder="Strona WWW (opcjonalnie)"
                        className={FIELD} />
                    <textarea value={note} onChange={e => setNote(e.target.value)} rows={2}
                        placeholder={manual
                            ? 'Jak możemy potwierdzić, że firma działa? (np. adres szyldu, strona, profil na Facebooku)'
                            : 'Jak możemy potwierdzić, że to Twoja firma? (np. oddzwonimy na numer z szyldu/strony)'}
                        className={`${FIELD} resize-none`} />
                    <label className="flex cursor-pointer items-start gap-3">
                        <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} className="mt-0.5 h-5 w-5 shrink-0 accent-[#1f4fff]" />
                        <span className="text-[13px] leading-relaxed text-tv-muted">
                            {manual
                                ? 'Oświadczam, że reprezentuję tę firmę, podane dane są prawdziwe, a firma działa na terenie gminy Rybno. Wyrażam zgodę na publikację danych kontaktowych na wizytówce w katalogu firm RybnoLive.'
                                : 'Oświadczam, że reprezentuję tę firmę, i wyrażam zgodę na publikację podanych danych kontaktowych na wizytówce w katalogu firm RybnoLive.'}
                            {' '}<span className="font-bold text-tv-yellow">*</span>
                        </span>
                    </label>
                    {error && <FormError>{error}</FormError>}
                    <button
                        onClick={submit}
                        disabled={submitting || !consent || (manual && !(mNazwa.trim() && mMiasto))}
                        className={PRIMARY_BTN}
                    >
                        {submitting ? 'Wysyłam…' : manual ? 'Zgłoś firmę (0 zł)' : 'Przejmij wizytówkę (0 zł)'}
                    </button>
                </div>
            )}
        </ModalShell>
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
        <ModalShell
            wide
            onClose={onClose}
            title={<span className="inline-flex items-center gap-2"><ShieldCheck size={22} className="text-tv-muted" aria-hidden /> Weryfikacja wizytówek</span>}
        >
            {loading ? (
                <p className="py-6 text-center text-[15px] text-tv-muted">Wczytuję…</p>
            ) : claims.length === 0 ? (
                <p className="flex items-center justify-center gap-2 py-6 text-[15px] text-tv-paper">
                    <CheckCircle2 size={18} className="text-tv-green" aria-hidden /> Brak przejęć do weryfikacji
                </p>
            ) : (
                <div className="grid grid-cols-1 gap-px bg-tv-seam">
                    {claims.map(c => (
                        <div key={c.claim_id} className="bg-tv-panel py-4">
                            <div className="flex items-start gap-2">
                                <p className="flex-1 text-[16px] font-bold text-white">{c.nazwa}</p>
                                {c.source === 'manual' && <Tag tone="yellow">spoza CEIDG</Tag>}
                            </div>
                            <p className="mt-0.5 flex items-center gap-1.5 text-[13px] text-tv-muted">
                                <MapPin size={13} aria-hidden /> {c.miasto}{c.nip ? ` · NIP ${c.nip}` : ' · bez NIP-u'}
                            </p>
                            {c.source === 'manual' && (
                                // Przy przejęciu dane firmy potwierdza rejestr i sprawdzamy
                                // tylko zgłaszającego. Tutaj rejestr nie mówi nic — odrzucenie
                                // kasuje wiersz firmy razem z wizytówką
                                <p className="mt-1.5 text-[14px] leading-relaxed text-tv-yellow">
                                    Wpis ręczny — potwierdź, że firma istnieje i działa w gminie.
                                    Rejestr tego nie potwierdza.
                                </p>
                            )}
                            <p className="mt-1.5 flex flex-wrap items-center gap-x-1.5 text-[14px] text-[#d7dbe8]">
                                <User size={14} className="text-tv-muted" aria-hidden /> {c.user_email}
                                {c.telefon && <> · <Phone size={14} className="text-tv-muted" aria-hidden /> {c.telefon}</>}
                                {c.email && <> · <Mail size={14} className="text-tv-muted" aria-hidden /> {c.email}</>}
                            </p>
                            {/* Historia zgłaszającego. Odrzucenie kasuje wiersz wizytówki,
                                więc bez `business_claim_log` każdy wniosek wyglądał jak
                                pierwszy — także trzeci z rzędu po dwóch odmowach. */}
                            <p className="mt-1 text-[13px] text-tv-muted">
                                {c.user_registered_at && <>konto od {new Date(c.user_registered_at).toLocaleDateString('pl-PL')}</>}
                                {!!c.user_verified_profiles && <> · prowadzi {c.user_verified_profiles} {pluralPL(c.user_verified_profiles, 'wizytówkę', 'wizytówki', 'wizytówek')}</>}
                            </p>
                            {!!c.user_rejected_before && (
                                <p className="mt-2 bg-tv-yellow px-3 py-2 text-[14px] font-bold text-tv-ink">
                                    Wcześniej odrzuciliśmy {c.user_rejected_before}{' '}
                                    {pluralPL(c.user_rejected_before, 'wniosek', 'wnioski', 'wniosków')} tego konta
                                </p>
                            )}
                            {c.note && <p className="mt-1.5 text-[14px] italic text-[#d7dbe8]">„{c.note}"</p>}
                            <div className="mt-3 flex gap-2">
                                <button
                                    disabled={busyId === c.claim_id}
                                    onClick={() => decide(c.claim_id, 'approve')}
                                    className="font-cond inline-flex min-h-[44px] flex-1 items-center justify-center gap-1.5 bg-tv-blue text-[16px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff] disabled:opacity-50"
                                >
                                    <Check size={16} aria-hidden /> Zatwierdź
                                </button>
                                <button
                                    disabled={busyId === c.claim_id}
                                    onClick={() => decide(c.claim_id, 'reject')}
                                    className="font-cond inline-flex min-h-[44px] flex-1 items-center justify-center gap-1.5 bg-tv-panel2 text-[16px] font-bold uppercase tracking-wide text-tv-paper transition-colors hover:bg-tv-seam hover:text-white disabled:opacity-50"
                                >
                                    <X size={16} aria-hidden /> Odrzuć
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </ModalShell>
    );
};


/** Kafel liczby rejestru — plakietka nad wartością, jak `Plate` na pulpicie, bez przycisku. */
const StatPlate: React.FC<{ tag: string; value: number; tone?: 'blue' | 'yellow' | 'seam' }> = ({ tag, value, tone = 'blue' }) => (
    <div className="flex min-w-0 flex-col items-start">
        <Tag tone={tone}>{tag}</Tag>
        <span className="font-cond tabular w-full bg-tv-panel px-3.5 pb-3.5 pt-3 text-[26px] font-extrabold leading-[1.05] text-white lg:text-[30px]">
            {value}
        </span>
    </div>
);

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
    // `.filter`, nie `.find`: kto zgłosił dwie firmy, ma prawo widzieć status obu.
    // Do 19.08 baner pokazywał wyłącznie pierwsze zgłoszenie, więc drugie
    // wyglądało, jakby przepadło.
    const myPendingClaims = myClaims.filter(c => c.claim_status === 'pending');

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
        <div className="space-y-6 pb-12 lg:space-y-8">
            {/* ── Główka + przełącznik widoków ── */}
            <div className="space-y-3">
                <PageHead
                    title={view === 'katalog' ? 'Katalog Firm' : 'Firmy — dane i statystyki'}
                    sub={view === 'katalog'
                        // Liczba mnoga przy jednej wizytówce obiecuje więcej, niż katalog ma do pokazania
                        ? (catalog.length > 2
                            ? 'Sprawdzone lokalne firmy z Gminy Rybno — z kontaktem i godzinami otwarcia'
                            : 'Katalog firm z Gminy Rybno właśnie startuje — przejmij wizytówkę swojej firmy za darmo')
                        : 'Rejestr CEIDG: statystyki, sołectwa, branże i trendy rejestracji firm'}
                />
                <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                    <div role="group" aria-label="Widok" className="flex gap-1.5">
                        <Chip active={view === 'katalog'} onClick={() => setView('katalog')}>
                            <Store size={16} aria-hidden /> Katalog
                        </Chip>
                        <Chip active={view === 'dane'} onClick={() => setView('dane')}>
                            <BarChart3 size={16} aria-hidden /> Dane
                        </Chip>
                    </div>
                    {isAdmin && (
                        <button
                            onClick={() => setShowClaimsModeration(true)}
                            className={`font-cond inline-flex min-h-[44px] items-center gap-2 whitespace-nowrap px-3 text-[15px] font-bold uppercase tracking-wide transition-colors ${
                                pendingClaimsCount > 0
                                    ? 'bg-tv-yellow text-tv-ink hover:bg-[#ffe27a]'
                                    : 'bg-tv-panel text-tv-paper hover:bg-tv-panel2 hover:text-white'
                            }`}
                        >
                            <ShieldCheck size={16} aria-hidden /> Weryfikacja{pendingClaimsCount > 0 && <span className="tabular">({pendingClaimsCount})</span>}
                        </button>
                    )}
                    <button
                        onClick={() => onNavigate?.('stats')}
                        className="ml-auto inline-flex min-h-[44px] items-center gap-1.5 text-[15px] font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline"
                    >
                        <BarChart3 size={16} aria-hidden /> Statystyki GUS <ArrowRight size={16} aria-hidden />
                    </button>
                </div>
            </div>

            {/* ══════════ WIDOK: KATALOG WIZYTÓWEK ══════════ */}
            {view === 'katalog' && (
                <>
                    {/* Status mojego przejęcia */}
                    {myPendingClaims.map(claim => (
                        <div key={claim.business_id}
                            className="flex items-start gap-3 bg-tv-panel px-4 py-3 text-[15px] leading-snug text-tv-paper">
                            <Clock size={18} className="mt-0.5 shrink-0 text-tv-muted" aria-hidden />
                            <p>
                                Twoje zgłoszenie firmy <strong className="text-white">{claim.nazwa}</strong> czeka
                                na weryfikację — zwykle do 2 dni roboczych.
                                {onNavigate && (
                                    <button onClick={() => onNavigate('profile')}
                                        className="ml-1 font-bold text-tv-bluesoft underline underline-offset-4 hover:text-white">
                                        Status wszystkich Twoich firm
                                    </button>
                                )}
                            </p>
                        </div>
                    ))}

                    {catalogLoading ? (
                        <div className="grid grid-cols-1 gap-px bg-tv-seam lg:grid-cols-2" aria-busy="true">
                            {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-48" />)}
                        </div>
                    ) : catalog.length > 0 ? (
                        <section aria-label="Wizytówki firm">
                            <div className="flex items-baseline gap-3">
                                <Tag as="h2">Wizytówki</Tag>
                                <span className="tabular text-[14px] text-tv-muted">{catalog.length}</span>
                            </div>
                            <div className="grid grid-cols-1 gap-px border-t-2 border-tv-blue bg-tv-seam lg:grid-cols-2">
                                {catalog.map((card, i) => (
                                    <CatalogBusinessCard
                                        key={card.id}
                                        // Nieparzysta liczba kart: ostatnia na całą szerokość, inaczej
                                        // od lg zostaje pusta komórka w kolorze szwu
                                        span={i === catalog.length - 1 && catalog.length % 2 === 1}
                                        card={card}
                                        isOwner={myVerifiedByBusinessId.has(card.id)}
                                        onEdit={() => setEditClaim(myVerifiedByBusinessId.get(card.id) || null)}
                                        onAnnouncements={() => setAnnClaim(myVerifiedByBusinessId.get(card.id) || null)}
                                        announcements={activeAnns.filter(a => a.business_id === card.id).slice(0, 2)}
                                    />
                                ))}
                            </div>
                        </section>
                    ) : (
                        <div className="bg-tv-panel p-4 lg:p-5">
                            <h3 className="font-cond text-[21px] font-extrabold leading-snug text-white">Bądź pierwszy i przejmij swoją wizytówkę</h3>
                            <p className="mt-1 max-w-[60ch] text-[15px] leading-relaxed text-[#d7dbe8]">
                                Katalog wizytówek właśnie startuje. Przejmij kartę swojej firmy za darmo
                                i bądź widoczny dla mieszkańców całej gminy.
                            </p>
                        </div>
                    )}

                    {/* Sekcja "Dla firm" — lejek przejęcia wizytówki */}
                    <section className="border-t-2 border-tv-blue bg-tv-panel p-4 lg:p-5">
                        <div className="max-w-3xl">
                            <h2 className="font-cond text-[22px] font-extrabold leading-snug text-white lg:text-[26px]">Prowadzisz firmę w gminie?</h2>
                            <p className="mt-1 max-w-[70ch] text-[15px] leading-relaxed text-[#d7dbe8]">
                                Twoja firma prawdopodobnie już jest w naszym rejestrze — ale jej karta jest pusta.
                                Przejmij wizytówkę <strong className="text-white">za darmo</strong>: dodasz telefon,
                                godziny otwarcia i opis, a mieszkańcy znajdą Cię w katalogu.
                            </p>
                            {/* Trzy poziomy wizytówki — numer niesie kolejność, nie ozdobę */}
                            <div className="mt-4 grid grid-cols-1 gap-px bg-tv-seam sm:grid-cols-3">
                                <div className="bg-tv-panel2 p-3.5">
                                    <p className="font-cond text-[16px] font-extrabold uppercase tracking-wide text-white">1 · Rejestrowa</p>
                                    <p className="mt-1 text-[14px] leading-snug text-tv-muted">Podstawowe dane z CEIDG — bez kontaktu</p>
                                </div>
                                <div className="bg-tv-panel2 p-3.5">
                                    <p className="font-cond text-[16px] font-extrabold uppercase tracking-wide text-white">2 · Przejęta — 0 zł</p>
                                    <p className="mt-1 text-[14px] leading-snug text-tv-muted">Kontakt, godziny, opis + odznaka „Zweryfikowana"</p>
                                </div>
                                <div className="bg-tv-panel2 p-3.5">
                                    <p className="font-cond text-[16px] font-extrabold uppercase tracking-wide text-white">3 · Firma lokalna — 49 zł/mc</p>
                                    <p className="mt-1 text-[14px] leading-snug text-tv-muted">„Polecane w Rybnie", top pozycji, ogłoszenia, statystyki</p>
                                </div>
                            </div>
                            <button
                                onClick={() => setShowClaim(true)}
                                className="font-cond mt-5 inline-flex min-h-[52px] w-full items-center justify-center gap-2 bg-tv-blue px-5 text-[17px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff] sm:w-auto"
                            >
                                Przejmij wizytówkę swojej firmy <ArrowRight size={18} aria-hidden />
                            </button>
                            <p className="mt-3 text-[14px] text-tv-muted">
                                Szukasz firmy, której tu nie ma? Pełny rejestr znajdziesz w zakładce „Dane".
                            </p>
                        </div>
                    </section>
                </>
            )}

            {/* ══════════ WIDOK: DANE REJESTROWE I STATYSTYKI ══════════ */}
            {view === 'dane' && (
                <>
            {/* Kluczowe liczby — plakietki z wartością jak „Na dziś” na pulpicie */}
            <div className="grid grid-cols-2 gap-x-3 gap-y-4 lg:grid-cols-4 lg:gap-4">
                <StatPlate tag="Firmy w rejestrze" value={registeredCount} />
                <StatPlate tag="Aktywne" value={activeCount} />
                <StatPlate tag="Zawieszone" tone="yellow" value={suspendedCount} />
                <StatPlate tag="Miejscowości" tone="seam" value={localities.length} />
            </div>

            {/* Year chart */}
            {analytics && Object.keys(analytics.by_year).length > 0 && (
                <section aria-label="Firmy w rejestrze wg roku założenia">
                    <Tag as="h2">Firmy w rejestrze wg roku założenia</Tag>
                    <div className="border-t-2 border-tv-blue bg-tv-panel p-4 lg:p-5">
                        <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                            <div>
                                <p className="text-[14px] text-tv-muted">
                                    Wpisy istniejące dziś (bez wykreślonych) — kliknij słupek, aby przefiltrować karty
                                </p>
                                <div className="mt-2 flex gap-4 text-[13px]">
                                    <span className="flex items-center gap-1.5 text-tv-paper">
                                        <span className="inline-block h-2.5 w-3.5 bg-tv-blue" aria-hidden />
                                        W rejestrze
                                    </span>
                                    <span className="flex items-center gap-1.5 text-tv-paper">
                                        <span className="inline-block h-2.5 w-3.5 bg-tv-yellow" aria-hidden />
                                        Zawieszone
                                    </span>
                                </div>
                            </div>

                            {/* Wybrany rok */}
                            {selectedYear && (
                                <div className="flex items-start gap-1">
                                    <div className="min-w-[150px] bg-tv-panel2 px-3.5 py-2.5">
                                        <p className="font-cond tabular text-[13px] font-extrabold uppercase tracking-wide text-tv-paper">
                                            Rok {selectedYear}
                                        </p>
                                        <p className="tabular mt-1 text-[15px] font-bold text-white">
                                            {analytics.by_year[String(selectedYear)] ?? 0}
                                            <span className="ml-1 text-[13px] font-normal text-tv-muted">zarejestrowanych</span>
                                        </p>
                                        <p className="tabular text-[15px] font-bold text-tv-yellow">
                                            {(analytics.by_year_suspended ?? {})[String(selectedYear)] ?? 0}
                                            <span className="ml-1 text-[13px] font-normal text-tv-muted">zawieszonych</span>
                                        </p>
                                    </div>
                                    <button
                                        onClick={() => handleYearClick(null)}
                                        className="flex h-11 w-11 items-center justify-center text-tv-muted transition-colors hover:bg-tv-panel2 hover:text-white"
                                        title="Wyczyść filtr roku"
                                        aria-label="Wyczyść filtr roku"
                                    >
                                        <X size={18} aria-hidden />
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
                </section>
            )}

            {/* Wyszukiwarka — ten sam wygląd co pole pytania na pulpicie (AskBar) */}
            <div>
                <div className="flex min-h-[56px] items-center gap-3 border-2 border-tv-seam bg-tv-panel pl-4 transition-colors focus-within:border-tv-paper">
                    <Search size={20} className="shrink-0 text-tv-muted" aria-hidden />
                    <input
                        type="text"
                        placeholder="Szukaj firmy po nazwie..."
                        aria-label="Szukaj firmy po nazwie"
                        value={searchTerm}
                        onChange={e => setSearchTerm(e.target.value)}
                        className="min-w-0 flex-1 bg-transparent py-3 text-[17px] text-white outline-none placeholder:text-tv-muted focus-visible:outline-none"
                    />
                    {searchTerm && (
                        <button
                            onClick={clearSearch}
                            aria-label="Wyczyść wyszukiwanie"
                            className="flex h-12 w-12 shrink-0 items-center justify-center text-tv-muted transition-colors hover:text-white"
                        >
                            <X size={20} aria-hidden />
                        </button>
                    )}
                </div>
                {isSearchMode && (
                    <p className="mt-1.5 text-[14px] text-tv-muted">
                        {searchLoading ? 'Szukam...' : <>Znaleziono: <span className="tabular">{searchResults?.length ?? 0}</span> firm</>}
                        {' '}— <button onClick={clearSearch} className="font-bold text-tv-bluesoft underline underline-offset-4 hover:text-white">wyczyść</button>
                    </p>
                )}
            </div>

            {/* Filters: not shown in search mode */}
            {!isSearchMode && (
                <>
                    {categories.length > 0 && (
                        <div>
                            <Tag as="h2" tone="seam" className="mb-2">Branża</Tag>
                            <div role="group" aria-label="Branża" className="flex flex-wrap gap-1.5">
                                <Chip active={selectedCategory === null} onClick={() => handleCategorySelect(null)}>
                                    Wszystkie branże
                                </Chip>
                                {categories.map(cat => (
                                    <Chip
                                        key={cat.category}
                                        active={selectedCategory === cat.category}
                                        onClick={() => handleCategorySelect(cat.category)}
                                        count={cat.count}
                                    >
                                        {cat.category}
                                    </Chip>
                                ))}
                            </div>
                        </div>
                    )}

                    <div>
                        <Tag as="h2" tone="seam" className="mb-2">Miejscowość</Tag>
                        <div role="group" aria-label="Miejscowość" className="flex flex-wrap gap-1.5">
                            <Chip active={selectedLocality === null} onClick={() => handleLocalitySelect(null)}>
                                Wszystkie
                            </Chip>
                            {localities.map(loc => (
                                <Chip
                                    key={loc.name}
                                    active={selectedLocality === loc.name}
                                    onClick={() => handleLocalitySelect(loc.name)}
                                    count={loc.count}
                                >
                                    {loc.name}
                                </Chip>
                            ))}
                        </div>
                    </div>
                </>
            )}

            {/* Active filter info */}
            {(selectedLocality || selectedCategory) && !isSearchMode && (
                <div className="flex flex-wrap items-center gap-1.5">
                    <span className="mr-1 text-[14px] text-tv-muted">Filtrowanie:</span>
                    {selectedLocality && (
                        <button
                            onClick={() => setSelectedLocality(null)}
                            aria-label={`Usuń filtr: ${selectedLocality}`}
                            className="inline-flex min-h-[44px] items-center gap-1.5 bg-tv-paper px-3 text-[15px] font-semibold text-tv-ink transition-colors hover:bg-white"
                        >
                            <MapPin size={14} aria-hidden /> {selectedLocality} <X size={14} aria-hidden />
                        </button>
                    )}
                    {selectedCategory && (
                        <button
                            onClick={() => setSelectedCategory(null)}
                            aria-label={`Usuń filtr: ${selectedCategory}`}
                            className="inline-flex min-h-[44px] items-center gap-1.5 bg-tv-paper px-3 text-[15px] font-semibold text-tv-ink transition-colors hover:bg-white"
                        >
                            {selectedCategory} <X size={14} aria-hidden />
                        </button>
                    )}
                </div>
            )}

            {/* Siatka rejestru — linie robi tło szwu (`gap-px`), od lg dwie kolumny */}
            {displayedBusinesses.length > 0 && (
                <div className="grid grid-cols-1 gap-px border-t-2 border-tv-blue bg-tv-seam lg:grid-cols-2">
                    {displayedBusinesses.map((business, i) => {
                        const span = i === displayedBusinesses.length - 1 && displayedBusinesses.length % 2 === 1;
                        return (
                            <div key={business.id} className={`flex gap-3 bg-tv-panel p-4 ${span ? 'lg:col-span-2' : ''}`}>
                                <div className="flex h-11 w-11 shrink-0 items-center justify-center bg-tv-panel2 font-cond text-[15px] font-extrabold text-tv-paper">
                                    {business.nazwa.substring(0, 2).toUpperCase()}
                                </div>
                                <div className="min-w-0 flex-1">
                                    {/* Status słowem; kolor tylko dla zawieszonej — zanim mieszkaniec
                                        zadzwoni, powinien wiedzieć, że firma może nie działać */}
                                    <p className="text-[13px] leading-snug">
                                        {business.status === 'ZAWIESZONY' ? (
                                            <Tag tone="yellow">Zawieszona</Tag>
                                        ) : (
                                            <span className={`font-bold ${business.status === 'AKTYWNY' ? 'text-tv-paper' : 'text-tv-muted'}`}>
                                                {business.status === 'AKTYWNY' ? 'Aktywna' : statusLabel(business.status)}
                                            </span>
                                        )}
                                        {business.branza && <span className="text-tv-muted"> · {business.branza}</span>}
                                    </p>
                                    <h3 className="mt-1 line-clamp-2 text-[16px] font-semibold leading-snug text-white">
                                        {business.nazwa}
                                    </h3>
                                    <p className="mt-1 flex items-start gap-1.5 text-[14px] leading-snug text-tv-muted">
                                        <MapPin size={14} className="mt-0.5 shrink-0" aria-hidden />
                                        <span>
                                            {business.ulica ? `${business.ulica} ${business.budynek}` : business.miasto}{business.lokal ? `/${business.lokal}` : ''}{' — '}
                                            {business.miasto}
                                        </span>
                                    </p>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Empty state */}
            {displayedBusinesses.length === 0 && !loading && !searchLoading && (
                <div className="bg-tv-panel px-4 py-3">
                    <p className="text-[15px] text-tv-paper">
                        {isSearchMode ? 'Brak firm pasujących do wyszukiwania' : 'Brak firm w tej kategorii'}
                    </p>
                    {isSearchMode && (
                        <button onClick={clearSearch} className="inline-flex min-h-[44px] items-center text-[15px] font-bold text-tv-bluesoft underline-offset-4 hover:text-white hover:underline">
                            Wyczyść wyszukiwanie
                        </button>
                    )}
                </div>
            )}
            {displayedBusinesses.length === 0 && (loading || searchLoading) && (
                <div className="grid grid-cols-1 gap-px bg-tv-seam lg:grid-cols-2" aria-busy="true">
                    {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-28" />)}
                </div>
            )}

            {/* Load More – only in list mode */}
            {!isSearchMode && hasMore && (
                <div className="flex justify-center">
                    <button
                        onClick={loadMore}
                        disabled={loading}
                        className="font-cond inline-flex min-h-[52px] items-center bg-tv-paper px-6 text-[17px] font-extrabold uppercase tracking-wide text-tv-ink transition-colors hover:bg-white disabled:opacity-50"
                    >
                        {loading ? 'Ładowanie...' : 'Pokaż więcej firm'}
                    </button>
                </div>
            )}
                </>
            )}

            {/* Nota prawna — klauzula informacyjna art. 14 RODO */}
            <div className="flex items-start gap-3 border-t border-tv-seam pt-4">
                <Info size={16} className="mt-0.5 shrink-0 text-tv-muted" aria-hidden />
                <p className="max-w-[80ch] text-[13px] leading-relaxed text-tv-muted">
                    Dane firm pochodzą z publicznego rejestru <strong className="text-tv-paper">CEIDG</strong> i
                    obejmują nazwę, adres wykonywania działalności, NIP, REGON, branżę, status wpisu
                    i rok rozpoczęcia działalności. Danych kontaktowych z rejestru nie pobieramy —
                    telefon i e-mail widać tylko tam, gdzie firma podała je sama.
                    Szczegóły w{' '}
                    <button
                        onClick={() => onNavigate?.('privacy')}
                        className="text-tv-bluesoft underline underline-offset-2 hover:text-white"
                    >
                        polityce prywatności (art. 14 RODO)
                    </button>.
                    {' '}Prowadzisz tę firmę i chcesz zaktualizować lub ukryć swoją kartę?
                    Napisz:{' '}
                    <a href="mailto:biuro@lumargo.pl?subject=Katalog%20firm%20RybnoLive" className="text-tv-bluesoft underline underline-offset-2 hover:text-white">
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
