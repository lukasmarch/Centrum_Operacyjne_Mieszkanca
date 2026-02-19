import React from 'react';

interface AirlyData {
    pm25: number;
    pm10: number;
    caqi: number;
    caqi_level: string;
    temperature: number;
    humidity: number;
    pressure: number;
    fetched_at: string;
}

interface AirlyWidgetProps {
    data: AirlyData | null;
    loading: boolean;
    error: string | null;
}

const AirlyWidget: React.FC<AirlyWidgetProps> = ({ data, loading, error }) => {
    const getLevelColor = (level: string) => {
        switch (level) {
            case 'VERY_LOW': return 'bg-emerald-500 shadow-emerald-500/50';
            case 'LOW': return 'bg-green-500 shadow-green-500/50';
            case 'MEDIUM': return 'bg-yellow-500 shadow-yellow-500/50';
            case 'HIGH': return 'bg-orange-500 shadow-orange-500/50';
            case 'VERY_HIGH': return 'bg-red-500 shadow-red-500/50';
            case 'EXTREME': return 'bg-purple-900 shadow-purple-900/50';
            default: return 'bg-slate-500';
        }
    };

    const getLevelText = (level: string) => {
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

    const getAdvice = (level: string) => {
        const map: Record<string, string> = {
            'VERY_LOW': 'Świetna pogoda na spacer! Oddychaj głęboko.',
            'LOW': 'Możesz spędzać czas na zewnątrz bez obaw.',
            'MEDIUM': 'Osoby wrażliwe powinny ograniczyć wysiłek.',
            'HIGH': 'Lepiej zostań w domu i zamknij okna.',
            'VERY_HIGH': 'Unikaj wychodzenia na zewnątrz!',
            'EXTREME': 'Zagrożenie życia! Bezwzględnie zostań w domu.'
        };
        return map[level] || 'Monitorujemy jakość powietrza dla Twojego bezpieczeństwa.';
    };

    if (loading) {
        return (
            <div className="w-full h-96 bg-slate-900 rounded-3xl flex items-center justify-center animate-pulse">
                <div className="text-center text-slate-400">
                    <div className="text-4xl mb-4">🌪️</div>
                    <p>Pobieranie danych o jakości powietrza...</p>
                </div>
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="w-full h-96 bg-slate-900 rounded-3xl flex items-center justify-center">
                <div className="text-center text-red-400">
                    <p>⚠️ Nie udało się pobrać danych</p>
                    <p className="text-sm mt-2">{error}</p>
                </div>
            </div>
        );
    }

    const levelColor = getLevelColor(data.caqi_level);
    const pm25Percent = Math.min((data.pm25 / 15) * 100, 100); // WHO standard 15 µg/m³
    const pm10Percent = Math.min((data.pm10 / 45) * 100, 100); // WHO standard 45 µg/m³

    return (
        <div className="relative overflow-hidden glass-panel rounded-3xl text-white p-8 shadow-2xl">
            {/* Background gradients */}
            <div className={`absolute -top-20 -right-20 w-64 h-64 rounded-full blur-[100px] opacity-40 ${levelColor.split(' ')[0]}`}></div>
            <div className="absolute -bottom-20 -left-20 w-64 h-64 rounded-full bg-blue-600 blur-[100px] opacity-20"></div>

            <div className="relative z-10 grid grid-cols-1 md:grid-cols-2 gap-12 items-center">

                {/* Left Column: CAQI & Status */}
                <div className="text-center md:text-left">
                    <div className="inline-block px-3 py-1 rounded-full bg-white/10 text-xs font-mono mb-4 backdrop-blur-sm border border-white/5">
                        STACJA: RYBNO
                    </div>
                    <h2 className="text-5xl font-black mb-2 flex items-center gap-4 justify-center md:justify-start">
                        <span className="text-8xl">{Math.round(data.caqi)}</span>
                        <div className="flex flex-col text-left">
                            <span className="text-lg font-medium text-slate-400">CAQI</span>
                            <span className={`text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400`}>
                                {getLevelText(data.caqi_level)}
                            </span>
                        </div>
                    </h2>
                    <p className="text-slate-400 mt-6 leading-relaxed max-w-sm">
                        {getAdvice(data.caqi_level)}
                    </p>
                </div>

                {/* Right Column: Measurements */}
                <div className="space-y-8 bg-white/5 p-6 rounded-2xl backdrop-blur-sm border border-white/5">

                    {/* PM Standards */}
                    <div className="space-y-4">
                        <div>
                            <div className="flex justify-between text-sm mb-1.5">
                                <span className="text-slate-300">PM 2.5</span>
                                <span className="font-mono">{Math.round(data.pm25)} µg/m³ ({Math.round(pm25Percent)}%)</span>
                            </div>
                            <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all duration-1000 ${pm25Percent > 100 ? 'bg-red-500' : 'bg-blue-400'}`}
                                    style={{ width: `${pm25Percent}%` }}
                                ></div>
                            </div>
                        </div>

                        <div>
                            <div className="flex justify-between text-sm mb-1.5">
                                <span className="text-slate-300">PM 10</span>
                                <span className="font-mono">{Math.round(data.pm10)} µg/m³ ({Math.round(pm10Percent)}%)</span>
                            </div>
                            <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all duration-1000 ${pm10Percent > 100 ? 'bg-red-500' : 'bg-blue-400'}`}
                                    style={{ width: `${pm10Percent}%` }}
                                ></div>
                            </div>
                        </div>
                    </div>

                    {/* Weather Details */}
                    <div className="grid grid-cols-3 gap-2 pt-4 border-t border-white/10">
                        <div className="text-center p-2 rounded-xl bg-white/5">
                            <div className="text-xl mb-1">🌡️</div>
                            <div className="text-sm text-slate-400">Temp</div>
                            <div className="font-bold">{data.temperature?.toFixed(1)}°C</div>
                        </div>
                        <div className="text-center p-2 rounded-xl bg-white/5">
                            <div className="text-xl mb-1">💧</div>
                            <div className="text-sm text-slate-400">Wilgoć</div>
                            <div className="font-bold">{data.humidity?.toFixed(0)}%</div>
                        </div>
                        <div className="text-center p-2 rounded-xl bg-white/5">
                            <div className="text-xl mb-1">⏲️</div>
                            <div className="text-sm text-slate-400">Ciśnienie</div>
                            <div className="font-bold">{data.pressure?.toFixed(0)} hPa</div>
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );
};

export default AirlyWidget;
