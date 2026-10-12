import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { createPortal } from 'react-dom';
import {
    Camera,
    Check,
    CheckCircle2,
    ChevronDown,
    Clock,
    Crosshair,
    Eye,
    Map as MapIcon,
    MapPin,
    Send,
    Shield,
    ThumbsUp,
    User,
    X,
} from 'lucide-react';
import type { Report, ReportCategory, AppSection } from '../../types';
import {
    fetchReports,
    fetchReportsForMap,
    fetchReportsStats,
    fetchPendingReports,
    updateReportStatus,
    createReport,
    upvoteReport,
    getImageUrl,
    CATEGORY_CONFIG,
    STATUS_CONFIG,
    SEVERITY_CONFIG,
} from '../services/reportsApi';
import type { ReportMapItem } from '../../types';
import { useAuth } from '../context/AuthContext';
import { Chip, Notice, PageHead, Skeleton, Tag } from '../../components/simple/tv';

// ==================== Helpers ====================

function timeAgo(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'przed chwilą';
    if (mins < 60) return `${mins} min temu`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h temu`;
    const days = Math.floor(hrs / 24);
    if (days === 1) return 'wczoraj';
    if (days < 7) return `${days} dni temu`;
    return new Date(dateStr).toLocaleDateString('pl-PL');
}

// ==================== Pasek interwencji (model Kontakt 24) ====================

const TRACK_STEPS = [
    { key: 'new', label: 'Zgłoszone' },
    { key: 'verified', label: 'Zweryfikowane' },
    { key: 'forwarded', label: 'Przekazane' },
    { key: 'resolved', label: 'Rozwiązane' },
];

/** Pozycja statusu na pasku: -1 = nie pokazuj (pending/rejected) */
function trackPosition(status: string): number {
    switch (status) {
        case 'new': return 0;
        case 'verified': return 1;
        case 'forwarded': return 2;
        case 'in_progress': return 2; // w realizacji = po przekazaniu
        case 'resolved': return 3;
        default: return -1;
    }
}

/**
 * Czerwień tylko dla TRWAJĄCEJ awarii — kolor = stan, nie kategoria.
 * Kategoria „Alarm/Pożar” z AI sama nie wystarcza: zgłoszenie sprzed tygodnia
 * albo już załatwione w czerwieni czytałoby się jak sprawa na teraz. Okno 36 h
 * to ten sam próg „sprawy najbliższych godzin”, co w feedzie.
 */
const LIVE_ALARM_H = 36;
const isLiveAlarm = (r: { category: string; status: string; created_at: string }): boolean =>
    (r.category === 'emergency' || r.category === 'fire') &&
    r.status !== 'resolved' &&
    r.status !== 'rejected' &&
    Date.now() - new Date(r.created_at).getTime() <= LIVE_ALARM_H * 3_600_000;

/** Plakietka statusu. Rozwiązane = papier z zieloną IKONĄ obok (zieleń nigdy jako tło). */
const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
    const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.new;
    return (
        <span className="inline-flex items-center gap-1.5">
            {status === 'resolved' && <CheckCircle2 size={16} className="shrink-0 text-tv-green" aria-hidden />}
            <Tag tone={cfg.tone}>{cfg.label}</Tag>
        </span>
    );
};

/** Pole formularza: szew 2 px na tle atramentu, 52 px, 16 px tekstu (iOS nie powiększa). */
const FIELD =
    'w-full min-h-[52px] border-2 border-tv-seam bg-tv-ink px-3 text-[16px] text-white outline-none transition-colors placeholder:text-tv-muted focus:border-tv-paper';
const LABEL = 'mb-1.5 block text-[15px] font-bold text-white';
const BTN_PRIMARY =
    'font-cond inline-flex min-h-[52px] items-center justify-center gap-2 bg-tv-blue px-5 text-[17px] font-extrabold uppercase tracking-wide text-white transition-colors hover:bg-[#3a63ff] disabled:cursor-not-allowed disabled:opacity-50';
const BTN_PAPER =
    'font-cond inline-flex min-h-[44px] items-center justify-center gap-2 bg-tv-paper px-5 text-[16px] font-extrabold uppercase tracking-wide text-tv-ink transition-colors hover:bg-white disabled:opacity-50';

/**
 * Płaski modal: panel z chabrowym szwem u góry, tło przyciemnione jednolicie (bez rozmycia).
 * Portal do `body`, bo `main` w App.tsx ma `relative z-10` — własny kontekst nakładania,
 * z którego `z-[1000]` nie wyjdzie: górny pasek i dolne zakładki zasłaniały główkę
 * modala i przycisk wysyłki.
 */
const ModalShell: React.FC<{
    onClose: () => void;
    label: string;
    maxWidth?: string;
    children: React.ReactNode;
}> = ({ onClose, label, maxWidth = 'max-w-2xl', children }) => createPortal(
    <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/70 p-3 sm:p-4" onClick={onClose}>
        <div
            role="dialog"
            aria-modal="true"
            aria-label={label}
            className={`relative max-h-[90vh] w-full ${maxWidth} overflow-y-auto border border-tv-seam border-t-2 border-t-tv-blue bg-tv-panel`}
            onClick={(e) => e.stopPropagation()}
        >
            {children}
        </div>
    </div>,
    document.body,
);

const CloseButton: React.FC<{ onClick: () => void; className?: string }> = ({ onClick, className = '' }) => (
    <button
        type="button"
        onClick={onClick}
        aria-label="Zamknij"
        className={`flex h-11 w-11 shrink-0 items-center justify-center bg-tv-panel2 text-tv-paper transition-colors hover:bg-tv-seam hover:text-white ${className}`}
    >
        <X size={20} aria-hidden />
    </button>
);

const InterventionTrack: React.FC<{ status: string; compact?: boolean }> = ({ status, compact }) => {
    const pos = trackPosition(status);
    if (pos < 0) return null;
    // Bieżący krok w kolorze stanu: żółć = w toku, papier = reszta; przebyte — wyciszone
    const nowBar = STATUS_CONFIG[status]?.tone === 'yellow' ? 'bg-tv-yellow' : 'bg-tv-paper';
    return (
        <ol className="grid w-full grid-cols-4 gap-px" aria-label={`Status interwencji: ${STATUS_CONFIG[status]?.label || status}`}>
            {TRACK_STEPS.map((step, i) => {
                const done = i < pos;
                const now = i === pos;
                return (
                    <li key={step.key} className="min-w-0" aria-current={now ? 'step' : undefined}>
                        <span className={`block ${compact ? 'h-1' : 'h-1.5'} ${now ? nowBar : done ? 'bg-tv-muted' : 'bg-tv-seam'}`} />
                        <span
                            className={`font-cond mt-1.5 flex items-center gap-1 text-[13px] leading-tight [overflow-wrap:anywhere] ${
                                now ? 'font-extrabold text-white' : 'text-tv-muted'
                            }`}
                        >
                            {now && status === 'resolved' && <CheckCircle2 size={13} className="shrink-0 text-tv-green" aria-hidden />}
                            {i === 2 && status === 'in_progress' ? 'W realizacji' : step.label}
                        </span>
                    </li>
                );
            })}
        </ol>
    );
};

/** Badge weryfikacji redakcyjnej — dla zgłoszeń potwierdzonych przez moderację */
const VERIFIED_STATUSES = ['verified', 'forwarded', 'in_progress', 'resolved'];

// ==================== ReportCard ====================

const ReportCard: React.FC<{
    report: Report;
    onUpvote: (id: number) => void;
    onView: (report: Report) => void;
}> = ({ report, onUpvote, onView }) => {
    const cat = CATEGORY_CONFIG[report.category] || CATEGORY_CONFIG.other;
    const severity = report.ai_severity ? SEVERITY_CONFIG[report.ai_severity] : null;
    const live = isLiveAlarm(report);
    const [imgError, setImgError] = useState(false);
    const [imgRetry, setImgRetry] = useState(0);

    const handleImgError = () => {
        if (imgRetry < 3) {
            setTimeout(() => setImgRetry((r) => r + 1), 1500);
        } else {
            setImgError(true);
        }
    };

    const imgSrc = report.image_url
        ? `${getImageUrl(report.image_url)}${imgRetry ? `?t=${imgRetry}` : ''}`
        : undefined;

    return (
        <div
            role="button"
            tabIndex={0}
            className="group flex cursor-pointer flex-col bg-tv-panel transition-colors hover:bg-tv-panel2"
            onClick={() => onView(report)}
            onKeyDown={(e) => { if (e.key === 'Enter') onView(report); }}
        >
            {/* Image */}
            {report.image_url && !imgError && (
                <div className="h-48 overflow-hidden bg-tv-panel2">
                    <img
                        src={imgSrc}
                        alt={report.title}
                        className="h-full w-full object-cover"
                        loading="lazy"
                        onError={handleImgError}
                    />
                </div>
            )}

            <div className="flex flex-1 flex-col p-4">
                {/* Rodzaj sprawy to opis, nie stan — bez koloru kategorii */}
                <div className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1.5 text-[13px] text-tv-muted">
                    {live && <Tag tone="red">Alarm</Tag>}
                    <span className="font-cond font-bold uppercase tracking-wide">{cat.label}</span>
                    {severity && !live && <span>· priorytet {severity.label.toLowerCase()}</span>}
                    {VERIFIED_STATUSES.includes(report.status) && (
                        <span className="inline-flex items-center gap-1 text-tv-paper">
                            <CheckCircle2 size={14} className="text-tv-green" aria-hidden /> Zweryfikowane
                        </span>
                    )}
                </div>

                <h3 className="mb-1.5 line-clamp-2 text-[18px] font-bold leading-snug text-white">
                    {report.title}
                </h3>

                <p className="mb-3 line-clamp-2 text-[15px] leading-snug text-[#d7dbe8]">
                    {report.ai_summary || report.description}
                </p>

                {/* Location */}
                {report.address && (
                    <p className="mb-3 flex items-center gap-1 text-[14px] text-tv-muted">
                        <MapPin size={14} className="shrink-0" aria-hidden />
                        <span className="truncate">{report.address}</span>
                    </p>
                )}

                {/* Pasek interwencji — publiczny postęp sprawy */}
                {trackPosition(report.status) >= 0 && (
                    <div className="mb-2 border-t border-tv-seam pt-3">
                        <InterventionTrack status={report.status} compact />
                    </div>
                )}

                {/* Footer */}
                <div className="mt-auto flex items-center justify-between border-t border-tv-seam pt-1">
                    <div className="flex items-center gap-3 text-[13px] text-tv-muted">
                        <span>{timeAgo(report.created_at)}</span>
                        <span className="tabular flex items-center gap-1">
                            <Eye size={14} aria-hidden /> {report.views_count}
                            <span className="sr-only">wyświetleń</span>
                        </span>
                    </div>

                    <button
                        onClick={(e) => {
                            e.stopPropagation();
                            onUpvote(report.id);
                        }}
                        className="inline-flex min-h-[44px] items-center gap-1.5 text-[15px] font-bold text-tv-bluesoft transition-colors hover:text-white"
                    >
                        <ThumbsUp size={16} aria-hidden />
                        {report.upvotes > 0 ? <span className="tabular">{report.upvotes} potwierdza</span> : 'Potwierdzam'}
                    </button>
                </div>
            </div>
        </div>
    );
};

// ==================== Report Detail Modal ====================

const ReportDetail: React.FC<{
    report: Report;
    onClose: () => void;
    onUpvote: (id: number) => void;
    isAdmin?: boolean;
    onStatusChange?: (id: number, status: string) => void;
}> = ({ report, onClose, onUpvote, isAdmin, onStatusChange }) => {
    const cat = CATEGORY_CONFIG[report.category] || CATEGORY_CONFIG.other;
    const severity = report.ai_severity ? SEVERITY_CONFIG[report.ai_severity] : null;
    const live = isLiveAlarm(report);
    const [detailImgError, setDetailImgError] = useState(false);
    const [savingStatus, setSavingStatus] = useState(false);

    return (
        <ModalShell onClose={onClose} label={report.title}>
            <CloseButton onClick={onClose} className="absolute right-3 top-3 z-10" />

            {/* Image */}
            {report.image_url && !detailImgError && (
                <div className="h-64 overflow-hidden bg-tv-panel2">
                    <img
                        src={getImageUrl(report.image_url)}
                        alt={report.title}
                        className="h-full w-full object-cover"
                        onError={() => setDetailImgError(true)}
                    />
                </div>
            )}

            <div className="p-5 sm:p-8">
                {/* Header */}
                <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2 pr-12">
                    {live && <Tag tone="red">Alarm</Tag>}
                    <StatusBadge status={report.status} />
                    <span className="font-cond text-[14px] font-bold uppercase tracking-wide text-tv-muted">{cat.label}</span>
                    {severity && !live && (
                        <span className="text-[14px] text-tv-muted">Priorytet: {severity.label}</span>
                    )}
                </div>

                <h2 className="font-cond mb-2 text-[26px] font-extrabold leading-tight text-white">{report.title}</h2>

                <div className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[14px] text-tv-muted">
                    <span className="flex items-center gap-1"><Clock size={14} aria-hidden /> {timeAgo(report.created_at)}</span>
                    {report.author_name && <span className="flex items-center gap-1"><User size={14} aria-hidden /> {report.author_name}</span>}
                    <span className="tabular flex items-center gap-1"><Eye size={14} aria-hidden /> {report.views_count} wyświetleń</span>
                </div>

                {/* Pasek interwencji */}
                {trackPosition(report.status) >= 0 && (
                    <div className="mb-6 max-w-md border-b border-tv-seam pb-6">
                        <InterventionTrack status={report.status} />
                    </div>
                )}

                {/* Panel urzędnika/redakcji — zmiana statusu interwencji */}
                {isAdmin && (
                    <div className="mb-6 border border-tv-seam bg-tv-ink p-4">
                        <h3 className="font-cond mb-2 flex items-center gap-1.5 text-[14px] font-extrabold uppercase tracking-wide text-tv-paper">
                            <Shield size={15} aria-hidden /> Panel redakcji — status interwencji
                        </h3>
                        <div className="flex flex-wrap gap-1.5">
                            {['new', 'verified', 'forwarded', 'in_progress', 'resolved', 'rejected'].map(s => (
                                <button
                                    key={s}
                                    disabled={savingStatus || report.status === s}
                                    aria-pressed={report.status === s}
                                    onClick={async () => {
                                        setSavingStatus(true);
                                        try { await onStatusChange?.(report.id, s); } finally { setSavingStatus(false); }
                                    }}
                                    className={`font-cond inline-flex min-h-[44px] items-center px-3 text-[15px] font-bold uppercase tracking-wide transition-colors ${
                                        report.status === s
                                            ? 'bg-tv-paper text-tv-ink'
                                            : 'bg-tv-panel text-tv-paper hover:bg-tv-panel2 hover:text-white'
                                    } disabled:cursor-default ${report.status === s ? '' : 'disabled:opacity-60'}`}
                                >
                                    {STATUS_CONFIG[s]?.label || s}
                                </button>
                            ))}
                        </div>
                        <p className="mt-2 text-[13px] text-tv-muted">
                            Autor zgłoszenia dostaje e-mail przy każdej zmianie statusu.
                        </p>
                    </div>
                )}

                {/* Description */}
                <section className="mb-6">
                    <Tag as="h3" tone="seam">Opis zgłoszenia</Tag>
                    <p className="whitespace-pre-wrap border-t border-tv-seam pt-3 text-[16px] leading-relaxed text-[#d7dbe8]">{report.description}</p>
                </section>

                {(report.ai_summary || report.ai_condition_assessment) && (
                    <div className="mb-6 grid gap-px bg-tv-seam md:grid-cols-2">
                        {/* AI Summary */}
                        {report.ai_summary && (
                            <section className="bg-tv-ink p-4">
                                <Tag as="h3" tone="seam">Streszczenie AI</Tag>
                                <p className="mt-2 text-[15px] leading-relaxed text-[#d7dbe8]">{report.ai_summary}</p>
                            </section>
                        )}

                        {/* AI Details */}
                        {report.ai_condition_assessment && (
                            <section className="bg-tv-ink p-4">
                                <Tag as="h3" tone="seam">Ocena stanu</Tag>
                                <p className="mt-2 text-[15px] leading-relaxed text-[#d7dbe8]">{report.ai_condition_assessment}</p>
                            </section>
                        )}
                    </div>
                )}

                {/* Location */}
                {report.address && (
                    <section className="mb-6">
                        <Tag as="h3" tone="seam">Lokalizacja</Tag>
                        <div className="border-t border-tv-seam pt-3">
                            <p className="flex items-start gap-1.5 text-[16px] text-[#d7dbe8]">
                                <MapPin size={16} className="mt-1 shrink-0 text-tv-muted" aria-hidden />{report.address}
                            </p>
                            {report.location_name && (
                                <p className="mt-1 pl-[22px] text-[14px] text-tv-muted">{report.location_name}</p>
                            )}
                        </div>
                    </section>
                )}

                {/* Actions */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-tv-seam pt-5">
                    <button
                        onClick={() => onUpvote(report.id)}
                        className={`${BTN_PRIMARY} min-h-[44px]`}
                    >
                        <ThumbsUp size={18} aria-hidden /> Potwierdź (<span className="tabular">{report.upvotes}</span>)
                    </button>
                    <button onClick={onClose} className={BTN_PAPER}>
                        Zamknij
                    </button>
                </div>
            </div>
        </ModalShell>
    );
};

// ==================== Locality GPS coordinates ====================

// Punkt podstawiany po wyborze miejscowości — dla każdego, kto nie zgodzi się
// na GPS przeglądarki. To jedyne źródło lokalizacji takiego zgłoszenia, więc
// błąd tutaj stawia pinezkę w cudzej wsi i nikt tego nie zauważy.
//
// 22.08.2026: poprzednia tabela była zmyślona — 11 z 12 sprawdzonych punktów
// leżało poza swoją miejscowością (Żabiny 8,9 km, Koszelewy 10,7 km, Kozłowo
// 23,5 km, samo Rybno 6,0 km). Do tego lista wyboru wymieniała pod nagłówkiem
// „Gmina Rybno" 16 wsi z OBCYCH gmin (Grodziczno, Szreńsk, Radomno…), a 15
// prawdziwych miejscowości gminy w ogóle w niej nie było.
//
// Nazwy pochodzą z `services/alert_policy.py` (_PLACES) — jedynej kanonicznej
// listy miejscowości gminy w projekcie. Współrzędne: Nominatim/OpenStreetMap,
// zapytanie „<nazwa>, gmina Rybno, powiat działdowski”.
const LOCALITY_COORDS: Record<string, [number, number]> = {
    // gmina Rybno
    'Rybno': [53.383457, 19.929167],
    'Dębień': [53.395153, 19.900660],
    'Grabacz': [53.344714, 19.948519],
    'Gralewo': [53.320128, 20.035088],
    'Gralewo-Stacja': [53.324807, 20.022768],
    'Gronowo': [53.373401, 19.867023],
    'Groszki': [53.423216, 19.966530],
    'Grądy': [53.357839, 19.859254],
    'Hartowiec': [53.397837, 19.843383],
    'Jeglia': [53.387398, 19.878273],
    'Kopaniarze': [53.348482, 19.905271],
    'Koszelewki': [53.327099, 19.892420],
    'Koszelewy': [53.327107, 19.968458],
    'Naguszewo': [53.418758, 19.960030],
    'Nowa Wieś': [53.388171, 20.003809],
    'Prusy': [53.372853, 19.987625],
    'Rapaty': [53.348831, 20.025953],
    'Rumian': [53.417703, 19.932398],
    'Szczupliny': [53.379718, 20.009078],
    'Truszczyny': [53.417985, 19.873705],
    'Tuczki': [53.354266, 19.953957],
    'Wery': [53.352684, 19.887731],
    'Żabiny': [53.343381, 19.989121],
    // okolice — poza gminą, ale w zasięgu spraw mieszkańca
    'Działdowo': [53.240637, 20.184687],
    'Lidzbark': [53.262804, 19.823184],
    'Iłowo-Osada': [53.166977, 20.297615],
    'Płośnica': [53.274575, 20.010217],
    'Kozłowo': [53.307176, 20.293128],
};

// ==================== Report Form Modal ====================

const ReportFormModal: React.FC<{
    onNavigate?: (section: AppSection) => void;
    onClose: () => void;
    onCreated: (report: Report) => void;
}> = ({ onNavigate, onClose, onCreated }) => {
    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');
    const [authorName, setAuthorName] = useState('');
    const [authorEmail, setAuthorEmail] = useState('');
    const [image, setImage] = useState<File | null>(null);
    const [imagePreview, setImagePreview] = useState<string | null>(null);
    const [address, setAddress] = useState('');
    const [locationName, setLocationName] = useState('');
    const [latitude, setLatitude] = useState<number | undefined>();
    const [longitude, setLongitude] = useState<number | undefined>();
    const [geoStatus, setGeoStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);
    const [gpsFromLocality, setGpsFromLocality] = useState(false);
    const [consentReport, setConsentReport] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Auto-geolocate on mount
    useEffect(() => {
        if ('geolocation' in navigator) {
            setGeoStatus('loading');
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    setLatitude(pos.coords.latitude);
                    setLongitude(pos.coords.longitude);
                    setGeoStatus('success');
                    // Reverse geocode
                    fetch(
                        `https://nominatim.openstreetmap.org/reverse?lat=${pos.coords.latitude}&lon=${pos.coords.longitude}&format=json&accept-language=pl`
                    )
                        .then((r) => r.json())
                        .then((data) => {
                            if (data.display_name) {
                                setAddress(data.display_name.split(',').slice(0, 3).join(','));
                            }
                            if (data.address?.city || data.address?.town || data.address?.village) {
                                setLocationName(data.address.city || data.address.town || data.address.village);
                            }
                        })
                        .catch(() => { });
                },
                () => setGeoStatus('error'),
                { enableHighAccuracy: true, timeout: 10000 }
            );
        }
    }, []);

    // When locality changes from dropdown, ALWAYS override GPS with locality coords
    useEffect(() => {
        if (locationName && locationName !== '__custom') {
            const coords = LOCALITY_COORDS[locationName];
            if (coords) {
                setLatitude(coords[0]);
                setLongitude(coords[1]);
                setGpsFromLocality(true);
            }
        }
    }, [locationName]);

    const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            setImage(file);
            const reader = new FileReader();
            reader.onload = () => setImagePreview(reader.result as string);
            reader.readAsDataURL(file);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!title.trim() || !description.trim()) {
            setError('Tytuł i opis są wymagane');
            return;
        }

        if (!consentReport) {
            setError('Wysłanie zgłoszenia wymaga zgody na przetwarzanie danych');
            return;
        }

        setSubmitting(true);
        setError(null);

        try {
            const report = await createReport({
                title: title.trim(),
                description: description.trim(),
                author_name: authorName.trim() || undefined,
                author_email: authorEmail.trim() || undefined,
                latitude,
                longitude,
                address: address.trim() || undefined,
                location_name: locationName.trim() || undefined,
                image: image || undefined,
            });

            setSuccess(true);
            setTimeout(() => {
                onCreated(report);
                onClose();
            }, 2000);
        } catch (err: any) {
            setError(err.message || 'Wystąpił błąd');
        } finally {
            setSubmitting(false);
        }
    };

    if (success) {
        return (
            <ModalShell onClose={() => {}} label="Zgłoszenie wysłane" maxWidth="max-w-md">
                <div className="p-8 text-center">
                    <CheckCircle2 size={44} className="mx-auto mb-4 text-tv-green" aria-hidden />
                    <h2 className="font-cond mb-2 text-[26px] font-extrabold text-white">Zgłoszenie wysłane!</h2>
                    <p className="text-[16px] leading-snug text-[#d7dbe8]">Dziękujemy. Zgłoszenie trafiło do moderacji — pojawi się na mapie po zatwierdzeniu.</p>
                </div>
            </ModalShell>
        );
    }

    return (
        <ModalShell onClose={onClose} label="Nowe zgłoszenie" maxWidth="max-w-lg">
            <div className="p-5 sm:p-8">
                <div className="mb-5 flex items-center justify-between gap-3 border-b border-tv-seam pb-3">
                    <h2 className="font-cond text-[26px] font-extrabold leading-tight text-white">Nowe zgłoszenie</h2>
                    <CloseButton onClick={onClose} />
                </div>

                <form onSubmit={handleSubmit} className="space-y-5">
                    {/* Photo */}
                    <div>
                        <span className={LABEL}>Zdjęcie (opcjonalne)</span>
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/*"
                            capture="environment"
                            onChange={handleImageChange}
                            className="hidden"
                        />
                        {imagePreview ? (
                            <div className="relative">
                                <img src={imagePreview} alt="Podgląd zdjęcia" className="h-48 w-full border-2 border-tv-seam object-cover" />
                                {/* Usuwanie zawsze widoczne — na telefonie nie ma „najechania” */}
                                <button
                                    type="button"
                                    aria-label="Usuń zdjęcie"
                                    onClick={() => {
                                        setImage(null);
                                        setImagePreview(null);
                                    }}
                                    className="absolute right-2 top-2 flex h-11 w-11 items-center justify-center bg-tv-ink text-white transition-colors hover:bg-tv-panel2"
                                >
                                    <X size={20} aria-hidden />
                                </button>
                            </div>
                        ) : (
                            <button
                                type="button"
                                onClick={() => fileInputRef.current?.click()}
                                className="flex h-32 w-full flex-col items-center justify-center gap-2 border-2 border-dashed border-tv-seam bg-tv-ink text-tv-paper transition-colors hover:border-tv-paper hover:text-white"
                            >
                                <Camera size={28} aria-hidden />
                                <span className="text-[15px] font-semibold">Zrób zdjęcie lub wybierz z galerii</span>
                            </button>
                        )}
                    </div>

                    {/* Title */}
                    <div>
                        <label htmlFor="report-title" className={LABEL}>Tytuł zgłoszenia *</label>
                        <input
                            id="report-title"
                            type="text"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="np. Dziura w drodze na ul. Głównej"
                            className={FIELD}
                            required
                            maxLength={200}
                        />
                    </div>

                    {/* Description */}
                    <div>
                        <label htmlFor="report-description" className={LABEL}>Opis problemu *</label>
                        <textarea
                            id="report-description"
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="Opisz problem jak najdokładniej..."
                            rows={4}
                            className={`${FIELD} resize-none py-3`}
                            required
                        />
                    </div>

                    {/* Geolocation */}
                    <div role="group" aria-labelledby="report-loc-head" className="space-y-4 bg-tv-panel2 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                            <span id="report-loc-head" className="text-[15px] font-bold text-white">Lokalizacja zdarzenia *</span>
                            {geoStatus === 'loading' && (
                                <span className="text-[13px] text-tv-muted">Pobieranie GPS…</span>
                            )}
                            {geoStatus === 'success' && (
                                <span className="inline-flex items-center gap-1 text-[13px] font-semibold text-tv-paper">
                                    <CheckCircle2 size={14} className="text-tv-green" aria-hidden /> GPS znaleziony
                                </span>
                            )}
                            {geoStatus === 'error' && <Tag tone="yellow">Wpisz ręcznie</Tag>}
                        </div>

                        <p className="text-[14px] leading-snug text-tv-muted">Podaj dokładne miejsce, by służby mogły szybko dotrzeć na miejsce zdarzenia</p>

                        {/* Locality selector */}
                        <div>
                            <label htmlFor="report-locality" className="mb-1.5 block text-[14px] font-semibold text-tv-paper">Miejscowość</label>
                            <div className="relative">
                                <select
                                    id="report-locality"
                                    value={locationName}
                                    onChange={(e) => {
                                        const val = e.target.value;
                                        setLocationName(val);
                                        // Immediately set GPS coords for known localities
                                        if (val && val !== '__custom') {
                                            const coords = LOCALITY_COORDS[val];
                                            if (coords) {
                                                setLatitude(coords[0]);
                                                setLongitude(coords[1]);
                                                setGpsFromLocality(true);
                                            }
                                        }
                                    }}
                                    className={`${FIELD} appearance-none pr-10`}
                                >
                                    <option value="">— Wybierz miejscowość —</option>
                                    <optgroup label="Gmina Rybno" className="bg-tv-ink">
                                        <option value="Rybno">Rybno</option>
                                        <option value="Dębień">Dębień</option>
                                        <option value="Grabacz">Grabacz</option>
                                        <option value="Gralewo">Gralewo</option>
                                        <option value="Gralewo-Stacja">Gralewo-Stacja</option>
                                        <option value="Gronowo">Gronowo</option>
                                        <option value="Groszki">Groszki</option>
                                        <option value="Grądy">Grądy</option>
                                        <option value="Hartowiec">Hartowiec</option>
                                        <option value="Jeglia">Jeglia</option>
                                        <option value="Kopaniarze">Kopaniarze</option>
                                        <option value="Koszelewki">Koszelewki</option>
                                        <option value="Koszelewy">Koszelewy</option>
                                        <option value="Naguszewo">Naguszewo</option>
                                        <option value="Nowa Wieś">Nowa Wieś</option>
                                        <option value="Prusy">Prusy</option>
                                        <option value="Rapaty">Rapaty</option>
                                        <option value="Rumian">Rumian</option>
                                        <option value="Szczupliny">Szczupliny</option>
                                        <option value="Truszczyny">Truszczyny</option>
                                        <option value="Tuczki">Tuczki</option>
                                        <option value="Wery">Wery</option>
                                        <option value="Żabiny">Żabiny</option>
                                    </optgroup>
                                    <optgroup label="Okolice" className="bg-tv-ink">
                                        <option value="Działdowo">Działdowo</option>
                                        <option value="Lidzbark">Lidzbark</option>
                                        <option value="Iłowo-Osada">Iłowo-Osada</option>
                                        <option value="Płośnica">Płośnica</option>
                                        <option value="Kozłowo">Kozłowo</option>
                                    </optgroup>
                                    <optgroup label="Inne" className="bg-tv-ink">
                                        <option value="__custom">Inna miejscowość…</option>
                                    </optgroup>
                                </select>
                                <ChevronDown size={18} aria-hidden className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-tv-muted" />
                            </div>
                            {locationName === '__custom' && (
                                <input
                                    type="text"
                                    aria-label="Nazwa miejscowości"
                                    placeholder="Wpisz nazwę miejscowości"
                                    className={`${FIELD} mt-2`}
                                    onChange={(e) => {
                                        if (e.target.value.trim()) {
                                            setLocationName(e.target.value.trim());
                                        }
                                    }}
                                    autoFocus
                                />
                            )}
                        </div>

                        {/* Street / address */}
                        <div>
                            <label htmlFor="report-address" className="mb-1.5 block text-[14px] font-semibold text-tv-paper">Ulica / nr domu / punkt orientacyjny</label>
                            <input
                                id="report-address"
                                type="text"
                                value={address}
                                onChange={(e) => setAddress(e.target.value)}
                                placeholder="np. ul. Główna 15, przy sklepie Biedronka, droga do szkoły"
                                className={FIELD}
                            />
                            <p className="mt-1.5 text-[13px] text-tv-muted">
                                Wpisz ulicę z numerem lub opisz miejsce tak, by łatwo je odnaleźć
                            </p>
                        </div>

                        {/* GPS coords preview */}
                        {latitude && longitude && (
                            <p className="tabular flex items-center gap-2 border-t border-tv-seam pt-3 text-[13px] text-tv-muted">
                                <Crosshair size={14} aria-hidden />
                                GPS: {latitude.toFixed(5)}, {longitude.toFixed(5)}
                            </p>
                        )}
                    </div>

                    {/* Author info (anonymous by default) */}
                    <div className="space-y-2">
                        <p className="text-[14px] leading-snug text-tv-muted">Podaj dane kontaktowe (opcjonalnie – zgłoszenie może być anonimowe)</p>
                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                            <input
                                type="text"
                                aria-label="Twoje imię"
                                value={authorName}
                                onChange={(e) => setAuthorName(e.target.value)}
                                placeholder="Twoje imię"
                                className={FIELD}
                            />
                            <input
                                type="email"
                                aria-label="E-mail"
                                value={authorEmail}
                                onChange={(e) => setAuthorEmail(e.target.value)}
                                placeholder="Email"
                                className={FIELD}
                            />
                        </div>
                    </div>

                    {/* Zgoda RODO + ostrzeżenie o zdjęciach */}
                    <div className="space-y-px">
                        {/* Żółć = ostrzeżenie: zgłoszenie może zostać odrzucone */}
                        <p className="bg-tv-yellow px-3 py-2.5 text-[14px] leading-snug text-tv-ink">
                            Nie publikuj wizerunku osób trzecich bez ich zgody ani czytelnych
                            tablic rejestracyjnych — takie zgłoszenia mogą zostać odrzucone lub
                            zanonimizowane przez moderację.
                        </p>
                        <label className="flex min-h-[44px] cursor-pointer items-start gap-3 bg-tv-panel2 px-3 py-3">
                            <input
                                type="checkbox"
                                checked={consentReport}
                                onChange={(e) => setConsentReport(e.target.checked)}
                                className="mt-0.5 h-5 w-5 shrink-0 accent-[#1f4fff]"
                            />
                            <span className="text-[14px] leading-snug text-[#d7dbe8]">
                                Wyrażam zgodę na przetwarzanie danych zawartych w zgłoszeniu
                                (treść, lokalizacja, zdjęcie, opcjonalne dane kontaktowe) w celu
                                jego publikacji i obsługi, zgodnie z{' '}
                                <button
                                    type="button"
                                    onClick={() => { onClose(); onNavigate?.('privacy'); }}
                                    className="font-semibold text-tv-bluesoft underline underline-offset-2 hover:text-white"
                                >
                                    Polityką prywatności
                                </button>{' '}
                                <span className="text-white">*</span>
                            </span>
                        </label>
                    </div>

                    {/* Error */}
                    {error && (
                        <Notice tone="warn" role="alert">{error}</Notice>
                    )}

                    {/* Submit */}
                    <button
                        type="submit"
                        disabled={submitting || !title.trim() || !description.trim() || !consentReport}
                        className={`${BTN_PRIMARY} w-full`}
                    >
                        {submitting ? (
                            'Analizuję z AI…'
                        ) : (
                            <><Send size={18} aria-hidden /> Wyślij zgłoszenie</>
                        )}
                    </button>
                </form>
            </div>
        </ModalShell>
    );
};

