import React, { useEffect, useMemo, useState } from 'react';
import { Construction, Route, CircleHelp } from 'lucide-react';
import { clockLabel, parseUtc } from '../../src/utils/articleTime';

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000/api';

interface Road {
    id: string;
    name: string;
    status: string;
    travelTime: string;
    description: string;
    delayMinutes: number;
}

/**
 * Pasek stanu dróg — jedna linia pod kartami „Na dziś".
 *
 * Zasada: **przy spokoju nie wymieniamy miast**. „Rybno–Działdowo płynnie,
 * Rybno–Lubawa płynnie, Rybno–Iława płynnie" to trzy zdania, które nic nie
 * wnoszą — mieszkaniec chce wiedzieć tylko tyle, czy dziś coś go zaskoczy.
 * Nazwa trasy pada dopiero wtedy, gdy naprawdę coś się na niej dzieje;
 * wtedy jest całą treścią komunikatu, bo „utrudnienie gdzieś w okolicy"
 * nie pozwala nikomu podjąć decyzji.
 *
 * ⚠️ Trasa do Olsztyna NIE liczy się do stanu paska. Gemini raportuje na niej
 * utrudnienie od ubiegłego roku (zamknięty wjazd S51 od Olsztynka, „i będzie
 * tak w 2026 roku"). To stan wieloletni, nie zdarzenie — gdyby wchodził do
 * stanu, pasek świeciłby bursztynem przez cały rok i przestałby cokolwiek
 * znaczyć. Zostaje w danych i na stronie ruchu, ale nie budzi paska.
 * Kryterium jest **zasięg**, nie treść opisu: pasek mówi o drogach, którymi
 * jedzie się do pracy, szkoły i lekarza — czyli w granicach powiatu.
 */
const LOCAL_ROUTES = /dzia[lł]dow|lubaw|i[lł]aw/i;

/** Utrudnienie liczy się, gdy Gemini nazwał je wprost albo doliczył opóźnienie */
const isDisrupted = (road: Road) =>
    road.delayMinutes > 0 || !/p[lł]ynnie/i.test(road.status);

const RoadStatusStrip: React.FC = () => {
    const [roads, setRoads] = useState<Road[] | null>(null);
    // Odczyt nieaktualny = brak wiedzy, nie „przejezdne”. 9–10.10.2026 pasek
    // przez 16 h pokazywał zielone „bez utrudnień” z odczytu, który wygasł
    // (audyt F-018): backend oddawał `is_expired`, front go nie czytał.
    const [stale, setStale] = useState(false);
    const [readAt, setReadAt] = useState<Date | null>(null);

    useEffect(() => {
        let cancelled = false;
        fetch(`${API_URL}/traffic`)
            .then(res => (res.ok ? res.json() : null))
            .then(data => {
                if (cancelled) return;
                setRoads(data?.roads ?? []);
                setStale(Boolean(data?.is_expired || data?.is_fallback));
                setReadAt(parseUtc(data?.fetched_at));
            })
            .catch(() => { if (!cancelled) setRoads([]); });
        return () => { cancelled = true; };
    }, []);

    const readTime = readAt ? clockLabel(readAt) : null;

    const trouble = useMemo(
        () => (roads ?? []).filter(r => LOCAL_ROUTES.test(r.name) && isDisrupted(r)),
        [roads],
    );

    // Zanim dane dojdą, pasek nie istnieje — „sprawdzam drogi…" migające
    // przy każdym wejściu jest gorsze niż pasek pojawiający się o sekundę później
    if (!roads?.length) return null;

    /* Ikona w kaflu, tak jak w kartach „Na dziś" — sama ikona 16 px na tle
       paska ginęła na desktopie i była praktycznie niewidoczna na telefonie.
       Kolorowe tło daje jej powierzchnię i od razu niesie stan: zielony/bursztyn */
    if (stale && !trouble.length) {
        return (
            <p className="flex items-center gap-3 bg-tv-panel px-4 py-3">
                <CircleHelp size={20} className="shrink-0 text-tv-muted" aria-hidden />
                <span className="text-[15px] leading-snug text-tv-paper">
                    Drogi: brak aktualnego odczytu
                    {readTime && <span className="text-tv-muted"> — ostatni z {readTime}</span>}
                </span>
            </p>
        );
    }

    if (!trouble.length) {
        return (
            <p className="flex items-center gap-3 bg-tv-panel px-4 py-3">
                <Route size={20} className="shrink-0 text-tv-green" aria-hidden />
                <span className="text-[15px] leading-snug text-tv-paper">
                    Drogi w okolicy <span className="font-bold text-white">przejezdne</span>
                    <span className="text-tv-muted"> — bez zgłoszonych utrudnień</span>
                </span>
            </p>
        );
    }

    return (
        <div className="space-y-2 bg-tv-yellow px-4 py-3 text-tv-ink">
            {trouble.map(road => (
                <p key={road.id} className="flex items-start gap-3">
                    <Construction size={20} className="mt-0.5 shrink-0" aria-hidden />
                    <span className="min-w-0 flex-1">
                        {/* Tu nazwa trasy JEST komunikatem — bez niej kierowca
                            nie wie, czy zmienia plan, czy nie */}
                        <span className="text-[15px] font-extrabold leading-snug">
                            {road.name.replace(/^Rybno[-–]/, 'Trasa do ')}
                        </span>
                        {road.delayMinutes > 0 && (
                            <span className="text-[15px] font-bold"> · +{road.delayMinutes} min</span>
                        )}
                        <span className="mt-0.5 block text-[15px] leading-snug">{road.description}</span>
                    </span>
                </p>
            ))}
            {stale && (
                <p className="pl-8 text-[15px] font-semibold">
                    Odczyt{readTime ? ` z ${readTime}` : ''} — może być już nieaktualny
                </p>
            )}
        </div>
    );
};

export default RoadStatusStrip;
