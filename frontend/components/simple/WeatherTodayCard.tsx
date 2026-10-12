import React, { useMemo } from 'react';
import {
    Cloud, CloudDrizzle, CloudFog, CloudLightning,
    CloudRain, CloudSnow, CloudSun, Moon, Sun, LucideIcon,
} from 'lucide-react';
import type { WeatherFull } from '../../src/hooks/useWeather';
import { clockLabel, parseUtc } from '../../src/utils/articleTime';
import { Plate } from './tv';

/**
 * Pogoda w sekcji „Na dziś" — kafel, nie podpis.
 *
 * Pozostałe trzy karty odpowiadają na pytanie jednym zdaniem („odpady — jutro").
 * Pogoda tak nie działa: mieszkaniec chce najpierw LICZBĘ, a dopiero potem
 * zdanie. Dlatego ta jedna karta ma inną hierarchię — temperatura jest tym,
 * czym w pozostałych jest tytuł.
 *
 * Powierzchnia zostaje ta sama co u sąsiadów (jedno pole siatki, na telefonie
 * wiersz): kafel ma być gęstszy, nie większy — inaczej rozepchnąłby sekcję
 * i zabrał miejsce odpadom i autobusowi.
 *
 * ⚠️ Ikona NIE jest pobierana z openweathermap.org, choć tak robi stary
 * `WeatherTile`. To PWA — kafel ma się rysować także wtedy, gdy telefon jest
 * bez zasięgu, a dane pogodowe idą z pamięci podręcznej. Ikona pochodzi
 * z tego samego zestawu (lucide), co reszta serwisu.
 *
 * 11.10.2026 (odświeżenie „Pasek informacyjny”): bez orba i poświaty — kafel
 * stoi na wspólnej plakietce `Plate`, kolor niesie wyłącznie stan.
 */

interface ConditionLook {
    Icon: LucideIcon;
    /** Kolor zjawiska — dziś nieużywany na pulpicie, zostaje dla strony pogody */
    glow: string;
    label: string;
}

/**
 * `main` z OpenWeather + pora doby z kodu ikony (`…d` / `…n`).
 * Nocne bezchmurne niebo z ikoną słońca to najczęstszy błąd widgetów pogodowych
 * i jedyny powód, dla którego w ogóle patrzymy tu na kod ikony.
 */
function conditionLook(main: string | undefined, icon: string | undefined): ConditionLook {
    const night = typeof icon === 'string' && icon.endsWith('n');
    switch ((main || '').toLowerCase()) {
        case 'thunderstorm': return { Icon: CloudLightning, glow: '#a78bfa', label: 'burza' };
        case 'drizzle': return { Icon: CloudDrizzle, glow: '#60a5fa', label: 'mżawka' };
        case 'rain': return { Icon: CloudRain, glow: '#60a5fa', label: 'deszcz' };
        case 'snow': return { Icon: CloudSnow, glow: '#bae6fd', label: 'śnieg' };
        case 'atmosphere':
        case 'mist':
        case 'fog': return { Icon: CloudFog, glow: '#94a3b8', label: 'mgła' };
        case 'clouds': return night
            ? { Icon: Cloud, glow: '#94a3b8', label: 'pochmurno' }
            : { Icon: CloudSun, glow: '#94a3b8', label: 'pochmurno' };
        default: return night
            ? { Icon: Moon, glow: '#93c5fd', label: 'pogodnie' }
            : { Icon: Sun, glow: '#fbbf24', label: 'słonecznie' };
    }
}

/**
 * Wygląd, zanim przyjdą dane. Do 11.10.2026 brak danych wpadał w gałąź
 * `default` i kafel pokazywał „słonecznie” ze słońcem — także w deszczu,
 * przy wolnym łączu albo awarii API (audyt V11). Pustka nie jest pogodą.
 */
const NO_DATA_LOOK: ConditionLook = { Icon: Cloud, glow: '#64748b', label: '' };

/** Pomiar starszy niż tyle — kafel mówi, z której godziny jest (job chodzi co godzinę) */
const STALE_AFTER_MS = 2 * 60 * 60 * 1000;

const WIND_DIRS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];

interface WeatherTodayCardProps {
    weather: WeatherFull | null;
    /** Pierwsze ładowanie — „Ładuję…” zamiast pustego kafla */
    loading?: boolean;
    /** Jakość powietrza słowem — liczby i jednostki dopiero na stronie pogody */
    airLabel: string | null;
    onClick: () => void;
}

const WeatherTodayCard: React.FC<WeatherTodayCardProps> = ({ weather, loading = false, airLabel, onClick }) => {
    const look = useMemo(
        () => (weather ? conditionLook(weather.main, weather.icon) : NO_DATA_LOOK),
        [weather],
    );

    // Godzina pomiaru tylko wtedy, gdy jest stary — świeży nie potrzebuje podpisu
    const staleAt = useMemo(() => {
        const at = parseUtc(weather?.fetched_at);
        if (!at || Date.now() - at.getTime() < STALE_AFTER_MS) return null;
        return clockLabel(at);
    }, [weather?.fetched_at]);

    // Wiatr i odczuwalna: dwie liczby, które zmieniają decyzję „w czym wyjść".
    // Kierunek wiatru tylko wtedy, gdy backend go zna — „9 km/h undefined"
    // widzieliśmy już w starym kaflu
    const details = useMemo(() => {
        if (!weather) return null;
        const parts = [`Odczuwalnie ${Math.round(weather.feels_like)}°`];
        const dir = weather.wind_deg !== null && weather.wind_deg !== undefined
            ? ` ${WIND_DIRS[Math.round(weather.wind_deg / 45) % 8]}`
            : '';
        parts.push(`${weather.windKmh} km/h${dir}`);
        return parts.join(' · ');
    }, [weather]);

    const description = weather
        ? weather.description || look.label
        : loading ? 'Ładuję…' : 'brak danych';
    const { Icon } = look;

    // Opis z OpenWeather przychodzi małą literą („zachmurzenie umiarkowane”).
    // Wielka litera tylko na początku — CSS `capitalize` dawał „Zachmurzenie Umiarkowane”
    const sentence = description ? description.charAt(0).toUpperCase() + description.slice(1) : '';

    return (
        <Plate
            tag="Pogoda · Rybno"
            onClick={onClick}
            ariaLabel={
                weather
                    ? `Pogoda w gminie: ${Math.round(weather.temperature)} stopni, ${description}. Otwórz pełną prognozę`
                    : 'Otwórz pełną prognozę pogody'
            }
            value={
                <span className="flex items-center gap-2">
                    {weather ? `${Math.round(weather.temperature)}°` : '—'}
                    <Icon aria-hidden className="h-6 w-6 text-tv-muted" strokeWidth={2} />
                </span>
            }
            sub={
                <>
                    <span className="block font-semibold text-tv-paper">{sentence}</span>
                    {details && <span className="block">{details}</span>}
                    {details && airLabel && <span className="block">{airLabel.charAt(0).toUpperCase() + airLabel.slice(1)}</span>}
                    {staleAt && <span className="block font-semibold text-tv-yellow">pomiar z {staleAt}</span>}
                </>
            }
        />
    );
};

export default WeatherTodayCard;
