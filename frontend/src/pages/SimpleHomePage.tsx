import React, { useEffect, useMemo, useState } from 'react';
import { Calendar, Trash2, Bus } from 'lucide-react';
import { AppSection, BusStatusResponse, BusStop } from '../../types';
import { useAuth } from '../context/AuthContext';
import { useArticles } from '../hooks/useArticles';
import { useWeather } from '../hooks/useWeather';
import { useWasteSchedule } from '../hooks/useWasteSchedule';
import { useEvents } from '../hooks/useEvents';
import {
    dayLabel,
    endOf,
    isInWeekend,
    phaseOf,
    timeSuffix,
    upcomingFirst,
} from '../utils/eventTime';
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
import CouncilCard from '../../components/simple/CouncilCard';
import RoadStatusStrip from '../../components/simple/RoadStatusStrip';
import HealthTodayCard from '../../components/simple/HealthTodayCard';
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

    const { articles } = useArticles({ limit: 12, location: user?.location });
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

    /**
     * Czerwoną ramkę dostaje awaria, która dotyczy WSI CZYTELNIKA.
     *
     * 25.08.2026 mieszkaniec Żabin zobaczył na stronie głównej „UWAGA — DZIŚ:
     * 9:30–15:00 wyłączenie prądu w Rybnie" — cztery adresy przy ulicy
     * Wyzwolenia, sześć kilometrów od niego. Push ma bramkę miejsca od 24.08
     * (`push_subscriptions.location`), strona nie miała jej wcale.
     *
     * O dopasowaniu rozstrzyga backend (`alert_policy.concerns`), bo tam stoi
     * lista wsi i normalizacja nazw („Rybno R1" na koncie, „Rybno" u Energi).
     * Komunikat bez nazwy wsi — ostrzeżenie meteo dla powiatu — dotyczy
     * każdego, tak samo jak dla push.
     */
    const alertArticle = useMemo(
        () => articles?.find(a => a.isPinnedAlert && a.concernsLocation !== false) ?? null,
        [articles],
    );

    /**
     * Wiadomości bez WSZYSTKICH przypiętych alertów, nie tylko tego z karty.
     *
     * 25.08.2026 Energa zapowiedziała dwa różne wyłączenia w Rybnie na ten sam
     * dzień. Oba są przypięte i słusznie — dotyczą innych ulic — ale karta
     * alertu pokazuje jeden, a odfiltrowanie „tego jednego" wpuszczało drugi
     * na szczyt kafla „Ostatnio w gminie". Ekran mówił trzy razy to samo.
     */
    const newsArticles = useMemo(
        () => (articles ?? []).filter(a => !a.isPinnedAlert).slice(0, 3),
        [articles],
    );

    /**
     * „Dziś w gminie" — wydarzenie z godziną, a gdy dziś nic nie ma, mówimy to
     * wprost i kierujemy na najbliższe. „Zobacz kalendarz wydarzeń" brzmiało
     * jak nazwa przycisku, a nie jak odpowiedź na pytanie „co się dzieje?".
     *
     * Karta liczy się z zegarem, nie z kalendarzem: do 21.08.2026 porównywała
     * sam DZIEŃ, więc o 10:25 zapraszała na posiedzenie komisji zakończone
     * o 9:00. `phaseOf` rozstrzyga, co minęło, co trwa, a co dopiero będzie.
     */
    const todaySubtitle = useMemo(() => {
        if (!events?.length) return 'Sprawdź, co się dzieje w okolicy';
        const now = new Date();
        const ahead = upcomingFirst(events, now);
        const todayAhead = ahead.filter(e => {
            const phase = phaseOf(e, now);
            return phase === 'ongoing' || phase === 'today';
        });

        if (todayAhead.length) {
            const first = todayAhead[0];
            const more = todayAhead.length > 1 ? ` (i ${todayAhead.length - 1} więcej)` : '';
            if (phaseOf(first, now) === 'ongoing') {
                const until = endOf(first).toLocaleTimeString('pl-PL', { hour: 'numeric', minute: '2-digit' });
                return `teraz: ${first.title}, do ${until}${more}`;
            }
            return `${first.title}${timeSuffix(first)}${more}`;
        }

        const next = ahead[0];
        if (!next) return 'Dziś spokojnie — zajrzyj po nowe wydarzenia';
        // Rozróżniamy dwa różne dni: „nic nie planowano" znaczy co innego niż
        // „było, ale się skończyło" — a mieszkaniec o 20:00 pyta o to drugie
        const somethingHappenedToday = events.some(
            e => new Date(e.date).toDateString() === now.toDateString() && phaseOf(e, now) === 'past',
        );
        const opener = somethingHappenedToday ? 'Dziś już po wszystkim' : 'Dziś nic nie planowano';
        return `${opener} · najbliższe: ${next.title}, ${dayLabel(next)}`;
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
     * Weekend: piątek po południu – niedziela (od TERAZ, jeśli weekend trwa).
     * `null` znaczy „nic nie ma" i tak też brzmi na karcie — wcześniej pustka
     * dostawała zdanie „Kino, koncerty i atrakcje w okolicy", które wyglądało
     * jak zapowiedź, a było wypełniaczem.
     *
     * Zakres liczy `weekendRange`. Wcześniej piątek zaczynał się o północy,
     * więc w piątek rano karta powtarzała treść „Dziś w gminie" i pokazywała
     * poranne posiedzenie komisji zamiast niedzielnego wyścigu MTB.
     */
    const weekendSubtitle = useMemo<string | null>(() => {
        if (!events?.length) return null;
        const now = new Date();
        const weekendEvents = upcomingFirst(events, now).filter(e => isInWeekend(e, now));
        if (!weekendEvents.length) return null;
        const first = weekendEvents[0];
        const label = `${first.title}${timeSuffix(first)}`;
        return weekendEvents.length > 1
            ? `${label} i jeszcze ${weekendEvents.length - 1} więcej`
            : label;
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

                {/* Zdrowie i drogi jako stopka sekcji, nie kolejne karty w siatce:
                    oba przez większość dni mówią „bez zmian", więc nie zasługują
                    na własne pole — ale gdy coś się dzieje (lekarz dziś nie
                    przyjmuje, droga zamknięta), mają być widoczne od razu.
                    Zdrowie idzie pierwsze: dotyczy wizyty, którą trzeba odwołać */}
                <div className="mt-3 space-y-3">
                    <HealthTodayCard />
                    <RoadStatusStrip />
                </div>
            </section>

            {/* Rada Gminy — jedyna rubryka, w której serwis mówi o decyzjach,
                a nie o zdarzeniach. Kafel sam wybiera, czy zapowiada najbliższą
                sesję, czy pokazuje ostatni skrót; znika tylko, gdy nie ma ani
                jednego, ani drugiego */}
            <CouncilCard onClick={() => onNavigate('council')} />

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
            <NewsletterCta onRegister={() => onNavigate('register')} />

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
