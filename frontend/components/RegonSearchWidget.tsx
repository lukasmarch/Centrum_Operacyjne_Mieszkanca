import React, { useState, useRef } from 'react';
import { Search, Loader2, Building2, MapPin, Phone, Globe, X, ChevronDown, ChevronUp, CalendarDays } from 'lucide-react';

interface LocalBusiness {
    id: number;
    nazwa: string;
    miasto: string;
    ulica?: string;
    budynek?: string;
    lokal?: string;
    kod_pocztowy?: string;
    branza?: string;
    status: string;
    wlasciciel_imie?: string;
    wlasciciel_nazwisko?: string;
    data_rozpoczecia?: string;
    telefon?: string;
    www?: string;
    email?: string;
    pkd_main?: string;
}

// Quick-search category chips shown before the user types anything
const QUICK_CATEGORIES = [
    { label: 'Fryzjer', query: 'fryzjer', icon: '✂️' },
    { label: 'Mechanik', query: 'mechanik', icon: '🔧' },
    { label: 'Budowlane', query: 'budow', icon: '🏗️' },
    { label: 'Księgowa', query: 'księgow', icon: '📊' },
    { label: 'Sklep', query: 'sklep', icon: '🛒' },
    { label: 'Transport', query: 'transport', icon: '🚚' },
];

const CATEGORY_ICONS: Record<string, string> = {
    'Handel i naprawy': '🛒',
    'Budownictwo': '🏗️',
    'Transport': '🚚',
    'Informacja i komunikacja': '💻',
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
};

