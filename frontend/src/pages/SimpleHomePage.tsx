import React, { useEffect, useMemo, useState } from 'react';
import { Calendar, Trash2, Bus } from 'lucide-react';
import { AppSection, BusStatusResponse, BusStop } from '../../types';
import { useAuth } from '../context/AuthContext';
import { useArticles } from '../hooks/useArticles';
import { useWeather } from '../hooks/useWeather';
import { useWasteSchedule } from '../hooks/useWasteSchedule';
import { useEvents } from '../hooks/useEvents';
import HeroBand from '../../components/simple/HeroBand';
import BriefingCard from '../../components/simple/BriefingCard';
import AlertOfTheDay from '../../components/simple/AlertOfTheDay';
import AlertPushPrompt from '../../components/AlertPushPrompt';
import TodayCard from '../../components/simple/TodayCard';
import WeatherTodayCard from '../../components/simple/WeatherTodayCard';
import KadrCard from '../../components/simple/KadrCard';
import NewsMini from '../../components/simple/NewsMini';
import AdBoard from '../../components/simple/AdBoard';
import ReportsMini from '../../components/simple/ReportsMini';
import NewsletterCta from '../../components/simple/NewsletterCta';
import CinemaCard from '../../components/simple/CinemaCard';
import RoadStatusStrip from '../../components/simple/RoadStatusStrip';
import AskBar from '../../components/simple/AskBar';

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api';

/**
 * Strona główna — jedyna wersja serwisu, nie „tryb prosty obok pełnego".
 *
 * Kolejność odpowiada temu, jak mieszkaniec czyta stronę: najpierw co się
 * dzieje (briefing), potem co go dotknie dziś (alert), potem cztery rzeczy
 * do sprawdzenia, na końcu weekend, wiadomości i pytanie do asystenta.
 *
 * Każda karta prowadzi GŁĘBIEJ w swój temat (pełna prognoza, cały harmonogram,
 * rozkład z mapą), nigdy „w bok" do innego układu tych samych danych —
 * dwie równoległe wersje strony to dwa razy więcej utrzymania i zero zysku.
 */

// CAQI po ludzku — liczby i jednostki dopiero na stronie szczegółowej
const AIR_WORDS: Record<string, string> = {
    VERY_LOW: 'powietrze bardzo czyste',
    LOW: 'powietrze czyste',
    MEDIUM: 'powietrze przeciętne',
    HIGH: 'powietrze złe',
    VERY_HIGH: 'powietrze bardzo złe',
    EXTREME: 'powietrze fatalne',
};

const WEEKDAYS = ['niedziela', 'poniedziałek', 'wtorek', 'środa', 'czwartek', 'piątek', 'sobota'];

interface SimpleHomePageProps {
    onNavigate: (section: AppSection) => void;
    onQuerySubmit: (query: string) => void;
}

