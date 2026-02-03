import React, { useState, useEffect } from 'react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const API_BASE = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';

interface TrendData {
    unit_id: string;
    unit_name: string;
    var_id: string;
    values: { year: number; value: number | null }[];
}

interface ComparisonData {
    var_id: string;
    year: number;
    gminy: Record<string, { value: number | null; year: number }>;
}

const VARIABLES = {
    'entities_regon_per_10k': { id: '60530', name: 'Podmioty REGON na 10 tys. ludności', unit: '' },
    'new_entities_per_10k': { id: '60529', name: 'Nowe firmy na 10 tys. ludności', unit: '' },
    'deregistered_per_10k': { id: '60528', name: 'Wykreślone firmy na 10 tys. ludności', unit: '' },
    'population_total': { id: '72305', name: 'Ludność ogółem', unit: 'os.' },
    'unemployment_rate': { id: '60270', name: 'Stopa bezrobocia', unit: '%' },
};

const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

const GUSPage: React.FC = () => {
    const [selectedVar, setSelectedVar] = useState('entities_regon_per_10k');
    const [trendData, setTrendData] = useState<TrendData | null>(null);
    const [comparisonData, setComparisonData] = useState<ComparisonData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const loadData = async (varKey: string) => {
        setLoading(true);
        setError(null);
        const varId = VARIABLES[varKey as keyof typeof VARIABLES]?.id;

        if (!varId) {
            setError('Nieznana zmienna');
            setLoading(false);
            return;
        }

        try {
            // Fetch trend data for Rybno
            const trendRes = await fetch(`${API_BASE}/api/stats/trend/${varId}?years_back=22`);
            if (trendRes.ok) {
                const trend = await trendRes.json();
                setTrendData(trend);
            }

            // Fetch comparison data
            const compRes = await fetch(`${API_BASE}/api/stats/comparison/${varId}`);
            if (compRes.ok) {
                const comp = await compRes.json();
                setComparisonData(comp);
            }
        } catch (err) {
            setError('Nie udało się pobrać danych. Sprawdź czy backend jest uruchomiony.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData(selectedVar);
    }, [selectedVar]);

    // Transform comparison data for bar chart
    const barChartData = comparisonData ? Object.entries(comparisonData.gminy).map(([name, data]: [string, { value: number | null; year: number }]) => ({
        name: name.replace(' (miasto)', '').replace(' (gmina)', ' gm.'),
        value: data.value || 0,
        isRybno: name === 'Rybno'
    })).sort((a, b) => (b.value || 0) - (a.value || 0)) : [];

    // Get Rybno's current value
    const rybnoValue = comparisonData?.gminy['Rybno']?.value;
    const rybnoYear = comparisonData?.year;

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
            {/* Header */}
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div>
                    <h2 className="text-3xl font-bold text-slate-900">Dane GUS – Gmina Rybno</h2>
                    <p className="text-slate-500">Statystyki z Banku Danych Lokalnych GUS. Aktualizowane raz w roku.</p>
                </div>
                <div className="flex items-center gap-2 bg-white p-2 px-4 rounded-2xl shadow-sm border border-slate-100">
                    <span className="text-2xl">📊</span>
                    <div className="text-sm">
                        <p className="font-semibold">Źródło: GUS BDL</p>
                        <p className="text-slate-400 text-xs">api.stat.gov.pl</p>
                    </div>
                </div>
            </header>

            {/* Variable Selector */}
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
                <h3 className="font-bold mb-4 text-slate-700">Wybierz wskaźnik</h3>
                <div className="flex flex-wrap gap-2">
                    {Object.entries(VARIABLES).map(([key, { name }]) => (
                        <button
                            key={key}
                            onClick={() => setSelectedVar(key)}
                            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${selectedVar === key
                                ? 'bg-blue-600 text-white shadow-md'
                                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                }`}
                        >
                            {name}
                        </button>
                    ))}
                </div>
            </div>

            {/* Loading / Error states */}
            {loading && (
                <div className="bg-white rounded-2xl p-12 shadow-sm border border-slate-100 text-center">
                    <div className="animate-spin text-4xl mb-4">🔄</div>
                    <p className="text-slate-500">Pobieranie danych z GUS...</p>
                </div>
            )}

            {error && (
                <div className="bg-rose-50 rounded-2xl p-6 border border-rose-200 text-rose-700">
                    <p className="font-bold">⚠️ Błąd</p>
                    <p>{error}</p>
                </div>
            )}

            {/* Main Stats Card */}
            {!loading && !error && rybnoValue !== undefined && (
                <div className="bg-gradient-to-br from-emerald-500 to-teal-600 rounded-3xl p-8 text-white shadow-xl">
                    <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                        <div>
                            <p className="text-emerald-100 text-sm font-medium uppercase tracking-wider">
                                {VARIABLES[selectedVar as keyof typeof VARIABLES]?.name}
                            </p>
                            <h3 className="text-5xl font-black mt-2">
                                {rybnoValue?.toLocaleString('pl-PL')}
                                <span className="text-2xl ml-2 font-normal text-emerald-100">
                                    {VARIABLES[selectedVar as keyof typeof VARIABLES]?.unit}
                                </span>
                            </h3>
                            <p className="text-emerald-100 mt-2">Gmina Rybno, {rybnoYear}</p>
                        </div>
                        <div className="bg-white/20 backdrop-blur-sm rounded-2xl px-6 py-4">
                            <p className="text-xs text-emerald-100 uppercase tracking-wider">Ranking w powiecie</p>
                            <p className="text-3xl font-black">
                                #{barChartData.findIndex(d => d.isRybno) + 1}
                                <span className="text-lg font-normal">/{barChartData.length}</span>
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Charts Grid */}
            {!loading && !error && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {/* Historical Trend Chart */}
                    {trendData && trendData.values.length > 0 && (
                        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
                            <h3 className="font-bold mb-4 text-slate-700">📈 Trend historyczny – Rybno</h3>
                            <ResponsiveContainer width="100%" height={300}>
                                <LineChart data={trendData.values}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                    <XAxis
                                        dataKey="year"
                                        tick={{ fontSize: 12 }}
                                        tickFormatter={(year) => year.toString().slice(-2)}
                                    />
                                    <YAxis tick={{ fontSize: 12 }} />
                                    <Tooltip
                                        formatter={(value: number) => [value?.toLocaleString('pl-PL'), 'Wartość']}
                                        labelFormatter={(year) => `Rok ${year}`}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="value"
                                        stroke="#10b981"
                                        strokeWidth={3}
                                        dot={{ fill: '#10b981', strokeWidth: 2 }}
                                        activeDot={{ r: 8 }}
                                    />
                                </LineChart>
                            </ResponsiveContainer>
                            <p className="text-xs text-slate-400 mt-2 text-center">
                                Dane od {trendData.values[0]?.year} do {trendData.values[trendData.values.length - 1]?.year}
                            </p>
                        </div>
                    )}

                    {/* Comparison Bar Chart */}
                    {barChartData.length > 0 && (
                        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
                            <h3 className="font-bold mb-4 text-slate-700">📊 Porównanie gmin w powiecie</h3>
                            <ResponsiveContainer width="100%" height={300}>
                                <BarChart data={barChartData} layout="vertical">
                                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                    <XAxis type="number" tick={{ fontSize: 12 }} />
                                    <YAxis
                                        dataKey="name"
                                        type="category"
                                        tick={{ fontSize: 11 }}
                                        width={90}
                                    />
                                    <Tooltip
                                        formatter={(value: number) => [value?.toLocaleString('pl-PL'), 'Wartość']}
                                    />
                                    <Bar
                                        dataKey="value"
                                        fill="#94a3b8"
                                        radius={[0, 4, 4, 0]}
                                    >
                                        {barChartData.map((entry, index) => (
                                            <rect
                                                key={`bar-${index}`}
                                                fill={entry.isRybno ? '#10b981' : '#94a3b8'}
                                            />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                            <p className="text-xs text-slate-400 mt-2 text-center">
                                Dane za {comparisonData?.year}. Rybno zaznaczone na zielono.
                            </p>
                        </div>
                    )}
                </div>
            )}

            {/* Data Table */}
            {!loading && !error && barChartData.length > 0 && (
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
                    <h3 className="font-bold mb-4 text-slate-700">📋 Szczegółowe dane</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="border-b border-slate-200">
                                    <th className="text-left py-3 px-4 font-semibold text-slate-600">Gmina</th>
                                    <th className="text-right py-3 px-4 font-semibold text-slate-600">Wartość</th>
                                    <th className="text-right py-3 px-4 font-semibold text-slate-600">Rok</th>
                                </tr>
                            </thead>
                            <tbody>
                                {Object.entries(comparisonData?.gminy || {})
                                    .sort(([, a]: [string, { value: number | null; year: number }], [, b]: [string, { value: number | null; year: number }]) => (b.value || 0) - (a.value || 0))
                                    .map(([name, data]: [string, { value: number | null; year: number }]) => (
                                        <tr
                                            key={name}
                                            className={`border-b border-slate-100 ${name === 'Rybno' ? 'bg-emerald-50' : ''}`}
                                        >
                                            <td className="py-3 px-4">
                                                {name === 'Rybno' && <span className="mr-2">🏠</span>}
                                                {name}
                                            </td>
                                            <td className="py-3 px-4 text-right font-mono font-bold">
                                                {data.value?.toLocaleString('pl-PL') || '—'}
                                            </td>
                                            <td className="py-3 px-4 text-right text-slate-400">
                                                {data.year || '—'}
                                            </td>
                                        </tr>
                                    ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Footer info */}
            <div className="text-center text-sm text-slate-400 py-4">
                <p>Dane pochodzą z Banku Danych Lokalnych GUS (api.stat.gov.pl)</p>
                <p>Jednostka: Gmina Rybno (042815403062) w Powiecie Działdowskim</p>
            </div>
        </div>
    );
};

export default GUSPage;
