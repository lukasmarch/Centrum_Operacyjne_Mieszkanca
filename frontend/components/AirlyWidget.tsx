import React from 'react';
import { Droplets, Gauge, Thermometer } from 'lucide-react';
import { Skeleton, Tag, TagTone } from './simple/tv';
import { clockLabel, parseUtc } from '../src/utils/articleTime';

interface AirlyData {
    pm25: number;
    pm10: number;
    caqi: number;
    caqi_level: string;
    // Czujnik Airly nie zawsze raportuje warunki pogodowe — pola bywają puste
    temperature: number | null;
    humidity: number | null;
    pressure: number | null;
    fetched_at: string;
}

/** Sformatuj pomiar lub pokaż kreskę — nigdy "undefined" na ekranie. */
const fmt = (value: number | null | undefined, digits: number, unit: string): string =>
    typeof value === 'number' && Number.isFinite(value)
        ? `${value.toFixed(digits)}${unit}`
        : '—';

interface AirlyWidgetProps {
    data: AirlyData | null;
    loading: boolean;
    error: string | null;
}

/**
 * Pomiar starszy niż tyle — żółta adnotacja „pomiar z HH:MM”. Próg wyższy niż
 * dla pogody (2 h), bo Airly odpytujemy co 4 h: inaczej zwykły odstęp między
 * pomiarami wyglądałby na awarię.
 */
const STALE_AFTER_MS = 5 * 60 * 60 * 1000;

/**
 * Kolor plakietki = stan powietrza (odświeżenie „Pasek informacyjny”, 10.2026).
 * Dobre powietrze nie dostaje koloru — chaber jak każda sekcja. Żółć, gdy osoby
 * wrażliwe mają uważać — i tak samo przy złym powietrzu: czerwień należy w tym
 * świecie wyłącznie do awarii (decyzja Łukasza 11.10.2026). Stopień mówi słowo
 * („Zła”, „Bardzo zła”) i zalecenie pod nim, nie kolor.
 * Tęczowa skala (zieleń → fiolet) była ozdobą, nie stanem.
 */
const levelTone = (level: string): TagTone => {
    switch (level) {
        case 'MEDIUM':
        case 'HIGH':
        case 'VERY_HIGH':
        case 'EXTREME':
            return 'yellow';
        case 'VERY_LOW':
        case 'LOW':
            return 'blue';
        default:
            return 'seam';
    }
};

const AirlyWidget: React.FC<AirlyWidgetProps> = ({ data, loading, error }) => {
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
            <section aria-label="Jakość powietrza" aria-busy="true">
                <Tag as="h2">Jakość powietrza · Rybno</Tag>
                <Skeleton className="h-48" />
                <p className="sr-only">Pobieranie danych o jakości powietrza...</p>
            </section>
        );
    }

    if (error || !data) {
        return (
            <section aria-label="Jakość powietrza">
                <Tag as="h2" tone="seam">Jakość powietrza · Rybno</Tag>
                <p role="alert" className="bg-tv-yellow px-4 py-3 text-[15px] leading-snug text-tv-ink">
                    <span className="font-semibold">Nie udało się pobrać danych</span>
                    {error && <span className="block">{error}</span>}
                </p>
            </section>
        );
    }

    const pm25Percent = Math.min((data.pm25 / 15) * 100, 100); // WHO standard 15 µg/m³
    const pm10Percent = Math.min((data.pm10 / 45) * 100, 100); // WHO standard 45 µg/m³

    // Do 11.10.2026 pasek miał być czerwony przy `percent > 100`, ale procent jest
    // przycięty do 100 wyżej — warunek nigdy nie zachodził. Przekroczenie normy
    // WHO czytamy z surowej wartości; kolor = stan (żółć: ponad normę).
    const pmRows = [
        { key: 'pm25', label: 'PM 2.5', value: data.pm25, percent: pm25Percent, over: data.pm25 > 15 },
        { key: 'pm10', label: 'PM 10', value: data.pm10, percent: pm10Percent, over: data.pm10 > 45 },
    ];

    const measuredAt = parseUtc(data.fetched_at);
    const staleAt = measuredAt && Date.now() - measuredAt.getTime() >= STALE_AFTER_MS ? clockLabel(measuredAt) : null;

    // Czujnik Airly nie zawsze raportuje warunki pogodowe — brakujące chowamy
    // zamiast pokazywać pustą kreskę
    const readings = [
        { key: 'temp', Icon: Thermometer, label: 'Temp', value: data.temperature, text: fmt(data.temperature, 1, '°C') },
        { key: 'hum', Icon: Droplets, label: 'Wilgoć', value: data.humidity, text: fmt(data.humidity, 0, '%') },
        { key: 'pres', Icon: Gauge, label: 'Ciśnienie', value: data.pressure, text: fmt(data.pressure, 0, ' hPa') },
    ].filter(r => typeof r.value === 'number' && Number.isFinite(r.value));

    return (
        <section aria-label="Jakość powietrza">
            <Tag as="h2" tone={levelTone(data.caqi_level)}>Jakość powietrza · stacja Rybno</Tag>
            <div className="grid grid-cols-1 gap-px border-t-2 border-tv-blue bg-tv-seam md:grid-cols-2">

                {/* Poziom słowem jest odpowiedzią; liczba CAQI to szczegół obok */}
                <div className="bg-tv-panel px-4 pb-4 pt-3 lg:px-5">
                    <p className="flex flex-wrap items-baseline gap-x-3">
                        <span className="font-cond text-[34px] font-extrabold leading-tight text-white lg:text-[40px]">
                            {getLevelText(data.caqi_level)}
                        </span>
                        <span className="font-cond tabular text-[20px] font-bold text-tv-muted">
                            CAQI {Math.round(data.caqi)}
                        </span>
                    </p>
                    <p className="mt-2 max-w-[60ch] text-[15px] leading-relaxed text-[#d7dbe8]">
                        {getAdvice(data.caqi_level)}
                    </p>
                    {staleAt && <p className="mt-1 text-[15px] font-semibold text-tv-yellow">pomiar z {staleAt}</p>}
                </div>

                <div className="flex flex-col gap-4 bg-tv-panel px-4 py-4 lg:px-5">
                    {/* Pasek = udział normy WHO; płaski segment, nie gradient */}
                    {pmRows.map(r => (
                        <div key={r.key}>
                            <div className="mb-1.5 flex justify-between gap-3 text-[15px]">
                                <span className="font-semibold text-tv-paper">{r.label}</span>
                                <span className="tabular text-white">
                                    {Math.round(r.value)} µg/m³ <span className="text-tv-muted">({Math.round(r.percent)}% normy WHO)</span>
                                </span>
                            </div>
                            <div className="h-2 bg-tv-seam">
                                <div
                                    className={`h-full ${r.over ? 'bg-tv-paper' : 'bg-tv-bluesoft'}`}
                                    style={{ width: `${r.percent}%` }}
                                />
                            </div>
                        </div>
                    ))}

                    {readings.length > 0 && (
                        <div className="grid grid-cols-3 gap-px border-t border-tv-seam bg-tv-seam">
                            {readings.map(({ key, Icon, label, text }) => (
                                <div key={key} className="bg-tv-panel pt-3">
                                    <div className="flex items-center gap-1.5 text-[13px] text-tv-muted">
                                        <Icon size={16} aria-hidden />
                                        {label}
                                    </div>
                                    <div className="font-cond tabular mt-0.5 text-[20px] font-extrabold text-white">{text}</div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </section>
    );
};

export default AirlyWidget;
