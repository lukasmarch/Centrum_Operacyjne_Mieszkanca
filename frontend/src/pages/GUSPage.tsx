import React, { useState, useEffect } from 'react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { useAuth } from '../context/AuthContext';

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

interface VariableMetadata {
    name: string;
    unit: string;
    tier: 'free' | 'premium' | 'business';
    category: string;
    var_id: string;  // GUS API variable ID
}

interface VariablesResponse {
    user_tier: string;
    total_available: number;
    variables: Record<string, VariableMetadata>;
    by_category: Record<string, Array<{ key: string } & VariableMetadata>>;
    tiers: Record<string, { count: number; price: string }>;
}

const COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

const CATEGORY_ICONS: Record<string, string> = {
    'demografia': '👥',
    'rynek_pracy': '💼',
    'przedsiebiorczosc': '🏢',
    'transport': '🚗',
    'infrastruktura': '🏗️',
    'turystyka': '🏨'
};

const CATEGORY_NAMES: Record<string, string> = {
    'demografia': 'Demografia',
    'rynek_pracy': 'Rynek Pracy',
    'przedsiebiorczosc': 'Przedsiębiorczość',
    'transport': 'Transport',
    'infrastruktura': 'Infrastruktura',
    'turystyka': 'Turystyka'
};

