import React, { useState, useEffect, useCallback } from 'react';
import { Wind as WindIcon } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

interface AirQualityData {
    pm25: number;
    pm10: number;
    caqi: number;
    caqi_level: string;
    temperature: number;
    humidity: number;
    pressure: number;
    fetched_at: string;
}

interface AirQualityHistoryItem {
    pm25: number;
    pm10: number;
    caqi: number;
    fetched_at: string;
}

const getLevelLabel = (level: string): string => {
    const map: Record<string, string> = {
        'VERY_LOW': 'Bardzo Dobra',
        'LOW': 'Dobra',
        'MEDIUM': 'Umiarkowana',
        'HIGH': 'Zła',
        'VERY_HIGH': 'Bardzo Zła',
        'EXTREME': 'Ekstremalna'
    };
    return map[level] || 'Brak danych';
};

const getLevelColor = (level: string): string => {
    switch (level) {
        case 'VERY_LOW': return 'text-emerald-400';
        case 'LOW': return 'text-green-400';
        case 'MEDIUM': return 'text-yellow-400';
        case 'HIGH': return 'text-orange-400';
        case 'VERY_HIGH': return 'text-red-400';
        case 'EXTREME': return 'text-purple-400';
        default: return 'text-neutral-400';
    }
};

const getLevelBg = (level: string): string => {
    switch (level) {
        case 'VERY_LOW': return 'bg-emerald-500';
        case 'LOW': return 'bg-green-500';
        case 'MEDIUM': return 'bg-yellow-500';
        case 'HIGH': return 'bg-orange-500';
        case 'VERY_HIGH': return 'bg-red-500';
        case 'EXTREME': return 'bg-purple-500';
        default: return 'bg-gray-500';
    }
};

const getBarColor = (caqi: number): string => {
    if (caqi <= 25) return 'bg-emerald-400';
    if (caqi <= 50) return 'bg-green-400';
    if (caqi <= 75) return 'bg-yellow-400';
    if (caqi <= 100) return 'bg-orange-400';
    return 'bg-red-400';
};

const getAdvice = (level: string): string => {
    const map: Record<string, string> = {
        'VERY_LOW': 'Idealna pogoda na spacer!',
        'LOW': 'Możesz spędzać czas na zewnątrz.',
        'MEDIUM': 'Osoby wrażliwe powinny ograniczyć wysiłek na zewnątrz.',
        'HIGH': 'Lepiej zostań w domu.',
        'VERY_HIGH': 'Unikaj wychodzenia na zewnątrz!',
        'EXTREME': 'Nie wychodź z domu!'
    };
    return map[level] || '';
};

// PM2.5 norm: 25 µg/m³ (WHO), PM10 norm: 50 µg/m³
const PM25_NORM = 25;
const PM10_NORM = 50;