// ==================== Alert Map (Leaflet with markers) ====================

const RYBNO_CENTER: [number, number] = [53.3904, 19.8400]; // Gmina Rybno center

/**
 * Kolor pinezki = stan, nie priorytet z AI. Czerwień wyłącznie dla trwającego
 * alarmu (`isLiveAlarm`); wysoki priorytet bez alarmu to „sprawdź” — żółć;
 * reszta papier. Kółko zostaje: na mapie to znak miejsca, nie ozdoba.
 */
const PIN_RED = '#d42a1f';
// Żółć znaczy w tym świecie kontekst/zapowiedź, nie „ważne” — priorytet niesie
// jasność: papier = wysoki, przygaszony = pozostałe (przegląd 11.10.2026)
const PIN_HIGH = '#f5f6fa';
const PIN_PAPER = '#7a83a0';

const pinColor = (r: ReportMapItem): string => {
    if (isLiveAlarm(r)) return PIN_RED;
    if (r.ai_severity === 'critical' || r.ai_severity === 'high') return PIN_HIGH;
    return PIN_PAPER;
};

const MapHead: React.FC<{ sub: React.ReactNode; legend?: boolean }> = ({ sub, legend }) => (
    <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 p-4">
        <div>
            <h2 className="font-cond text-[20px] font-extrabold text-white">Mapa alertów – gmina Rybno</h2>
            <p className="mt-0.5 text-[14px] text-tv-muted">{sub}</p>
        </div>
        {legend && (
            <ul className="flex flex-wrap gap-x-3 gap-y-1 text-[13px] text-tv-muted" aria-label="Legenda">
                <li className="flex items-center gap-1.5"><span className="inline-block h-3 w-3" style={{ background: PIN_RED }} />Alarm teraz</li>
                <li className="flex items-center gap-1.5"><span className="inline-block h-3 w-3" style={{ background: PIN_HIGH }} />Wysoki priorytet</li>
                <li className="flex items-center gap-1.5"><span className="inline-block h-3 w-3" style={{ background: PIN_PAPER }} />Pozostałe</li>
            </ul>
        )}
    </div>
);