// Expandable business detail card
const BusinessCard: React.FC<{ item: LocalBusiness; onClose: () => void }> = ({ item, onClose }) => {
    const yearFounded = item.data_rozpoczecia ? new Date(item.data_rozpoczecia).getFullYear() : null;
    const addressLine = [item.ulica, item.budynek, item.lokal ? `m.${item.lokal}` : '']
        .filter(Boolean).join(' ') || item.miasto;

    return (
        <div className="rounded-2xl border border-blue-500/30 bg-gradient-to-br from-gray-950 to-gray-900/80 overflow-hidden shadow-xl">
            {/* Card header */}
            <div className="px-4 pt-4 pb-3 border-b border-gray-700/50/50 flex items-start justify-between gap-3">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                    <div className="w-10 h-10 rounded-xl bg-blue-500/20 border border-blue-500/30 flex items-center justify-center text-xs font-black text-blue-400 shrink-0">
                        {item.nazwa.substring(0, 2).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                        <h4 className="text-sm font-bold text-neutral-100 leading-tight">{item.nazwa}</h4>
                        {item.wlasciciel_imie && (
                            <p className="text-[11px] text-neutral-500 mt-0.5">
                                {item.wlasciciel_imie} {item.wlasciciel_nazwisko}
                            </p>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${item.status === 'AKTYWNY'
                        ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25'
                        : 'bg-gray-700 text-neutral-400 border border-gray-600'
                        }`}>
                        {item.status === 'AKTYWNY' ? '● aktywna' : item.status.toLowerCase()}
                    </span>
                    <button onClick={onClose} className="text-neutral-500 hover:text-neutral-300 transition-colors">
                        <X className="w-4 h-4" />
                    </button>
                </div>
            </div>

            {/* Card body */}
            <div className="px-4 py-3 space-y-2.5">
                {/* Category */}
                {item.branza && (
                    <div className="flex items-center gap-2">
                        <span className="text-neutral-500 w-4 text-center text-sm">{CATEGORY_ICONS[item.branza] ?? '📌'}</span>
                        <span className="text-[11px] font-semibold text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 rounded-md">
                            {item.branza}
                        </span>
                    </div>
                )}

                {/* Address */}
                <div className="flex items-start gap-2 text-xs text-neutral-400">
                    <MapPin className="w-3.5 h-3.5 text-neutral-500 mt-0.5 shrink-0" />
                    <span className="leading-snug">
                        {addressLine}
                        {item.kod_pocztowy && <>, {item.kod_pocztowy}</>} {item.miasto}
                    </span>
                </div>

                {/* Year founded */}
                {yearFounded && (
                    <div className="flex items-center gap-2 text-xs text-neutral-500">
                        <CalendarDays className="w-3.5 h-3.5 shrink-0" />
                        <span>Założona w {yearFounded} r.</span>
                    </div>
                )}

                {/* Phone */}
                {item.telefon && (
                    <a
                        href={`tel:${item.telefon.replace(/\s/g, '')}`}
                        className="flex items-center gap-2 text-xs text-blue-400 hover:text-blue-300 transition-colors group"
                    >
                        <Phone className="w-3.5 h-3.5 shrink-0" />
                        <span className="group-hover:underline">{item.telefon}</span>
                    </a>
                )}

                {/* Website */}
                {item.www && (
                    <a
                        href={item.www.startsWith('http') ? item.www : `https://${item.www}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-xs text-blue-400 hover:text-blue-300 transition-colors group truncate"
                    >
                        <Globe className="w-3.5 h-3.5 shrink-0" />
                        <span className="group-hover:underline truncate">{item.www}</span>
                    </a>
                )}
            </div>
        </div>
    );
};

// Compact result row (before expansion)
const ResultRow: React.FC<{ item: LocalBusiness; isSelected: boolean; onClick: () => void }> = ({ item, isSelected, onClick }) => (
    <button
        onClick={onClick}
        className={`w-full text-left px-3 py-2.5 rounded-xl border transition-all flex items-center justify-between gap-2 ${isSelected
            ? 'bg-blue-500/10 border-blue-500/30 text-neutral-100'
            : 'bg-white/[0.03] border-white/5 hover:bg-white/[0.07] hover:border-white/10 text-neutral-300'
            }`}
    >
        <div className="min-w-0">
            <p className="text-xs font-bold leading-tight truncate">{item.nazwa}</p>
            <p className="text-[10px] text-neutral-500 mt-0.5 flex items-center gap-1">
                <MapPin className="w-2.5 h-2.5 inline" /> {item.miasto}
                {item.branza && <> · <span className="text-indigo-400">{CATEGORY_ICONS[item.branza] ?? '📌'} {item.branza}</span></>}
            </p>
        </div>
        {isSelected
            ? <ChevronUp className="w-3.5 h-3.5 text-blue-400 shrink-0" />
            : <ChevronDown className="w-3.5 h-3.5 text-neutral-600 shrink-0" />
        }
    </button>
);

// ─── Main widget ─────────────────────────────────────────────────────────────

const BusinessSearchWidget: React.FC = () => {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState<LocalBusiness[]>([]);
    const [loading, setLoading] = useState(false);
    const [searched, setSearched] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedId, setSelectedId] = useState<number | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    const doSearch = async (term: string) => {
        if (term.trim().length < 2) return;
        setLoading(true);
        setError(null);
        setResults([]);
        setSearched(false);
        setSelectedId(null);

        try {
            const res = await fetch(
                `http://localhost:8000/api/business/search?nazwa=${encodeURIComponent(term.trim())}&limit=20`
            );
            if (!res.ok) {
                const e = await res.json();
                throw new Error(e.detail || 'Błąd wyszukiwania');
            }
            setResults(await res.json());
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
            setSearched(true);
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        doSearch(query);
    };

    const handleChip = (chipQuery: string) => {
        setQuery(chipQuery);
        doSearch(chipQuery);
        inputRef.current?.focus();
    };

    const handleSelect = (id: number) => setSelectedId(prev => prev === id ? null : id);

    const selectedItem = results.find(r => r.id === selectedId) ?? null;

    return (
        <div className="bg-gray-950 rounded-3xl p-5 border border-gray-800/50 h-full flex flex-col gap-4">
            {/* Header */}
            <div className="flex items-center gap-2">
                <Building2 size={14} className="text-emerald-400" />
                <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">Katalog Firm</span>
            </div>

            {/* Search bar */}
            <form onSubmit={handleSubmit} className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500 pointer-events-none" />
                <input
                    ref={inputRef}
                    type="text"
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    placeholder="Szukaj firmy po nazwie…"
                    className="w-full pl-9 pr-20 py-2.5 rounded-xl bg-black/60 border border-gray-700/50 text-sm text-neutral-200 placeholder:text-neutral-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all"
                />
                <button
                    type="submit"
                    disabled={loading || query.trim().length < 2}
                    className="absolute right-2 top-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold disabled:opacity-40 transition-colors flex items-center gap-1.5"
                >
                    {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Szukaj'}
                </button>
            </form>

            {/* Quick-category chips */}
            {!searched && !loading && (
                <div>
                    <p className="text-[10px] text-neutral-600 uppercase tracking-wider font-bold mb-2">Popularne kategorie</p>
                    <div className="flex flex-wrap gap-1.5">
                        {QUICK_CATEGORIES.map(cat => (
                            <button
                                key={cat.label}
                                onClick={() => handleChip(cat.query)}
                                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-gray-900/70 border border-gray-700/50 text-neutral-400 hover:bg-gray-700 hover:text-neutral-200 hover:border-gray-600 transition-all text-xs font-medium"
                            >
                                <span>{cat.icon}</span>
                                {cat.label}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Results area */}
            <div className="flex-1 flex flex-col gap-2 overflow-y-auto min-h-0 max-h-[360px] custom-scrollbar">
                {error && (
                    <div className="px-3 py-2 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
                        {error}
                    </div>
                )}

                {searched && results.length === 0 && !error && (
                    <div className="text-center py-8 text-neutral-500 text-xs">
                        Brak firm pasujących do „{query}"
                    </div>
                )}

                {results.map(item => (
                    <div key={item.id}>
                        <ResultRow
                            item={item}
                            isSelected={selectedId === item.id}
                            onClick={() => handleSelect(item.id)}
                        />
                        {selectedId === item.id && (
                            <div className="mt-1.5">
                                <BusinessCard item={item} onClose={() => setSelectedId(null)} />
                            </div>
                        )}
                    </div>
                ))}

                {results.length > 0 && !selectedId && (
                    <p className="text-[10px] text-neutral-600 text-center pt-1">
                        Kliknij firmę, aby zobaczyć szczegóły
                    </p>
                )}
            </div>
        </div>
    );
};

export default BusinessSearchWidget;
