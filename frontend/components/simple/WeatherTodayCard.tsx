import React, { useMemo } from 'react';
import {
    ChevronRight, Cloud, CloudDrizzle, CloudFog, CloudLightning,
    CloudRain, CloudSnow, CloudSun, Moon, Sun, LucideIcon,
} from 'lucide-react';
import type { WeatherFull } from '../../src/hooks/useWeather';

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
 * bez zasięgu, a dane pogodowe idą z pamięci podręcznej. Orb jest gradientem
 * CSS, ikona pochodzi z tego samego zestawu (lucide), co reszta serwisu.
 */

interface ConditionLook {
    Icon: LucideIcon;
    /** Kolor przewodni — orb, poświata i nazwa zjawiska */
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

const WIND_DIRS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];

interface WeatherTodayCardProps {
    weather: WeatherFull | null;
    /** Jakość powietrza słowem — liczby i jednostki dopiero na stronie pogody */
    airLabel: string | null;
    onClick: () => void;
}

const WeatherTodayCard: React.FC<WeatherTodayCardProps> = ({ weather, airLabel, onClick }) => {
    const look = useMemo(
        () => conditionLook(weather?.main, weather?.icon),
        [weather?.main, weather?.icon],
    );

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

    const description = weather?.description ?? look.label;
    const { Icon } = look;

    return (
        <button
            onClick={onClick}
            aria-label={
                weather
                    ? `Pogoda w gminie: ${Math.round(weather.temperature)} stopni, ${description}. Otwórz pełną prognozę`
                    : 'Otwórz pełną prognozę pogody'
            }
            className="group relative flex min-h-[72px] w-full items-center gap-4 overflow-hidden rounded-2xl border border-white/10 bg-[#0d1117] p-4 text-left transition-colors hover:border-white/20 hover:bg-white/[0.04] lg:block lg:min-h-0 lg:p-5"
        >
            {/* Poświata w kolorze zjawiska — jedyna „grafika" w tym kaflu i jedyne
                miejsce, w którym pogoda zmienia wygląd karty, a nie tylko tekst.
                Oddech zamiast migotania: 3 s, i nic przy `prefers-reduced-motion` */}
            <span
                aria-hidden
                className="pointer-events-none absolute -right-8 -top-10 h-36 w-36 rounded-full animate-pulse-slow motion-reduce:animate-none"
                style={{ background: look.glow, filter: 'blur(46px)', opacity: 0.22 }}
            />

            {/* Orb: kula światła w kolorze pogody z ikoną w środku. Na telefonie
                stoi tam, gdzie u sąsiadów ikona kategorii — rytm sekcji zostaje.
                Na desktopie odpływa w prawo, a tekst układa się obok, tak jak
                na kaflu z panelu, z którego ten układ pochodzi */}
            <span className="relative flex h-12 w-12 shrink-0 items-center justify-center lg:float-right lg:ml-2 lg:h-16 lg:w-16">
                {/* Kula, nie plama: pełne koło z rozjaśnieniem w lewym górnym
                    rogu i poświatą na zewnątrz. Sam gradient promienisty
                    rozmywał krawędź i wyglądał jak smuga */}
                <span
                    aria-hidden
                    className="absolute inset-0 rounded-full"
                    style={{
                        background: `radial-gradient(circle at 32% 28%, #ffffffcc, ${look.glow} 58%)`,
                        boxShadow: `0 0 18px 2px ${look.glow}66`,
                    }}
                />
                <Icon
                    aria-hidden
                    className="relative h-6 w-6 text-[#05080f]/80 lg:h-8 lg:w-8"
                    strokeWidth={2.25}
                />
            </span>

            <span className="relative block min-w-0 flex-1">
                {/* Na telefonie temperatura i zjawisko dzielą wiersz, na desktopie
                    stoją jedno pod drugim — ta sama treść, inna wysokość kafla */}
                <span className="flex flex-wrap items-baseline gap-x-2 lg:block">
                    <span className="text-2xl font-black leading-none tracking-tight text-white lg:block lg:text-4xl">
                        {weather ? `${Math.round(weather.temperature)}°` : '—'}
                    </span>
                    <span
                        className="text-sm font-semibold capitalize lg:mt-1.5 lg:block"
                        style={{ color: look.glow }}
                    >
                        {description}
                    </span>
                </span>

                <span className="mt-1 block text-[13px] leading-snug text-neutral-400 lg:text-xs">
                    {details ?? 'Prognoza i jakość powietrza dla gminy'}
                    {details && airLabel && <span className="text-neutral-500"> · {airLabel}</span>}
                </span>
            </span>

            <ChevronRight size={18} className="relative shrink-0 text-neutral-600 lg:hidden" aria-hidden />
        </button>
    );
};

export default WeatherTodayCard;
