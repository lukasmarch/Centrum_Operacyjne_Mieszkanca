import React, { useState, useEffect } from 'react';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    BarChart, Bar, Legend, LineChart, Line, ComposedChart
} from 'recharts';
import AirlyWidget from '../../components/AirlyWidget';

// Types matching backend response
interface WeatherRecord {
    temperature: number;
    temp_min: number;
    temp_max: number;
    feels_like: number;
    humidity: number;
    pressure: number;
    wind_speed: number;
    wind_deg?: number;
    clouds: number;
    visibility?: number;
    rain_1h?: number;
    description: string;
    fetched_at: string;
}

interface AirQualityRecord {
    pm25: number;
    pm10: number;
    caqi: number;
    fetched_at: string;
}

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';

// Wind direction helper
const getWindDirection = (deg?: number): string => {
    if (deg === undefined) return '';
    const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    const index = Math.round(deg / 45) % 8;
    return directions[index];
};

const WeatherPage: React.FC = () => {
    const [currentAirQuality, setCurrentAirQuality] = useState<any>(null);
    const [weatherHistory, setWeatherHistory] = useState<WeatherRecord[]>([]);
    const [airQualityHistory, setAirQualityHistory] = useState<AirQualityRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedDays, setSelectedDays] = useState(3);

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            try {
                const [currentRes, weatherHistRes, aqHistRes] = await Promise.all([
                    fetch(`${API_URL}/api/weather/air-quality/current`),
                    fetch(`${API_URL}/api/weather/history?days=${selectedDays}`),
                    fetch(`${API_URL}/api/weather/air-quality/history?days=${selectedDays}`)
                ]);

                if (currentRes.ok) {
                    const data = await currentRes.json();
                    setCurrentAirQuality(data);
                }

                if (weatherHistRes.ok) {
                    const data = await weatherHistRes.json();
                    setWeatherHistory(data);
                }

                if (aqHistRes.ok) {
                    const data = await aqHistRes.json();
                    setAirQualityHistory(data);
                }

            } catch (err) {
                console.error("Failed to fetch weather data", err);
                setError("Nie udało się pobrać danych.");
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, [selectedDays]);

    // Format data for charts
    const formatTime = (isoString: string) => {
        const date = new Date(isoString);
        return `${date.getHours()}:00`;
    };

    const formatDate = (isoString: string) => {
        const date = new Date(isoString);
        return date.toLocaleDateString('pl-PL', { weekday: 'short', day: 'numeric' });
    };

    const formatDateTime = (isoString: string) => {
        const date = new Date(isoString);
        return date.toLocaleDateString('pl-PL', { weekday: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    };

    // Temperature chart data with min/max range
    const tempChartData = weatherHistory.map(item => ({
        time: formatTime(item.fetched_at),
        date: formatDate(item.fetched_at),
        fullDate: formatDateTime(item.fetched_at),
        temp: Math.round(item.temperature * 10) / 10,
        tempMin: Math.round(item.temp_min * 10) / 10,
        tempMax: Math.round(item.temp_max * 10) / 10,
        feelsLike: Math.round(item.feels_like * 10) / 10
    }));

    // Humidity & Pressure chart data
    const conditionsChartData = weatherHistory.map(item => ({
        time: formatTime(item.fetched_at),
        date: formatDate(item.fetched_at),
        fullDate: formatDateTime(item.fetched_at),
        humidity: item.humidity,
        pressure: item.pressure,
        clouds: item.clouds
    }));

    // Wind chart data
    const windChartData = weatherHistory.map(item => ({
        time: formatTime(item.fetched_at),
        date: formatDate(item.fetched_at),
        fullDate: formatDateTime(item.fetched_at),
        speed: Math.round(item.wind_speed * 10) / 10,
        direction: getWindDirection(item.wind_deg),
        speedKmh: Math.round(item.wind_speed * 3.6 * 10) / 10 // m/s to km/h
    }));

    // Air quality chart data
    const aqChartData = airQualityHistory.map(item => ({
        time: formatTime(item.fetched_at),
        date: formatDate(item.fetched_at),
        fullDate: formatDateTime(item.fetched_at),
        pm25: item.pm25,
        pm10: item.pm10,
        caqi: item.caqi
    }));

    // Stats calculations
    const stats = weatherHistory.length > 0 ? {
        avgTemp: Math.round((weatherHistory.reduce((sum, w) => sum + w.temperature, 0) / weatherHistory.length) * 10) / 10,
        maxTemp: Math.max(...weatherHistory.map(w => w.temp_max)),
        minTemp: Math.min(...weatherHistory.map(w => w.temp_min)),
        avgHumidity: Math.round(weatherHistory.reduce((sum, w) => sum + w.humidity, 0) / weatherHistory.length),
        avgWind: Math.round((weatherHistory.reduce((sum, w) => sum + w.wind_speed, 0) / weatherHistory.length) * 10) / 10,
        maxWind: Math.max(...weatherHistory.map(w => w.wind_speed))
    } : null;

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">

            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-3xl font-black text-slate-900">Pogoda i Jakość Powietrza</h1>
                    <p className="text-slate-500">Analityka historyczna warunków atmosferycznych w Gminie Rybno.</p>
                </div>
                <div className="flex items-center gap-4">
                    <select
                        value={selectedDays}
                        onChange={(e) => setSelectedDays(Number(e.target.value))}
                        className="px-4 py-2 border border-slate-200 rounded-xl bg-white text-sm font-medium"
                    >
                        <option value={1}>Ostatni dzień</option>
                        <option value={3}>Ostatnie 3 dni</option>
                        <option value={7}>Ostatni tydzień</option>
                        <option value={14}>Ostatnie 2 tygodnie</option>
                    </select>
                    <div className="text-right hidden sm:block">
                        <div className="text-sm font-bold text-slate-400">PUNKTÓW DANYCH</div>
                        <div className="font-mono text-slate-600">{weatherHistory.length}</div>
                    </div>
                </div>
            </div>

            {/* Stats Summary */}
            {stats && (
                <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
                    <div className="bg-gradient-to-br from-blue-50 to-blue-100 p-4 rounded-2xl border border-blue-200">
                        <div className="text-xs font-bold text-blue-600 mb-1">ŚR. TEMP</div>
                        <div className="text-2xl font-black text-blue-900">{stats.avgTemp}°C</div>
                    </div>
                    <div className="bg-gradient-to-br from-red-50 to-red-100 p-4 rounded-2xl border border-red-200">
                        <div className="text-xs font-bold text-red-600 mb-1">MAX TEMP</div>
                        <div className="text-2xl font-black text-red-900">{stats.maxTemp}°C</div>
                    </div>
                    <div className="bg-gradient-to-br from-cyan-50 to-cyan-100 p-4 rounded-2xl border border-cyan-200">
                        <div className="text-xs font-bold text-cyan-600 mb-1">MIN TEMP</div>
                        <div className="text-2xl font-black text-cyan-900">{stats.minTemp}°C</div>
                    </div>
                    <div className="bg-gradient-to-br from-indigo-50 to-indigo-100 p-4 rounded-2xl border border-indigo-200">
                        <div className="text-xs font-bold text-indigo-600 mb-1">ŚR. WILG</div>
                        <div className="text-2xl font-black text-indigo-900">{stats.avgHumidity}%</div>
                    </div>
                    <div className="bg-gradient-to-br from-teal-50 to-teal-100 p-4 rounded-2xl border border-teal-200">
                        <div className="text-xs font-bold text-teal-600 mb-1">ŚR. WIATR</div>
                        <div className="text-2xl font-black text-teal-900">{stats.avgWind} m/s</div>
                    </div>
                    <div className="bg-gradient-to-br from-orange-50 to-orange-100 p-4 rounded-2xl border border-orange-200">
                        <div className="text-xs font-bold text-orange-600 mb-1">MAX WIATR</div>
                        <div className="text-2xl font-black text-orange-900">{stats.maxWind} m/s</div>
                    </div>
                </div>
            )}

            {/* Main Widget */}
            <AirlyWidget
                data={currentAirQuality}
                loading={loading}
                error={error}
            />

            {/* Charts Section - Row 1 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

                {/* Temperature Range Chart */}
                <div className="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm">
                    <div className="flex justify-between items-center mb-6">
                        <h3 className="font-bold text-lg">🌡️ Temperatura (min/max/aktualna)</h3>
                        <span className="text-xs bg-blue-100 text-blue-600 px-2 py-1 rounded-full font-bold">
                            Ostatnie {selectedDays} dni
                        </span>
                    </div>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <ComposedChart data={tempChartData}>
                                <defs>
                                    <linearGradient id="colorTempRange" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
                                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                <XAxis
                                    dataKey="date"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fontSize: 11, fill: '#94a3b8' }}
                                    interval="preserveStartEnd"
                                />
                                <YAxis
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fontSize: 11, fill: '#94a3b8' }}
                                    unit="°"
                                    domain={['auto', 'auto']}
                                />
                                <Tooltip
                                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                    labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ''}
                                />
                                <Legend iconType="circle" />
                                <Area
                                    type="monotone"
                                    dataKey="tempMax"
                                    stroke="#ef4444"
                                    strokeWidth={2}
                                    fillOpacity={0.1}
                                    fill="#ef4444"
                                    name="Max"
                                />
                                <Line
                                    type="monotone"
                                    dataKey="temp"
                                    stroke="#3b82f6"
                                    strokeWidth={3}
                                    dot={false}
                                    name="Aktualna"
                                />
                                <Area
                                    type="monotone"
                                    dataKey="tempMin"
                                    stroke="#06b6d4"
                                    strokeWidth={2}
                                    fillOpacity={0.1}
                                    fill="#06b6d4"
                                    name="Min"
                                />
                            </ComposedChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Wind Chart */}
                <div className="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm">
                    <div className="flex justify-between items-center mb-6">
                        <h3 className="font-bold text-lg">💨 Prędkość wiatru</h3>
                        <span className="text-xs bg-teal-100 text-teal-600 px-2 py-1 rounded-full font-bold">m/s</span>
                    </div>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={windChartData}>
                                <defs>
                                    <linearGradient id="colorWind" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#14b8a6" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                <XAxis
                                    dataKey="date"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fontSize: 11, fill: '#94a3b8' }}
                                    interval="preserveStartEnd"
                                />
                                <YAxis
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fontSize: 11, fill: '#94a3b8' }}
                                    unit=" m/s"
                                />
                                <Tooltip
                                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                    labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ''}
                                    formatter={(value: any, name: string) => [
                                        `${value} m/s (${Math.round(value * 3.6)} km/h)`,
                                        'Prędkość'
                                    ]}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="speed"
                                    stroke="#14b8a6"
                                    strokeWidth={3}
                                    fillOpacity={1}
                                    fill="url(#colorWind)"
                                    name="Wiatr"
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>

            </div>

            {/* Charts Section - Row 2 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

                {/* Humidity & Clouds Chart */}
                <div className="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm">
                    <div className="flex justify-between items-center mb-6">
                        <h3 className="font-bold text-lg">💧 Wilgotność i Zachmurzenie</h3>
                        <span className="text-xs bg-indigo-100 text-indigo-600 px-2 py-1 rounded-full font-bold">%</span>
                    </div>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={conditionsChartData}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                <XAxis
                                    dataKey="date"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fontSize: 11, fill: '#94a3b8' }}
                                    interval="preserveStartEnd"
                                />
                                <YAxis
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fontSize: 11, fill: '#94a3b8' }}
                                    unit="%"
                                    domain={[0, 100]}
                                />
                                <Tooltip
                                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                    labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ''}
                                />
                                <Legend iconType="circle" />
                                <Line
                                    type="monotone"
                                    dataKey="humidity"
                                    stroke="#6366f1"
                                    strokeWidth={2}
                                    dot={false}
                                    name="Wilgotność"
                                />
                                <Line
                                    type="monotone"
                                    dataKey="clouds"
                                    stroke="#94a3b8"
                                    strokeWidth={2}
                                    dot={false}
                                    strokeDasharray="5 5"
                                    name="Zachmurzenie"
                                />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Pressure Chart */}
                <div className="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm">
                    <div className="flex justify-between items-center mb-6">
                        <h3 className="font-bold text-lg">🔵 Ciśnienie atmosferyczne</h3>
                        <span className="text-xs bg-purple-100 text-purple-600 px-2 py-1 rounded-full font-bold">hPa</span>
                    </div>
                    <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={conditionsChartData}>
                                <defs>
                                    <linearGradient id="colorPressure" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                                        <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                <XAxis
                                    dataKey="date"
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fontSize: 11, fill: '#94a3b8' }}
                                    interval="preserveStartEnd"
                                />
                                <YAxis
                                    axisLine={false}
                                    tickLine={false}
                                    tick={{ fontSize: 11, fill: '#94a3b8' }}
                                    unit=" hPa"
                                    domain={['dataMin - 5', 'dataMax + 5']}
                                />
                                <Tooltip
                                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                    labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ''}
                                />
                                <Area
                                    type="monotone"
                                    dataKey="pressure"
                                    stroke="#8b5cf6"
                                    strokeWidth={3}
                                    fillOpacity={1}
                                    fill="url(#colorPressure)"
                                    name="Ciśnienie"
                                />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>

            </div>

            {/* Air Quality Chart */}
            <div className="bg-white p-6 rounded-3xl border border-slate-100 shadow-sm">
                <div className="flex justify-between items-center mb-6">
                    <h3 className="font-bold text-lg">🌫️ Zanieczyszczenie PM (Pyły zawieszone)</h3>
                    <span className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded-full font-bold">µg/m³</span>
                </div>
                <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={aqChartData}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis
                                dataKey="date"
                                axisLine={false}
                                tickLine={false}
                                tick={{ fontSize: 11, fill: '#94a3b8' }}
                                interval={0}
                            />
                            <YAxis
                                axisLine={false}
                                tickLine={false}
                                tick={{ fontSize: 11, fill: '#94a3b8' }}
                            />
                            <Tooltip
                                cursor={{ fill: '#f8fafc' }}
                                contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ''}
                            />
                            <Legend iconType="circle" />
                            <Bar dataKey="pm25" name="PM 2.5" fill="#60a5fa" radius={[4, 4, 0, 0]} />
                            <Bar dataKey="pm10" name="PM 10" fill="#94a3b8" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Info Box */}
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 rounded-2xl p-6">
                <h4 className="font-bold text-blue-900 mb-3 text-lg">📊 O analizie danych pogodowych</h4>
                <div className="grid md:grid-cols-2 gap-4 text-sm text-blue-800">
                    <div>
                        <strong>Temperatura:</strong> Wykres pokazuje zakres temperatur (min/max) oraz aktualną temperaturę.
                        Różnica między nimi wskazuje na dobowe wahania termiczne.
                    </div>
                    <div>
                        <strong>Wiatr:</strong> Prędkość wiatru w metrach na sekundę. Wartości powyżej 10 m/s oznaczają silny wiatr.
                    </div>
                    <div>
                        <strong>Wilgotność:</strong> Poziom wilgotności powietrza (%). Optymalna wilgotność to 40-60%.
                    </div>
                    <div>
                        <strong>Ciśnienie:</strong> Wahania ciśnienia atmosferycznego wpływają na samopoczucie.
                        Nagłe spadki często zwiastują zmianę pogody.
                    </div>
                </div>
            </div>

        </div>
    );
};

export default WeatherPage;

