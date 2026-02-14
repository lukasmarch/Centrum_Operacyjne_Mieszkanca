import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Report, ReportCategory, AppSection } from '../../types';
import {
    fetchReports,
    fetchReportsForMap,
    createReport,
    upvoteReport,
    getImageUrl,
    CATEGORY_CONFIG,
    STATUS_CONFIG,
    SEVERITY_CONFIG,
} from '../services/reportsApi';
import type { ReportMapItem } from '../../types';

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

// ==================== ReportCard ====================

const ReportCard: React.FC<{
    report: Report;
    onUpvote: (id: number) => void;
    onView: (report: Report) => void;
}> = ({ report, onUpvote, onView }) => {
    const cat = CATEGORY_CONFIG[report.category] || CATEGORY_CONFIG.other;
    const status = STATUS_CONFIG[report.status] || STATUS_CONFIG.new;
    const severity = report.ai_severity ? SEVERITY_CONFIG[report.ai_severity] : null;

    return (
        <div
            className="bg-white rounded-2xl border border-slate-100 shadow-sm hover:shadow-lg transition-all duration-300 overflow-hidden cursor-pointer group"
            onClick={() => onView(report)}
        >
            {/* Image */}
            {report.image_url && (
                <div className="h-48 overflow-hidden relative">
                    <img
                        src={getImageUrl(report.image_url)}
                        alt={report.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                        loading="lazy"
                    />
                    <div className="absolute top-3 left-3 flex gap-2">
                        <span
                            className="px-2.5 py-1 rounded-full text-xs font-bold text-white shadow-lg"
                            style={{ backgroundColor: cat.color }}
                        >
                            {cat.emoji} {cat.label}
                        </span>
                    </div>
                    {severity && (
                        <div className="absolute top-3 right-3">
                            <span
                                className="px-2 py-1 rounded-full text-[10px] font-bold text-white uppercase tracking-wider"
                                style={{ backgroundColor: severity.color }}
                            >
                                {severity.label}
                            </span>
                        </div>
                    )}
                </div>
            )}

            <div className="p-5">
                {/* Category tag if no image */}
                {!report.image_url && (
                    <div className="flex gap-2 mb-3">
                        <span
                            className="px-2.5 py-1 rounded-full text-xs font-bold text-white"
                            style={{ backgroundColor: cat.color }}
                        >
                            {cat.emoji} {cat.label}
                        </span>
                        {severity && (
                            <span
                                className="px-2 py-1 rounded-full text-[10px] font-bold text-white uppercase"
                                style={{ backgroundColor: severity.color }}
                            >
                                {severity.label}
                            </span>
                        )}
                    </div>
                )}

                <h3 className="font-bold text-slate-900 text-lg leading-tight mb-2 line-clamp-2">
                    {report.title}
                </h3>

                <p className="text-slate-500 text-sm mb-4 line-clamp-2">
                    {report.ai_summary || report.description}
                </p>

                {/* Location */}
                {report.address && (
                    <p className="text-xs text-slate-400 mb-3 flex items-center gap-1">
                        <span>📍</span>
                        <span className="truncate">{report.address}</span>
                    </p>
                )}

                {/* Footer */}
                <div className="flex items-center justify-between pt-3 border-t border-slate-50">
                    <div className="flex items-center gap-3 text-xs text-slate-400">
                        <span
                            className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase"
                            style={{ backgroundColor: `${status.color}15`, color: status.color }}
                        >
                            {status.label}
                        </span>
                        <span>{timeAgo(report.created_at)}</span>
                    </div>

                    <div className="flex items-center gap-3">
                        <span className="text-xs text-slate-400">
                            👁 {report.views_count}
                        </span>
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                onUpvote(report.id);
                            }}
                            className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-red-50 text-red-500 hover:bg-red-100 transition-colors text-xs font-bold"
                        >
                            👍 {report.upvotes}
                        </button>
                    </div>
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
}> = ({ report, onClose, onUpvote }) => {
    const cat = CATEGORY_CONFIG[report.category] || CATEGORY_CONFIG.other;
    const status = STATUS_CONFIG[report.status] || STATUS_CONFIG.new;
    const severity = report.ai_severity ? SEVERITY_CONFIG[report.ai_severity] : null;

    return (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
            <div
                className="bg-white rounded-3xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Image */}
                {report.image_url && (
                    <div className="h-64 overflow-hidden rounded-t-3xl">
                        <img
                            src={getImageUrl(report.image_url)}
                            alt={report.title}
                            className="w-full h-full object-cover"
                        />
                    </div>
                )}

                <div className="p-8">
                    {/* Header */}
                    <div className="flex flex-wrap gap-2 mb-4">
                        <span className="px-3 py-1 rounded-full text-xs font-bold text-white" style={{ backgroundColor: cat.color }}>
                            {cat.emoji} {cat.label}
                        </span>
                        <span className="px-3 py-1 rounded-full text-xs font-bold" style={{ backgroundColor: `${status.color}15`, color: status.color }}>
                            {status.label}
                        </span>
                        {severity && (
                            <span className="px-3 py-1 rounded-full text-xs font-bold text-white" style={{ backgroundColor: severity.color }}>
                                Priorytet: {severity.label}
                            </span>
                        )}
                    </div>

                    <h2 className="text-2xl font-black text-slate-900 mb-2">{report.title}</h2>

                    <div className="flex items-center gap-4 text-sm text-slate-400 mb-6">
                        <span>🕐 {timeAgo(report.created_at)}</span>
                        {report.author_name && <span>👤 {report.author_name}</span>}
                        <span>👁 {report.views_count} wyświetleń</span>
                    </div>

                    {/* Description */}
                    <div className="mb-6">
                        <h3 className="font-bold text-slate-700 mb-2">Opis zgłoszenia</h3>
                        <p className="text-slate-600 whitespace-pre-wrap">{report.description}</p>
                    </div>

                    {/* AI Summary */}
                    {report.ai_summary && (
                        <div className="mb-6 p-4 bg-blue-50 rounded-xl border border-blue-100">
                            <h3 className="font-bold text-blue-700 mb-1 text-sm">🤖 Streszczenie AI</h3>
                            <p className="text-blue-800 text-sm">{report.ai_summary}</p>
                        </div>
                    )}

                    {/* AI Details */}
                    {report.ai_condition_assessment && (
                        <div className="mb-6 p-4 bg-amber-50 rounded-xl border border-amber-100">
                            <h3 className="font-bold text-amber-700 mb-1 text-sm">📋 Ocena stanu</h3>
                            <p className="text-amber-800 text-sm">{report.ai_condition_assessment}</p>
                        </div>
                    )}

                    {/* Location */}
                    {report.address && (
                        <div className="mb-6">
                            <h3 className="font-bold text-slate-700 mb-2">📍 Lokalizacja</h3>
                            <p className="text-slate-600">{report.address}</p>
                            {report.location_name && (
                                <p className="text-sm text-slate-400 mt-1">{report.location_name}</p>
                            )}
                        </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center justify-between pt-6 border-t border-slate-100">
                        <button
                            onClick={() => onUpvote(report.id)}
                            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-red-50 text-red-600 hover:bg-red-100 transition-colors font-bold"
                        >
                            👍 Potwierdź problem ({report.upvotes})
                        </button>
                        <button
                            onClick={onClose}
                            className="px-6 py-3 rounded-xl bg-slate-100 text-slate-600 hover:bg-slate-200 transition-colors font-bold"
                        >
                            Zamknij
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

// ==================== Locality GPS coordinates ====================

const LOCALITY_COORDS: Record<string, [number, number]> = {
    'Rybno': [53.3904, 19.8400],
    'Hartowiec': [53.3716, 19.7821],
    'Rumian': [53.4155, 19.8063],
    'Żabiny': [53.3502, 19.8555],
    'Koszelewki': [53.3990, 19.8751],
    'Jeżewo': [53.4056, 19.7635],
    'Dłutowo': [53.3660, 19.8200],
    'Fijewo': [53.3835, 19.8750],
    'Grodziczno': [53.3350, 19.8310],
    'Jamiełnik': [53.3550, 19.8110],
    'Koszelewy': [53.3940, 19.8520],
    'Lewałd Wielki': [53.4100, 19.8380],
    'Litwa': [53.3750, 19.7950],
    'Naguszewo': [53.3615, 19.8660],
    'Olszewko': [53.3450, 19.8400],
    'Ostaszewo': [53.3800, 19.8620],
    'Radomno': [53.3700, 19.8450],
    'Ruda': [53.3560, 19.8290],
    'Słup': [53.3490, 19.8150],
    'Starczówek': [53.3860, 19.7740],
    'Szreńsk': [53.3600, 19.7800],
    'Trzonki': [53.3950, 19.8150],
    'Zwiniarz': [53.4000, 19.7900],
    'Działdowo': [53.2375, 20.1688],
    'Lidzbark': [53.2619, 19.8285],
    'Iłowo-Osada': [53.1979, 20.2618],
    'Płośnica': [53.3180, 20.0670],
    'Kozłowo': [53.5075, 20.4055],
};

// ==================== Report Form Modal ====================

const ReportFormModal: React.FC<{
    onClose: () => void;
    onCreated: (report: Report) => void;
}> = ({ onClose, onCreated }) => {
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
            <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/50 p-4">
                <div className="bg-white rounded-3xl p-12 text-center max-w-md w-full shadow-2xl">
                    <div className="text-6xl mb-4">✅</div>
                    <h2 className="text-2xl font-black text-slate-900 mb-2">Zgłoszenie wysłane!</h2>
                    <p className="text-slate-500">Zgłoszenie jest analizowane...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
            <div
                className="bg-white rounded-3xl max-w-lg w-full max-h-[90vh] overflow-y-auto shadow-2xl"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="p-8">
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-2xl font-black text-slate-900">🚨 Nowe Zgłoszenie</h2>
                        <button onClick={onClose} className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center text-slate-400 hover:bg-slate-200 transition-colors">
                            ✕
                        </button>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-5">
                        {/* Photo */}
                        <div>
                            <label className="block text-sm font-bold text-slate-700 mb-2">📸 Zdjęcie (opcjonalne)</label>
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
                                    <img src={imagePreview} alt="Preview" className="w-full h-48 object-cover rounded-xl" />
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setImage(null);
                                            setImagePreview(null);
                                        }}
                                        className="absolute top-2 right-2 w-8 h-8 rounded-full bg-red-500 text-white flex items-center justify-center text-sm font-bold"
                                    >
                                        ✕
                                    </button>
                                </div>
                            ) : (
                                <button
                                    type="button"
                                    onClick={() => fileInputRef.current?.click()}
                                    className="w-full h-32 border-2 border-dashed border-slate-200 rounded-xl flex flex-col items-center justify-center text-slate-400 hover:border-blue-300 hover:text-blue-500 transition-colors"
                                >
                                    <span className="text-3xl mb-1">📷</span>
                                    <span className="text-sm font-medium">Zrób zdjęcie lub wybierz z galerii</span>
                                </button>
                            )}
                        </div>

                        {/* Title */}
                        <div>
                            <label className="block text-sm font-bold text-slate-700 mb-2">Tytuł zgłoszenia *</label>
                            <input
                                type="text"
                                value={title}
                                onChange={(e) => setTitle(e.target.value)}
                                placeholder="np. Dziura w drodze na ul. Głównej"
                                className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 outline-none transition-all text-slate-800"
                                required
                                maxLength={200}
                            />
                        </div>

                        {/* Description */}
                        <div>
                            <label className="block text-sm font-bold text-slate-700 mb-2">Opis problemu *</label>
                            <textarea
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                placeholder="Opisz problem jak najdokładniej..."
                                rows={4}
                                className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 outline-none transition-all text-slate-800 resize-none"
                                required
                            />
                        </div>

                        {/* Geolocation */}
                        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="text-sm font-bold text-slate-700">📍 Lokalizacja zdarzenia *</span>
                                {geoStatus === 'loading' && (
                                    <span className="text-xs text-blue-500 animate-pulse px-2 py-0.5 bg-blue-50 rounded-full">📡 Pobieranie GPS...</span>
                                )}
                                {geoStatus === 'success' && (
                                    <span className="text-xs text-green-600 px-2 py-0.5 bg-green-50 rounded-full font-medium">✓ GPS znaleziony</span>
                                )}
                                {geoStatus === 'error' && (
                                    <span className="text-xs text-amber-600 px-2 py-0.5 bg-amber-50 rounded-full font-medium">⚠ Wpisz ręcznie</span>
                                )}
                            </div>

                            <p className="text-xs text-slate-400">Podaj dokładne miejsce, by służby mogły szybko dotrzeć na miejsce zdarzenia</p>

                            {/* Locality selector */}
                            <div>
                                <label className="block text-xs font-semibold text-slate-500 mb-1">Miejscowość</label>
                                <select
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
                                    className="w-full px-3 py-2.5 rounded-lg border border-slate-200 text-sm text-slate-700 bg-white focus:border-blue-400 focus:ring-2 focus:ring-blue-100 outline-none"
                                >
                                    <option value="">— Wybierz miejscowość —</option>
                                    <optgroup label="Gmina Rybno">
                                        <option value="Rybno">Rybno</option>
                                        <option value="Hartowiec">Hartowiec</option>
                                        <option value="Rumian">Rumian</option>
                                        <option value="Żabiny">Żabiny</option>
                                        <option value="Koszelewki">Koszelewki</option>
                                        <option value="Jeżewo">Jeżewo</option>
                                        <option value="Dłutowo">Dłutowo</option>
                                        <option value="Fijewo">Fijewo</option>
                                        <option value="Grodziczno">Grodziczno</option>
                                        <option value="Jamiełnik">Jamiełnik</option>
                                        <option value="Koszelewy">Koszelewy</option>
                                        <option value="Lewałd Wielki">Lewałd Wielki</option>
                                        <option value="Litwa">Litwa</option>
                                        <option value="Naguszewo">Naguszewo</option>
                                        <option value="Olszewko">Olszewko</option>
                                        <option value="Ostaszewo">Ostaszewo</option>
                                        <option value="Radomno">Radomno</option>
                                        <option value="Ruda">Ruda</option>
                                        <option value="Słup">Słup</option>
                                        <option value="Starczówek">Starczówek</option>
                                        <option value="Szreńsk">Szreńsk</option>
                                        <option value="Trzonki">Trzonki</option>
                                        <option value="Zwiniarz">Zwiniarz</option>
                                    </optgroup>
                                    <optgroup label="Okolice">
                                        <option value="Działdowo">Działdowo</option>
                                        <option value="Lidzbark">Lidzbark</option>
                                        <option value="Iłowo-Osada">Iłowo-Osada</option>
                                        <option value="Płośnica">Płośnica</option>
                                        <option value="Kozłowo">Kozłowo</option>
                                    </optgroup>
                                    <optgroup label="Inne">
                                        <option value="__custom">✏️ Inna miejscowość...</option>
                                    </optgroup>
                                </select>
                                {locationName === '__custom' && (
                                    <input
                                        type="text"
                                        placeholder="Wpisz nazwę miejscowości"
                                        className="w-full mt-2 px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-700 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 outline-none"
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
                                <label className="block text-xs font-semibold text-slate-500 mb-1">Ulica / nr domu / punkt orientacyjny</label>
                                <input
                                    type="text"
                                    value={address}
                                    onChange={(e) => setAddress(e.target.value)}
                                    placeholder="np. ul. Główna 15, przy sklepie Biedronka, droga do szkoły"
                                    className="w-full px-3 py-2.5 rounded-lg border border-slate-200 text-sm text-slate-700 focus:border-blue-400 focus:ring-2 focus:ring-blue-100 outline-none"
                                />
                                <p className="text-[11px] text-slate-300 mt-1">
                                    Wpisz ulicę z numerem lub opisz miejsce tak, by łatwo je odnaleźć
                                </p>
                            </div>

                            {/* GPS coords preview */}
                            {latitude && longitude && (
                                <div className="flex items-center gap-2 text-[11px] text-slate-400 bg-white px-3 py-2 rounded-lg border border-slate-100">
                                    <span>🛰️</span>
                                    <span>GPS: {latitude.toFixed(5)}, {longitude.toFixed(5)}</span>
                                </div>
                            )}
                        </div>

                        {/* Author info (anonymous by default) */}
                        <div className="space-y-3">
                            <p className="text-xs text-slate-400">Podaj dane kontaktowe (opcjonalnie – zgłoszenie może być anonimowe)</p>
                            <div className="grid grid-cols-2 gap-3">
                                <input
                                    type="text"
                                    value={authorName}
                                    onChange={(e) => setAuthorName(e.target.value)}
                                    placeholder="Twoje imię"
                                    className="px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-700"
                                />
                                <input
                                    type="email"
                                    value={authorEmail}
                                    onChange={(e) => setAuthorEmail(e.target.value)}
                                    placeholder="Email"
                                    className="px-3 py-2 rounded-lg border border-slate-200 text-sm text-slate-700"
                                />
                            </div>
                        </div>

                        {/* Error */}
                        {error && (
                            <div className="p-3 bg-red-50 text-red-600 rounded-xl text-sm font-medium">
                                ⚠️ {error}
                            </div>
                        )}

                        {/* Submit */}
                        <button
                            type="submit"
                            disabled={submitting || !title.trim() || !description.trim()}
                            className="w-full py-4 bg-gradient-to-r from-red-500 to-orange-500 text-white font-black text-lg rounded-xl hover:from-red-600 hover:to-orange-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-red-200"
                        >
                            {submitting ? (
                                <span className="flex items-center justify-center gap-2">
                                    <span className="animate-spin">⏳</span> Analizuję z AI...
                                </span>
                            ) : (
                                '🚨 Wyślij zgłoszenie'
                            )}
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
};

// ==================== Alert Map (Leaflet with markers) ====================

const RYBNO_CENTER: [number, number] = [53.3904, 19.8400]; // Gmina Rybno center

const AlertMap: React.FC<{
    reports: ReportMapItem[];
    onSelectReport: (id: number) => void;
}> = ({ reports, onSelectReport }) => {
    // Calculate map center from reports or use Rybno default
    const center = useMemo<[number, number]>(() => {
        if (!reports.length) return RYBNO_CENTER;
        const avgLat = reports.reduce((s, r) => s + r.latitude, 0) / reports.length;
        const avgLng = reports.reduce((s, r) => s + r.longitude, 0) / reports.length;
        return [avgLat, avgLng];
    }, [reports]);

    if (!reports.length) {
        return (
            <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
                <div className="p-4 border-b border-slate-100">
                    <h3 className="font-bold text-slate-900">🗺️ Mapa Alertów – Gmina Rybno</h3>
                    <p className="text-xs text-slate-400 mt-1">Brak zgłoszeń z lokalizacją GPS</p>
                </div>
                <div style={{ height: 350 }}>
                    <MapContainer center={RYBNO_CENTER} zoom={12} style={{ height: '100%', width: '100%' }} scrollWheelZoom={false}>
                        <TileLayer
                            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        />
                    </MapContainer>
                </div>
            </div>
        );
    }

    // Create a colored pin icon
    const createPinIcon = (color: string, emoji: string, size: number) => {
        return L.divIcon({
            className: '',
            iconSize: [size, size * 1.35],
            iconAnchor: [size / 2, size * 1.35],
            popupAnchor: [0, -size * 1.1],
            html: `
                <div style="position:relative;width:${size}px;height:${size * 1.35}px;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.35))">
                    <svg viewBox="0 0 40 54" width="${size}" height="${size * 1.35}">
                        <path d="M20 0C9 0 0 9 0 20c0 15 20 34 20 34s20-19 20-34C40 9 31 0 20 0z" fill="${color}" stroke="#fff" stroke-width="2"/>
                    </svg>
                    <span style="position:absolute;top:${size * 0.15}px;left:0;width:${size}px;text-align:center;font-size:${size * 0.42}px;line-height:1">${emoji}</span>
                </div>
            `,
        });
    };

    return (
        <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                <div>
                    <h3 className="font-bold text-slate-900">🗺️ Mapa Alertów – Gmina Rybno</h3>
                    <p className="text-xs text-slate-400 mt-1">{reports.length} zgłoszeń z lokalizacją GPS</p>
                </div>
                {/* Legend */}
                <div className="flex gap-3 text-[10px] text-slate-500">
                    <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-[#e74c3c] inline-block"></span>Krytyczny</span>
                    <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-[#e67e22] inline-block"></span>Wysoki</span>
                    <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-[#f39c12] inline-block"></span>Średni</span>
                    <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-[#27ae60] inline-block"></span>Niski</span>
                </div>
            </div>

            {/* Leaflet Map */}
            <div style={{ height: 500 }}>
                <MapContainer center={center} zoom={12} style={{ height: '100%', width: '100%' }} scrollWheelZoom={true}>
                    <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    />
                    {reports.map((r) => {
                        const cat = CATEGORY_CONFIG[r.category] || CATEGORY_CONFIG.other;
                        const sev = r.ai_severity ? (SEVERITY_CONFIG[r.ai_severity] || SEVERITY_CONFIG.medium) : SEVERITY_CONFIG.medium;
                        const pinSize = r.ai_severity === 'critical' ? 42 : r.ai_severity === 'high' ? 36 : r.ai_severity === 'medium' ? 30 : 26;
                        const icon = createPinIcon(sev.color, cat.emoji, pinSize);
                        return (
                            <Marker
                                key={r.id}
                                position={[r.latitude, r.longitude]}
                                icon={icon}
                                eventHandlers={{
                                    click: () => onSelectReport(r.id),
                                }}
                            >
                                <Popup>
                                    <div style={{ minWidth: 200 }}>
                                        <div style={{ fontWeight: 'bold', fontSize: 14, marginBottom: 6 }}>
                                            {cat.emoji} {r.title}
                                        </div>
                                        <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6 }}>
                                            {timeAgo(r.created_at)}
                                        </div>
                                        <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 6 }}>
                                            <span style={{
                                                fontSize: 10, fontWeight: 'bold', padding: '3px 10px',
                                                borderRadius: 12, color: '#fff', backgroundColor: cat.color
                                            }}>
                                                {cat.label}
                                            </span>
                                            <span style={{
                                                fontSize: 10, fontWeight: 'bold', padding: '3px 10px',
                                                borderRadius: 12, color: '#fff', backgroundColor: sev.color
                                            }}>
                                                {sev.label}
                                            </span>
                                        </div>
                                        {r.upvotes > 0 && (
                                            <div style={{ fontSize: 11, color: '#94a3b8' }}>
                                                👍 {r.upvotes} potwierdzeń
                                            </div>
                                        )}
                                    </div>
                                </Popup>
                            </Marker>
                        );
                    })}
                </MapContainer>
            </div>
        </div>
    );
};

// ==================== Main ReportsPage ====================

interface ReportsPageProps {
    onNavigate?: (section: AppSection) => void;
}

const ReportsPage: React.FC<ReportsPageProps> = ({ onNavigate }) => {
    const [reports, setReports] = useState<Report[]>([]);
    const [mapReports, setMapReports] = useState<ReportMapItem[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(false);
    const [category, setCategory] = useState<ReportCategory | undefined>();
    const [sort, setSort] = useState<'newest' | 'popular'>('newest');
    const [showForm, setShowForm] = useState(false);
    const [selectedReport, setSelectedReport] = useState<Report | null>(null);
    const [showMap, setShowMap] = useState(true);

    const loadReports = useCallback(async (pageNum: number, reset = false) => {
        setLoading(true);
        try {
            const data = await fetchReports({
                page: pageNum,
                limit: 12,
                category,
                sort,
            });
            setReports((prev) => (reset ? data.reports : [...prev, ...data.reports]));
            setTotal(data.total);
        } catch (err) {
            console.error('Failed to load reports:', err);
        } finally {
            setLoading(false);
        }
    }, [category, sort]);

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
    }, [category, sort, loadReports, loadMapReports]);

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

    const categories: { value: ReportCategory | undefined; label: string; emoji: string }[] = [
        { value: undefined, label: 'Wszystkie', emoji: '📋' },
        { value: 'emergency', label: 'Alarm', emoji: '🚨' },
        { value: 'fire', label: 'Pożar', emoji: '🔥' },
        { value: 'infrastructure', label: 'Infrastruktura', emoji: '🏗️' },
        { value: 'water', label: 'Woda', emoji: '💧' },
        { value: 'safety', label: 'Bezpieczeństwo', emoji: '⚠️' },
        { value: 'waste', label: 'Odpady', emoji: '🗑️' },
        { value: 'greenery', label: 'Zieleń', emoji: '🌳' },
        { value: 'other', label: 'Inne', emoji: '📋' },
    ];

    return (
        <div className="space-y-8 pb-12">
            {/* Header */}
            <header className="bg-gradient-to-r from-red-500 to-orange-500 rounded-3xl p-8 text-white shadow-xl shadow-red-200/30">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
                    <div>
                        <h2 className="text-3xl font-black">🚨 Zgłoszenie24</h2>
                        <p className="text-white/80 mt-2">Centrum Powiadamiania o Zdarzeniach – zgłoś problem w Twojej okolicy</p>
                    </div>
                    <button
                        onClick={() => setShowForm(true)}
                        className="px-8 py-4 bg-white text-red-600 font-black rounded-2xl hover:bg-red-50 transition-colors shadow-lg text-lg"
                    >
                        + Nowe zgłoszenie
                    </button>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8">
                    <div className="bg-white/10 backdrop-blur p-4 rounded-xl">
                        <p className="text-xs text-white/60 font-bold uppercase tracking-wider mb-1">Wszystkie</p>
                        <p className="text-2xl font-black">{total}</p>
                    </div>
                    <div className="bg-white/10 backdrop-blur p-4 rounded-xl">
                        <p className="text-xs text-white/60 font-bold uppercase tracking-wider mb-1">🚨 Alarm</p>
                        <p className="text-2xl font-black">{reports.filter(r => r.category === 'emergency').length}</p>
                    </div>
                    <div className="bg-white/10 backdrop-blur p-4 rounded-xl">
                        <p className="text-xs text-white/60 font-bold uppercase tracking-wider mb-1">🔥 Pożar</p>
                        <p className="text-2xl font-black">{reports.filter(r => r.category === 'fire').length}</p>
                    </div>
                    <div className="bg-white/10 backdrop-blur p-4 rounded-xl">
                        <p className="text-xs text-white/60 font-bold uppercase tracking-wider mb-1">🗺️ Na mapie</p>
                        <p className="text-2xl font-black">{mapReports.length}</p>
                    </div>
                </div>
            </header>

            {/* Filters */}
            <div className="flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
                <div className="flex flex-wrap gap-2">
                    {categories.map((cat) => (
                        <button
                            key={cat.label}
                            onClick={() => setCategory(cat.value)}
                            className={`px-4 py-2 rounded-full text-sm font-bold whitespace-nowrap transition-colors ${category === cat.value
                                ? 'bg-slate-900 text-white'
                                : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                                }`}
                        >
                            {cat.emoji} {cat.label}
                        </button>
                    ))}
                </div>

                <div className="flex gap-2">
                    <button
                        onClick={() => setSort('newest')}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${sort === 'newest' ? 'bg-blue-100 text-blue-700' : 'bg-white text-slate-500 border border-slate-200'
                            }`}
                    >
                        🕐 Najnowsze
                    </button>
                    <button
                        onClick={() => setSort('popular')}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${sort === 'popular' ? 'bg-blue-100 text-blue-700' : 'bg-white text-slate-500 border border-slate-200'
                            }`}
                    >
                        🔥 Popularne
                    </button>
                    <button
                        onClick={() => setShowMap(!showMap)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${showMap ? 'bg-green-100 text-green-700' : 'bg-white text-slate-500 border border-slate-200'
                            }`}
                    >
                        🗺️ Mapa
                    </button>
                </div>
            </div>

            {/* Map */}
            {showMap && <AlertMap reports={mapReports} onSelectReport={handleSelectFromMap} />}

            {/* Reports Grid */}
            {loading && reports.length === 0 ? (
                <div className="text-center py-12">
                    <span className="text-4xl animate-bounce block mb-4">🔍</span>
                    <p className="text-slate-400 font-medium">Ładowanie zgłoszeń...</p>
                </div>
            ) : reports.length === 0 ? (
                <div className="text-center py-16 bg-white rounded-3xl border border-slate-100">
                    <span className="text-6xl block mb-4">📭</span>
                    <h3 className="text-xl font-bold text-slate-700 mb-2">Brak zgłoszeń</h3>
                    <p className="text-slate-400 mb-6">Bądź pierwszy – zgłoś problem w swojej okolicy!</p>
                    <button
                        onClick={() => setShowForm(true)}
                        className="px-8 py-3 bg-red-500 text-white font-bold rounded-xl hover:bg-red-600 transition-colors"
                    >
                        + Dodaj zgłoszenie
                    </button>
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
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
                        <div className="text-center pt-4">
                            <button
                                onClick={() => {
                                    const next = page + 1;
                                    setPage(next);
                                    loadReports(next);
                                }}
                                disabled={loading}
                                className="px-8 py-3 bg-white border border-slate-200 text-slate-600 rounded-xl font-bold hover:bg-slate-50 disabled:opacity-50"
                            >
                                {loading ? 'Ładowanie...' : 'Pokaż więcej'}
                            </button>
                        </div>
                    )}
                </>
            )}

            {/* Modals */}
            {showForm && (
                <ReportFormModal onClose={() => setShowForm(false)} onCreated={handleReportCreated} />
            )}
            {selectedReport && (
                <ReportDetail
                    report={selectedReport}
                    onClose={() => setSelectedReport(null)}
                    onUpvote={handleUpvote}
                />
            )}
        </div>
    );
};

export default ReportsPage;
