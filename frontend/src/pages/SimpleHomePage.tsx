import React, { useEffect, useMemo, useState } from 'react';
import { AppSection, BusStatusResponse, BusStop } from '../../types';
import { useAuth } from '../context/AuthContext';
import { useArticles } from '../hooks/useArticles';
import { useWeather } from '../hooks/useWeather';
import { useWasteSchedule } from '../hooks/useWasteSchedule';
import { resolveWasteTown } from '../utils/wasteTown';
import { useEvents } from '../hooks/useEvents';
import { useMyVillage } from '../hooks/useMyVillage';
import { useOutageOutlook } from '../hooks/useOutageOutlook';
import { useHealthToday } from '../hooks/useHealthToday';
import {
    endOf,
    isInWeekend,
    phaseOf,
    timeSuffix,
    upcomingFirst,
} from '../utils/eventTime';
import BriefingCard from '../../components/simple/BriefingCard';
import Masthead from '../../components/simple/Masthead';
import StatusBelt from '../../components/simple/StatusBelt';
import VillagePushCta from '../../components/simple/VillagePushCta';
import { Plate, dayWord } from '../../components/simple/tv';
import WeekendCard from '../../components/simple/WeekendCard';
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
 * Kolejność odpowiada temu, jak mieszkaniec czyta stronę (odświeżenie
 * 11.10.2026, kierunek „Pasek informacyjny”): najpierw JEGO WIEŚ — stan prądu
 * i wody na belce i prośba o powiadomienia — potem cztery plakietki „Na dziś”,
 * dopiero niżej briefing, wiadomości, rada, weekend i pytanie do asystenta.
 * Wcześniej pierwszy ekran zajmowało hasło, a odpowiedzi stały 3–4 ekrany niżej.
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
    // Wieś czytelnika — jedno pytanie, z którego korzystają belka, wywóz i push
    const { village, accountVillage, isPreview, places, setVillage } = useMyVillage();
    const [pickerRequest, setPickerRequest] = useState(0);
    const openPicker = () => {
        setPickerRequest(n => n + 1);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };
    // Pozycja harmonogramu albo `null` — „Rybno” bez rejonu to niewiadoma, nie R1 (F-039).
    // Konto z rejonem („Rybno R2”) wie więcej niż sama nazwa wsi, więc ma pierwszeństwo —
    // ale tylko dla wsi z konta. Podgląd cudzej wsi liczy wywóz dla niej
    const town = resolveWasteTown(isPreview ? village : (user?.location ?? village));
    const outlook = useOutageOutlook(village);
    // Jeden odczyt grafiku ośrodka dla paska „Na żywo” i kafla zdrowia
    const { data: health } = useHealthToday();
    const [healthOpen, setHealthOpen] = useState(false);
    const openHealth = () => {
        setHealthOpen(true);
        requestAnimationFrame(() =>
            document.getElementById('osrodek-zdrowia')?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
        );
    };

    const { articles, loading: articlesLoading } = useArticles({ limit: 20, location: village ?? undefined });
    const { weather, loading: weatherLoading } = useWeather('Rybno');
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
    // Awarie (prąd, woda, pożar, wypadek) mówi belka z `/alerts/outlook`.
    // Z przypiętych wpisów feedu zostaje tylko to, czego tam nie ma: obowiązujące
    // ostrzeżenie meteo (feed przypina je obok awarii — `is_pinned_alert`)
    const weatherWarning = useMemo(
        () => articles?.find(a =>
            a.isPinnedAlert
            && a.concernsLocation !== false
            && !(a.category || '').toLowerCase().includes('awari'),
        ) ?? null,
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
    // Kafel nazywa się „Ostatnio w gminie”, więc bierze WYŁĄCZNIE wpisy z gminy.
    // Do 11.10.2026 brał trzy pierwsze z feedu — 10.10 dwa z nich były z regionu
    // (audyt F-011). Lista z 20 wpisów, bo filtr zjada część czołówki; gdy z gminy
    // nie ma nic, kafel mówi to wprost zamiast podsuwać Działdowo jako „gminę”.
    const newsArticles = useMemo(
        () => (articles ?? []).filter(a => !a.isPinnedAlert && a.scope === 'gmina').slice(0, 3),
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
    const today = useMemo<{ value: string; sub: string }>(() => {
        if (!events?.length) return { value: 'Kalendarz', sub: 'Sprawdź, co się dzieje w okolicy' };
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
                return { value: 'Trwa teraz', sub: `${first.title}, do ${until}${more}` };
            }
            const at = new Date(first.date);
            const hasHour = at.getHours() !== 0 || at.getMinutes() !== 0;
            return {
                value: hasHour ? `dziś ${at.toLocaleTimeString('pl-PL', { hour: 'numeric', minute: '2-digit' })}` : 'dziś',
                sub: `${first.title}${more}`,
            };
        }

        const next = ahead[0];
        if (!next) return { value: 'Spokojnie', sub: 'W kalendarzu nic przed nami' };
        // „nic nie planowano” znaczy co innego niż „było, ale się skończyło”
        const somethingHappenedToday = events.some(
            e => new Date(e.date).toDateString() === now.toDateString() && phaseOf(e, now) === 'past',
        );
        return {
            value: dayWord(new Date(next.date)),
            sub: `${somethingHappenedToday ? 'Dziś już po wszystkim. ' : ''}Najbliżej: ${next.title}${timeSuffix(next)}`,
        };
    }, [events]);

    const waste = useMemo<{ value: string; sub: string; needsVillage: boolean }>(() => {
        if (!town) {
            // „Rybno” ma dwa rejony różniące się o tydzień — zgadywanie podałoby
            // połowie mieszkańców cudzy termin (F-039). Pytamy wprost
            if (village) return { value: `${village}: który rejon?`, sub: 'Wybierz rejon w harmonogramie — różnią się o tydzień', needsVillage: false };
            return { value: 'Wybierz wieś', sub: 'Pokażemy najbliższy termin wywozu', needsVillage: true };
        }
        const next = wasteEvents[0];
        if (!next) return { value: 'Brak terminu', sub: `${town}: nie ma zaplanowanych odbiorów`, needsVillage: false };
        const [day, month] = next.originalDateString.split('.');
        // Dzień tygodnia z `daysRemaining`, nie z „dzień.miesiąc + bieżący rok”:
        // w grudniu styczniowy odbiór wypadał wtedy o rok wstecz
        const date = new Date();
        date.setHours(0, 0, 0, 0);
        date.setDate(date.getDate() + next.daysRemaining);
        const when =
            next.daysRemaining === 0 ? 'dziś'
            : next.daysRemaining === 1 ? 'jutro'
            : `${WEEKDAYS[date.getDay()]} ${day}.${month}`;
        // Nazwa miejscowości przy terminie: czytelnik widzi, CZYJ to termin
        return { value: when, sub: `${next.type} · ${town}`, needsVillage: false };
    }, [wasteEvents, town, village]);

    /**
     * Autobus: liczba (godzina) jako odpowiedź, zdanie jako dopowiedzenie.
     * Kierunek do Działdowa jest domyślny — to nim jedzie się do pracy,
     * szkoły i lekarza; kurs powrotny pokazujemy, gdy akurat jest w trasie.
     */
    const busInfo = useMemo<{ value: string; sub: string }>(() => {
        if (!bus) return { value: 'Rozkład', sub: 'Kursy do Działdowa i z powrotem' };
        const out = bus.directions.RYBNO_DZIALDOWO;
        const back = bus.directions.DZIALDOWO_RYBNO;
        const stopName = (id?: string) =>
            busStops.find(stop => stop.stop_id === id)?.name.replace(/\s*\(.*\)/, '');

        // Kurs w trasie: gdzie jest teraz — nazwa mijanego przystanku mówi,
        // czy zdążę, sama informacja „jedzie” nie mówi nic
        for (const [dir, label] of [[out, 'do Działdowa'], [back, 'do Rybna']] as const) {
            if (dir.is_active && dir.active_bus) {
                const where = stopName(dir.active_bus.next_stop_id);
                return { value: 'W trasie', sub: where ? `Wg rozkładu jedzie ${label} — zbliża się do: ${where}` : `Wg rozkładu jedzie ${label}` };
            }
        }

        if (out.next_departure) {
            const mins = out.next_departure.in_minutes;
            return {
                value: out.next_departure.time,
                sub: mins <= 60 ? `Do Działdowa — odjazd za ${mins} min` : 'Do Działdowa — najbliższy odjazd dziś',
            };
        }
        if (out.next_service) {
            return { value: `${out.next_service.day_label} ${out.next_service.time}`, sub: 'Do Działdowa — dziś już nie kursuje' };
        }
        return { value: 'Nie kursuje', sub: 'Dziś już nie ma kursów' };
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
        <div className="space-y-6 pb-10 lg:space-y-8">
            <Masthead
                village={village}
                accountVillage={accountVillage}
                isPreview={isPreview}
                onOpenProfile={() => onNavigate('profile')}
                places={places}
                onSelectVillage={setVillage}
                pickerRequest={pickerRequest}
            />

            {/* Pierwszy ekran = odpowiedzi. Belka mówi o prądzie i wodzie w Twojej
                wsi, prośba o powiadomienia stoi tuż pod nią — w jedynym miejscu,
                w którym jej wartość jest oczywista (pomiar: 73 wyświetlenia
                starego banera na piątym miejscu, 0 kliknięć) */}
            <div className="space-y-3">
                <StatusBelt
                    outlook={outlook}
                    village={village}
                    health={health}
                    articles={articles ?? []}
                    weatherWarning={weatherWarning}
                    onOpenDetails={() => onNavigate('news')}
                    onOpenHealth={openHealth}
                    onOpenNews={() => onNavigate('news')}
                />
                <VillagePushCta village={village} onPickVillage={openPicker} />
            </div>

            <section aria-labelledby="na-dzis">
                <h2 id="na-dzis" className="sr-only">Na dziś</h2>
                <div className="grid grid-cols-2 gap-x-3 gap-y-4 lg:grid-cols-4 lg:gap-x-4">
                    <Plate
                        tag="Wywóz"
                        value={waste.value}
                        sub={waste.sub}
                        onClick={waste.needsVillage ? openPicker : () => onNavigate('waste')}
                    />
                    <Plate
                        tag="Autobus"
                        value={busInfo.value}
                        sub={busInfo.sub}
                        onClick={() => onNavigate('bus')}
                    />
                    {/* Pogoda odpowiada liczbą — temperatura jest tu tym, czym
                        u sąsiadów termin albo godzina */}
                    <WeatherTodayCard
                        weather={weather}
                        loading={weatherLoading}
                        airLabel={airLevel ? AIR_WORDS[airLevel] ?? null : null}
                        onClick={() => onNavigate('weather')}
                    />
                    <Plate
                        tag="Wydarzenia"
                        value={today.value}
                        sub={today.sub}
                        onClick={() => onNavigate('events')}
                    />
                </div>

                {/* Zdrowie i drogi jako pasy pod plakietkami: przez większość dni
                    mówią „bez zmian”, więc nie dostają własnego pola — ale zmiana
                    (lekarz nie przyjmuje, droga zamknięta) zapala je na żółto */}
                <div className="mt-4 grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
                    <HealthTodayCard data={health} open={healthOpen} onToggle={() => setHealthOpen(o => !o)} />
                    <RoadStatusStrip />
                </div>
            </section>

            <BriefingCard onShowAll={() => onNavigate('news')} />

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.3fr_1fr] lg:gap-6">
                <NewsMini
                    articles={newsArticles}
                    loading={articlesLoading && !articles}
                    onShowAll={() => onNavigate('news')}
                />
                {/* Rada Gminy — jedyna rubryka o decyzjach, nie o zdarzeniach.
                    Sama wybiera: zapowiedź najbliższej sesji albo ostatni skrót */}
                <CouncilCard onClick={() => onNavigate('council')} />
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.3fr_1fr] lg:items-start lg:gap-6">
                <KadrCard />
                {/* Wolny czas: kino (chowa się, gdy nie ma seansu przed nami) i weekend */}
                <div className="flex flex-col gap-6">
                    <CinemaCard onClick={() => onNavigate('cinema')} />
                    <WeekendCard subtitle={weekendSubtitle} onOpenEvents={() => onNavigate('events')} />
                </div>
            </div>

            {/* Konto to DRUGI krok, po wsi i powiadomieniach — propozycja
                pod treścią, nie bramka przy wejściu */}
            <NewsletterCta onRegister={() => onNavigate('register')} />

            {/* Zgłoszenia 24 PRZED reklamą: miejsce, w którym mieszkaniec
                coś wnosi, stoi wyżej niż to, za co ktoś zapłacił */}
            <ReportsMini onOpenReports={() => onNavigate('reports')} />

            <AdBoard onOpenBusinesses={() => onNavigate('business')} />

            <section aria-labelledby="zapytaj">
                <h2 id="zapytaj" className="sr-only">Zapytaj asystenta</h2>
                <AskBar onAsk={ask} />
            </section>
        </div>
    );
};

export default SimpleHomePage;
