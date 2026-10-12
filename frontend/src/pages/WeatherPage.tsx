import React, { useState, useEffect } from 'react';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    BarChart, Bar, Legend, LineChart, Line, ComposedChart
} from 'recharts';
import AirlyWidget from '../../components/AirlyWidget';
import { PageHead, Select, Skeleton, Tag } from '../../components/simple/tv';
import { clockLabel, parseUtc } from '../utils/articleTime';

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

// Fallback musi zawierać /api — endpointy doklejają samą ścieżkę („/events").
// Bez tego `npm run dev` bez jawnej zmiennej trafiał w :8000/events → 404:
// vite.config ma envDir wskazujący ../backend, więc frontend/.env NIE jest
// wczytywany, a produkcja działa tylko dlatego, że deploy-frontend.sh podaje
// VITE_API_URL w linii poleceń.
const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api';

// Wind direction helper
const getWindDirection = (deg?: number): string => {
    if (deg === undefined) return '';
    const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    const index = Math.round(deg / 45) % 8;
    return directions[index];
};

/** Pomiar starszy niż tyle — „pomiar z HH:MM” jak na kaflu pulpitu (job chodzi co godzinę) */
const STALE_AFTER_MS = 2 * 60 * 60 * 1000;

/* Barwy wykresów z palety „Pasek informacyjny”: seria główna chabrem jasnym,
   pomocnicze papierem i przygaszeniem. Kolor nie rozróżnia zjawisk — robi to
   legenda; czerwień i żółć zostają dla stanów, nie dla serii. */
const C = {
    main: '#8fa8ff',
    paper: '#f5f6fa',
    muted: '#b4bbd0',
    seam: '#222b45',
    panel: '#121829',
};
const AXIS_TICK = { fontSize: 13, fill: C.muted };
const TOOLTIP_STYLE = { backgroundColor: C.panel, borderRadius: 0, border: `1px solid ${C.seam}`, color: C.paper, fontSize: 14 };
const LEGEND_STYLE = { paddingTop: '10px', fontSize: 13, color: C.muted };

