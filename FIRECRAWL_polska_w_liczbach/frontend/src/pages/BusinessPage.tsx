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
            <header className="bg-white rounded-3xl p-8 border border-slate-100 shadow-sm">
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 mb-8">
                    <div>
                        <h2 className="text-3xl font-black text-slate-900">Katalog Firm</h2>
                        <p className="text-slate-500 mt-2">Baza przedsiębiorców z Gminy Rybno (CEIDG)</p>
                    </div>
                    {/* Sync button removed as requested */}
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                        <p className="text-xs text-slate-400 font-bold uppercase tracking-wider mb-1">Wszystkie Firmy</p>
                        <p className="text-2xl font-black text-slate-900">{stats?.total_count || 0}</p>
                    </div>
                    <div className="bg-green-50 p-4 rounded-xl border border-green-100">
                        <p className="text-xs text-green-600 font-bold uppercase tracking-wider mb-1">Aktywne</p>
                        <p className="text-2xl font-black text-green-700">{stats?.active_count || 0}</p>
                    </div>
                    <div className="bg-blue-50 p-4 rounded-xl border border-blue-100">
                        <p className="text-xs text-blue-600 font-bold uppercase tracking-wider mb-1">Miejscowości</p>
                        <p className="text-2xl font-black text-blue-700">{localities.length}</p>
                    </div>
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                        <p className="text-xs text-slate-400 font-bold uppercase tracking-wider mb-1">Ostatnia Akt.</p>
                        <p className="text-sm font-semibold text-slate-700 mt-1">
                            {stats?.last_sync ? new Date(stats.last_sync).toLocaleDateString() : '-'}
                        </p>
                    </div>
                </div>
            </header>

            {/* Localities Tabs */}
            <div className="flex flex-wrap gap-2 pb-4 overflow-x-auto">
                <button
                    onClick={() => setSelectedLocality(null)}
                    className={`px-4 py-2 rounded-full text-sm font-bold whitespace-nowrap transition-colors ${selectedLocality === null
                        ? 'bg-slate-900 text-white'
                        : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                        }`}
                >
                    Wszystkie
                </button>
                {localities.map(loc => (
                    <button
                        key={loc.name}
                        onClick={() => setSelectedLocality(loc.name)}
                        className={`px-4 py-2 rounded-full text-sm font-bold whitespace-nowrap transition-colors ${selectedLocality === loc.name
                            ? 'bg-blue-600 text-white shadow-lg shadow-blue-200'
                            : 'bg-white text-slate-600 hover:bg-slate-100 border border-slate-200'
                            }`}
                    >
                        {loc.name} <span className="ml-1 opacity-60 text-xs">({loc.count})</span>
                    </button>
                ))}
            </div>

            {/* Business Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {businesses.map((business) => (
                    <div key={business.id} className="bg-white p-6 rounded-2xl border border-slate-100 shadow-sm hover:shadow-md transition-shadow flex flex-col h-full">
                        <div className="flex justify-between items-start mb-4">
                            <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider ${business.status === 'AKTYWNY' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'
                                }`}>
                                {business.status}
                            </span>
                            {/* Initials Logo */}
                            <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-xs font-bold text-slate-400">
                                {business.nazwa.substring(0, 2).toUpperCase()}
                            </div>
                        </div>

                        <h3 className="font-bold text-slate-900 mb-2 min-h-[3rem]">
                            {business.nazwa}
                        </h3>

                        <div className="space-y-2 text-sm text-slate-500 mb-6 flex-1">
                            {business.wlasciciel_imie && (
                                <p className="flex items-center gap-2">
                                    <span className="text-slate-400">👤</span>
                                    {business.wlasciciel_imie} {business.wlasciciel_nazwisko}
                                </p>
                            )}
                            <p className="flex items-start gap-2">
                                <span className="text-slate-400 mt-0.5">📍</span>
                                <span>
                                    {business.ulica ? `${business.ulica} ${business.budynek}` : business.miasto}
                                    {business.lokal ? `/${business.lokal}` : ''} <br />
                                    {business.kod_pocztowy} {business.miasto}
                                </span>
                            </p>
                            <p className="flex items-center gap-2">
                                <span className="text-slate-400">💼</span>
                                NIP: {business.nip}
                            </p>
                            {business.branza && (
                                <p className="flex items-start gap-2">
                                    <span className="text-slate-400 mt-0.5">🏭</span>
                                    <span className="text-xs font-semibold text-slate-700 bg-slate-100 px-2 py-1 rounded-lg whitespace-normal">
                                        {business.branza}
                                    </span>
                                </p>
                            )}

                            {/* PREMIUM FEATURES (Business Account Only) 
                                - Contact Info (Phone, Email, WWW)
                                - Correspondence Address
                                - Partnerships
                                - Raw PKD
                            */}
                        </div>

                        <div className="pt-4 border-t border-slate-50 mt-auto">
                            {business.ceidg_link ? (
                                <a
                                    href={business.ceidg_link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="block w-full text-center py-2 rounded-xl bg-slate-50 text-slate-600 font-bold text-sm hover:bg-slate-100 transition-colors"
                                >
                                    Zobacz w CEIDG ↗
                                </a>
                            ) : (
                                <button disabled className="block w-full text-center py-2 rounded-xl bg-slate-50 text-slate-300 font-bold text-sm cursor-not-allowed">
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
                        className="px-8 py-3 bg-white border border-slate-200 text-slate-600 rounded-xl font-bold hover:bg-slate-50 disabled:opacity-50"
                    >
                        {loading ? 'Ładowanie...' : 'Pokaż więcej firm'}
                    </button>
                </div>
            )}
        </div>
    );
};

export default BusinessPage;
