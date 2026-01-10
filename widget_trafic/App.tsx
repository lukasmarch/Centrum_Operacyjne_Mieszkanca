
import React, { useState, useEffect, useCallback } from 'react';
import { TrafficData, RoadStatus, TrafficStatus, GroundingSource } from './types';
import { fetchTrafficData } from './services/geminiService';
import TrafficItem from './components/TrafficItem';

const App: React.FC = () => {
  const [data, setData] = useState<TrafficData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [location, setLocation] = useState<{lat: number, lng: number} | null>(null);

  const loadTraffic = useCallback(async (lat?: number, lng?: number) => {
    setLoading(true);
    try {
      const result = await fetchTrafficData(lat, lng);
      setData({
        roads: result.roads,
        sources: result.sources,
        lastUpdated: new Date()
      });
      setError(null);
    } catch (err) {
      setError("Nie udało się pobrać danych o ruchu.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Start with Rybno coordinates as base
    loadTraffic(53.3917, 19.9111);

    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const { latitude, longitude } = position.coords;
          setLocation({ lat: latitude, lng: longitude });
          loadTraffic(latitude, longitude);
        },
        () => console.log("Lokalizacja niedostępna, używam współrzędnych Rybna.")
      );
    }

    const interval = setInterval(() => loadTraffic(location?.lat, location?.lng), 180000);
    return () => clearInterval(interval);
  }, [loadTraffic]);

  return (
    <div className="min-h-screen bg-[#020617] flex flex-col items-center justify-center p-4 sm:p-8">
      {/* Widget Container */}
      <div className="w-full max-w-xl bg-gradient-to-br from-[#1e293b] to-[#0f172a] rounded-[3rem] p-8 shadow-[0_32px_64px_-12px_rgba(0,0,0,0.6)] border border-white/5 relative overflow-hidden">
        
        {/* Glow Effects */}
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-blue-500/40 to-transparent"></div>
        <div className="absolute -top-24 -left-24 w-64 h-64 bg-blue-600/10 blur-[100px] rounded-full"></div>

        <div className="relative z-10">
          <header className="flex justify-between items-center mb-10">
            <div>
              <h1 className="text-white text-3xl font-black tracking-tighter">Rybno Traffic</h1>
              <div className="flex items-center gap-2 mt-1">
                <span className="relative flex h-2 w-2">
                  <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${loading ? 'bg-blue-400' : 'bg-emerald-400'} opacity-75`}></span>
                  <span className={`relative inline-flex rounded-full h-2 w-2 ${loading ? 'bg-blue-500' : 'bg-emerald-500'}`}></span>
                </span>
                <span className="text-[11px] text-slate-400 font-black uppercase tracking-[0.2em]">
                  {loading ? 'Skanowanie tras...' : 'Monitoring aktywny'}
                </span>
              </div>
            </div>
            <button 
              onClick={() => loadTraffic(location?.lat, location?.lng)}
              disabled={loading}
              className="group p-4 bg-white/5 hover:bg-white/10 active:scale-95 transition-all rounded-[1.5rem] border border-white/10 shadow-xl"
            >
              <svg className={`h-6 w-6 text-slate-300 group-hover:text-white ${loading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </header>

          <main className="space-y-2">
            {data?.roads.map((road, idx) => (
              <TrafficItem 
                key={road.id} 
                road={road} 
                isLast={idx === data.roads.length - 1} 
              />
            ))}
            
            {!data && loading && (
              <div className="space-y-8 py-4">
                {[1, 2, 3, 4].map(i => (
                  <div key={i} className="animate-pulse">
                    <div className="flex justify-between items-center mb-4">
                      <div className="h-6 bg-slate-700/40 rounded-full w-48"></div>
                      <div className="h-8 bg-slate-700/40 rounded-xl w-16"></div>
                    </div>
                    <div className="h-16 bg-slate-800/30 rounded-2xl w-full"></div>
                  </div>
                ))}
              </div>
            )}
          </main>

          {/* Sources Section */}
          {data?.sources && data.sources.length > 0 && (
            <div className="mt-10 pt-8 border-t border-white/5">
              <h3 className="text-[10px] text-slate-500 font-black uppercase tracking-widest mb-4">Weryfikacja źródeł:</h3>
              <div className="flex flex-wrap gap-2">
                {data.sources.map((source, idx) => (
                  <a 
                    key={idx}
                    href={source.uri}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[11px] bg-blue-500/5 hover:bg-blue-500/15 text-blue-400/80 px-4 py-2 rounded-xl border border-blue-500/10 transition-all flex items-center gap-2 hover:-translate-y-0.5"
                  >
                    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 010-5 2.5 2.5 0 010 5z"/></svg>
                    {source.title}
                  </a>
                ))}
              </div>
            </div>
          )}

          <footer className="mt-10 flex justify-between items-center text-[10px] text-slate-500 font-bold uppercase tracking-tighter">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Skan: {data?.lastUpdated.toLocaleTimeString('pl-PL')}
            </div>
            <div className="flex items-center gap-2 bg-white/5 px-3 py-1 rounded-lg border border-white/5">
              <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse"></span>
              Centrum: Rybno, Gmina Rybno
            </div>
          </footer>
        </div>
      </div>

      <p className="mt-8 text-slate-600 text-[11px] max-w-sm text-center leading-relaxed font-medium">
        System analizuje realny czas przejazdu w oparciu o aktualne dane GPS z floty pojazdów Google. 
        Uwzględnia warunki pogodowe i sezonowe w regionie warmińsko-mazurskim.
      </p>
    </div>
  );
};

export default App;
