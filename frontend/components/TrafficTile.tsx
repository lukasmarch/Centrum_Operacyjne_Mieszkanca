import React, { useState, useEffect, useCallback } from 'react';
import { TrafficData, TrafficCondition } from '../types';
import { Car } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const TrafficTile: React.FC = () => {
    const [data, setData] = useState<TrafficData | null>(null);
    const [loading, setLoading] = useState<boolean>(true);

    const loadTraffic = useCallback(async () => {
        setLoading(true);
        try {
            const response = await fetch(`${API_URL}/traffic`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const result = await response.json();
            setData({
                roads: result.roads.map((r: any) => ({
                    ...r,
                    status: (Object.values(TrafficCondition) as string[]).includes(r.status)
                        ? r.status as TrafficCondition
                        : TrafficCondition.UNKNOWN,
                })),
                sources: result.sources ?? [],
                lastUpdated: new Date()
            });
        } catch {
            // silent
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadTraffic();
        const interval = setInterval(loadTraffic, 4 * 60 * 60 * 1000);
        return () => clearInterval(interval);
    }, [loadTraffic]);

    const getIndicatorColor = (status: TrafficCondition) => {
        switch (status) {
            case TrafficCondition.FLUID: return 'border-slate-500';
            case TrafficCondition.DIFFICULTIES: return 'border-amber-500 bg-amber-500';
            case TrafficCondition.JAM: return 'border-rose-500 bg-rose-500';
            default: return 'border-slate-600';
        }
    };

    const getStatusLabel = (status: TrafficCondition) => {
        switch (status) {
            case TrafficCondition.FLUID: return 'Płynny';
            case TrafficCondition.DIFFICULTIES: return 'Utrudnienia';
            case TrafficCondition.JAM: return 'Korki';
            default: return '—';
        }
    };

    const getStatusColor = (status: TrafficCondition) => {
        switch (status) {
            case TrafficCondition.FLUID: return 'text-emerald-400';
            case TrafficCondition.DIFFICULTIES: return 'text-amber-400';
            case TrafficCondition.JAM: return 'text-rose-400';
            default: return 'text-slate-500';
        }
    };

    const hasProblem = (status: TrafficCondition) =>
        status === TrafficCondition.DIFFICULTIES || status === TrafficCondition.JAM;

    return (
        <div className="h-full flex flex-col p-5 relative overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-2">
                    <Car size={14} className="text-blue-400" />
                    <span className="text-sm font-extrabold text-white uppercase tracking-wide">Ruch Drogowy</span>
                </div>
                <div className={`w-2 h-2 rounded-full ${loading ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400'}`} />
            </div>

            {/* Routes */}
            <div className="flex-1 space-y-0">
                {loading && !data ? (
                    <div className="space-y-5 animate-pulse">
                        {[1, 2, 3].map(i => (
                            <div key={i}>
                                <div className="h-5 bg-slate-800/40 rounded w-2/3 mb-2" />
                                <div className="h-3 bg-slate-800/30 rounded w-full" />
                            </div>
                        ))}
                    </div>
                ) : data?.roads.map((road, idx) => (
                    <div
                        key={road.id}
                        className={`py-4 ${idx < data.roads.length - 1 ? 'border-b border-white/5' : ''}`}
                    >
                        {/* Route name + status */}
                        <div className="flex items-start gap-3">
                            {/* Circle indicator */}
                            <div className={`w-3 h-3 rounded-full border-2 mt-1 shrink-0 ${getIndicatorColor(road.status)}`} />

                            <div className="flex-1 min-w-0">
                                {/* Route name + badge on same line */}
                                <div className="flex items-center justify-between gap-2 flex-wrap">
                                    <span className="text-[15px] font-bold text-white">{road.name}</span>
                                    <div className="flex items-center gap-2">
                                        <span className={`text-xs font-bold ${getStatusColor(road.status)}`}>
                                            {getStatusLabel(road.status)}
                                        </span>
                                        {road.delayMinutes > 0 && (
                                            <span className="text-xs font-bold text-amber-400 bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 rounded-md">
                                                +{road.delayMinutes} min
                                            </span>
                                        )}
                                    </div>
                                </div>

                                {/* Description */}
                                {road.description && (
                                    hasProblem(road.status) ? (
                                        /* Amber warning box for difficulties/jams */
                                        <div className="mt-2 p-3 rounded-xl bg-amber-900/30 border border-amber-700/40">
                                            <p className="text-[11px] text-amber-200/90 leading-relaxed">
                                                <span className="mr-1">⚠️</span>
                                                {road.description}
                                            </p>
                                        </div>
                                    ) : (
                                        /* Simple gray text for normal routes */
                                        <p className="mt-1.5 text-[11px] text-slate-500 leading-relaxed">
                                            {road.description}
                                        </p>
                                    )
                                )}
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Footer */}
            <button className="mt-3 pt-3 border-t border-white/5 flex items-center justify-center gap-2 text-[12px] text-slate-400 hover:text-blue-400 transition-colors font-medium w-full py-2 rounded-xl hover:bg-white/5">
                <span>✏️</span>
                <span>Zobacz mapę na żywo</span>
            </button>
        </div>
    );
};

export default TrafficTile;