const GUSPage: React.FC = () => {
    const { user } = useAuth();
    const [activeCategory, setActiveCategory] = useState<string>('przedsiebiorczosc');
    const [selectedVar, setSelectedVar] = useState('entities_regon_per_10k');
    const [trendData, setTrendData] = useState<TrendData | null>(null);
    const [comparisonData, setComparisonData] = useState<ComparisonData | null>(null);
    const [variablesData, setVariablesData] = useState<VariablesResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const userTier = user?.tier || 'free';

    // Load available variables
    useEffect(() => {
        const loadVariables = async () => {
            try {
                const headers: HeadersInit = {};
                if (user?.token) {
                    headers['Authorization'] = `Bearer ${user.token}`;
                }

                const res = await fetch(`${API_BASE}/api/stats/variables/list`, { headers });
                if (res.ok) {
                    const data = await res.json();
                    setVariablesData(data);
                }
            } catch (err) {
                console.error('Failed to load variables:', err);
            }
        };

        loadVariables();
    }, [user]);

    const loadData = async (varKey: string) => {
        setLoading(true);
        setError(null);

        if (!variablesData?.variables[varKey]) {
            setError('Nieznana zmienna');
            setLoading(false);
            return;
        }

        // Get var_id from metadata
        const varId = variablesData.variables[varKey].var_id;
        if (!varId) {
            setError('Nieznana zmienna - brak var_id');
            setLoading(false);
            return;
        }

        try {
            const headers: HeadersInit = {};
            if (user?.token) {
                headers['Authorization'] = `Bearer ${user.token}`;
            }

            // Try to get variable-specific data (new endpoint)
            const varRes = await fetch(`${API_BASE}/api/stats/variable/${varKey}`, { headers });

            if (varRes.status === 403) {
                // User doesn't have access - show paywall
                setError('premium_required');
                setLoading(false);
                return;
            }

            // Fallback to old endpoints for trend/comparison
            const trendRes = await fetch(`${API_BASE}/api/stats/trend/${varId}?years_back=22`, { headers });
            if (trendRes.ok) {
                const trend = await trendRes.json();
                setTrendData(trend);
            }

            const compRes = await fetch(`${API_BASE}/api/stats/comparison/${varId}`, { headers });
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
        if (variablesData) {
            loadData(selectedVar);
        }
    }, [selectedVar, variablesData]);

    // Transform comparison data for bar chart
    const barChartData = comparisonData ? Object.entries(comparisonData.gminy).map(([name, data]: [string, { value: number | null; year: number }]) => ({
        name: name.replace(' (miasto)', '').replace(' (gmina)', ' gm.'),
        value: data.value || 0,
        isRybno: name === 'Rybno'
    })).sort((a, b) => (b.value || 0) - (a.value || 0)) : [];

    // Get Rybno's current value
    const rybnoValue = comparisonData?.gminy['Rybno']?.value;
    const rybnoYear = comparisonData?.year;

    // Get variables for current category
    const categoryVariables = variablesData?.by_category?.[activeCategory] || [];

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
            {/* Header */}
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div>
                    <h2 className="text-3xl font-bold text-slate-900">Dane GUS – Gmina Rybno</h2>
                    <p className="text-slate-500">
                        Statystyki z Banku Danych Lokalnych GUS.
                        {variablesData && ` Dostępnych: ${variablesData.total_available} wskaźników (${userTier})`}
                    </p>
                </div>
                <div className="flex items-center gap-2 bg-white p-2 px-4 rounded-2xl shadow-sm border border-slate-100">
                    <span className="text-2xl">📊</span>
                    <div className="text-sm">
                        <p className="font-semibold">Źródło: GUS BDL</p>
                        <p className="text-slate-400 text-xs">api.stat.gov.pl</p>
                    </div>
                </div>
            </header>

            {/* Category Navigation */}
            {variablesData && (
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
                    <h3 className="font-bold mb-4 text-slate-700">Kategorie</h3>
                    <div className="flex gap-2 overflow-x-auto pb-2">
                        {Object.keys(variablesData.by_category).map((category) => (
                            <button
                                key={category}
                                onClick={() => {
                                    setActiveCategory(category);
                                    // Auto-select first variable in category
                                    const firstVar = variablesData.by_category[category]?.[0]?.key;
                                    if (firstVar) setSelectedVar(firstVar);
                                }}
                                className={`px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${
                                    activeCategory === category
                                        ? 'bg-blue-600 text-white shadow-md'
                                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                }`}
                            >
                                {CATEGORY_ICONS[category]} {CATEGORY_NAMES[category] || category}
                                <span className="ml-2 text-xs opacity-75">
                                    ({variablesData.by_category[category].length})
                                </span>
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Variable Selector */}
            {categoryVariables.length > 0 && (
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100">
                    <h3 className="font-bold mb-4 text-slate-700">
                        Wybierz wskaźnik – {CATEGORY_NAMES[activeCategory]}
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                        {categoryVariables.map((variable) => (
                            <button
                                key={variable.key}
                                onClick={() => setSelectedVar(variable.key)}
                                className={`px-4 py-3 rounded-xl text-sm font-medium transition-all text-left ${
                                    selectedVar === variable.key
                                        ? 'bg-blue-600 text-white shadow-md'
                                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                                }`}
                            >
                                <div className="font-bold">{variable.name}</div>
                                {variable.unit && (
                                    <div className="text-xs opacity-75 mt-1">{variable.unit}</div>
                                )}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Premium Upsell dla Free users */}
            {userTier === 'free' && (
                <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-6 text-white shadow-xl">
                    <div className="flex items-start gap-4">
                        <div className="text-4xl">🔓</div>
                        <div className="flex-1">
                            <h3 className="text-xl font-bold mb-2">Odblokuj 17+ wskaźników Premium</h3>
                            <ul className="text-sm space-y-1 mb-4 opacity-90">
                                <li>✓ Stopa bezrobocia i średnie wynagrodzenie</li>
                                <li>✓ Analiza przedsiębiorczości (MŚP, duże firmy)</li>
                                <li>✓ Transport i infrastruktura</li>
                                <li>✓ Trendy historyczne 25 lat</li>
                            </ul>
                            <button className="bg-white text-blue-600 px-6 py-2 rounded-xl font-bold hover:shadow-lg transition-all">
                                Przejdź na Premium (19 zł/mc) →
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Business Upsell dla Premium users */}
            {userTier === 'premium' && (
                <div className="bg-slate-900 rounded-2xl p-6 text-white shadow-xl">
                    <div className="flex items-start gap-4">
                        <div className="text-4xl">💎</div>
                        <div className="flex-1">
                            <h3 className="text-xl font-bold mb-2">Upgrade do Business</h3>
                            <ul className="text-sm space-y-1 mb-4 opacity-90">
                                <li>✓ Multi-metric comparison (2-5 wskaźników jednocześnie)</li>
                                <li>✓ Eksport danych (Excel, CSV)</li>
                                <li>✓ API access (1000 req/day)</li>
                                <li>✓ Wszystkie 40+ wskaźników GUS</li>
                            </ul>
                            <button className="bg-white text-slate-900 px-6 py-2 rounded-xl font-bold hover:shadow-lg transition-all">
                                Przejdź na Business (99 zł/mc) →
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Loading / Error states */}
            {loading && (
                <div className="bg-white rounded-2xl p-12 shadow-sm border border-slate-100 text-center">
                    <div className="animate-spin text-4xl mb-4">🔄</div>
                    <p className="text-slate-500">Pobieranie danych z GUS...</p>
                </div>
            )}

            {error === 'premium_required' && (
                <div className="bg-amber-50 rounded-2xl p-6 border border-amber-200 text-amber-800">
                    <p className="font-bold">🔒 Premium Feature</p>
                    <p>Ten wskaźnik wymaga subskrypcji Premium lub Business.</p>
                </div>
            )}

            {error && error !== 'premium_required' && (
                <div className="bg-rose-50 rounded-2xl p-6 border border-rose-200 text-rose-700">
                    <p className="font-bold">⚠️ Błąd</p>
                    <p>{error}</p>
                </div>
            )}

            {/* Main Stats Card */}
            {!loading && !error && rybnoValue !== undefined && variablesData?.variables[selectedVar] && (
                <div className="bg-gradient-to-br from-emerald-500 to-teal-600 rounded-3xl p-8 text-white shadow-xl">
                    <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                        <div>
                            <p className="text-emerald-100 text-sm font-medium uppercase tracking-wider">
                                {variablesData.variables[selectedVar].name}
                            </p>
                            <h3 className="text-5xl font-black mt-2">
                                {rybnoValue?.toLocaleString('pl-PL')}
                                <span className="text-2xl ml-2 font-normal text-emerald-100">
                                    {variablesData.variables[selectedVar].unit}
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

            {/* Tier Info Footer */}
            {variablesData && (
                <div className="bg-slate-50 rounded-2xl p-6 border border-slate-200">
                    <h3 className="font-bold mb-3 text-slate-700">📊 Plany subskrypcyjne</h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className={`p-4 rounded-xl ${userTier === 'free' ? 'bg-white border-2 border-blue-500' : 'bg-white border border-slate-200'}`}>
                            <div className="text-2xl mb-2">🆓</div>
                            <div className="font-bold text-slate-900">Free</div>
                            <div className="text-sm text-slate-500 mb-2">{variablesData.tiers.free.price}</div>
                            <div className="text-2xl font-bold text-slate-900">{variablesData.tiers.free.count}</div>
                            <div className="text-xs text-slate-500">wskaźników</div>
                        </div>
                        <div className={`p-4 rounded-xl ${userTier === 'premium' ? 'bg-white border-2 border-blue-500' : 'bg-white border border-slate-200'}`}>
                            <div className="text-2xl mb-2">⭐</div>
                            <div className="font-bold text-slate-900">Premium</div>
                            <div className="text-sm text-slate-500 mb-2">{variablesData.tiers.premium.price}</div>
                            <div className="text-2xl font-bold text-slate-900">{variablesData.tiers.premium.count}</div>
                            <div className="text-xs text-slate-500">wskaźników</div>
                        </div>
                        <div className={`p-4 rounded-xl ${userTier === 'business' ? 'bg-white border-2 border-blue-500' : 'bg-white border border-slate-200'}`}>
                            <div className="text-2xl mb-2">💎</div>
                            <div className="font-bold text-slate-900">Business</div>
                            <div className="text-sm text-slate-500 mb-2">{variablesData.tiers.business.price}</div>
                            <div className="text-2xl font-bold text-slate-900">{variablesData.tiers.business.count}</div>
                            <div className="text-xs text-slate-500">wskaźników + API</div>
                        </div>
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
