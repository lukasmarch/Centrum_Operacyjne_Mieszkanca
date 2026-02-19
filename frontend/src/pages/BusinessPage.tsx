import React, { useState, useEffect } from 'react';
import { Business } from '../../types';
import { useAuth } from '../context/AuthContext';

interface Locality {
    name: string;
    count: number;
}

interface Stats {
    total_count: number;
    active_count: number;
    last_sync: string;
}

const BusinessPage: React.FC = () => {
    const { isAuthenticated } = useAuth();
    const [businesses, setBusinesses] = useState<Business[]>([]);
    const [localities, setLocalities] = useState<Locality[]>([]);
    const [stats, setStats] = useState<Stats | null>(null);
    const [selectedLocality, setSelectedLocality] = useState<string | null>(null);
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const [loading, setLoading] = useState(false);
    const [searchTerm, setSearchTerm] = useState("");

    // Fetch initial data (stats & localities)
    useEffect(() => {
        const fetchMetadata = async () => {
            try {
                // Fetch Stats
                const statsResponse = await fetch('http://localhost:8000/api/business/stats');
                if (statsResponse.ok) {
                    const statsData = await statsResponse.json();
                    if (statsData) setStats(statsData);
                }

                // Fetch Localities
                const locResponse = await fetch('http://localhost:8000/api/business/localities');
                if (locResponse.ok) {
                    const locData = await locResponse.json();
                    setLocalities(locData);
                }
            } catch (error) {
                console.error("Error fetching metadata:", error);
            }
        };
        fetchMetadata();
    }, []);

    // Fetch businesses when filters change
    useEffect(() => {
        setBusinesses([]);
        setPage(1);
        setHasMore(true);
        fetchBusinesses(1, true);
    }, [selectedLocality, searchTerm]);

    const fetchBusinesses = async (pageParam = 1, reset = false) => {
        if (loading) return;
        setLoading(true);

        try {
            let url = `http://localhost:8000/api/business/list?page=${pageParam}&limit=24`;

            if (selectedLocality) {
                // Use list endpoint with filter instead of dedicated endpoint for consistency
                url += `&miasto=${encodeURIComponent(selectedLocality)}`;
            }

            // Note: Current backend search endpoint is separate, 
            // but for simplicity we might want to consolidate or handle search differently.
            // If searchTerm is present, we use search endpoint instead of list
            if (searchTerm.length > 2) {
                // Only searching by name/NIP logic here if needed, 
                // but for now let's focus on locality filtering as requested.
                // If user wants general search, we might add it later or use the REGON widget.
                // Let's rely on list endpoint for now.
            }

            const response = await fetch(url);
            const data = await response.json();

            if (data.businesses) {
                setBusinesses(prev => reset ? data.businesses : [...prev, ...data.businesses]);
                setHasMore(data.businesses.length === 24); // assumption based on limit
            } else {
                setHasMore(false);
            }
        } catch (error) {
            console.error("Error fetching businesses:", error);
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

    // For manual sync trigger
    const handleSync = async () => {
        if (!isAuthenticated) return;
        try {
            const token = localStorage.getItem('access_token');
            const res = await fetch('http://localhost:8000/api/business/sync', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
            if (res.ok) {
                alert('Synchronizacja rozpoczęta! Odśwież stronę za chwilę.');
            } else {
                alert('Błąd synchronizacji');
            }
        } catch (e) {
            console.error(e);
        }
    };


    return (
        <div className="space-y-8 pb-12">
            {/* Header / Stats */}
            <header className="bg-slate-900/50 backdrop-blur-xl rounded-3xl p-8 border border-slate-800 shadow-sm">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 mb-8">
                    <div>
                        <h2 className="text-3xl font-black text-slate-100 tracking-tight">Katalog Firm</h2>
                        <p className="text-slate-400 mt-2">Baza przedsiębiorców z Gminy Rybno (CEIDG)</p>
                    </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700">
                        <p className="text-xs text-slate-400 font-bold uppercase tracking-wider mb-1">Wszystkie Firmy</p>
                        <p className="text-2xl font-black text-slate-100">{stats?.total_count || 0}</p>
                    </div>
                    <div className="bg-green-500/10 p-4 rounded-xl border border-green-500/20">
                        <p className="text-xs text-green-400 font-bold uppercase tracking-wider mb-1">Aktywne</p>
                        <p className="text-2xl font-black text-green-400">{stats?.active_count || 0}</p>
                    </div>
                    <div className="bg-blue-500/10 p-4 rounded-xl border border-blue-500/20">
                        <p className="text-xs text-blue-400 font-bold uppercase tracking-wider mb-1">Miejscowości</p>
                        <p className="text-2xl font-black text-blue-400">{localities.length}</p>
                    </div>
                    <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700">
                        <p className="text-xs text-slate-400 font-bold uppercase tracking-wider mb-1">Ostatnia Akt.</p>
                        <p className="text-sm font-semibold text-slate-300 mt-1">
                            {stats?.last_sync ? new Date(stats.last_sync).toLocaleDateString() : '-'}
                        </p>
                    </div>
                </div>
            </header>

            {/* Localities Tabs */}
            <div className="flex flex-wrap gap-2 pb-4 overflow-x-auto">
                <button
                    onClick={() => setSelectedLocality(null)}
                    className={`px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider whitespace-nowrap transition-colors ${selectedLocality === null
                        ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/30'
                        : 'bg-slate-800/50 text-slate-400 hover:bg-slate-800 border border-slate-700 hover:text-slate-200'
                        }`}
                >
                    Wszystkie
                </button>
                {localities.map(loc => (
                    <button
                        key={loc.name}
                        onClick={() => setSelectedLocality(loc.name)}
                        className={`px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider whitespace-nowrap transition-colors ${selectedLocality === loc.name
                            ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/30'
                            : 'bg-slate-800/50 text-slate-400 hover:bg-slate-800 border border-slate-700 hover:text-slate-200'
                            }`}
                    >
                        {loc.name} <span className="ml-1 opacity-60">({loc.count})</span>
                    </button>
                ))}
            </div>

            {/* Business Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {businesses.map((business) => (
                    <div key={business.id} className="group bg-slate-900/50 backdrop-blur-sm p-6 rounded-2xl border border-slate-800 hover:border-slate-700 shadow-sm hover:shadow-xl transition-all duration-300 flex flex-col h-full">
                        <div className="flex justify-between items-start mb-4">
                            <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider ${business.status === 'AKTYWNY'
                                    ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                                    : 'bg-slate-800 text-slate-500 border border-slate-700'
                                }`}>
                                {business.status}
                            </span>
                            {/* Initials Logo */}
                            <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-bold text-slate-400 group-hover:bg-slate-700 group-hover:text-white transition-colors">
                                {business.nazwa.substring(0, 2).toUpperCase()}
                            </div>
                        </div>

                        <h3 className="font-bold text-slate-100 mb-2 min-h-[3rem] line-clamp-2 group-hover:text-blue-400 transition-colors">
                            {business.nazwa}
                        </h3>

                        <div className="space-y-3 text-sm text-slate-400 mb-6 flex-1">
                            {business.wlasciciel_imie && (
                                <p className="flex items-center gap-2">
                                    <span className="text-slate-500">👤</span>
                                    <span>{business.wlasciciel_imie} {business.wlasciciel_nazwisko}</span>
                                </p>
                            )}
                            <p className="flex items-start gap-2">
                                <span className="text-slate-500 mt-0.5">📍</span>
                                <span>
                                    {business.ulica ? `${business.ulica} ${business.budynek}` : business.miasto}
                                    {business.lokal ? `/${business.lokal}` : ''} <br />
                                    {business.kod_pocztowy} {business.miasto}
                                </span>
                            </p>
                            <p className="flex items-center gap-2">
                                <span className="text-slate-500">💼</span>
                                NIP: <span className="font-mono text-slate-300">{business.nip}</span>
                            </p>
                            {business.branza && (
                                <p className="flex items-start gap-2 pt-2">
                                    <span className="text-xs font-semibold text-slate-300 bg-slate-800 border border-slate-700 px-2 py-1 rounded-lg">
                                        {business.branza}
                                    </span>
                                </p>
                            )}
                        </div>

                        <div className="pt-4 border-t border-slate-800 mt-auto">
                            {business.ceidg_link ? (
                                <a
                                    href={business.ceidg_link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="block w-full text-center py-2 rounded-xl bg-slate-800 text-slate-300 border border-slate-700 font-bold text-xs uppercase tracking-wider hover:bg-slate-700 hover:text-white hover:border-slate-600 transition-all"
                                >
                                    Zobacz w CEIDG ↗
                                </a>
                            ) : (
                                <button disabled className="block w-full text-center py-2 rounded-xl bg-slate-800/50 text-slate-600 border border-slate-800 font-bold text-xs uppercase tracking-wider cursor-not-allowed">
                                    Brak linku
                                </button>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            {/* Load More Trigger */}
            {hasMore && (
                <div className="text-center pt-8">
                    <button
                        onClick={loadMore}
                        disabled={loading}
                        className="px-8 py-3 bg-slate-900 border border-slate-700 text-slate-300 rounded-xl font-bold hover:bg-slate-800 disabled:opacity-50 transition-colors"
                    >
                        {loading ? 'Ładowanie...' : 'Pokaż więcej firm'}
                    </button>
                </div>
            )}
        </div>
    );
};

export default BusinessPage;