const AlertMap: React.FC<{
    reports: ReportMapItem[];
    onSelectReport: (id: number) => void;
}> = ({ reports, onSelectReport }) => {
    // Auto-fit map to show all markers
    const bounds = useMemo(() => {
        if (!reports.length) return null;
        return L.latLngBounds(reports.map((r) => [r.latitude, r.longitude]));
    }, [reports]);

    // FitBounds helper component
    const FitBounds: React.FC<{ bounds: L.LatLngBounds }> = ({ bounds: b }) => {
        const map = useMap();
        useEffect(() => {
            map.fitBounds(b, { padding: [40, 40], maxZoom: 15 });
        }, [b, map]);
        return null;
    };

    if (!reports.length) {
        return (
            <section className="border-t-2 border-tv-blue bg-tv-panel" aria-label="Mapa alertów">
                <MapHead sub="Brak zgłoszeń z lokalizacją GPS" />
                <div style={{ height: 350 }}>
                    <MapContainer center={RYBNO_CENTER} zoom={12} style={{ height: '100%', width: '100%' }} scrollWheelZoom={false}>
                        <TileLayer
                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
                            url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
                        />
                    </MapContainer>
                </div>
            </section>
        );
    }

    // Płaska kropka: obwódka atramentu zamiast cienia
    const createPinIcon = (color: string, size: number) => {
        const dotSize = Math.round(Math.max(size * 0.5, 14));
        return L.divIcon({
            className: '',
            iconSize: [dotSize, dotSize],
            iconAnchor: [dotSize / 2, dotSize / 2],
            popupAnchor: [0, -dotSize / 2 - 4],
            html: `
                <div style="
                    width:${dotSize}px;
                    height:${dotSize}px;
                    background:${color};
                    border-radius:50%;
                    border:3px solid #0a0e1a;
                    cursor:pointer;
                "></div>
            `,
        });
    };

    return (
        <section className="border-t-2 border-tv-blue bg-tv-panel" aria-label="Mapa alertów">
            <MapHead sub={<><span className="tabular">{reports.length}</span> zgłoszeń z lokalizacją GPS</>} legend />

            {/* Leaflet Map */}
            <div className="h-[380px] lg:h-[500px]">
                <MapContainer center={RYBNO_CENTER} zoom={12} style={{ height: '100%', width: '100%' }} scrollWheelZoom={true}>
                    {bounds && <FitBounds bounds={bounds} />}
                    <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
                        url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
                    />
                    {reports.map((r) => {
                        const cat = CATEGORY_CONFIG[r.category] || CATEGORY_CONFIG.other;
                        const sev = r.ai_severity ? (SEVERITY_CONFIG[r.ai_severity] || SEVERITY_CONFIG.medium) : SEVERITY_CONFIG.medium;
                        const pinSize = r.ai_severity === 'critical' ? 42 : r.ai_severity === 'high' ? 36 : r.ai_severity === 'medium' ? 30 : 26;
                        const icon = createPinIcon(pinColor(r), pinSize);
                        return (
                            <Marker
                                key={r.id}
                                position={[r.latitude, r.longitude]}
                                icon={icon}
                                eventHandlers={{
                                    click: () => onSelectReport(r.id),
                                }}
                            >
                                <Popup className="dark-popup">
                                    {/* Dymek Leaflet ma jasne tło — tekst ciemny, bez kolorów kategorii */}
                                    <div style={{ minWidth: 200, color: '#0a0e1a' }}>
                                        <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 4, lineHeight: 1.3 }}>
                                            {r.title}
                                        </div>
                                        <div style={{ fontSize: 13, color: '#4a5168', marginBottom: 4 }}>
                                            {timeAgo(r.created_at)} · {cat.label} · priorytet {sev.label.toLowerCase()}
                                        </div>
                                        {r.upvotes > 0 && (
                                            <div style={{ fontSize: 13, color: '#4a5168' }}>
                                                {r.upvotes} potwierdzeń
                                            </div>
                                        )}
                                    </div>
                                </Popup>
                            </Marker>
                        );
                    })}
                </MapContainer>
            </div>
        </section>
    );
};