const SimpleHomePage: React.FC<SimpleHomePageProps> = ({ onNavigate, onQuerySubmit }) => {
    const { user } = useAuth();
    const town = user?.location || 'Rybno';

    const { articles } = useArticles({ limit: 12 });
    const { weather } = useWeather('Rybno');
    const wasteEvents = useWasteSchedule(town);
    const { events } = useEvents(30);
    const [airLevel, setAirLevel] = useState<string | null>(null);
    const [bus, setBus] = useState<BusStatusResponse | null>(null);
    const [busStops, setBusStops] = useState<BusStop[]>([]);

    useEffect(() => {
        fetch(`${API_URL}/weather/air-quality/current`)
            .then(res => (res.ok ? res.json() : null))
            .then(data => setAirLevel(data?.caqi_level ?? null))
            .catch(() => setAirLevel(null));
    }, []);

    // Kurs w trasie zmienia się co chwilę — bez odświeżania karta kłamałaby
    // po kilkunastu minutach otwartej zakładki
    useEffect(() => {
        const load = () => {
            fetch(`${API_URL}/bus/status`)
                .then(res => (res.ok ? res.json() : null))
                .then(setBus)
                .catch(() => setBus(null));
        };
        load();
        const interval = setInterval(load, 60_000);
        return () => clearInterval(interval);
    }, []);

    // Nazwy przystanków są stałe — pobieramy raz, żeby zamienić id na „Tuczki"
    useEffect(() => {
        fetch(`${API_URL}/bus/timetable`)
            .then(res => (res.ok ? res.json() : null))
            .then(data => setBusStops(data?.stops ?? []))
            .catch(() => setBusStops([]));
    }, []);

    const alertArticle = useMemo(
        () => articles?.find(a => a.isPinnedAlert) ?? null,
        [articles],
    );

    const newsArticles = useMemo(
        () => (articles ?? []).filter(a => a.id !== alertArticle?.id).slice(0, 3),
        [articles, alertArticle],
    );

    /**
     * „Dziś w gminie" — wydarzenie z godziną, a gdy dziś nic nie ma, mówimy to
     * wprost i kierujemy na najbliższe. „Zobacz kalendarz wydarzeń" brzmiało
     * jak nazwa przycisku, a nie jak odpowiedź na pytanie „co się dzieje?".
     */
    const todaySubtitle = useMemo(() => {
        if (!events?.length) return 'Sprawdź, co się dzieje w okolicy';
        const now = new Date();
        const today = now.toDateString();
        const todayEvents = events.filter(e => new Date(e.date).toDateString() === today);

        if (todayEvents.length) {
            const first = todayEvents[0];
            // Wydarzenia całodniowe mają w bazie 00:00 — godzina „0:00" niczego
            // nie mówi, więc przy północy pomijamy ją zamiast wypisywać
            const start = new Date(first.date);
            const time = start.getHours() === 0 && start.getMinutes() === 0
                ? ''
                : `, ${start.toLocaleTimeString('pl-PL', { hour: 'numeric', minute: '2-digit' })}`;
            const more = todayEvents.length > 1 ? ` (i ${todayEvents.length - 1} więcej)` : '';
            return `${first.title}${time}${more}`;
        }

        const next = events
            .filter(e => new Date(e.date) > now)
            .sort((a, b) => +new Date(a.date) - +new Date(b.date))[0];
        if (!next) return 'Dziś spokojnie — zajrzyj po nowe wydarzenia';
        const day = new Date(next.date).toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'numeric' });
        return `Dziś nic nie planowano · najbliższe: ${next.title}, ${day}`;
    }, [events]);

    const wasteSubtitle = useMemo(() => {
        const next = wasteEvents[0];
        if (!next) return 'Sprawdź termin dla swojej miejscowości';
        const [day, month] = next.originalDateString.split('.');
        // Dzień tygodnia liczymy z `daysRemaining`, nie z „dzień.miesiąc + bieżący
        // rok": w grudniu styczniowy odbiór wypadał wtedy o rok wstecz i karta
        // podawała zły dzień tygodnia przy poprawnej dacie
        const date = new Date();
        date.setHours(0, 0, 0, 0);
        date.setDate(date.getDate() + next.daysRemaining);
        const when =
            next.daysRemaining === 0 ? 'dziś'
            : next.daysRemaining === 1 ? 'jutro'
            : `${WEEKDAYS[date.getDay()]} ${day}.${month}`;
        return `${next.type} — ${when}`;
    }, [wasteEvents]);

    /**
     * Autobus mówi jedno zdanie: jedzie / za ile odjeżdża / kiedy następny.
     * Kierunek do Działdowa jest domyślny — to nim jedzie się do pracy,
     * szkoły i lekarza; kurs powrotny pokazujemy, gdy akurat jest w trasie.
     */
    const busSubtitle = useMemo(() => {
        if (!bus) return 'Rozkład i pozycja kursu na żywo';
        const out = bus.directions.RYBNO_DZIALDOWO;
        const back = bus.directions.DZIALDOWO_RYBNO;
        const stopName = (id?: string) =>
            busStops.find(stop => stop.stop_id === id)?.name.replace(/\s*\(.*\)/, '');

        // Kurs w trasie: gdzie jest teraz. Sama informacja „jedzie" nie mówi,
        // czy zdążę na przystanek — nazwa mijanego przystanku mówi
        for (const [dir, label] of [[out, 'do Działdowa'], [back, 'do Rybna']] as const) {
            if (dir.is_active && dir.active_bus) {
                const where = stopName(dir.active_bus.next_stop_id);
                return where
                    ? `Jedzie ${label} — zbliża się do: ${where}`
                    : `Jedzie ${label} — kurs w trasie`;
            }
        }

        if (out.next_departure) {
            const mins = out.next_departure.in_minutes;
            return mins <= 60
                ? `Odjazd do Działdowa za ${mins} min (${out.next_departure.time})`
                : `Najbliższy odjazd do Działdowa o ${out.next_departure.time}`;
        }
        if (out.next_service) {
            return `Dziś już nie kursuje · następny ${out.next_service.day_label} o ${out.next_service.time}`;
        }
        return 'Dziś już nie kursuje';
    }, [bus, busStops]);

    /**
     * Weekend: najbliższy piątek–niedziela (dziś, jeśli weekend trwa).
     * `null` znaczy „nic nie ma" i tak też brzmi na karcie — wcześniej pustka
     * dostawała zdanie „Kino, koncerty i atrakcje w okolicy", które wyglądało
     * jak zapowiedź, a było wypełniaczem
     */
    const weekendSubtitle = useMemo<string | null>(() => {
        if (!events?.length) return null;
        const now = new Date();
        const friday = new Date(now);
        friday.setHours(0, 0, 0, 0);
        friday.setDate(friday.getDate() + ((5 - friday.getDay() + 7) % 7));
        if (now.getDay() === 6 || now.getDay() === 0) friday.setDate(friday.getDate() - 7);
        const monday = new Date(friday);
        monday.setDate(friday.getDate() + 3);
        const weekendEvents = events.filter(e => {
            const d = new Date(e.date);
            return d >= friday && d < monday;
        });
        if (!weekendEvents.length) return null;
        const first = weekendEvents[0].title;
        return weekendEvents.length > 1
            ? `${first} i jeszcze ${weekendEvents.length - 1} więcej`
            : first;
    }, [events]);

    const ask = (query: string) => {
        onQuerySubmit(query);
        onNavigate('assistant');
    };

    return (
        <div className="mx-auto max-w-5xl px-4 py-6 lg:py-10 space-y-6 lg:space-y-8">
            <HeroBand onOpenCalendar={() => onNavigate('events')} />

            <BriefingCard onShowAll={() => onNavigate('news')} />

            {/*
              Push to jedyna rzecz, którą ten serwis może dać mieszkańcowi, gdy
              nie patrzy na stronę — i jedyny mierzalny cel kampanii. Przy awarii
              prosi o zgodę AlertOfTheDay (kontekst mówi sam za siebie), w każdy
              inny dzień spokojny baner. Nigdy oba naraz.
            */}
            {alertArticle
                ? <AlertOfTheDay article={alertArticle} />
                : <AlertPushPrompt tone="calm" />}

            <section aria-label="Na dziś">
                <h2 className="mb-3 text-xs font-bold uppercase tracking-widest text-neutral-500">
                    Na dziś
                </h2>
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-4 lg:gap-4">
                    {/* Pogoda ma własny kafel: jako jedyna z czterech odpowiada
                        liczbą, nie zdaniem, więc temperatura musi być widoczna
                        z odległości ręki. Powierzchnia bez zmian — jedno pole */}
                    <WeatherTodayCard
                        weather={weather}
                        airLabel={airLevel ? AIR_WORDS[airLevel] ?? null : null}
                        onClick={() => onNavigate('weather')}
                    />
                    <TodayCard
                        icon={Calendar}
                        iconClass="text-amber-400"
                        iconBgClass="bg-amber-500/10"
                        title="Dziś w gminie"
                        subtitle={todaySubtitle}
                        onClick={() => onNavigate('events')}
                    />
                    <TodayCard
                        icon={Trash2}
                        iconClass="text-emerald-400"
                        iconBgClass="bg-emerald-500/10"
                        title="Wywóz śmieci"
                        subtitle={wasteSubtitle}
                        onClick={() => onNavigate('waste')}
                    />
                    <TodayCard
                        icon={Bus}
                        iconClass="text-violet-400"
                        iconBgClass="bg-violet-500/10"
                        title="Autobus do Działdowa"
                        subtitle={busSubtitle}
                        onClick={() => onNavigate('bus')}
                    />
                </div>

                {/* Stan dróg jako stopka sekcji, nie piąta karta: to jedno zdanie
                    przez większość dni w roku, więc nie zasługuje na własne pole
                    w siatce — ale gdy coś się dzieje, ma być widoczne od razu */}
                <div className="mt-3">
                    <RoadStatusStrip />
                </div>
            </section>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.35fr_1fr] lg:gap-5">
                <KadrCard
                    weekendSubtitle={weekendSubtitle ?? ''}
                    hasWeekendEvents={weekendSubtitle !== null}
                    onOpenEvents={() => onNavigate('events')}
                />
                <NewsMini articles={newsArticles} onShowAll={() => onNavigate('news')} />
            </div>

            {/* Wypoczynek — na razie samo kino. Kafel sam się chowa, gdy nie ma
                seansu przed nami, więc sekcja nie zostaje z pustym miejscem */}
            <section aria-label="Wypoczynek">
                <h2 className="mb-3 text-xs font-bold uppercase tracking-widest text-neutral-500">
                    Wypoczynek
                </h2>
                <CinemaCard onClick={() => onNavigate('cinema')} />
            </section>

            {/*
              Prośba o adres e-mail dopiero POD treścią: mieszkaniec zdążył
              przeczytać briefing i wiadomości, więc „to samo co tydzień na maila"
              jest propozycją, a nie bramką przy wejściu.
            */}
            <NewsletterCta town={town} onOpenPrivacy={() => onNavigate('privacy')} />

            {/*
              Zgłoszenia 24 PRZED reklamą: to jedyne miejsce, w którym mieszkaniec
              coś od siebie wnosi, więc stoi wyżej niż to, za co ktoś zapłacił
            */}
            <ReportsMini onOpenReports={() => onNavigate('reports')} />

            {/*
              Reklama stoi PONIŻEJ treści i jest nazwana po imieniu. Komunikaty
              sołtysów dostaną osobną sekcję i nigdy nie zmieszają się z tą
            */}
            <AdBoard onOpenBusinesses={() => onNavigate('business')} />

            <AskBar onAsk={ask} />
        </div>
    );
};

export default SimpleHomePage;
