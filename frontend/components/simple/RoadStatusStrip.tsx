import React, { useEffect, useMemo, useState } from 'react';
import { Construction, Route } from 'lucide-react';

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

    useEffect(() => {
        let cancelled = false;
        fetch(`${API_URL}/traffic`)
            .then(res => (res.ok ? res.json() : null))
            .then(data => { if (!cancelled) setRoads(data?.roads ?? []); })
            .catch(() => { if (!cancelled) setRoads([]); });
        return () => { cancelled = true; };
    }, []);

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
    if (!trouble.length) {
        return (
            <p className="flex items-center gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.07] px-4 py-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500/15">
                    <Route size={20} className="text-emerald-400" aria-hidden />
                </span>
                <span className="text-[15px] leading-snug text-neutral-200">
                    Drogi w okolicy <span className="font-bold text-emerald-300">przejezdne</span>
                    <span className="text-neutral-400"> — bez zgłoszonych utrudnień</span>
                </span>
            </p>
        );
    }

    return (
        <div className="space-y-2 rounded-xl border border-amber-500/25 bg-amber-500/[0.08] px-4 py-3">
            {trouble.map(road => (
                <p key={road.id} className="flex items-start gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/15">
                        <Construction size={20} className="text-amber-400" aria-hidden />
                    </span>
                    <span className="min-w-0 flex-1">
                        {/* Tu nazwa trasy JEST komunikatem — bez niej kierowca
                            nie wie, czy zmienia plan, czy nie */}
                        <span className="text-[15px] font-bold leading-snug text-amber-300">
                            {road.name.replace(/^Rybno[-–]/, 'Trasa do ')}
                        </span>
                        {road.delayMinutes > 0 && (
                            <span className="text-[15px] font-semibold text-amber-200/80"> · +{road.delayMinutes} min</span>
                        )}
                        <span className="mt-0.5 block text-sm leading-snug text-neutral-300">{road.description}</span>
                    </span>
                </p>
            ))}
        </div>
    );
};

export default RoadStatusStrip;