// ==================== Panel moderacji (admin) ====================

const ModerationPanel: React.FC<{
    onClose: () => void;
    onModerated: () => void;
}> = ({ onClose, onModerated }) => {
    const [pending, setPending] = useState<Report[]>([]);
    const [loading, setLoading] = useState(true);
    const [busyId, setBusyId] = useState<number | null>(null);

    const load = useCallback(() => {
        setLoading(true);
        fetchPendingReports()
            .then(data => setPending(data.reports))
            .catch(() => setPending([]))
            .finally(() => setLoading(false));
    }, []);

    useEffect(() => { load(); }, [load]);

    const moderate = async (id: number, status: 'verified' | 'rejected') => {
        setBusyId(id);
        try {
            await updateReportStatus(id, status);
            setPending(prev => prev.filter(r => r.id !== id));
            onModerated();
        } catch (err) {
            console.error('Moderation failed:', err);
        } finally {
            setBusyId(null);
        }
    };

    return (
        <ModalShell onClose={onClose} label="Moderacja zgłoszeń">
            <div className="p-5 sm:p-8">
                <div className="mb-5 flex items-start justify-between gap-3 border-b border-tv-seam pb-3">
                    <div>
                        <h2 className="font-cond text-[26px] font-extrabold leading-tight text-white">Moderacja zgłoszeń</h2>
                        <p className="mt-1 text-[14px] leading-snug text-tv-muted">
                            Zatwierdzone zgłoszenia publikują się na liście i mapie; przy zagrożeniach
                            wysyłany jest push. Autor dostaje e-mail o decyzji.
                        </p>
                    </div>
                    <CloseButton onClick={onClose} />
                </div>

                {loading ? (
                    <div className="space-y-px">
                        <Skeleton className="h-28" />
                        <Skeleton className="h-28" />
                    </div>
                ) : pending.length === 0 ? (
                    <p className="flex items-center gap-2 bg-tv-ink px-4 py-3 text-[15px] text-tv-paper">
                        <CheckCircle2 size={18} className="shrink-0 text-tv-green" aria-hidden />
                        Brak zgłoszeń oczekujących na moderację
                    </p>
                ) : (
                    <div className="grid gap-px bg-tv-seam">
                        {pending.map(r => {
                            const cat = CATEGORY_CONFIG[r.category] || CATEGORY_CONFIG.other;
                            return (
                                <div key={r.id} className="bg-tv-ink p-4">
                                    <div className="flex gap-4">
                                        {r.image_url && (
                                            <img
                                                src={getImageUrl(r.image_url)}
                                                alt=""
                                                className="h-20 w-20 shrink-0 object-cover"
                                            />
                                        )}
                                        <div className="min-w-0 flex-1">
                                            <div className="mb-1 flex flex-wrap gap-x-2 gap-y-0.5 text-[13px] text-tv-muted">
                                                <span className="font-cond font-bold uppercase tracking-wide">{cat.label}</span>
                                                <span>{timeAgo(r.created_at)}</span>
                                                {r.location_name && (
                                                    <span className="inline-flex items-center gap-1"><MapPin size={13} aria-hidden />{r.location_name}</span>
                                                )}
                                            </div>
                                            <p className="text-[16px] font-bold leading-snug text-white">{r.title}</p>
                                            <p className="mt-0.5 line-clamp-2 text-[14px] leading-snug text-[#d7dbe8]">{r.description}</p>
                                            {r.author_name && (
                                                <p className="mt-1 inline-flex items-center gap-1 text-[13px] text-tv-muted"><User size={13} aria-hidden />{r.author_name}</p>
                                            )}
                                        </div>
                                    </div>
                                    <div className="mt-3 grid grid-cols-2 gap-2">
                                        <button
                                            disabled={busyId === r.id}
                                            onClick={() => moderate(r.id, 'verified')}
                                            className={`${BTN_PRIMARY} min-h-[44px] px-3 text-[15px]`}
                                        >
                                            <Check size={16} aria-hidden /> Zatwierdź i opublikuj
                                        </button>
                                        <button
                                            disabled={busyId === r.id}
                                            onClick={() => moderate(r.id, 'rejected')}
                                            className="font-cond inline-flex min-h-[44px] items-center justify-center gap-2 bg-tv-panel2 px-3 text-[15px] font-extrabold uppercase tracking-wide text-tv-paper transition-colors hover:bg-tv-seam hover:text-white disabled:opacity-50"
                                        >
                                            <X size={16} aria-hidden /> Odrzuć
                                        </button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </ModalShell>
    );
};

// ==================== Main ReportsPage ====================

interface ReportsPageProps {
    onNavigate?: (section: AppSection) => void;
}

const ReportsPage: React.FC<ReportsPageProps> = ({ onNavigate }) => {
    const { user } = useAuth();
    const isAdmin = !!user?.is_admin;
    const [reports, setReports] = useState<Report[]>([]);
    const [mapReports, setMapReports] = useState<ReportMapItem[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(false);
    const [category, setCategory] = useState<ReportCategory | undefined>();
    const [showForm, setShowForm] = useState(false);
    const [selectedReport, setSelectedReport] = useState<Report | null>(null);
    const [showMap, setShowMap] = useState(true);
    const [showModeration, setShowModeration] = useState(false);
    const [resolvedLast30d, setResolvedLast30d] = useState<number | null>(null);
    const [pendingCount, setPendingCount] = useState(0);

    // Licznik skuteczności + liczba oczekujących (admin)
    const loadStats = useCallback(() => {
        fetchReportsStats()
            .then((s: any) => setResolvedLast30d(s.resolved_last_30d ?? 0))
            .catch(() => {});
        if (isAdmin) {
            fetchPendingReports()
                .then(data => setPendingCount(data.total))
                .catch(() => setPendingCount(0));
        }
    }, [isAdmin]);

    useEffect(() => { loadStats(); }, [loadStats]);

    // Zmiana statusu z panelu redakcji w szczegółach zgłoszenia
    const handleStatusChange = async (id: number, status: string) => {
        try {
            await updateReportStatus(id, status);
            setReports(prev => prev.map(r => (r.id === id ? { ...r, status: status as Report['status'] } : r)));
            setSelectedReport(prev => (prev && prev.id === id ? { ...prev, status: status as Report['status'] } : prev));
            loadStats();
        } catch (err) {
            console.error('Status change failed:', err);
        }
    };

    const loadReports = useCallback(async (pageNum: number, reset = false) => {
        setLoading(true);
        try {
            const data = await fetchReports({
                page: pageNum,
                limit: 12,
                category,
                sort: 'newest',
            });
            setReports((prev) => (reset ? data.reports : [...prev, ...data.reports]));
            setTotal(data.total);
        } catch (err) {
            console.error('Failed to load reports:', err);
        } finally {
            setLoading(false);
        }
    }, [category]);

    const loadMapReports = useCallback(async () => {
        try {
            const data = await fetchReportsForMap({ category, limit: 100 });
            setMapReports(data);
        } catch (err) {
            console.error('Failed to load map reports:', err);
        }
    }, [category]);

    useEffect(() => {
        setPage(1);
        loadReports(1, true);
        loadMapReports();
    }, [category, loadReports, loadMapReports]);

    const handleUpvote = async (id: number) => {
        try {
            const updated = await upvoteReport(id);
            setReports((prev) =>
                prev.map((r) => (r.id === id ? { ...r, upvotes: updated.upvotes } : r))
            );
            if (selectedReport?.id === id) {
                setSelectedReport({ ...selectedReport, upvotes: updated.upvotes });
            }
        } catch (err) {
            console.error('Upvote failed:', err);
        }
    };

    const handleViewReport = async (report: Report) => {
        setSelectedReport(report);
    };

    const handleSelectFromMap = async (id: number) => {
        const report = reports.find((r) => r.id === id);
        if (report) {
            setSelectedReport(report);
        }
    };

    const handleReportCreated = (newReport: Report) => {
        setReports((prev) => [newReport, ...prev]);
        setTotal((t) => t + 1);
        loadMapReports();
    };

    const hasMore = reports.length < total;

    const categories: { value: ReportCategory | undefined; label: string }[] = [
        { value: undefined, label: 'Wszystkie' },
        { value: 'emergency', label: 'Alarm' },
        { value: 'fire', label: 'Pożar' },
        { value: 'infrastructure', label: 'Infrastruktura' },
        { value: 'water', label: 'Woda' },
        { value: 'safety', label: 'Bezpieczeństwo' },
        { value: 'waste', label: 'Odpady' },
        { value: 'greenery', label: 'Zieleń' },
        { value: 'other', label: 'Inne' },
    ];

    return (
        <div className="space-y-6 pb-12 lg:space-y-8">
            <PageHead
                title="Zgłoszenia 24"
                sub="Widzisz coś ważnego? Sfotografuj i zgłoś — redakcja zweryfikuje, opublikuje i dopilnuje sprawy w urzędzie."
                aside={
                    <div className="flex flex-wrap items-center gap-2">
                        {isAdmin && (
                            <button
                                onClick={() => setShowModeration(true)}
                                className={`font-cond inline-flex min-h-[52px] items-center gap-2 px-4 text-[16px] font-extrabold uppercase tracking-wide transition-colors ${
                                    // Żółć = czeka na decyzję redakcji; bez kolejki — neutralnie
                                    pendingCount > 0
                                        ? 'bg-tv-yellow text-tv-ink hover:bg-[#ffe27a]'
                                        : 'bg-tv-panel text-tv-paper hover:bg-tv-panel2'
                                }`}
                            >
                                <Shield size={18} aria-hidden /> Moderacja{pendingCount > 0 ? <span className="tabular">({pendingCount})</span> : ''}
                            </button>
                        )}
                        <button onClick={() => setShowForm(true)} className={BTN_PRIMARY}>
                            <Camera size={20} aria-hidden /> Zgłoś temat
                        </button>
                    </div>
                }
            />

            {/* Liczniki — płyty na szwie, jak „Na dziś” na pulpicie */}
            <dl className="grid grid-cols-2 gap-px border-t-2 border-tv-blue bg-tv-seam md:grid-cols-4">
                <div className="bg-tv-panel p-4">
                    <dt className="font-cond text-[13px] font-extrabold uppercase tracking-wide text-tv-muted">Wszystkie</dt>
                    <dd className="font-cond tabular mt-1 text-[30px] font-extrabold leading-none text-white">{total}</dd>
                </div>
                <div className="bg-tv-panel p-4">
                    <dt className="font-cond text-[13px] font-extrabold uppercase tracking-wide text-tv-muted">Alarm</dt>
                    <dd className="font-cond tabular mt-1 text-[30px] font-extrabold leading-none text-white">{reports.filter(r => r.category === 'emergency').length}</dd>
                </div>
                <div className="bg-tv-panel p-4">
                    <dt className="font-cond flex items-center gap-1 text-[13px] font-extrabold uppercase tracking-wide text-tv-muted">
                        <CheckCircle2 size={14} className="text-tv-green" aria-hidden /> Rozwiązane (30 dni)
                    </dt>
                    <dd className="font-cond tabular mt-1 text-[30px] font-extrabold leading-none text-white">{resolvedLast30d ?? '—'}</dd>
                </div>
                <div className="bg-tv-panel p-4">
                    <dt className="font-cond text-[13px] font-extrabold uppercase tracking-wide text-tv-muted">Na mapie</dt>
                    <dd className="font-cond tabular mt-1 text-[30px] font-extrabold leading-none text-white">{mapReports.length}</dd>
                </div>
            </dl>

            {/* Controls bar above map */}
            <div className="flex flex-col items-start justify-between gap-3 md:flex-row md:items-center">
                <div role="group" aria-label="Kategorie" className="flex flex-wrap gap-1.5">
                    {categories.map((cat) => (
                        <Chip
                            key={cat.label}
                            active={category === cat.value}
                            alert={cat.value === 'emergency'}
                            onClick={() => setCategory(cat.value)}
                        >
                            {cat.label}
                        </Chip>
                    ))}
                </div>

                <button
                    onClick={() => setShowMap(!showMap)}
                    aria-pressed={showMap}
                    className="inline-flex min-h-[44px] shrink-0 items-center gap-1.5 text-[15px] font-bold text-tv-bluesoft underline-offset-4 transition-colors hover:text-white hover:underline"
                >
                    <MapIcon size={16} aria-hidden /> {showMap ? 'Ukryj mapę' : 'Pokaż mapę'}
                </button>
            </div>

            {/* Map */}
            {showMap && <AlertMap reports={mapReports} onSelectReport={handleSelectFromMap} />}

            {/* Reports Grid */}
            {loading && reports.length === 0 ? (
                <div className="grid grid-cols-1 gap-px sm:grid-cols-2" aria-label="Ładowanie zgłoszeń">
                    {[1, 2, 3].map(i => <Skeleton key={i} className="h-72" />)}
                </div>
            ) : reports.length === 0 ? (
                <div className="border-t-2 border-tv-blue bg-tv-panel p-6">
                    <h2 className="font-cond text-[22px] font-extrabold text-white">Brak zgłoszeń</h2>
                    <p className="mb-4 mt-1 text-[15px] text-[#d7dbe8]">Bądź pierwszy – zgłoś problem w swojej okolicy!</p>
                    <button onClick={() => setShowForm(true)} className={BTN_PRIMARY}>
                        <Camera size={20} aria-hidden /> Dodaj zgłoszenie
                    </button>
                </div>
            ) : (
                <section aria-label="Zgłoszenia mieszkańców">
                    {/* Section heading */}
                    <div className="flex items-baseline gap-3">
                        <Tag as="h2">Zgłoszenia mieszkańców</Tag>
                        <span className="tabular text-[14px] text-tv-muted">{total} łącznie</span>
                    </div>

                    {/* Szczeliny na tle atramentu, nie szwu: przy niepełnym ostatnim rzędzie
                        puste pole zlewa się ze stroną zamiast stać jak pusty kafel */}
                    <div className="grid grid-cols-1 gap-px border-t-2 border-tv-blue bg-tv-ink sm:grid-cols-2">
                        {reports.map((report) => (
                            <ReportCard
                                key={report.id}
                                report={report}
                                onUpvote={handleUpvote}
                                onView={handleViewReport}
                            />
                        ))}
                    </div>

                    {hasMore && (
                        <div className="pt-6 text-center">
                            <button
                                onClick={() => {
                                    const next = page + 1;
                                    setPage(next);
                                    loadReports(next);
                                }}
                                disabled={loading}
                                className={`${BTN_PAPER} min-h-[52px]`}
                            >
                                {loading ? 'Ładowanie...' : 'Pokaż więcej'}
                            </button>
                        </div>
                    )}
                </section>
            )}

            {/* Modals */}
            {showForm && (
                <ReportFormModal onNavigate={onNavigate} onClose={() => setShowForm(false)} onCreated={handleReportCreated} />
            )}
            {selectedReport && (
                <ReportDetail
                    report={selectedReport}
                    onClose={() => setSelectedReport(null)}
                    onUpvote={handleUpvote}
                    isAdmin={isAdmin}
                    onStatusChange={handleStatusChange}
                />
            )}
            {showModeration && (
                <ModerationPanel
                    onClose={() => setShowModeration(false)}
                    onModerated={() => {
                        loadStats();
                        loadReports(1, true);
                        loadMapReports();
                    }}
                />
            )}
        </div>
    );
};

export default ReportsPage;
