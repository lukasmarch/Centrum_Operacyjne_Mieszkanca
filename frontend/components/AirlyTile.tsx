import React from 'react';
import { Activity } from 'lucide-react';
import { useDataCache } from '../src/context/DataCacheContext';

const AirlyTile: React.FC = () => {
    // In a real scenario, use real AirlyData. Using mock for the layout or fetching it:
    // We can pull it from the context or pass it as prop.
    // For now we simulate the image exactly.
    const loading = false;
    const caqi = 24;
    const levelText = "DOBRA";
    
    // Fake mini chart bars
    const bars = [2, 3, 2, 4, 3, 6, 8, 4];
    const maxBar = Math.max(...bars);

    return (
        <div className="h-full flex flex-col p-5 relative overflow-hidden bg-slate-900 border border-slate-800">
            {/* Header */}
            <div className="flex items-center gap-2 mb-4">
                <Activity size={13} className="text-blue-500" />
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Jakość powietrza</p>
            </div>

            {/* Content */}
            <div className="mt-auto flex justify-between items-end relative z-10">
                <div>
                    <h3 className="text-4xl font-black text-emerald-500 leading-none mb-1 shadow-emerald-500/20 drop-shadow-lg">{caqi}</h3>
                    <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wide">CAQI ({levelText})</p>
                </div>

                {/* Mini Chart */}
                <div className="flex items-end gap-1 h-8 opacity-80">
                    {bars.map((val, idx) => (
                        <div 
                            key={idx}
                            className={`w-1.5 rounded-t-sm ${idx >= bars.length - 2 ? 'bg-emerald-500' : 'bg-emerald-500/30'}`}
                            style={{ height: `${(val / maxBar) * 100}%` }}
                        />
                    ))}
                </div>
            </div>
            
            {/* Subtle Green Glow bottom right */}
            <div className="absolute -bottom-8 -right-8 w-32 h-32 bg-emerald-500/10 blur-2xl rounded-full"></div>
        </div>
    );
};

export default AirlyTile;
