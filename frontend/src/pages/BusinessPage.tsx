import React, { useState, useEffect, useCallback } from 'react';
import { Business } from '../../types';
import { useAuth } from '../context/AuthContext';
import { Search, X } from 'lucide-react';

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

const BusinessPage: React.FC = () => {
    const { isAuthenticated } = useAuth();
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

    return (
        <div className="space-y-8 pb-12">
            {/* Header / Stats */}
            <header className="bg-white/[0.04] backdrop-blur-xl rounded-3xl p-8 border border-white/5">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 mb-8">
                    <div>
                        <h2 className="text-3xl font-black text-neutral-100 tracking-tight">Katalog Firm</h2>
                        <p className="text-neutral-400 mt-2">Baza przedsiębiorców z Gminy Rybno (CEIDG)</p>
                    </div>
                </div>

                {/* Key stats */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    <div className="bg-white/[0.04] p-4 rounded-xl border border-white/8">
                        <p className="text-xs text-neutral-400 font-bold uppercase tracking-wider mb-1">Wszystkie Firmy</p>
                        <p className="text-2xl font-black text-neutral-100">{stats?.total_count ?? analytics?.total ?? 0}</p>
                    </div>
                    <div className="bg-green-500/10 p-4 rounded-xl border border-green-500/20">
                        <p className="text-xs text-green-400 font-bold uppercase tracking-wider mb-1">Aktywne</p>
                        <p className="text-2xl font-black text-green-400">{stats?.active_count ?? analytics?.by_status?.['AKTYWNY'] ?? 0}</p>
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
                                    📈 Rejestracje firm wg roku
                                </h3>
                                <p className="text-xs text-neutral-500 mt-0.5 mb-2">
                                    Kliknij słupek, aby przefiltrować karty po roku rejestracji
                                </p>
                                <div className="flex gap-4 text-xs">
                                    <span className="flex items-center gap-1.5 text-neutral-400">
                                        <span className="w-3 h-2 rounded-sm bg-blue-500/70 inline-block" />
                                        Zarejestrowane
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
                    const yearFounded = business.data_rozpoczecia
                        ? new Date(business.data_rozpoczecia).getFullYear()
                        : null;

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
                                {business.wlasciciel_imie && (
                                    <p className="flex items-center gap-2 text-xs">
                                        <span className="text-neutral-500">👤</span>
                                        <span className="truncate">{business.wlasciciel_imie} {business.wlasciciel_nazwisko}</span>
                                    </p>
                                )}
                                <p className="flex items-start gap-2 text-xs">
                                    <span className="text-neutral-500 mt-0.5 shrink-0">📍</span>
                                    <span className="leading-tight">
                                        {business.ulica ? `${business.ulica} ${business.budynek}` : business.miasto}{business.lokal ? `/${business.lokal}` : ''}{' — '}
                                        {business.miasto}
                                    </span>
                                </p>
                                {yearFounded && (
                                    <p className="flex items-center gap-2 text-xs text-neutral-500">
                                        <span>📅</span>
                                        <span>Zał. {yearFounded}</span>
                                    </p>
                                )}
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
        </div>
    );
};

export default BusinessPage;
