import React, { useState, useEffect } from 'react';
import { Film, CalendarDays, MapPin, Star, Clock, Ticket } from 'lucide-react';
import { fetchCinemaRepertoire } from '../src/services/geminiService';
import { CinemaRepertoire, CinemaLocation } from '../types';
import { useDataCache } from '../src/context/DataCacheContext';

export const CinemaWidget: React.FC = () => {
    const { getCinema, setCinema } = useDataCache();
    const [activeTab, setActiveTab] = useState<CinemaLocation>(CinemaLocation.DZIALDOWO);
    const [data, setData] = useState<Record<CinemaLocation, CinemaRepertoire | null>>({
        [CinemaLocation.DZIALDOWO]: null,
        [CinemaLocation.LUBAWA]: null
    });
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const loadData = async () => {
            // Check cache first
            const cachedData = getCinema(activeTab);
            if (cachedData) {
                setData(prev => ({ ...prev, [activeTab]: cachedData }));
                return;
            }

            // Fetch from API if not in cache
            setLoading(true);
            const rep = await fetchCinemaRepertoire(activeTab);
            setData(prev => ({ ...prev, [activeTab]: rep }));
            setCinema(activeTab, rep); // Store in cache
            setLoading(false);
        };

        if (!data[activeTab]) {
            loadData();
        }
    }, [activeTab, getCinema, setCinema]);

    const currentRepertoire = data[activeTab];

    return (
        <div className="glass-panel rounded-3xl border border-white/10 overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b border-white/10 flex items-center justify-between bg-white/5 backdrop-blur-md text-slate-100">
                <div className="flex items-center gap-2">
                    <div className="p-2 bg-blue-500/20 rounded-lg backdrop-blur-sm text-blue-400">
                        <Film size={18} />
                    </div>
                    <div>
                        <h3 className="font-bold text-sm">Kino & Kultura</h3>
                        <p className="text-[10px] text-slate-400 opacity-90">Repertuar na dziś</p>
                    </div>
                </div>
                <div className="flex bg-slate-950/50 rounded-lg p-1 gap-1">
                    <button
                        onClick={() => setActiveTab(CinemaLocation.DZIALDOWO)}
                        className={`px-3 py-1 text-[10px] font-medium rounded-md transition-all ${activeTab === CinemaLocation.DZIALDOWO ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/50' : 'text-slate-400 hover:text-slate-200'}`}
                    >
                        Działdowo
                    </button>
                    <button
                        onClick={() => setActiveTab(CinemaLocation.LUBAWA)}
                        className={`px-3 py-1 text-[10px] font-medium rounded-md transition-all ${activeTab === CinemaLocation.LUBAWA ? 'bg-blue-600 text-white shadow-lg shadow-blue-900/50' : 'text-slate-400 hover:text-slate-200'}`}
                    >
                        Lubawa
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="p-4 min-h-[300px]">
                {loading && !currentRepertoire ? (
                    <div className="flex flex-col items-center justify-center h-48 space-y-3">
                        <div className="w-8 h-8 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
                        <p className="text-xs text-slate-400">Pobieranie repertuaru AI...</p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
                            <span className="flex items-center gap-1"><CalendarDays size={12} /> {currentRepertoire?.date || 'Dzisiaj'}</span>
                            <span className="flex items-center gap-1"><MapPin size={12} /> {currentRepertoire?.cinemaName || 'Kino'}</span>
                        </div>

                        <div className="space-y-3">
                            {currentRepertoire?.movies?.map((movie, idx) => (
                                <div key={idx} className="flex gap-3 group cursor-pointer hover:bg-white/5 p-2 rounded-lg -mx-2 transition-colors items-start">
                                    <div className="relative w-16 flex-shrink-0 rounded-md overflow-hidden shadow-lg shadow-black/50 aspect-[2/3]">
                                        <img src={movie.posterUrl} alt={movie.title} className="w-full h-full object-cover" />
                                    </div>
                                    <div className="flex flex-col flex-1 min-h-full">
                                        <div>
                                            <h4 className="text-sm font-bold text-slate-200 leading-tight group-hover:text-blue-400 transition-colors">{movie.title}</h4>
                                            <div className="flex flex-wrap items-center gap-x-2 mt-1">
                                                <p className="text-[10px] text-slate-500 uppercase tracking-wide">{movie.genre}</p>
                                                {movie.rating && movie.rating !== 'N/A' && (
                                                    <span className="text-[9px] text-blue-400 font-medium bg-blue-500/10 px-1.5 py-0.5 rounded border border-blue-500/20">
                                                        {movie.rating}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <div className="flex flex-wrap gap-1.5 mt-2 mb-2">
                                            {movie.time?.map((t, tIdx) => (
                                                <span key={tIdx} className="px-2 py-1 bg-slate-800 text-slate-300 rounded text-[10px] font-semibold border border-slate-700 flex items-center gap-1 hover:border-blue-500/50 hover:text-blue-400 transition-colors">
                                                    <Clock size={8} /> {t}
                                                </span>
                                            ))}
                                        </div>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                if (movie.link) {
                                                    window.open(movie.link, '_blank');
                                                } else {
                                                    alert('Rezerwacja online niedostępna. Zapraszamy do kas kina.');
                                                }
                                            }}
                                            className="mt-auto w-full py-1.5 bg-blue-600/20 hover:bg-blue-600/40 text-blue-300 border border-blue-500/30 text-[10px] font-medium rounded transition-all flex items-center justify-center gap-1.5 shadow-sm"
                                        >
                                            <Ticket size={10} />
                                            Kup Bilet
                                        </button>
                                    </div>
                                </div>
                            ))}
                            {(!currentRepertoire?.movies || currentRepertoire.movies.length === 0) && (
                                <div className="text-center py-8 text-slate-500 text-xs">
                                    Brak seansów na dziś lub błąd pobierania.
                                </div>
                            )}
                        </div>

                        <button className="w-full mt-2 py-2 text-xs font-medium text-slate-400 border border-slate-800 rounded-lg hover:bg-white/5 hover:text-slate-200 transition-colors">
                            Zobacz pełny repertuar
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};
