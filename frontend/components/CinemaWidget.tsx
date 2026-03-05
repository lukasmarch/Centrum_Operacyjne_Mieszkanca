import React, { useState, useEffect } from 'react';
import { Film, Clock, Ticket, MapPin, CalendarDays } from 'lucide-react';
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
            const cachedData = getCinema(activeTab);
            if (cachedData) {
                setData(prev => ({ ...prev, [activeTab]: cachedData }));
                return;
            }
            setLoading(true);
            const rep = await fetchCinemaRepertoire(activeTab);
            setData(prev => ({ ...prev, [activeTab]: rep }));
            setCinema(activeTab, rep);
            setLoading(false);
        };
        if (!data[activeTab]) {
            loadData();
        }
    }, [activeTab, getCinema, setCinema]);

    const currentRepertoire = data[activeTab];

    return (
        <div className="bg-slate-900 rounded-3xl border border-slate-800 overflow-hidden h-full flex flex-col">
            {/* Header */}
            <div className="p-4 pb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Film size={14} className="text-purple-400" />
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Repertuar Kina</span>
                </div>
                <div className="flex bg-slate-800/80 rounded-lg p-0.5 gap-0.5">
                    {[CinemaLocation.DZIALDOWO, CinemaLocation.LUBAWA].map(loc => (
                        <button
                            key={loc}
                            onClick={() => setActiveTab(loc)}
                            className={`px-2.5 py-1 text-[9px] font-bold rounded-md transition-all ${activeTab === loc
                                    ? 'bg-purple-600 text-white shadow-lg shadow-purple-900/30'
                                    : 'text-slate-500 hover:text-slate-300'
                                }`}
                        >
                            {loc === CinemaLocation.DZIALDOWO ? 'Działdowo' : 'Lubawa'}
                        </button>
                    ))}
                </div>
            </div>

            {/* Date bar */}
            <div className="px-4 pb-3 flex items-center justify-between text-[9px] text-slate-400">
                <span className="flex items-center gap-1"><CalendarDays size={9} /> Repertuar tygodnia</span>
                <span className="flex items-center gap-1"><MapPin size={9} /> {currentRepertoire?.cinemaName || 'Kino'}</span>
            </div>

            {/* Movies */}
            <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-2 custom-scrollbar">
                {loading && !currentRepertoire ? (
                    <div className="flex flex-col items-center justify-center h-40 space-y-2">
                        <div className="w-6 h-6 border-2 border-purple-500/30 border-t-purple-500 rounded-full animate-spin" />
                        <p className="text-[9px] text-slate-500">Ładowanie repertuaru...</p>
                    </div>
                ) : currentRepertoire?.movies?.length ? (
                    currentRepertoire.movies.map((movie, idx) => (
                        <div key={idx} className="flex gap-3 p-2 rounded-xl hover:bg-white/5 transition-colors group cursor-pointer items-start">
                            {/* Poster */}
                            <div className="w-14 flex-shrink-0 rounded-lg overflow-hidden shadow-lg shadow-black/40 aspect-[2/3] border border-white/5">
                                <img src={movie.posterUrl} alt={movie.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                            </div>

                            {/* Info */}
                            <div className="flex-1 min-w-0 flex flex-col">
                                <h4 className="text-[11px] font-bold text-slate-200 leading-tight group-hover:text-purple-300 transition-colors line-clamp-2">
                                    {movie.title}
                                </h4>
                                <p className="text-[9px] text-slate-600 uppercase tracking-wide mt-0.5">{movie.genre}</p>

                                {/* Showtimes */}
                                <div className="flex flex-wrap gap-1 mt-1.5">
                                    {movie.time?.map((t, tIdx) => (
                                        <span key={tIdx} className="px-1.5 py-0.5 bg-slate-800 text-slate-300 rounded text-[9px] font-semibold border border-slate-700/50 flex items-center gap-0.5">
                                            <Clock size={7} className="text-purple-400" /> {t}
                                        </span>
                                    ))}
                                </div>

                                {/* Buy ticket */}
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        if (movie.link) window.open(movie.link, '_blank');
                                    }}
                                    className="mt-1.5 w-full py-1 bg-purple-600/15 hover:bg-purple-600/30 text-purple-300 border border-purple-500/20 text-[9px] font-semibold rounded-lg transition-all flex items-center justify-center gap-1"
                                >
                                    <Ticket size={9} /> Kup Bilet
                                </button>
                            </div>
                        </div>
                    ))
                ) : (
                    <div className="text-center py-8 text-slate-600 text-[10px]">
                        Brak seansów na dziś
                    </div>
                )}
            </div>

            {/* Footer */}
            <div className="px-4 py-2.5 border-t border-white/5">
                <span className="text-[9px] text-purple-400 font-semibold cursor-pointer hover:text-purple-300 transition-colors flex items-center justify-center gap-1">
                    Zobacz pełny repertuar →
                </span>
            </div>
        </div>
    );
};
