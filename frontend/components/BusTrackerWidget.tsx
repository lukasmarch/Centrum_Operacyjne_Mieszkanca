import React, { useState, useMemo } from 'react';
import { useBusStatus } from '../src/hooks/useBusData';
import {
  ActiveBus, BusDirectionStatus, BusStop, BusTripTimetable, Direction,
} from '../types';
import BusMap from './BusMap';
import { ArrowRight, ChevronDown } from 'lucide-react';
import { Chip, Notice, Skeleton, Tag } from './simple/tv';
import { serviceTypeLabel } from '../src/services/busLogic';

// Odświeżenie „Pasek informacyjny” (10.2026): kolor niesie stan, nie typ kursu.
// Typ (Zawsze / Szkolny / Wolne) jest słowem w neutralnej ramce — rozróżnienie
// zielenią, chabrem i bursztynem było trzecią legendą do nauczenia się.

// ── Etykieta typu kursu ─────────────────────────────────────────────────────
const ServiceBadge: React.FC<{ type: string }> = ({ type }) => (
  <span className="font-cond inline-flex items-center border border-tv-seam px-1.5 py-0.5 text-[13px] font-bold uppercase leading-none tracking-wide text-tv-muted">
    {serviceTypeLabel(type)}
  </span>
);

const DIR_LABEL: Record<Direction, string> = {
  RYBNO_DZIALDOWO: 'Działdowo',
  DZIALDOWO_RYBNO: 'Rybno',
};

const DirectionName: React.FC<{ direction: Direction }> = ({ direction }) => (
  <span className="inline-flex items-center gap-1.5">
    <ArrowRight size={16} aria-hidden className="text-tv-muted" />
    {DIR_LABEL[direction]}
  </span>
);