/** Panel wykresu: plakietka-nagłówek, jednostka obok, panel z chabrową krawędzią */
const ChartPanel: React.FC<{ title: string; unit: string; children: React.ReactNode }> = ({ title, unit, children }) => (
    <section aria-label={title}>
        <div className="flex items-baseline gap-3">
            <Tag as="h2">{title}</Tag>
            <span className="text-[14px] text-tv-muted">{unit}</span>
        </div>
        <div className="h-64 border-t-2 border-tv-blue bg-tv-panel p-3 lg:p-4">
            {children}
        </div>
    </section>
);

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
                    fetch(`${API_URL}/weather/air-quality/current`),
                    fetch(`${API_URL}/weather/history?days=${selectedDays}`),
                    fetch(`${API_URL}/weather/air-quality/history?days=${selectedDays}`)
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

    // Ostatni wiersz historii to bieżący pomiar (backend sortuje rosnąco po `fetched_at`)
    const latest = weatherHistory.length > 0 ? weatherHistory[weatherHistory.length - 1] : null;
    const latestAt = parseUtc(latest?.fetched_at);
    const staleAt = latestAt && Date.now() - latestAt.getTime() >= STALE_AFTER_MS ? clockLabel(latestAt) : null;
    const latestSentence = latest?.description
        ? latest.description.charAt(0).toUpperCase() + latest.description.slice(1)
        : null;
    const latestDetails = latest
        ? [
            `Odczuwalnie ${Math.round(latest.feels_like)}°`,
            `${Math.round(latest.wind_speed * 3.6)} km/h${latest.wind_deg !== undefined && latest.wind_deg !== null ? ` ${getWindDirection(latest.wind_deg)}` : ''}`,
            `wilgotność ${latest.humidity}%`,
        ].join(' · ')
        : null;

    // Przecinek dziesiętny i jedna cyfra po nim — „15.93°C” obok „-0,6” w GUS to dwie konwencje na jednej stronie
    const pl = (v: number | string) => Number(v).toLocaleString('pl-PL', { maximumFractionDigits: 1 });
    const statCells = stats ? [
        { label: 'Śr. temp', value: `${pl(stats.avgTemp)}°C` },
        { label: 'Max temp', value: `${pl(stats.maxTemp)}°C` },
        { label: 'Min temp', value: `${pl(stats.minTemp)}°C` },
        { label: 'Śr. wilg', value: `${pl(stats.avgHumidity)}%` },
        { label: 'Śr. wiatr', value: `${pl(stats.avgWind)} m/s` },
        { label: 'Max wiatr', value: `${pl(stats.maxWind)} m/s` },
    ] : [];

    return (
        <div className="space-y-6 lg:space-y-8">

            <PageHead
                title="Pogoda i jakość powietrza"
                sub="Analityka historyczna warunków atmosferycznych w Gminie Rybno."
                aside={
                    <div className="flex items-center gap-4">
                        <label className="sr-only" htmlFor="weather-days">Okres</label>
                        <Select
                            id="weather-days"
                            value={selectedDays}
                            onChange={(e) => setSelectedDays(Number(e.target.value))}
                        >
                            <option value={1}>Ostatni dzień</option>
                            <option value={3}>Ostatnie 3 dni</option>
                            <option value={7}>Ostatni tydzień</option>
                            <option value={14}>Ostatnie 2 tygodnie</option>
                        </Select>
                        <span className="hidden text-[14px] text-tv-muted sm:block">
                            Punktów danych <span className="tabular font-bold text-tv-paper">{weatherHistory.length}</span>
                        </span>
                    </div>
                }
            />

            {/* Teraz: temperatura jest odpowiedzią, zdanie pod nią dopowiada — jak kafel pulpitu */}
            <section aria-label="Pogoda teraz">
                <Tag as="h2">Teraz · Rybno</Tag>
                {loading && !latest ? (
                    <Skeleton className="h-32" />
                ) : latest ? (
                    <div className="grid grid-cols-1 gap-px border-t-2 border-tv-blue bg-tv-seam md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
                        <div className="bg-tv-panel px-4 pb-4 pt-3 lg:px-5">
                            <p className="font-cond tabular text-[56px] font-extrabold leading-none text-white lg:text-[72px]">
                                {Math.round(latest.temperature)}°
                            </p>
                            {latestSentence && <p className="mt-2 text-[16px] font-semibold text-tv-paper">{latestSentence}</p>}
                            {latestDetails && <p className="mt-0.5 text-[15px] text-tv-muted">{latestDetails}</p>}
                            {staleAt && <p className="mt-1 text-[15px] font-semibold text-tv-yellow">pomiar z {staleAt}</p>}
                        </div>
                        {/* Podsumowanie wybranego okresu — siatka na tle szwu, nie kolorowe karty */}
                        {statCells.length > 0 && (
                            <div className="grid grid-cols-2 gap-px bg-tv-seam sm:grid-cols-3">
                                <p className="col-span-full bg-tv-panel px-4 pt-3 text-[14px] text-tv-muted">W wybranym okresie</p>
                                {statCells.map(c => (
                                    <div key={c.label} className="bg-tv-panel px-4 py-3">
                                        <div className="font-cond text-[13px] font-extrabold uppercase tracking-wide text-tv-muted">{c.label}</div>
                                        <div className="font-cond tabular mt-1 text-[26px] font-extrabold leading-[1.05] text-white">{c.value}</div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                ) : (
                    <p className="border-t-2 border-tv-seam bg-tv-panel px-4 py-3 text-[15px] text-tv-paper">
                        Brak pomiarów pogody w wybranym okresie.
                    </p>
                )}
            </section>

            {/* Jakość powietrza — widżet niesie własną plakietkę (kolor = stan powietrza) */}
            <AirlyWidget
                data={currentAirQuality}
                loading={loading}
                error={error}
            />

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">

                <ChartPanel title="Temperatura" unit="min / max / aktualna, °C">
                    <ResponsiveContainer width="100%" height="100%">
                        <ComposedChart data={tempChartData}>
                            <CartesianGrid vertical={false} stroke={C.seam} />
                            <XAxis dataKey="date" axisLine={false} tickLine={false} tick={AXIS_TICK} interval="preserveStartEnd" />
                            <YAxis axisLine={false} tickLine={false} tick={AXIS_TICK} unit="°" domain={['auto', 'auto']} width={40} />
                            <Tooltip
                                contentStyle={TOOLTIP_STYLE}
                                labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ''}
                            />
                            <Legend iconType="plainline" wrapperStyle={LEGEND_STYLE} />
                            <Line type="monotone" dataKey="tempMax" stroke={C.paper} strokeWidth={1.5} dot={false} name="Max" />
                            <Line type="monotone" dataKey="temp" stroke={C.main} strokeWidth={3} dot={false} name="Aktualna" />
                            <Line type="monotone" dataKey="tempMin" stroke={C.muted} strokeWidth={1.5} strokeDasharray="5 5" dot={false} name="Min" />
                        </ComposedChart>
                    </ResponsiveContainer>
                </ChartPanel>

                <ChartPanel title="Prędkość wiatru" unit="m/s">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={windChartData}>
                            <CartesianGrid vertical={false} stroke={C.seam} />
                            <XAxis dataKey="date" axisLine={false} tickLine={false} tick={AXIS_TICK} interval="preserveStartEnd" />
                            <YAxis axisLine={false} tickLine={false} tick={AXIS_TICK} unit=" m/s" width={56} />
                            <Tooltip
                                contentStyle={TOOLTIP_STYLE}
                                labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ''}
                                formatter={(value: any) => [
                                    `${value} m/s (${Math.round(value * 3.6)} km/h)`,
                                    'Prędkość'
                                ]}
                            />
                            {/* Płaskie wypełnienie zamiast gradientu */}
                            <Area type="monotone" dataKey="speed" stroke={C.main} strokeWidth={3} fill={C.main} fillOpacity={0.12} name="Wiatr" />
                        </AreaChart>
                    </ResponsiveContainer>
                </ChartPanel>

                <ChartPanel title="Wilgotność i zachmurzenie" unit="%">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={conditionsChartData}>
                            <CartesianGrid vertical={false} stroke={C.seam} />
                            <XAxis dataKey="date" axisLine={false} tickLine={false} tick={AXIS_TICK} interval="preserveStartEnd" />
                            <YAxis axisLine={false} tickLine={false} tick={AXIS_TICK} unit="%" domain={[0, 100]} width={48} />
                            <Tooltip
                                contentStyle={TOOLTIP_STYLE}
                                labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ''}
                            />
                            <Legend iconType="plainline" wrapperStyle={LEGEND_STYLE} />
                            <Line type="monotone" dataKey="humidity" stroke={C.main} strokeWidth={2} dot={false} name="Wilgotność" />
                            <Line type="monotone" dataKey="clouds" stroke={C.muted} strokeWidth={2} dot={false} strokeDasharray="5 5" name="Zachmurzenie" />
                        </LineChart>
                    </ResponsiveContainer>
                </ChartPanel>

                <ChartPanel title="Ciśnienie atmosferyczne" unit="hPa">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={conditionsChartData}>
                            <CartesianGrid vertical={false} stroke={C.seam} />
                            <XAxis dataKey="date" axisLine={false} tickLine={false} tick={AXIS_TICK} interval="preserveStartEnd" />
                            <YAxis axisLine={false} tickLine={false} tick={AXIS_TICK} unit=" hPa" domain={['dataMin - 5', 'dataMax + 5']} width={72} />
                            <Tooltip
                                contentStyle={TOOLTIP_STYLE}
                                labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ''}
                            />
                            <Area type="monotone" dataKey="pressure" stroke={C.main} strokeWidth={3} fill={C.main} fillOpacity={0.12} name="Ciśnienie" />
                        </AreaChart>
                    </ResponsiveContainer>
                </ChartPanel>

            </div>

            <ChartPanel title="Zanieczyszczenie PM (pyły zawieszone)" unit="µg/m³">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={aqChartData}>
                        <CartesianGrid vertical={false} stroke={C.seam} />
                        <XAxis dataKey="date" axisLine={false} tickLine={false} tick={AXIS_TICK} interval="preserveStartEnd" />
                        <YAxis axisLine={false} tickLine={false} tick={AXIS_TICK} width={40} />
                        <Tooltip
                            cursor={{ fill: '#182036' }}
                            contentStyle={TOOLTIP_STYLE}
                            labelFormatter={(_, payload) => payload?.[0]?.payload?.fullDate || ''}
                        />
                        <Legend iconType="square" wrapperStyle={LEGEND_STYLE} />
                        <Bar dataKey="pm25" name="PM 2.5" fill={C.main} />
                        <Bar dataKey="pm10" name="PM 10" fill={C.muted} />
                    </BarChart>
                </ResponsiveContainer>
            </ChartPanel>

            <section aria-label="O analizie danych pogodowych">
                <Tag as="h2" tone="seam">O analizie danych pogodowych</Tag>
                <div className="grid grid-cols-1 gap-px border-t border-tv-seam bg-tv-seam md:grid-cols-2">
                    {[
                        ['Temperatura', 'Wykres pokazuje zakres temperatur (min/max) oraz aktualną temperaturę. Różnica między nimi wskazuje na dobowe wahania termiczne.'],
                        ['Wiatr', 'Prędkość wiatru w metrach na sekundę. Wartości powyżej 10 m/s oznaczają silny wiatr.'],
                        ['Wilgotność', 'Poziom wilgotności powietrza (%). Optymalna wilgotność to 40-60%.'],
                        ['Ciśnienie', 'Wahania ciśnienia atmosferycznego wpływają na samopoczucie. Nagłe spadki często zwiastują zmianę pogody.'],
                    ].map(([title, text]) => (
                        <div key={title} className="bg-tv-panel px-4 py-3">
                            <h3 className="text-[16px] font-bold text-white">{title}</h3>
                            <p className="mt-1 max-w-[70ch] text-[15px] leading-relaxed text-[#d7dbe8]">{text}</p>
                        </div>
                    ))}
                </div>
            </section>

        </div>
    );
};

export default WeatherPage;