const AirlyTile: React.FC = () => {
    const [data, setData] = useState<AirQualityData | null>(null);
    const [history, setHistory] = useState<AirQualityHistoryItem[]>([]);
    const [loading, setLoading] = useState(true);

    const fetchData = useCallback(async () => {
        try {
            const [currentRes, historyRes] = await Promise.all([
                fetch(`${API_URL}/weather/air-quality/current`),
                fetch(`${API_URL}/weather/air-quality/history?days=3`)
            ]);

            if (currentRes.ok) {
                const current = await currentRes.json();
                setData(current);
            }

            if (historyRes.ok) {
                const hist = await historyRes.json();
                setHistory(Array.isArray(hist) ? hist : []);
            }
        } catch {
            // silent
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 30 * 60 * 1000);
        return () => clearInterval(interval);
    }, [fetchData]);

    // Sample history for bar chart
    const sampledHistory = (() => {
        if (history.length <= 12) return history;
        const step = Math.max(1, Math.floor(history.length / 12));
        const sampled: AirQualityHistoryItem[] = [];
        for (let i = 0; i < history.length; i += step) {
            sampled.push(history[i]);
            if (sampled.length >= 12) break;
        }
        return sampled;
    })();

    const maxCaqi = sampledHistory.length > 0 ? Math.max(...sampledHistory.map(h => h.caqi), 1) : 1;
    const hasChart = sampledHistory.length > 1;

    return (
        <div className="h-full flex flex-col p-5 relative overflow-hidden">
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
                <WindIcon size={14} className="text-blue-400" />
                <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">Jakość Powietrza</span>
            </div>

            {loading ? (
                <div className="flex-1 flex items-center justify-center animate-pulse">
                    <div className="h-12 w-20 bg-gray-900/60 rounded" />
                </div>
            ) : data ? (
                <div className="flex-1 flex flex-col">
                    {/* CAQI big number */}
                    <div className="flex items-baseline gap-2 mb-0.5">
                        <h3 className={`text-4xl font-black leading-none tracking-tight ${getLevelColor(data.caqi_level)}`}>
                            {Math.round(data.caqi)}
                        </h3>
                        <span className="text-[10px] font-bold text-neutral-500 uppercase">CAQI</span>
                    </div>
                    <p className={`text-xs font-semibold ${getLevelColor(data.caqi_level)} mb-3`}>
                        {getLevelLabel(data.caqi_level)}
                    </p>

                    {/* History bar chart if available */}
                    {hasChart ? (
                        <div className="flex-1 flex flex-col justify-end min-h-0 mb-2">
                            <p className="text-[8px] text-neutral-600 uppercase tracking-wider font-bold mb-1.5">Ostatnie 3 dni</p>
                            <div className="flex items-end gap-[3px] h-full max-h-[80px]">
                                {sampledHistory.map((item, idx) => {
                                    const heightPct = Math.max((item.caqi / maxCaqi) * 100, 8);
                                    const isLast = idx === sampledHistory.length - 1;
                                    return (
                                        <div key={idx} className="flex-1 flex flex-col items-center justify-end h-full gap-0.5 group relative">
                                            <div className="absolute -top-7 left-1/2 -translate-x-1/2 bg-gray-900 border border-gray-700/50 text-[8px] text-neutral-300 px-1.5 py-0.5 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                                                {Math.round(item.caqi)}
                                            </div>
                                            <div
                                                className={`w-full min-w-[4px] rounded-t-sm ${getBarColor(item.caqi)} ${isLast ? 'opacity-100 ring-1 ring-white/20' : 'opacity-50'} transition-all`}
                                                style={{ height: `${heightPct}%` }}
                                            />
                                        </div>
                                    );
                                })}
                            </div>
                            <div className="flex justify-between mt-1">
                                <span className="text-[7px] text-neutral-600">3 dni temu</span>
                                <span className="text-[7px] text-neutral-600">teraz</span>
                            </div>
                        </div>
                    ) : (
                        /* Fallback when no chart data: show PM gauges + advice */
                        <div className="flex-1 flex flex-col justify-center gap-3">
                            {/* PM 2.5 gauge */}
                            <div>
                                <div className="flex justify-between items-center mb-1">
                                    <span className="text-[9px] font-bold text-neutral-400">PM 2.5</span>
                                    <span className="text-[9px] font-bold text-neutral-300">{data.pm25.toFixed(1)} µg/m³</span>
                                </div>
                                <div className="h-1.5 bg-gray-900 rounded-full overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all ${data.pm25 <= PM25_NORM ? 'bg-emerald-400' : data.pm25 <= PM25_NORM * 2 ? 'bg-yellow-400' : 'bg-red-400'}`}
                                        style={{ width: `${Math.min((data.pm25 / (PM25_NORM * 3)) * 100, 100)}%` }}
                                    />
                                </div>
                                <div className="flex justify-between mt-0.5">
                                    <span className="text-[7px] text-neutral-600">0</span>
                                    <span className="text-[7px] text-emerald-600">norma {PM25_NORM}</span>
                                    <span className="text-[7px] text-neutral-600">{PM25_NORM * 3}</span>
                                </div>
                            </div>

                            {/* PM 10 gauge */}
                            <div>
                                <div className="flex justify-between items-center mb-1">
                                    <span className="text-[9px] font-bold text-neutral-400">PM 10</span>
                                    <span className="text-[9px] font-bold text-neutral-300">{data.pm10.toFixed(1)} µg/m³</span>
                                </div>
                                <div className="h-1.5 bg-gray-900 rounded-full overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all ${data.pm10 <= PM10_NORM ? 'bg-emerald-400' : data.pm10 <= PM10_NORM * 2 ? 'bg-yellow-400' : 'bg-red-400'}`}
                                        style={{ width: `${Math.min((data.pm10 / (PM10_NORM * 3)) * 100, 100)}%` }}
                                    />
                                </div>
                                <div className="flex justify-between mt-0.5">
                                    <span className="text-[7px] text-neutral-600">0</span>
                                    <span className="text-[7px] text-emerald-600">norma {PM10_NORM}</span>
                                    <span className="text-[7px] text-neutral-600">{PM10_NORM * 3}</span>
                                </div>
                            </div>

                            {/* Advice */}
                            {getAdvice(data.caqi_level) && (
                                <p className="text-[10px] text-neutral-500 italic mt-1">
                                    💡 {getAdvice(data.caqi_level)}
                                </p>
                            )}
                        </div>
                    )}

                    {/* PM values bottom row (only when chart is shown, otherwise they're in gauges) */}
                    {hasChart && (
                        <div className="flex gap-4 pt-2 border-t border-white/5">
                            <div>
                                <p className="text-[8px] font-bold text-neutral-500 uppercase tracking-wider">PM 2.5</p>
                                <p className="text-xs font-bold text-neutral-300">{data.pm25.toFixed(1)} <span className="text-neutral-500">µg/m³</span></p>
                            </div>
                            <div>
                                <p className="text-[8px] font-bold text-neutral-500 uppercase tracking-wider">PM 10</p>
                                <p className="text-xs font-bold text-neutral-300">{data.pm10.toFixed(1)} <span className="text-neutral-500">µg/m³</span></p>
                            </div>
                        </div>
                    )}
                </div>
            ) : (
                <p className="text-xs text-neutral-500 italic flex-1 flex items-center">Brak danych z czujnika</p>
            )}
        </div>
    );
};

export default AirlyTile;