// ── Timeline przystanków z ETA ──────────────────────────────────────────────
const RouteTimeline: React.FC<{ bus: ActiveBus; stops: BusStop[] }> = ({ bus, stops }) => {
  const stopOrder = Object.keys(bus.all_stop_times);
  const currentIndex = stopOrder.indexOf(bus.current_stop_id);
  const nameOf = (id: string) => stops.find(s => s.stop_id === id)?.name;

  return (
    <section aria-label="Trasa i postęp">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <Tag as="h3">Trasa i postęp · <DirectionName direction={bus.direction} /></Tag>
        {/* Pozycja liczona z ROZKŁADU, nie z GPS — „Live” obiecywało coś, czego nie mamy (audyt F-039) */}
        <span className="text-[14px] text-tv-muted">wg rozkładu</span>
      </div>

      <div className="border-t-2 border-tv-blue bg-tv-panel px-4 pb-2 pt-4">
        {/* Pasek postępu: płaski tor + wypełnienie, końce trasy podpisane pod nim */}
        <div className="h-1.5 bg-tv-seam">
          <div
            className="h-full bg-tv-blue transition-[width] duration-1000"
            style={{ width: `${stopOrder.length > 1 ? (currentIndex / (stopOrder.length - 1)) * 100 : 0}%` }}
          />
        </div>
        <div className="mt-1.5 flex justify-between gap-3 text-[13px] text-tv-muted">
          <span>{nameOf(stopOrder[0])?.split(' ')[0]} <span className="tabular">{bus.all_stop_times[stopOrder[0]]}</span></span>
          <span className="text-right">{nameOf(stopOrder[stopOrder.length - 1])?.split(' ')[0]} <span className="tabular">{bus.all_stop_times[stopOrder[stopOrder.length - 1]]}</span></span>
        </div>

        {/* Lista przystanków z ETA */}
        <ol className="mt-3 divide-y divide-tv-seam border-t border-tv-seam">
          {stopOrder.map((id, index) => {
            const isPassed = index < currentIndex;
            const isCurrent = index === currentIndex;
            const isNext = index === currentIndex + 1;
            const eta = bus.all_stop_times[id];
            return (
              <li key={id} className="flex items-center justify-between gap-3 py-2">
                <span className="flex min-w-0 items-center gap-2.5">
                  <span aria-hidden className={`h-2 w-2 flex-shrink-0 ${isCurrent ? 'bg-tv-blue' : isPassed ? 'bg-tv-seam' : isNext ? 'bg-tv-bluesoft' : 'bg-tv-panel2'}`} />
                  <span className={`truncate text-[15px] ${
                    isPassed ? 'text-tv-muted line-through' : isCurrent ? 'font-bold text-white' : isNext ? 'font-semibold text-tv-paper' : 'text-[#d7dbe8]'
                  }`}>
                    {nameOf(id)}
                  </span>
                  {isCurrent && <span className="sr-only">(teraz)</span>}
                </span>
                <span className={`tabular flex-shrink-0 text-[15px] font-bold ${isPassed ? 'text-tv-muted' : 'text-white'}`}>
                  {eta}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
};

// ── Karta statusu kierunku ──────────────────────────────────────────────────
const StatusCard: React.FC<{
  direction: Direction;
  status: BusDirectionStatus;
  stops: BusStop[];
}> = ({ direction, status, stops }) => {
  const { is_active, active_bus: bus, next_departure: next, next_service: resume } = status;

  const nextStopName = bus
    ? stops.find(s => s.stop_id === bus.next_stop_id)?.name ?? bus.next_stop_id
    : null;

  const label = 'text-[14px] text-tv-muted';
  const value = 'font-cond tabular text-[30px] font-extrabold leading-[1.05] text-white lg:text-[34px]';

  return (
    <div className={`flex flex-col px-4 pb-4 pt-3 ${is_active ? 'bg-tv-panel2' : 'bg-tv-panel'}`}>
      <div className="mb-2 flex items-start justify-between gap-3">
        <h3 className="font-cond text-[18px] font-extrabold uppercase tracking-wide text-white">
          <DirectionName direction={direction} />
        </h3>
        {is_active
          ? <Tag tone="blue">W trasie</Tag>
          : <span className="font-cond text-[13px] font-bold uppercase tracking-wide text-tv-muted">Oczekiwanie</span>}
      </div>

      {is_active && bus ? (
        <div>
          <p className={label}>Następny przystanek:</p>
          <p className="font-cond truncate text-[26px] font-extrabold leading-tight text-white">{nextStopName}</p>
          <div className="mt-2 h-1.5 bg-tv-seam">
            <div className="h-full bg-tv-blue transition-[width] duration-1000" style={{ width: `${bus.progress * 100}%` }} />
          </div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
            <span className="tabular text-[14px] text-tv-muted">Kurs {bus.departure_time} · do końca <span className="font-bold text-white">{bus.time_left_minutes} min</span></span>
            <ServiceBadge type={bus.service_type} />
          </div>
        </div>
      ) : next ? (
        <div>
          <p className={label}>Następny odjazd:</p>
          <p className={value}>{next.time}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <span className="tabular text-[15px] text-tv-paper">za {next.in_minutes} min</span>
            <ServiceBadge type={next.service_type} />
          </div>
        </div>
      ) : (
        <div>
          <p className={label}>{resume ? 'Kursy wracają:' : 'Brak kursów'}</p>
          {resume ? (
            <>
              {/* Najbliższy kurs jako jedna wartość: „jutro 06:40” */}
              <p className={value}>{resume.day_label} {resume.time}</p>
              <div className="mt-1.5">
                <ServiceBadge type={resume.service_type} />
              </div>
            </>
          ) : (
            <p className="text-[15px] text-tv-paper">Rozkład niedostępny</p>
          )}
        </div>
      )}
    </div>
  );
};

// ── Widok rozkładu dnia ─────────────────────────────────────────────────────
const TimetableView: React.FC<{
  trips: { RYBNO_DZIALDOWO: BusTripTimetable[]; DZIALDOWO_RYBNO: BusTripTimetable[] };
  currentNow: string;
}> = ({ trips, currentNow }) => {
  const [dir, setDir] = useState<Direction>('RYBNO_DZIALDOWO');
  const list = trips[dir];

  const isActive = (t: BusTripTimetable) => {
    const stopTimes = Object.values(t.stop_times);
    return currentNow >= stopTimes[0] && currentNow <= stopTimes[stopTimes.length - 1];
  };
  const isPast = (t: BusTripTimetable) => {
    const stopTimes = Object.values(t.stop_times);
    return currentNow > stopTimes[stopTimes.length - 1];
  };

  return (
    <section aria-label="Rozkład jazdy" className="mt-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <Tag as="h3">Rozkład jazdy</Tag>
        <div role="group" aria-label="Kierunek" className="flex gap-1.5">
          {(['RYBNO_DZIALDOWO', 'DZIALDOWO_RYBNO'] as Direction[]).map(d => (
            <Chip key={d} active={dir === d} onClick={() => setDir(d)}>
              <DirectionName direction={d} />
            </Chip>
          ))}
        </div>
      </div>

      <ul className="grid grid-cols-1 gap-px border-t-2 border-tv-blue bg-tv-seam sm:grid-cols-2">
        {list.map(trip => {
          const active = isActive(trip);
          const past = isPast(trip);
          const firstStop = Object.keys(trip.stop_times)[0];
          const lastStop = Object.keys(trip.stop_times).at(-1)!;
          return (
            <li key={trip.trip_id}
              className={`flex min-h-[48px] items-center justify-between gap-3 px-4 py-2 ${active ? 'bg-tv-panel2' : 'bg-tv-panel'}`}>
              <span className={`font-cond tabular flex items-baseline gap-2 text-[20px] font-extrabold ${past ? 'text-tv-muted' : 'text-white'}`}>
                {trip.stop_times[firstStop]}
                <ArrowRight size={14} aria-label="do" className="self-center text-tv-muted" />
                <span className={past ? '' : 'text-tv-paper'}>{trip.stop_times[lastStop]}</span>
              </span>
              <span className="flex items-center gap-2">
                {active && <Tag tone="blue">W trasie</Tag>}
                <ServiceBadge type={trip.service_type} />
              </span>
            </li>
          );
        })}
      </ul>

      <p className="mt-2 text-[13px] text-tv-muted">GS – Zawsze · S – Szkolny · G – Wolne</p>
    </section>
  );
};

// ── Skeleton loader ─────────────────────────────────────────────────────────
const LoadingState: React.FC = () => (
  <div className="flex flex-col gap-4" aria-busy="true">
    <Skeleton className="h-11 w-48" />
    <Skeleton className="h-64" />
    <div className="grid grid-cols-1 gap-px sm:grid-cols-2">
      <Skeleton className="h-32" />
      <Skeleton className="h-32" />
    </div>
  </div>
);

// ── Widget główny ────────────────────────────────────────────────────────────
const BusTrackerWidget: React.FC = () => {
  const { status, timetable, error } = useBusStatus();
  const [showTimetable, setShowTimetable] = useState(false);

  const activeBuses = useMemo((): ActiveBus[] => {
    if (!status) return [];
    return Object.values(status.directions)
      .filter(d => d.is_active && d.active_bus)
      .map(d => d.active_bus!);
  }, [status]);

  const stops = timetable?.stops ?? [];
  const trips = timetable?.trips ?? { RYBNO_DZIALDOWO: [], DZIALDOWO_RYBNO: [] };

  if (!timetable && !error) return <LoadingState />;

  if (error) return (
    <Notice tone="warn" role="alert">Brak połączenia z API rozkładu jazdy</Notice>
  );

  const now = status?.now ?? new Date().toLocaleTimeString('pl', { hour: '2-digit', minute: '2-digit' });
  const isWeekend = status?.is_weekend ?? ([0, 6].includes(new Date().getDay()));

  return (
    <div className="flex w-full flex-col gap-6">

      {/* Nagłówek: plakietka sekcji, obok stan i godzina, od której liczymy pozycję */}
      <div>
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
          <Tag as="h2">Monitoring</Tag>
          <span className="flex items-center gap-3 text-[14px] text-tv-muted">
            <span>Pozycja wg rozkładu · <span className="tabular text-tv-paper">{now}</span></span>
            <span className={`font-cond inline-flex items-center gap-1.5 text-[13px] font-extrabold uppercase tracking-wide ${activeBuses.length > 0 ? 'text-white' : 'text-tv-muted'}`}>
              <span aria-hidden className={`h-2 w-2 ${activeBuses.length > 0 ? 'bg-tv-blue' : 'bg-tv-seam'}`} />
              {activeBuses.length > 0 ? 'Aktywny' : 'Czuwanie'}
            </span>
          </span>
        </div>
        {/* Mapa */}
        <div className="border-t-2 border-tv-blue">
          <BusMap activeBuses={activeBuses} stops={stops} trips={trips} />
        </div>
        {isWeekend && (
          <p className="bg-tv-yellow px-4 py-2 text-[15px] font-semibold text-tv-ink">Linia kursuje pon–pt</p>
        )}
      </div>

      {/* Karty statusu: dwa kierunki na tle szwu */}
      {status ? (
        <div className="grid grid-cols-1 gap-px border-t-2 border-tv-blue bg-tv-seam sm:grid-cols-2">
          <StatusCard direction="RYBNO_DZIALDOWO" status={status.directions.RYBNO_DZIALDOWO} stops={stops} />
          <StatusCard direction="DZIALDOWO_RYBNO" status={status.directions.DZIALDOWO_RYBNO} stops={stops} />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-px sm:grid-cols-2">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
      )}

      {/* Route Timeline dla aktywnych autobusów */}
      {activeBuses.map((bus, idx) => (
        <RouteTimeline key={idx} bus={bus} stops={stops} />
      ))}

      {/* Toggle rozkładu / timeline */}
      <div>
        <button
          onClick={() => setShowTimetable(v => !v)}
          aria-expanded={showTimetable}
          className="font-cond flex min-h-[52px] w-full items-center justify-between bg-tv-panel px-4 text-[16px] font-extrabold uppercase tracking-wide text-tv-paper transition-colors hover:bg-tv-panel2 hover:text-white"
        >
          {showTimetable ? 'Ukryj rozkład' : 'Pokaż rozkład jazdy'}
          <ChevronDown size={20} aria-hidden className={`text-tv-muted transition-transform ${showTimetable ? 'rotate-180' : ''}`} />
        </button>

        {showTimetable && timetable && (
          <TimetableView trips={trips} currentNow={now} />
        )}
      </div>
    </div>
  );
};

export default BusTrackerWidget;
