import React, { useState, useMemo } from 'react';
import { useBusStatus } from '../src/hooks/useBusData';
import {
  ActiveBus, BusDirectionStatus, BusStop, BusTripTimetable, Direction,
} from '../types';
import BusMap from './BusMap';
import { serviceTypeLabel } from '../src/services/busLogic';

// ── Etykieta typu kursu ─────────────────────────────────────────────────────
const ServiceBadge: React.FC<{ type: string }> = ({ type }) => {
  const styles: Record<string, string> = {
    GS: 'bg-green-500/20 text-green-400 border-green-500/30',
    S:  'bg-blue-500/20 text-blue-400 border-blue-500/30',
    G:  'bg-amber-500/20 text-amber-400 border-amber-500/30',
  };
  return (
    <span className={`inline-flex items-center text-[8px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-wide ${styles[type] ?? 'bg-white/10 text-neutral-400 border-white/10'}`}>
      {serviceTypeLabel(type)}
    </span>
  );
};

// ── Timeline przystanków z ETA ──────────────────────────────────────────────
const RouteTimeline: React.FC<{ bus: ActiveBus; stops: BusStop[] }> = ({ bus, stops }) => {
  const stopOrder = Object.keys(bus.all_stop_times);
  const currentIndex = stopOrder.indexOf(bus.current_stop_id);

  return (
    <div className="mt-2 pt-4 border-t border-white/5">
      <div className="flex justify-between items-center mb-3">
        <h4 className="text-[9px] font-bold text-neutral-400 uppercase tracking-widest">Trasa i Postęp</h4>
        <div className="flex items-center gap-1 bg-blue-500/10 px-2 py-0.5 rounded-full border border-blue-500/20">
          <div className="w-1 h-1 rounded-full bg-blue-500 animate-pulse" />
          <span className="text-[8px] font-bold text-blue-400 uppercase">Live</span>
        </div>
      </div>

      {/* Pasek wizualny */}
      <div className="relative flex justify-between items-center px-4 mb-8 h-6">
        <div className="absolute left-6 right-6 h-[4px] bg-gray-700/50 z-0 rounded-full" />
        <div
          className="absolute left-6 h-[4px] bg-blue-500 z-[1] rounded-full transition-all duration-1000 shadow-[0_0_8px_rgba(37,99,235,0.4)]"
          style={{ width: `calc(${(currentIndex / (stopOrder.length - 1)) * 100}% - 4px)` }}
        />
        {stopOrder.map((id, index) => {
          const isFirst = index === 0;
          const isLast = index === stopOrder.length - 1;
          const isPassed = index < currentIndex;
          const isCurrent = index === currentIndex;
          const eta = bus.all_stop_times[id];

          if (isFirst || isLast) {
            return (
              <div key={id} className="relative z-10 flex flex-col items-center">
                <div className={`w-4 h-4 rounded-full border-[1.5px] transition-all duration-500 flex items-center justify-center
                  ${isPassed || isCurrent ? 'bg-blue-500 border-white' : 'bg-gray-950 border-blue-500'}`}>
                  <div className={`w-1 h-1 rounded-full ${isPassed || isCurrent ? 'bg-white' : 'bg-blue-500'}`} />
                </div>
                <span className={`absolute -bottom-5 whitespace-nowrap text-[8px] font-bold uppercase tracking-tight
                  ${isPassed || isCurrent ? 'text-blue-400' : 'text-neutral-500'}`}>
                  {stops.find(s => s.stop_id === id)?.name.split(' ')[0]}
                </span>
                <span className="absolute -bottom-9 text-[7px] font-mono text-neutral-600">{eta}</span>
              </div>
            );
          }

          return (
            <div key={id} className="relative z-10 flex flex-col items-center group">
              <div className={`w-2 h-2 rounded-full border-[1.5px] transition-all duration-500
                ${isPassed ? 'bg-blue-500 border-blue-500' :
                  isCurrent ? 'bg-gray-950 border-blue-500 ring-2 ring-blue-500/30 scale-125' :
                    'bg-gray-950 border-gray-600'}`}
              />
              {/* Tooltip ETA przy hover */}
              <div className="absolute -bottom-8 hidden group-hover:flex flex-col items-center pointer-events-none z-20">
                <span className="bg-gray-800 text-white text-[9px] font-bold px-2 py-1 rounded-md whitespace-nowrap border border-white/10 shadow-lg">
                  {stops.find(s => s.stop_id === id)?.name} · {eta}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Lista przystanków z ETA */}
      <div className="mt-2 space-y-1 max-h-32 overflow-y-auto pr-1">
        {stopOrder.map((id, index) => {
          const stop = stops.find(s => s.stop_id === id);
          const isPassed = index < currentIndex;
          const isCurrent = index === currentIndex;
          const isNext = index === currentIndex + 1;
          const eta = bus.all_stop_times[id];
          return (
            <div key={id} className={`flex items-center justify-between py-1 px-2 rounded-lg transition-all
              ${isCurrent ? 'bg-blue-500/10 border border-blue-500/20' :
                isNext ? 'bg-white/5' : ''}`}>
              <div className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0
                  ${isPassed ? 'bg-blue-500' : isCurrent ? 'bg-blue-500 animate-pulse' : isNext ? 'bg-blue-500/50' : 'bg-gray-700'}`} />
                <span className={`text-[10px] font-semibold truncate max-w-[140px]
                  ${isPassed ? 'text-neutral-600 line-through' : isCurrent ? 'text-blue-300' : isNext ? 'text-neutral-300' : 'text-neutral-500'}`}>
                  {stop?.name}
                </span>
              </div>
              <span className={`text-[10px] font-mono font-bold flex-shrink-0
                ${isPassed ? 'text-neutral-700' : isCurrent ? 'text-blue-400' : isNext ? 'text-neutral-300' : 'text-neutral-600'}`}>
                {eta}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ── Karta statusu kierunku ──────────────────────────────────────────────────
const StatusCard: React.FC<{
  direction: Direction;
  status: BusDirectionStatus;
  stops: BusStop[];
}> = ({ direction, status, stops }) => {
  const isRybDza = direction === 'RYBNO_DZIALDOWO';
  const { is_active, active_bus: bus, next_departure: next } = status;

  const nextStopName = bus
    ? stops.find(s => s.stop_id === bus.next_stop_id)?.name ?? bus.next_stop_id
    : null;

  return (
    <div className={`flex-1 p-4 rounded-2xl border transition-all duration-500
      ${is_active ? 'bg-blue-500/10 border-blue-500/20 ring-1 ring-blue-500/10' : 'bg-white/5 border-white/5'}`}>

      <div className="flex justify-between items-start mb-3">
        <div className="flex flex-col gap-1">
          <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md w-fit
            ${isRybDza ? 'bg-indigo-500/20 text-indigo-300' : 'bg-blue-500/20 text-blue-300'}`}>
            {isRybDza ? '➔ DZIAŁDOWO' : '➔ RYBNO'}
          </span>
          <div className="flex items-center gap-1.5 mt-0.5">
            <div className={`w-1.5 h-1.5 rounded-full ${is_active ? 'bg-blue-500 animate-pulse' : 'bg-gray-600'}`} />
            <p className={`text-[10px] font-bold uppercase tracking-tight
              ${is_active ? 'text-blue-400' : 'text-neutral-500'}`}>
              {is_active ? 'W TRASIE' : 'OCZEKIWANIE'}
            </p>
          </div>
        </div>
        {is_active && bus && (
          <div className="bg-blue-600 text-white text-[11px] font-bold px-2 py-1 rounded-lg shadow-md shadow-blue-500/20">
            {bus.time_left_minutes} min
          </div>
        )}
      </div>

      {is_active && bus ? (
        <div className="mt-3">
          <p className="text-[9px] font-bold text-neutral-400 uppercase leading-none mb-1 tracking-wide">
            Następny przystanek:
          </p>
          <p className="text-sm font-black text-blue-200 uppercase tracking-tight mb-1.5 truncate">
            {nextStopName}
          </p>
          <div className="w-full bg-gray-900 h-1.5 rounded-full overflow-hidden">
            <div
              className="bg-blue-500 h-full rounded-full transition-all duration-1000 shadow-[0_0_8px_rgba(37,99,235,0.3)]"
              style={{ width: `${bus.progress * 100}%` }}
            />
          </div>
          <div className="flex items-center justify-between mt-1.5">
            <ServiceBadge type={bus.service_type} />
            <span className="text-[9px] text-neutral-500 font-mono">Kurs {bus.departure_time}</span>
          </div>
        </div>
      ) : next ? (
        <div className="mt-3">
          <p className="text-[9px] font-bold text-neutral-500 uppercase tracking-wider mb-1">Następny odjazd:</p>
          <div className="flex items-baseline gap-1.5">
            <span className="text-xl font-black text-neutral-200 tabular-nums tracking-tighter">{next.time}</span>
            <span className="text-[10px] font-bold text-neutral-500 uppercase">za {next.in_minutes}m</span>
          </div>
          <div className="mt-1">
            <ServiceBadge type={next.service_type} />
          </div>
        </div>
      ) : (
        <div className="mt-4 flex items-center gap-2 text-neutral-500">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-[10px] font-bold italic">Koniec kursów na dziś</p>
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
    <div className="mt-2 pt-4 border-t border-white/5">
      <div className="flex justify-between items-center mb-3">
        <h4 className="text-[9px] font-bold text-neutral-400 uppercase tracking-widest">Rozkład Jazdy</h4>
        <div className="flex gap-1">
          {(['RYBNO_DZIALDOWO', 'DZIALDOWO_RYBNO'] as Direction[]).map(d => (
            <button
              key={d}
              onClick={() => setDir(d)}
              className={`text-[9px] font-bold px-2 py-0.5 rounded-md uppercase tracking-wide transition-all
                ${dir === d ? 'bg-blue-600 text-white' : 'bg-white/5 text-neutral-400 hover:bg-white/10'}`}
            >
              {d === 'RYBNO_DZIALDOWO' ? '→ Dz.' : '→ Ryb.'}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-1.5">
        {list.map(trip => {
          const active = isActive(trip);
          const past = isPast(trip);
          const firstStop = Object.keys(trip.stop_times)[0];
          const lastStop = Object.keys(trip.stop_times).at(-1)!;
          return (
            <div key={trip.trip_id}
              className={`flex items-center justify-between px-3 py-2 rounded-xl border transition-all
                ${active ? 'bg-blue-500/10 border-blue-500/20' :
                  past ? 'bg-white/3 border-white/5 opacity-40' : 'bg-white/5 border-white/5'}`}>
              <div className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-full ${active ? 'bg-blue-500 animate-pulse' : past ? 'bg-gray-700' : 'bg-gray-500'}`} />
                <span className={`text-[11px] font-black tabular-nums ${active ? 'text-blue-300' : past ? 'text-neutral-600' : 'text-neutral-300'}`}>
                  {trip.stop_times[firstStop]}
                </span>
                <span className="text-[9px] text-neutral-600">→</span>
                <span className={`text-[11px] font-bold tabular-nums ${active ? 'text-blue-200' : past ? 'text-neutral-600' : 'text-neutral-400'}`}>
                  {trip.stop_times[lastStop]}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                {active && <span className="text-[8px] font-bold text-blue-400 uppercase">W trasie</span>}
                <ServiceBadge type={trip.service_type} />
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-3 pt-3 border-t border-white/5 flex gap-3 flex-wrap">
        {[['GS', '#22c55e', 'Zawsze'], ['S', '#3b82f6', 'Szkolny'], ['G', '#f59e0b', 'Wolne']].map(([k, c, l]) => (
          <div key={k} className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full" style={{ background: c }} />
            <span className="text-[9px] text-neutral-500 font-bold">{k} – {l}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ── Skeleton loader ─────────────────────────────────────────────────────────
const Skeleton: React.FC = () => (
  <div className="p-5 flex flex-col gap-5 w-full h-full">
    <div className="flex justify-between items-start px-1">
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 bg-white/5 rounded-lg animate-pulse" />
        <div className="w-28 h-5 bg-white/5 rounded animate-pulse" />
      </div>
      <div className="w-16 h-8 bg-white/5 rounded-lg animate-pulse" />
    </div>
    <div className="px-1 w-full h-64 bg-white/5 rounded-2xl animate-pulse" />
    <div className="flex gap-3 px-1">
      <div className="flex-1 h-28 bg-white/5 rounded-2xl animate-pulse" />
      <div className="flex-1 h-28 bg-white/5 rounded-2xl animate-pulse" />
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

  if (!timetable && !error) return <Skeleton />;

  if (error) return (
    <div className="p-5 flex items-center justify-center h-full">
      <p className="text-[11px] text-neutral-500 font-bold">Brak połączenia z API rozkładu jazdy</p>
    </div>
  );

  const now = status?.now ?? new Date().toLocaleTimeString('pl', { hour: '2-digit', minute: '2-digit' });
  const isWeekend = status?.is_weekend ?? ([0, 6].includes(new Date().getDay()));

  return (
    <div className="p-5 flex flex-col gap-4 overflow-hidden w-full h-full">

      {/* Nagłówek */}
      <div className="flex justify-between items-start px-1">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-8 h-8 bg-blue-600/20 rounded-lg flex items-center justify-center border border-blue-500/20">
              <svg className="w-4 h-4 text-blue-400" fill="currentColor" viewBox="0 0 24 24">
                <path d="M18 11V7a2 2 0 00-2-2H8a2 2 0 00-2 2v4m12 0a2 2 0 012 2v3a2 2 0 01-2 2h-1a2 2 0 01-2-2v-1H7v1a2 2 0 01-2 2H4a2 2 0 01-2-2v-3a2 2 0 012-2m14 0H4M8 11h2m4 0h2" />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-neutral-100 leading-none">Monitoring</h3>
          </div>
          <p className="text-[10px] text-neutral-400 font-bold uppercase tracking-wider ml-10 pl-0.5">
            Lokalizacja Live
          </p>
        </div>

        <div className="flex flex-col items-end gap-1.5 pt-0.5">
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border
            ${activeBuses.length > 0 ? 'bg-blue-600 border-blue-500' : 'bg-gray-900 border-gray-700/50'}`}>
            <div className={`w-1.5 h-1.5 rounded-full ${activeBuses.length > 0 ? 'bg-white animate-pulse' : 'bg-gray-500'}`} />
            <span className={`text-[9px] font-bold uppercase tracking-tight
              ${activeBuses.length > 0 ? 'text-white' : 'text-neutral-400'}`}>
              {activeBuses.length > 0 ? 'Aktywny' : 'Czuwanie'}
            </span>
          </div>
          <span className="text-[10px] text-neutral-500 font-bold tabular-nums">{now}</span>
          {isWeekend && (
            <span className="text-[8px] text-amber-500/80 font-bold uppercase tracking-wide">Weekend – brak kursów</span>
          )}
        </div>
      </div>

      {/* Mapa */}
      <div className="px-1">
        <BusMap activeBuses={activeBuses} stops={stops} trips={trips} />
      </div>

      {/* Karty statusu */}
      <div className="flex flex-col sm:flex-row gap-3 px-1">
        {status ? (
          <>
            <StatusCard direction="RYBNO_DZIALDOWO" status={status.directions.RYBNO_DZIALDOWO} stops={stops} />
            <StatusCard direction="DZIALDOWO_RYBNO" status={status.directions.DZIALDOWO_RYBNO} stops={stops} />
          </>
        ) : (
          <>
            <div className="flex-1 h-28 bg-white/5 rounded-2xl border border-white/5 animate-pulse" />
            <div className="flex-1 h-28 bg-white/5 rounded-2xl border border-white/5 animate-pulse" />
          </>
        )}
      </div>

      {/* Route Timeline dla aktywnych autobusów */}
      {activeBuses.map((bus, idx) => (
        <div key={idx} className="px-1">
          <RouteTimeline bus={bus} stops={stops} />
        </div>
      ))}

      {/* Toggle rozkładu / timeline */}
      <div className="px-1">
        <button
          onClick={() => setShowTimetable(v => !v)}
          className="w-full flex items-center justify-between px-3 py-2 rounded-xl bg-white/5 border border-white/5 hover:bg-white/10 transition-all"
        >
          <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-wider">
            {showTimetable ? 'Ukryj rozkład' : 'Pokaż rozkład jazdy'}
          </span>
          <svg className={`w-3 h-3 text-neutral-500 transition-transform ${showTimetable ? 'rotate-180' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {showTimetable && timetable && (
          <TimetableView trips={trips} currentNow={now} />
        )}
      </div>
    </div>
  );
};

export default BusTrackerWidget;
